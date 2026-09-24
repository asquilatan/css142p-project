"""
Hardware, simulation, and financial configuration parameters.
Allows dynamic modification during runtime for live experimentation.
"""

from dataclasses import dataclass, field


@dataclass
class HardwareConfig:
    # Power consumption ratings in Watts (literature benchmarks: Fan et al., 2007; Gandhi et al., 2009)
    peak_power_watts: float = 300.0     # Power drawn when fully active serving requests
    idle_power_watts: float = 150.0     # Power drawn when powered on with 0 active requests (50% of peak)
    sleep_power_watts: float = 15.0     # Low-power ACPI S3 sleep state
    off_power_watts: float = 2.0        # Dormant/off power consumption
    boot_power_watts: float = 300.0     # Power consumed during cold boot sequence

    # Transition latencies (seconds)
    cold_boot_delay_sec: float = 120.0  # Cold boot delay (120s - 180s)
    sleep_wake_delay_sec: float = 4.0   # Fast wake from sleep (2s - 5s)
    shutdown_delay_sec: float = 5.0     # Graceful power off

    # Cooling & facility overhead
    cooling_pue: float = 1.4            # Power Usage Effectiveness (1.0 = ideal, 1.4 = standard data center)


@dataclass
class EconomicsConfig:
    # Financial parameters in Philippine Peso (PHP)
    cost_per_kwh_php: float = 9.50      # Typical Meralco commercial electricity rate (~PHP 9.50 - 11.00/kWh)
    cost_per_dropped_req_php: float = 0.50 # Estimated SLA penalty/revenue loss per dropped request


@dataclass
class WorkloadConfig:
    base_arrival_rate: float = 20.0     # Base requests/second during trough
    peak_arrival_rate: float = 80.0     # Peak requests/second during diurnal surge
    surge_multiplier: float = 3.5       # Multiplier during flash crowd burst
    mean_service_time_sec: float = 0.08 # Mean execution time per request (~80ms)
    request_timeout_sec: float = 3.0    # Drop request if queued longer than this timeout
    max_queue_capacity: int = 120       # Maximum buffer size before tail-drop
    diurnal_cycle_active: bool = True   # Follow 24h diurnal curve automatically


@dataclass
class SimConfig:
    num_servers: int = 5                # Number of servers (default 5, adjustable 3-10)
    server_capacity_concurrency: int = 2# Requests a single server can process concurrently
    hardware: HardwareConfig = field(default_factory=HardwareConfig)
    economics: EconomicsConfig = field(default_factory=EconomicsConfig)
    workload: WorkloadConfig = field(default_factory=WorkloadConfig)

    # UI Theme colors (matching clean architectural sketch aesthetic)
    bg_color: tuple = (250, 250, 252)
    border_color: tuple = (20, 20, 25)
    text_color: tuple = (25, 25, 30)
    text_muted: tuple = (110, 115, 125)
    accent_blue: tuple = (41, 128, 185)
    accent_green: tuple = (46, 204, 113)
    accent_orange: tuple = (230, 126, 34)
    accent_red: tuple = (231, 76, 60)
    accent_purple: tuple = (155, 89, 182)
    panel_bg: tuple = (255, 255, 255)
