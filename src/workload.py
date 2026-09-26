"""
Workload Generator.
Models diurnal web traffic curves (trough at night, peak in afternoon),
sudden flash crowd surges, and abrupt traffic drops.
"""

import math
import random
from src.config import WorkloadConfig


class WorkloadGenerator:
    def __init__(self, config: WorkloadConfig):
        self.config = config
        self.flash_crowd_active = False
        self.flash_crowd_start_time = 0.0
        self.flash_crowd_duration = 300.0  # 5-minute surge by default
        self.traffic_scale_factor = 1.0     # Controlled by the UI slider (0.2x to 3.0x)
        self.abrupt_drop_active = False

    def trigger_flash_crowd(self, current_time: float, duration: float = 300.0):
        """Inject a sudden flash crowd surge."""
        self.flash_crowd_active = True
        self.flash_crowd_start_time = current_time
        self.flash_crowd_duration = duration
        self.abrupt_drop_active = False

    def trigger_abrupt_drop(self):
        """Instantly collapse traffic to test de-provisioning and hysteresis."""
        self.abrupt_drop_active = True
        self.flash_crowd_active = False

    def reset_triggers(self):
        """Clear surge or drop overrides back to standard diurnal baseline."""
        self.flash_crowd_active = False
        self.abrupt_drop_active = False

    def get_current_arrival_rate(self, sim_time_seconds: float) -> float:
        """
        Calculates the instantaneous expected Poisson arrival rate (requests/sec)
        at the specified simulated second of the day.
        """
        if self.abrupt_drop_active:
            return 2.0 * self.traffic_scale_factor

        # Check flash crowd expiration
        if self.flash_crowd_active:
            if sim_time_seconds - self.flash_crowd_start_time > self.flash_crowd_duration:
                self.flash_crowd_active = False

        if not self.config.diurnal_cycle_active:
            base_rate = (self.config.base_arrival_rate + self.config.peak_arrival_rate) / 2.0
        else:
            # 24-hour cycle = 86,400 seconds. Trough at 03:00 (10800s), Peak at 15:00 (54000s)
            day_seconds = sim_time_seconds % 86400.0
            # Phase shift so trough is near 3 AM (0.125 of day) and peak near 3 PM (0.625 of day)
            radians = (2.0 * math.pi * (day_seconds - 10800.0)) / 86400.0
            # Normalized wave from 0.0 to 1.0
            wave = (math.sin(radians - math.pi / 2.0) + 1.0) / 2.0
            rate_span = self.config.peak_arrival_rate - self.config.base_arrival_rate
            base_rate = self.config.base_arrival_rate + (rate_span * wave)

        # Apply flash crowd multiplier if active
        if self.flash_crowd_active:
            base_rate *= self.config.surge_multiplier

        # Apply interactive UI slider scale factor
        return max(1.0, base_rate * self.traffic_scale_factor)

    def get_next_interarrival_time(self, sim_time_seconds: float) -> float:
        """Draws the next inter-arrival interval using an exponential distribution."""
        rate = self.get_current_arrival_rate(sim_time_seconds)
        return random.expovariate(rate)
