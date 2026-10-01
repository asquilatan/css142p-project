"""
Hybrid engine bridge: Rust accelerator with automatic SimPy fallback.

`create_engine(config)` returns a simulation engine with the same public
surface the UI and policies rely on:

- ``step_simulation(target_time)``, ``set_policy(policy)``,
  ``set_num_servers(count)``, ``clean_packet_animations(...)``
- ``servers`` (state/active/capacity/boot-progress introspection),
  ``request_queue`` (``len()``), ``workload`` (surge/drop/scale triggers),
  ``metrics`` (counters + full-timeline histories), ``env.now``
- ``is_rust_accelerated`` flag so the UI can badge the active backend.

When ``sim_core`` (``crates/sim_core/target/release/`` or ``assets/bin/``,
platform-appropriate extension) loads, all physics runs in RustBehind a
`ctypes` C-ABI; economics (tariff/SLA) stay Python-side so the settings
sliders keep working with no extra ABI. Otherwise a pure-SimPy
``SimulationEngine`` is used transparently.
"""

import ctypes
import os
import platform
from types import SimpleNamespace
from typing import List, Optional

from src.config import SimConfig
from src.metrics import MetricsCollector
from src.server import ServerState

_POLICY_IDS = {}
_RUST_SEED = 0xC0FFEE


def _policy_map():
    # Imported lazily to keep module import order cycle-free.
    from src.policies import (
        AlwaysOnPolicy,
        ScheduledPolicy,
        SleepBufferPolicy,
        ThresholdPolicy,
    )
    return {
        AlwaysOnPolicy: 0,
        ThresholdPolicy: 1,
        ScheduledPolicy: 2,
        SleepBufferPolicy: 3,
    }


def policy_id_for(policy) -> int:
    global _POLICY_IDS
    if not _POLICY_IDS:
        _POLICY_IDS = _policy_map()
    for cls, pid in _POLICY_IDS.items():
        if isinstance(policy, cls):
            return pid
    return 1


class _SimConfigC(ctypes.Structure):
    _fields_ = [
        ("num_servers", ctypes.c_uint32),
        ("policy_id", ctypes.c_uint32),
        ("server_capacity", ctypes.c_uint32),
        ("peak_w", ctypes.c_double),
        ("idle_w", ctypes.c_double),
        ("sleep_w", ctypes.c_double),
        ("off_w", ctypes.c_double),
        ("boot_w", ctypes.c_double),
        ("cold_boot_s", ctypes.c_double),
        ("wake_s", ctypes.c_double),
        ("pue", ctypes.c_double),
        ("base_rate", ctypes.c_double),
        ("peak_rate", ctypes.c_double),
        ("surge_mult", ctypes.c_double),
        ("service_s", ctypes.c_double),
        ("timeout_s", ctypes.c_double),
        ("max_queue", ctypes.c_uint32),
        ("diurnal_on", ctypes.c_uint8),
        ("traffic_scale", ctypes.c_double),
        ("seed", ctypes.c_uint64),
    ]


class _TelemetryC(ctypes.Structure):
    _fields_ = [
        ("now_s", ctypes.c_double),
        ("arrived", ctypes.c_uint64),
        ("served", ctypes.c_uint64),
        ("dropped", ctypes.c_uint64),
        ("queue_depth", ctypes.c_uint32),
        ("instant_w", ctypes.c_double),
        ("facility_instant_w", ctypes.c_double),
        ("energy_kwh", ctypes.c_double),
        ("facility_energy_kwh", ctypes.c_double),
        ("arrival_rate", ctypes.c_double),
    ]


class _ServerStateC(ctypes.Structure):
    _fields_ = [
        ("state_id", ctypes.c_uint32),
        ("active", ctypes.c_uint32),
        ("capacity", ctypes.c_uint32),
        ("boot_progress", ctypes.c_double),
        ("power_w", ctypes.c_double),
        ("energy_kwh", ctypes.c_double),
    ]


