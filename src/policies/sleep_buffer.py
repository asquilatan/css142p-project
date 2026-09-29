"""
Sleep-Buffer Provisioning Policy (Hybrid Low-Power Standby).
Maintains dormant servers in low-power ACPI sleep rather than full power-off,
trading minor standby power (15W vs 2W) for near-instant wake times (4s vs 120s)
to eliminate SLA request drops during sudden flash crowd surges.
"""

from src.policies.base import ProvisioningPolicy
from src.server import ServerState


class SleepBufferPolicy(ProvisioningPolicy):
    def __init__(self, wake_threshold: int = 3, sleep_cooldown_sec: float = 12.0, min_active_servers: int = 2):
        super().__init__("Sleep-Buffer")
        self.wake_threshold = wake_threshold
        self.sleep_cooldown_sec = sleep_cooldown_sec
        self.min_active_servers = min_active_servers
        self.last_sleep_transition_time = 0.0

    def on_init(self):
        # Keep minimum core servers active, put all remaining into low-power sleep
        active_count = 0
        for s in self.sim.servers:
            if active_count < self.min_active_servers:
                if s.state == ServerState.OFF:
                    s.boot()
                elif s.state == ServerState.SLEEPING:
                    s.wake()
                active_count += 1
            else:
                s.sleep()

    def on_tick(self, current_time: float):
        queue_len = len(self.sim.request_queue)
        ready_servers = [s for s in self.sim.servers if s.state in (ServerState.IDLE, ServerState.ACTIVE)]

        # Wake condition: Queue is growing, rapidly wake from sleep buffer
        if queue_len >= self.wake_threshold:
            sleeping_servers = [s for s in self.sim.servers if s.state == ServerState.SLEEPING]
            if sleeping_servers:
                sleeping_servers[0].wake()
            else:
                # If all asleep servers are already awake and load still high, cold boot any OFF servers
                off_servers = [s for s in self.sim.servers if s.state == ServerState.OFF]
                if off_servers:
                    off_servers[0].boot()

        # Sleep condition: Queue is drained, return surplus idle nodes to low-power sleep
        elif queue_len == 0 and (current_time - self.last_sleep_transition_time) > self.sleep_cooldown_sec:
            idle_servers = [s for s in self.sim.servers if s.state == ServerState.IDLE and s.active_request_count == 0]
            if len(ready_servers) > self.min_active_servers and idle_servers:
                server_to_sleep = idle_servers[-1]
                server_to_sleep.sleep()
                self.last_sleep_transition_time = current_time
