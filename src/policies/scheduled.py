"""
Scheduled Provisioning Policy (Predictive / Proactive).
Utilizes known diurnal traffic schedule to pre-boot servers ahead of peak hours,
ensuring zero cold-boot delays during scheduled morning surges while conserving night energy.
"""

from src.policies.base import ProvisioningPolicy
from src.server import ServerState


class ScheduledPolicy(ProvisioningPolicy):
    def __init__(self, peak_start_hour: float = 9.0, peak_end_hour: float = 18.0,
                 pre_boot_minutes: float = 20.0, min_night_servers: int = 1):
        super().__init__("Scheduled")
        self.peak_start_hour = peak_start_hour
        self.peak_end_hour = peak_end_hour
        self.pre_boot_minutes = pre_boot_minutes
        self.min_night_servers = min_night_servers

    def on_init(self):
        self._evaluate_schedule(self.sim.env.now)

    def on_tick(self, current_time: float):
        self._evaluate_schedule(current_time)

    def _evaluate_schedule(self, current_time: float):
        # Time of day in hours (0.0 to 24.0)
        day_seconds = current_time % 86400.0
        current_hour = day_seconds / 3600.0

        # Pre-boot threshold (e.g., 8:40 AM for 9:00 AM peak)
        pre_boot_hour = self.peak_start_hour - (self.pre_boot_minutes / 60.0)

        is_peak_window = (pre_boot_hour <= current_hour <= self.peak_end_hour)

        if is_peak_window:
            # Power on all servers for peak hours
            for s in self.sim.servers:
                if s.state == ServerState.OFF:
                    s.boot()
                elif s.state == ServerState.SLEEPING:
                    s.wake()
        else:
            # Off-peak night trough: retain minimum servers, power off the rest
            active_count = 0
            for s in self.sim.servers:
                if active_count < self.min_night_servers:
                    if s.state == ServerState.OFF:
                        s.boot()
                    active_count += 1
                else:
                    if s.state in (ServerState.IDLE, ServerState.SLEEPING) and s.active_request_count == 0:
                        s.power_off()