_STATE_BY_ID = {
    0: ServerState.OFF,
    1: ServerState.BOOTING,
    2: ServerState.IDLE,
    3: ServerState.ACTIVE,
    4: ServerState.SLEEPING,
    5: ServerState.WAKING,
}


def _lib_name() -> str:
    system = platform.system()
    if system == "Windows":
        return "sim_core.dll"
    if system == "Darwin":
        return "libsim_core.dylib"
    return "libsim_core.so"


def _find_library() -> Optional[str]:
    name = _lib_name()
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(here, "crates", "sim_core", "target", "release", name),
        os.path.join(here, "assets", "bin", name),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


class RustServerProxy:
    """UI-facing server snapshot refreshed from the Rust core each step."""

    def __init__(self, server_id: int, hw, capacity: int):
        self.server_id = server_id
        self.hw = hw
        self.capacity = capacity
        self.state = ServerState.IDLE
        self.active_request_count = 0
        self.total_served_count = 0
        self._boot_progress = 1.0

    def get_boot_progress_pct(self) -> float:
        return self._boot_progress

    def get_load_pct(self) -> float:
        if self.state != ServerState.ACTIVE or self.capacity <= 0:
            return 0.0
        return min(100.0, (self.active_request_count / self.capacity) * 100.0)


class _QueueLenProxy:
    """Display-only queue stand-in exposing ``len()`` for the canvas."""

    def __init__(self, engine: "RustEngine"):
        self._engine = engine

    def __len__(self) -> int:
        return int(self._engine.metrics.current_queue_depth)

    def __bool__(self) -> bool:
        return self._engine.metrics.current_queue_depth > 0


class _WorkloadProxy:
    """Forwards surge/drop/scale controls to the Rust core."""

    def __init__(self, engine: "RustEngine"):
        self._engine = engine

    @property
    def traffic_scale_factor(self) -> float:
        return self._engine._traffic_scale

    @traffic_scale_factor.setter
    def traffic_scale_factor(self, value: float):
        self._engine._traffic_scale = float(value)
        self._engine._lib.sim_set_traffic_scale(self._engine._handle, float(value))

    def trigger_flash_crowd(self, current_time: float, duration: float = 300.0):
        self._engine._lib.sim_trigger_flash_crowd(self._engine._handle, float(duration))

    def trigger_abrupt_drop(self):
        self._engine._lib.sim_trigger_abrupt_drop(self._engine._handle)

    def reset_triggers(self):
        self._engine._lib.sim_reset_triggers(self._engine._handle)

    def get_current_arrival_rate(self, sim_time_seconds: float) -> float:
        # Simulation views only use this for display; the last telemetry
        # snapshot's rate is fresh enough (refreshed every step).
        return self._engine.metrics.history_arrival_rate[-1] \
            if self._engine.metrics.history_arrival_rate else 0.0

    def get_next_interarrival_time(self, sim_time_seconds: float) -> float:
        rate = self.get_current_arrival_rate(sim_time_seconds)
        if rate <= 0:
            return 1.0
        import random
        return random.expovariate(rate)


