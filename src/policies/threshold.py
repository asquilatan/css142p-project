"""
Threshold-Based Provisioning Policy (Reactive).
Scales servers up when the request queue exceeds a high watermark,
and powers servers down after a cooldown when demand subsides.
"""

from src.policies.base import ProvisioningPolicy
from src.server import ServerState


class ThresholdPolicy(ProvisioningPolicy):
    def __init__(self, q_high: int = 5, q_low: int = 0, cooldown_sec: float = 20.0, min_active_servers: int = 1):
        super().__init__("Threshold-Based")
        self.q_high = q_high
        self.q_low = q_low
        self.cooldown_sec = cooldown_sec
        self.min_active_servers = min_active_servers
        self.last_scale_down_time = 0.0

    def on_init(self):
        # Keep minimum servers ready, shut off the rest to conserve energy
        active_count = 0
        for s in self.sim.servers:
            if active_count < self.min_active_servers:
                if s.state == ServerState.OFF:
                    s.boot()
                active_count += 1
            else:
                s.power_off()

    def on_tick(self, current_time: float):
        queue_len = len(self.sim.request_queue)
        ready_servers = [s for s in self.sim.servers if s.state in (ServerState.IDLE, ServerState.ACTIVE)]

        # Scale UP Condition
        if queue_len >= self.q_high:
            # Check if any dormant server can be cold booted
            dormant = [s for s in self.sim.servers if s.state == ServerState.OFF]
            if dormant:
                dormant[0].boot()

        # Scale DOWN Condition (Hysteresis & Cooldown to avoid thrashing)
        elif queue_len <= self.q_low and (current_time - self.last_scale_down_time) > self.cooldown_sec:
            # Find idle servers that have 0 active requests
            idle_servers = [s for s in self.sim.servers if s.state == ServerState.IDLE and s.active_request_count == 0]
            if len(ready_servers) > self.min_active_servers and idle_servers:
                server_to_stop = idle_servers[-1]
                server_to_stop.power_off()
                self.last_scale_down_time = current_time
