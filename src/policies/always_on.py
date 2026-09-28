"""
Always-On Provisioning Policy (Baseline / Over-provisioned).
Keeps 100% of servers powered and ready 24/7.
Minimizes latency and drops; maximizes energy consumption.
"""

from src.policies.base import ProvisioningPolicy
from src.server import ServerState


class AlwaysOnPolicy(ProvisioningPolicy):
    def __init__(self):
        super().__init__("Always-On")

    def on_init(self):
        for s in self.sim.servers:
            if s.state in (ServerState.OFF, ServerState.SLEEPING):
                s.boot()

    def on_tick(self, current_time: float):
        for s in self.sim.servers:
            if s.state == ServerState.OFF:
                s.boot()
            elif s.state == ServerState.SLEEPING:
                s.wake()