class RustEngine:
    """ctypes-backed engine with the SimulationEngine public surface."""

    is_rust_accelerated = True

    def __init__(self, config: SimConfig, lib: ctypes.CDLL, policy_id: int = 4):
        self.config = config
        self._lib = lib
        self._policy_id = policy_id
        self._policy_name = "Threshold-Based"
        self._traffic_scale = 1.0
        self._server_count = max(1, min(10, config.num_servers))
        self.env = SimpleNamespace(now=0.0)
        self.metrics = MetricsCollector(config)
        self.servers: List[RustServerProxy] = [
            RustServerProxy(i + 1, config.hardware, config.server_capacity_concurrency)
            for i in range(self._server_count)
        ]
        self.request_queue = _QueueLenProxy(self)
        self.workload = _WorkloadProxy(self)
        self._handle = None
        self._create()

    # -- lifecycle ------------------------------------------------------
    def _config_struct(self) -> _SimConfigC:
        hw = self.config.hardware
        wl = self.config.workload
        return _SimConfigC(
            num_servers=self._server_count,
            policy_id=self._policy_id,
            server_capacity=self.config.server_capacity_concurrency,
            peak_w=hw.peak_power_watts,
            idle_w=hw.idle_power_watts,
            sleep_w=hw.sleep_power_watts,
            off_w=hw.off_power_watts,
            boot_w=hw.boot_power_watts,
            cold_boot_s=hw.cold_boot_delay_sec,
            wake_s=hw.sleep_wake_delay_sec,
            pue=hw.cooling_pue,
            base_rate=wl.base_arrival_rate,
            peak_rate=wl.peak_arrival_rate,
            surge_mult=wl.surge_multiplier,
            service_s=wl.mean_service_time_sec,
            timeout_s=wl.request_timeout_sec,
            max_queue=wl.max_queue_capacity,
            diurnal_on=1 if wl.diurnal_cycle_active else 0,
            traffic_scale=self._traffic_scale,
            seed=_RUST_SEED,
        )

    def _create(self):
        if self._handle is not None:
            self._lib.sim_destroy(self._handle)
            self._handle = None
        self._handle = self._lib.sim_create(
            self._server_count, self._policy_id, ctypes.byref(self._config_struct())
        )
        if not self._handle:
            raise RuntimeError("sim_create returned null")
        self.env.now = 0.0
        self._refresh_servers()

    def __del__(self):
        try:
            if getattr(self, "_handle", None):
                self._lib.sim_destroy(self._handle)
                self._handle = None
        except Exception:
            pass

    # -- SimulationEngine-compatible API --------------------------------
    def set_policy(self, policy):
        self._policy_id = policy_id_for(policy)
        self._policy_name = getattr(policy, "name", self._policy_name)
        self._lib.sim_set_policy(self._handle, self._policy_id)
        self._refresh_servers()

    def set_num_servers(self, new_count: int):
        new_count = max(3, min(10, new_count))
        self.config.num_servers = new_count
        if new_count != self._server_count:
            self._server_count = new_count
            self._lib.sim_set_server_count(self._handle, new_count)
            self.servers = [
                RustServerProxy(i + 1, self.config.hardware,
                                self.config.server_capacity_concurrency)
                for i in range(new_count)
            ]
            self._refresh_servers()

    def step_simulation(self, target_time: float):
        if target_time <= self.env.now:
            return
        # Push live-tunable physics (tariffs stay Python-side by design).
        self._lib.sim_apply_config(self._handle, ctypes.byref(self._config_struct()))
        self._lib.sim_set_diurnal(
            self._handle, 1 if self.config.workload.diurnal_cycle_active else 0
        )
        self._lib.sim_set_traffic_scale(
            self._handle, float(self._traffic_scale)
        )
        self._lib.sim_step(self._handle, float(target_time))
        self._record_snapshot()

    def clean_packet_animations(self, current_real_time: float):
        pass

    # -- snapshots ------------------------------------------------------
    def _snapshot(self) -> _TelemetryC:
        out = _TelemetryC()
        rc = self._lib.sim_get_telemetry(self._handle, ctypes.byref(out))
        if rc != 0:
            raise RuntimeError("sim_get_telemetry failed")
        return out

    def _refresh_servers(self):
        out = _ServerStateC()
        for i, proxy in enumerate(self.servers):
            rc = self._lib.sim_get_server_state(self._handle, i, ctypes.byref(out))
            if rc != 0:
                continue
            proxy.state = _STATE_BY_ID.get(out.state_id, ServerState.OFF)
            proxy.active_request_count = int(out.active)
            proxy.capacity = int(out.capacity)
            proxy._boot_progress = float(out.boot_progress)

    def _record_snapshot(self):
        tele = self._snapshot()
        self.env.now = float(tele.now_s)
        m = self.metrics
        m.total_requests_arrived = int(tele.arrived)
        m.total_requests_served = int(tele.served)
        m.total_requests_dropped = int(tele.dropped)
        m.current_queue_depth = int(tele.queue_depth)
        m.instant_power_watts = float(tele.instant_w)
        m.facility_instant_power_watts = float(tele.facility_instant_w)
        m.cumulative_energy_kwh = float(tele.energy_kwh)
        m.facility_cumulative_energy_kwh = float(tele.facility_energy_kwh)
        econ = self.config.economics
        m.estimated_cost_php = (
            m.facility_cumulative_energy_kwh * econ.cost_per_kwh_php
            + m.total_requests_dropped * econ.cost_per_dropped_req_php
        )
        m.history_timestamps.append(float(tele.now_s))
        m.history_queue_depth.append(float(tele.queue_depth))
        m.history_power_watts.append(float(tele.facility_instant_w))
        m.history_cost_php.append(m.estimated_cost_php)
        m.history_energy_kwh.append(float(tele.facility_energy_kwh))
        m.history_arrival_rate.append(float(tele.arrival_rate))
        m.history_dropped_rate.append(float(tele.dropped))
        self._refresh_servers()


