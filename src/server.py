"""
Physical Server Model & Energy Integrator.
Simulates realistic server state transitions (Cold boot, Sleep wake, Idle, Active, Off)
and numerically integrates continuous power and cooling energy consumption.
"""

from enum import Enum
import simpy
from src.config import HardwareConfig


class ServerState(Enum):
    OFF = "OFF"
    BOOTING = "BOOT"
    IDLE = "IDLE"
    ACTIVE = "ACTIVE"
    SLEEPING = "SLEEP"
    WAKING = "WAKE"


class Server:
    def __init__(self, env: simpy.Environment, server_id: int, hw_config: HardwareConfig, capacity: int = 2):
        self.env = env
        self.server_id = server_id
        self.hw = hw_config
        self.capacity = capacity  # Max concurrent requests this server can handle simultaneously

        self.state = ServerState.IDLE
        self.active_request_count = 0
        self.total_served_count = 0

        # State transition tracking
        self.transition_start_time = 0.0
        self.transition_target_duration = 0.0
        self.current_process = None

        # Energy tracking (Numerical integration of Power x Time)
        self.last_energy_update_time = self.env.now
        self.energy_joules_consumed = 0.0

        # SimPy Resource representing server concurrency slots
        self.resource = simpy.Resource(env, capacity=self.capacity)

    @property
    def total_energy_kwh(self) -> float:
        """Total server electrical energy consumed in Kilowatt-hours (kWh)."""
        self._update_energy()
        return self.energy_joules_consumed / 3_600_000.0

    def total_facility_energy_kwh(self, pue: float) -> float:
        """Total facility energy including cooling and power delivery overhead."""
        return self.total_energy_kwh * pue

    def get_instantaneous_power_watts(self) -> float:
        """Returns the current continuous power draw in Watts based on hardware state."""
        if self.state == ServerState.OFF:
            return self.hw.off_power_watts
        elif self.state in (ServerState.BOOTING, ServerState.WAKING):
            return self.hw.boot_power_watts
        elif self.state == ServerState.SLEEPING:
            return self.hw.sleep_power_watts
        elif self.state == ServerState.IDLE:
            return self.hw.idle_power_watts
        elif self.state == ServerState.ACTIVE:
            # Proportional power scaling: P_idle + (P_peak - P_idle) * (load / capacity)
            load_fraction = min(1.0, self.active_request_count / max(1, self.capacity))
            power_span = self.hw.peak_power_watts - self.hw.idle_power_watts
            return self.hw.idle_power_watts + (power_span * load_fraction)
        return self.hw.idle_power_watts

    def _update_energy(self):
        """Integrates energy consumption between the last recorded event and current sim time."""
        now = self.env.now
        delta_seconds = now - self.last_energy_update_time
        if delta_seconds > 0:
            current_watts = self.get_instantaneous_power_watts()
            # Joules = Watts * Seconds
            self.energy_joules_consumed += current_watts * delta_seconds
            self.last_energy_update_time = now

    def get_boot_progress_pct(self) -> float:
        """Returns 0.0 to 1.0 indicating completion of current boot or wake transition."""
        if self.state not in (ServerState.BOOTING, ServerState.WAKING) or self.transition_target_duration <= 0:
            return 1.0
        elapsed = self.env.now - self.transition_start_time
        return min(1.0, max(0.0, elapsed / self.transition_target_duration))

    def get_load_pct(self) -> float:
        """Returns current CPU/request capacity utilization percentage (0 to 100%)."""
        if self.state != ServerState.ACTIVE or self.capacity <= 0:
            return 0.0
        return min(100.0, (self.active_request_count / self.capacity) * 100.0)

    # -------------------------------------------------------------------------
    # State Transition Processes
    # -------------------------------------------------------------------------

    def boot(self):
        """Initiate physical cold-boot sequence from OFF to IDLE."""
        self._update_energy()
        if self.state in (ServerState.IDLE, ServerState.ACTIVE, ServerState.BOOTING):
            return
        self.state = ServerState.BOOTING
        self.transition_start_time = self.env.now
        self.transition_target_duration = self.hw.cold_boot_delay_sec
        self.current_process = self.env.process(self._boot_process())

    def _boot_process(self):
        try:
            yield self.env.timeout(self.hw.cold_boot_delay_sec)
            self._update_energy()
            self.state = ServerState.IDLE
            self.current_process = None
        except simpy.Interrupt:
            self._update_energy()
            self.state = ServerState.OFF

    def wake(self):
        """Initiate fast wake sequence from SLEEPING to IDLE."""
        self._update_energy()
        if self.state in (ServerState.IDLE, ServerState.ACTIVE, ServerState.WAKING):
            return
        self.state = ServerState.WAKING
        self.transition_start_time = self.env.now
        self.transition_target_duration = self.hw.sleep_wake_delay_sec
        self.current_process = self.env.process(self._wake_process())

    def _wake_process(self):
        try:
            yield self.env.timeout(self.hw.sleep_wake_delay_sec)
            self._update_energy()
            self.state = ServerState.IDLE
            self.current_process = None
        except simpy.Interrupt:
            self._update_energy()
            self.state = ServerState.SLEEPING

    def sleep(self):
        """Put server into low-power ACPI standby sleep."""
        self._update_energy()
        if self.active_request_count > 0:
            return  # Do not sleep while actively processing requests
        if self.current_process and self.current_process.is_alive:
            self.current_process.interrupt()
        self.state = ServerState.SLEEPING

    def power_off(self):
        """Completely power off the server node."""
        self._update_energy()
        if self.active_request_count > 0:
            return  # Do not power off while actively processing requests
        if self.current_process and self.current_process.is_alive:
            self.current_process.interrupt()
        self.state = ServerState.OFF

    # -------------------------------------------------------------------------
    # Request Execution
    # -------------------------------------------------------------------------

    def can_accept_request(self) -> bool:
        """Returns True if node is ready and has available processing capacity."""
        if self.state not in (ServerState.IDLE, ServerState.ACTIVE):
            return False
        return self.active_request_count < self.capacity

    def reserve_slot(self):
        """Synchronously reserves a processing slot at dispatch time."""
        if self.env.now != self.last_energy_update_time:
            self._update_energy()
        self.active_request_count += 1
        self.state = ServerState.ACTIVE

    def release_slot(self):
        """Releases a processing slot upon request completion."""
        if self.env.now != self.last_energy_update_time:
            self._update_energy()
        self.active_request_count = max(0, self.active_request_count - 1)
        self.total_served_count += 1
        if self.active_request_count == 0:
            self.state = ServerState.IDLE

    def serve_request(self, service_time: float):
        """SimPy process that executes a request on this server node."""
        try:
            yield self.env.timeout(service_time)
        finally:
            self.release_slot()

