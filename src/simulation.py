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

        # Visual packet animations for Pygame
        self.flying_packets: List[PacketAnimation] = []

        # Start primary SimPy background processes
        self.arrival_process = self.env.process(self._arrival_loop())
        self.dispatch_process = self.env.process(self._dispatch_loop())
        self.telemetry_process = self.env.process(self._telemetry_loop())

    def _init_servers(self, count: int):
        self.servers.clear()
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

    def set_policy(self, policy):
        """Attaches a provisioning policy."""
        self.policy = policy
        self.policy.attach(self)

    # -------------------------------------------------------------------------
    # SimPy Processes
    # -------------------------------------------------------------------------

    def _arrival_loop(self):
        """Generates Poisson request arrivals and inserts into queue."""
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
            self.request_queue.append(req)
            self.metrics.current_queue_depth = len(self.request_queue)

            if self.policy:
                self.policy.on_arrival(req)

    def _dispatch_loop(self):
        """
        Load Balancer dispatch process:
        Examines incoming queue, checks timeouts, and routes requests to ready servers.
        """
        timeout_limit = self.config.workload.request_timeout_sec
        while True:
            now = self.env.now

            # Clean expired requests from front of queue (SLA Timeout Drop)
            while self.request_queue and (now - self.request_queue[0]["arrival_time"]) > timeout_limit:
                self.request_queue.popleft()
                self.metrics.total_requests_dropped += 1
            self.metrics.current_queue_depth = len(self.request_queue)

            # Try to dispatch queued requests to ready servers (IDLE or ACTIVE with capacity)
            if self.request_queue:
                # Find available servers
                ready_servers = [s for s in self.servers if s.can_accept_request()]
                if ready_servers:
                    # Load balancing heuristic: Pick server with lowest active load
                    ready_servers.sort(key=lambda s: s.active_request_count)
                    chosen_server = ready_servers[0]
                    req = self.request_queue.popleft()
                    self.metrics.current_queue_depth = len(self.request_queue)

                    # Launch request execution process on chosen server
                    self.env.process(self._execute_request(chosen_server, req))

            if self.policy:
                self.policy.on_tick(now)

            yield self.env.timeout(0.05)  # 50ms dispatch resolution

    def _execute_request(self, server: Server, req: dict):
        yield self.env.process(server.serve_request(req["service_time"]))
        self.metrics.total_requests_served += 1
        if self.policy:
            self.policy.on_completion(server, req)

    def _telemetry_loop(self):
        """Periodically samples system metrics for live graph rendering."""
        while True:
            yield self.env.timeout(0.5)  # Sample every 0.5 simulated seconds
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
        """Prunes finished visual packet animations."""
        self.flying_packets = [p for p in self.flying_packets if not p.is_finished(current_real_time)]
