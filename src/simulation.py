"""
Discrete-Event Simulation Orchestrator.
Manages SimPy discrete events, the central Load Balancer,
request queuing, packet animations, and policy decisions.
"""

from collections import deque
from dataclasses import dataclass, field
from typing import List, Optional
import simpy
from src.config import SimConfig
from src.server import Server, ServerState
from src.workload import WorkloadGenerator
from src.metrics import MetricsCollector


@dataclass
class PacketAnimation:
    packet_id: int
    start_pos: tuple
    end_pos: tuple
    start_time: float = 0.0
    duration: float = 0.35  # seconds of visual travel
    server_id: Optional[int] = None
    color: tuple = (30, 30, 40)
    progress: float = 0.0

    def get_progress(self, current_time: float = 0.0) -> float:
        if self.duration <= 0:
            return 1.0
        return min(1.0, max(0.0, self.progress))

    def is_finished(self, current_time: float = 0.0) -> bool:
        return self.progress >= 1.0


class SimulationEngine:
    def __init__(self, config: SimConfig):
        self.config = config
        self.env = simpy.Environment()
        self.workload = WorkloadGenerator(config.workload)
        self.metrics = MetricsCollector(config)

        # Servers
        self.servers: List[Server] = []
        self._init_servers(config.num_servers)

        # Incoming request queue
        self.request_queue: deque = deque()
        self.next_request_id = 1

        # Provisioning Policy (set externally)
        self.policy = None

        # Round-robin load balancer index pointer
        self.lb_round_robin_idx: int = 0

        # Start primary SimPy background processes
        self.arrival_process = self.env.process(self._arrival_loop())
        self.dispatch_process = self.env.process(self._dispatch_loop())
        self.telemetry_process = self.env.process(self._telemetry_loop())

    def _init_servers(self, count: int):
        self.servers.clear()
        self.lb_round_robin_idx = 0
        for i in range(count):
            srv = Server(self.env, server_id=i + 1, hw_config=self.config.hardware,
                         capacity=self.config.server_capacity_concurrency)
            self.servers.append(srv)

    def set_num_servers(self, new_count: int):
        """Dynamically adjusts server count at runtime (3 to 10)."""
        new_count = max(3, min(10, new_count))
        self.config.num_servers = new_count
        current_count = len(self.servers)

        if new_count > current_count:
            for i in range(current_count, new_count):
                srv = Server(self.env, server_id=i + 1, hw_config=self.config.hardware,
                             capacity=self.config.server_capacity_concurrency)
                self.servers.append(srv)
        elif new_count < current_count:
            # Safely trim excess idle/off servers from the end
            while len(self.servers) > new_count:
                srv = self.servers.pop()
                srv.power_off()
        self.lb_round_robin_idx = 0

    def set_policy(self, policy):
        """Attaches a provisioning policy."""
        self.policy = policy
        self.policy.attach(self)

    # -------------------------------------------------------------------------
    # SimPy Processes & Dispatch
    # -------------------------------------------------------------------------

    def _find_ready_server(self) -> Optional[Server]:
        """Finds the next ready server with available capacity in fair round-robin order."""
        num_servers = len(self.servers)
        if num_servers == 0:
            return None
        for offset in range(num_servers):
            idx = (self.lb_round_robin_idx + offset) % num_servers
            srv = self.servers[idx]
            if srv.can_accept_request():
                self.lb_round_robin_idx = (idx + 1) % num_servers
                return srv
        return None

    def _start_serving(self, server: Server, req: dict):
        """Starts request execution on server via direct SimPy event callback without Process overhead."""
        server.reserve_slot()
        evt = self.env.timeout(req["service_time"])
        evt.callbacks.append(lambda _evt, s=server, r=req: self._on_request_completed(s, r))

    def _on_request_completed(self, server: Server, req: dict):
        """Handles request completion, invokes policy hook, and performs O(1) handoff to queued requests."""
        server.release_slot()
        self.metrics.total_requests_served += 1
        if self.policy:
            self.policy.on_completion(server, req)

        # Clean expired requests from front of queue (SLA Timeout Drop)
        now = self.env.now
        timeout_limit = self.config.workload.request_timeout_sec
        while self.request_queue and (now - self.request_queue[0]["arrival_time"]) > timeout_limit:
            self.request_queue.popleft()
            self.metrics.total_requests_dropped += 1

        # Direct O(1) server handoff: server that just freed a slot takes next item
        if self.request_queue and server.can_accept_request():
            next_req = self.request_queue.popleft()
            self._start_serving(server, next_req)

        self.metrics.current_queue_depth = len(self.request_queue)

    def _arrival_loop(self):
        """Generates Poisson request arrivals, enqueues, and triggers direct O(1) dispatch."""
        while True:
            interarrival = self.workload.get_next_interarrival_time(self.env.now)
            yield self.env.timeout(interarrival)

            self.metrics.total_requests_arrived += 1

            # Check queue capacity (Tail Drop)
            if len(self.request_queue) >= self.config.workload.max_queue_capacity:
                self.metrics.total_requests_dropped += 1
                continue

            req = {
                "id": self.next_request_id,
                "arrival_time": self.env.now,
                "service_time": self.config.workload.mean_service_time_sec
            }
            self.next_request_id += 1

            if self.policy:
                self.policy.on_arrival(req)

            # If queue is empty, attempt immediate round-robin dispatch to a ready server
            if not self.request_queue:
                chosen_server = self._find_ready_server()
                if chosen_server is not None:
                    self._start_serving(chosen_server, req)
                    continue

            # Otherwise (or if all servers busy), append to queue
            self.request_queue.append(req)
            self.metrics.current_queue_depth = len(self.request_queue)

    def _try_dispatch(self):
        """
        Load Balancer Round-Robin dispatch:
        Purges timed-out requests (SLA drops) and assigns queued requests
        to ready servers in fair round-robin order.
        """
        now = self.env.now
        timeout_limit = self.config.workload.request_timeout_sec

        # Clean expired requests from front of queue (SLA Timeout Drop)
        while self.request_queue and (now - self.request_queue[0]["arrival_time"]) > timeout_limit:
            self.request_queue.popleft()
            self.metrics.total_requests_dropped += 1

        num_servers = len(self.servers)
        if num_servers == 0 or not self.request_queue:
            self.metrics.current_queue_depth = len(self.request_queue)
            return

        # Distribute queued requests across ready servers
        while self.request_queue:
            chosen_server = self._find_ready_server()
            if chosen_server is None:
                # All servers are currently at capacity, booting, or off
                break

            req = self.request_queue.popleft()
            self._start_serving(chosen_server, req)

        self.metrics.current_queue_depth = len(self.request_queue)

    def _dispatch_loop(self):
        """
        Periodic housekeeping process:
        Checks queue timeouts, executes policy ticks, and retries dispatch.
        """
        while True:
            now = self.env.now
            self._try_dispatch()

            if self.policy:
                self.policy.on_tick(now)

            yield self.env.timeout(0.1)  # 100ms periodic resolution

    def _telemetry_loop(self):
        """Periodically samples system metrics for full-timeline graph rendering."""
        while True:
            yield self.env.timeout(2.0)  # Sample every 2.0 simulated seconds
            rate = self.workload.get_current_arrival_rate(self.env.now)
            self.metrics.record_sample(self.env.now, self.servers, rate)

    # -------------------------------------------------------------------------
    # Visual Frame Update Bridge
    # -------------------------------------------------------------------------

    def step_simulation(self, target_time: float):
        """Runs SimPy discrete events up to target_time."""
        if target_time > self.env.now:
            self.env.run(until=target_time)

    def clean_packet_animations(self, current_real_time: float):
        """Compatibility no-op (SimulationView manages active visual packets)."""
        pass
