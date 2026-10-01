"""
Telemetry & Metrics Collector.
Records continuous data center power, cumulative energy consumption,
queue depth, SLA drop counts, and rolling time-series for live graph rendering.
"""

from collections import deque
from typing import List
from src.config import SimConfig


class MetricsCollector:
    def __init__(self, config: SimConfig, history_max_len: int = 150):
        self.config = config
        self.history_max_len = history_max_len

        # Counters
        self.total_requests_arrived = 0
        self.total_requests_served = 0
        self.total_requests_dropped = 0
        self.current_queue_depth = 0

        # Energy & Power
        self.instant_power_watts = 0.0
        self.facility_instant_power_watts = 0.0
        self.cumulative_energy_kwh = 0.0
        self.facility_cumulative_energy_kwh = 0.0
        self.estimated_cost_php = 0.0

        # Historical time-series spanning the entire simulation
        self.history_timestamps: List[float] = []
        self.history_queue_depth: List[float] = []
        self.history_power_watts: List[float] = []
        self.history_cost_php: List[float] = []
        self.history_energy_kwh: List[float] = []
        self.history_arrival_rate: List[float] = []
        self.history_dropped_rate: List[float] = []

    def record_sample(self, sim_time_sec: float, servers: list, arrival_rate: float):
        """Called periodically (e.g. every simulated 2s) to record full-simulation telemetry."""
        # Calculate step-wise provisioned facility power based on server hardware states
        # (eliminates microsecond 80ms active/idle load fraction jitter)
        step_watts = 0.0
        from src.server import ServerState
        for s in servers:
            if s.state == ServerState.OFF:
                step_watts += s.hw.off_power_watts
            elif s.state == ServerState.SLEEPING:
                step_watts += s.hw.sleep_power_watts
            elif s.state in (ServerState.BOOTING, ServerState.WAKING):
                step_watts += s.hw.boot_power_watts
            else:
                # Online operational node (IDLE or ACTIVE)
                # Nominal provisioned baseline power (250W + 50W when actively loaded)
                load_factor = min(1.0, s.active_request_count / max(1, s.capacity))
                step_watts += s.hw.idle_power_watts + (s.hw.peak_power_watts - s.hw.idle_power_watts) * (0.4 + 0.6 * load_factor)

        self.instant_power_watts = step_watts
        self.facility_instant_power_watts = step_watts * self.config.hardware.cooling_pue

        # Calculate cumulative server and facility energy
        server_kwh = sum(s.total_energy_kwh for s in servers)
        self.cumulative_energy_kwh = server_kwh
        self.facility_cumulative_energy_kwh = server_kwh * self.config.hardware.cooling_pue

        # Calculate estimated financial cost (Electricity Bill + SLA Drop Penalties)
        electricity_cost = self.facility_cumulative_energy_kwh * self.config.economics.cost_per_kwh_php
        sla_penalty_cost = self.total_requests_dropped * self.config.economics.cost_per_dropped_req_php
        self.estimated_cost_php = electricity_cost + sla_penalty_cost

        # Append to full simulation history
        self.history_timestamps.append(sim_time_sec)
        self.history_queue_depth.append(float(self.current_queue_depth))
        self.history_power_watts.append(self.facility_instant_power_watts)
        self.history_cost_php.append(self.estimated_cost_php)
        self.history_energy_kwh.append(self.facility_cumulative_energy_kwh)
        self.history_arrival_rate.append(arrival_rate)
        self.history_dropped_rate.append(float(self.total_requests_dropped))

    def reset(self):
        """Clear all metrics counters and historical telemetry."""
        self.total_requests_arrived = 0
        self.total_requests_served = 0
        self.total_requests_dropped = 0
        self.current_queue_depth = 0
        self.instant_power_watts = 0.0
        self.facility_instant_power_watts = 0.0
        self.cumulative_energy_kwh = 0.0
        self.facility_cumulative_energy_kwh = 0.0
        self.estimated_cost_php = 0.0
        self.history_timestamps.clear()
        self.history_queue_depth.clear()
        self.history_power_watts.clear()
        self.history_cost_php.clear()
        self.history_energy_kwh.clear()
        self.history_arrival_rate.clear()
        self.history_dropped_rate.clear()