def _bind_library(lib: ctypes.CDLL):
    lib.sim_create.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(_SimConfigC)]
    lib.sim_create.restype = ctypes.c_void_p
    lib.sim_destroy.argtypes = [ctypes.c_void_p]
    lib.sim_destroy.restype = None
    lib.sim_step.argtypes = [ctypes.c_void_p, ctypes.c_double]
    lib.sim_step.restype = None
    lib.sim_now.argtypes = [ctypes.c_void_p]
    lib.sim_now.restype = ctypes.c_double
    lib.sim_get_telemetry.argtypes = [ctypes.c_void_p, ctypes.POINTER(_TelemetryC)]
    lib.sim_get_telemetry.restype = ctypes.c_int
    lib.sim_get_server_state.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(_ServerStateC)]
    lib.sim_get_server_state.restype = ctypes.c_int
    lib.sim_set_policy.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    lib.sim_set_policy.restype = None
    lib.sim_trigger_flash_crowd.argtypes = [ctypes.c_void_p, ctypes.c_double]
    lib.sim_trigger_flash_crowd.restype = None
    lib.sim_trigger_abrupt_drop.argtypes = [ctypes.c_void_p]
    lib.sim_trigger_abrupt_drop.restype = None
    lib.sim_reset_triggers.argtypes = [ctypes.c_void_p]
    lib.sim_reset_triggers.restype = None
    lib.sim_set_traffic_scale.argtypes = [ctypes.c_void_p, ctypes.c_double]
    lib.sim_set_traffic_scale.restype = None
    lib.sim_set_diurnal.argtypes = [ctypes.c_void_p, ctypes.c_uint8]
    lib.sim_set_diurnal.restype = None
    lib.sim_set_server_count.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    lib.sim_set_server_count.restype = None
    lib.sim_apply_config.argtypes = [ctypes.c_void_p, ctypes.POINTER(_SimConfigC)]
    lib.sim_apply_config.restype = None


def create_engine(config: SimConfig):
    """Builds the fastest available engine (Rust, else pure SimPy)."""
    path = _find_library()
    if path is not None:
        try:
            lib = ctypes.CDLL(path)
            _bind_library(lib)
            engine = RustEngine(config, lib)
            # Smoke-check the ABI before committing to this backend.
            engine.step_simulation(1.0)
            return engine
        except Exception:
            pass
    from src.simulation import SimulationEngine
    engine = SimulationEngine(config)
    engine.is_rust_accelerated = False
    return engine
