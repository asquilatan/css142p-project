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

        # Rolling time-series for live Picture-in-Picture graphs
        self.history_timestamps = deque(maxlen=history_max_len)
        self.history_queue_depth = deque(maxlen=history_max_len)
        self.history_power_watts = deque(maxlen=history_max_len)
        self.history_arrival_rate = deque(maxlen=history_max_len)
        self.history_dropped_rate = deque(maxlen=history_max_len)

    def record_sample(self, sim_time_sec: float, servers: list, arrival_rate: float):
        """Called periodically (e.g. every simulated 0.5s or 1s) to record rolling telemetry."""
        # Calculate instantaneous server power
        server_watts = sum(s.get_instantaneous_power_watts() for s in servers)
        self.instant_power_watts = server_watts
        self.facility_instant_power_watts = server_watts * self.config.hardware.cooling_pue

        # Calculate cumulative server and facility energy
        server_kwh = sum(s.total_energy_kwh for s in servers)
        self.cumulative_energy_kwh = server_kwh
        self.facility_cumulative_energy_kwh = server_kwh * self.config.hardware.cooling_pue

        # Calculate estimated financial cost (Electricity Bill + SLA Drop Penalties)
        electricity_cost = self.facility_cumulative_energy_kwh * self.config.economics.cost_per_kwh_php
        sla_penalty_cost = self.total_requests_dropped * self.config.economics.cost_per_dropped_req_php
        self.estimated_cost_php = electricity_cost + sla_penalty_cost

        # Append to rolling history deque
        self.history_timestamps.append(sim_time_sec)
        self.history_queue_depth.append(self.current_queue_depth)
        self.history_power_watts.append(self.facility_instant_power_watts)
        self.history_arrival_rate.append(arrival_rate)
        self.history_dropped_rate.append(self.total_requests_dropped)

    def reset(self):
        """Clear all metrics counters and rolling histories."""
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
        self.history_arrival_rate.clear()
        self.history_dropped_rate.clear()
