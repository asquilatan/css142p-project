//! C-ABI surface for the Python `ctypes` bridge (`src/engine_bridge.py`).
//!
//! Safety contract (all enforced, never assumed):
//! - Every struct crossing the boundary is `#[repr(C)]` and contains only
//!   FFI-safe scalars (`u32`/`u64`/`f64`); no `bool`, no `usize`, no Rust
//!   enums, no fat pointers.
//! - Every entry point null-checks raw pointers and catches panics via
//!   `catch_unwind`, so a Rust bug can never unwind into the Pygame loop.
//! - Time crosses the boundary as `f64` seconds (the unit Python works in);
//!   integer microseconds exist only inside the engine for heap ordering.
//! - Financial parameters (tariff, SLA penalty) are intentionally NOT part
//!   of the ABI: cost is computed Python-side from reported energy + drops,
//!   so the in-app economics sliders keep working with zero extra calls.

mod engine;
mod rng;
mod workload;

use std::panic::{catch_unwind, AssertUnwindSafe};

use engine::{HardwareConfig, PolicyId, ServerState, Simulation, Telemetry, MAX_SERVERS};
use workload::WorkloadConfig;

const US_PER_S: f64 = 1_000_000.0;

fn s_to_us(s: f64) -> u64 {
    if !s.is_finite() || s <= 0.0 {
        0
    } else {
        (s * US_PER_S).round().max(1.0) as u64
    }
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct SimConfigC {
    pub num_servers: u32,
    pub policy_id: u32,
    pub server_capacity: u32,
    pub peak_w: f64,
    pub idle_w: f64,
    pub sleep_w: f64,
    pub off_w: f64,
    pub boot_w: f64,
    pub cold_boot_s: f64,
    pub wake_s: f64,
    pub pue: f64,
    pub base_rate: f64,
    pub peak_rate: f64,
    pub surge_mult: f64,
    pub service_s: f64,
    pub timeout_s: f64,
    pub max_queue: u32,
    pub diurnal_on: u8,
    pub traffic_scale: f64,
    pub seed: u64,
}

impl SimConfigC {
    fn hardware(&self) -> HardwareConfig {
        HardwareConfig {
            peak_w: self.peak_w,
            idle_w: self.idle_w,
            sleep_w: self.sleep_w,
            off_w: self.off_w,
            boot_w: self.boot_w,
            cold_boot_us: s_to_us(self.cold_boot_s).max(1),
            wake_us: s_to_us(self.wake_s).max(1),
            pue: self.pue,
        }
    }

    fn workload(&self) -> WorkloadConfig {
        WorkloadConfig {
            base_rate: self.base_rate,
            peak_rate: self.peak_rate,
            surge_multiplier: self.surge_mult,
            service_time_s: self.service_s.max(0.001),
            request_timeout_s: self.timeout_s.max(0.1),
            max_queue_capacity: self.max_queue.max(1) as usize,
            diurnal_active: self.diurnal_on != 0,
        }
    }
}

#[repr(C)]
#[derive(Clone, Copy, Default)]
pub struct TelemetryC {
    pub now_s: f64,
    pub arrived: u64,
    pub served: u64,
    pub dropped: u64,
    pub queue_depth: u32,
    pub instant_w: f64,
    pub facility_instant_w: f64,
    pub energy_kwh: f64,
    pub facility_energy_kwh: f64,
    pub arrival_rate: f64,
}

impl From<Telemetry> for TelemetryC {
    fn from(t: Telemetry) -> Self {
        Self {
            now_s: t.now_s,
            arrived: t.arrived,
            served: t.served,
            dropped: t.dropped,
            queue_depth: t.queue_depth,
            instant_w: t.instant_w,
            facility_instant_w: t.facility_instant_w,
            energy_kwh: t.energy_kwh,
            facility_energy_kwh: t.facility_energy_kwh,
            arrival_rate: t.arrival_rate,
        }
    }
}

#[repr(C)]
#[derive(Clone, Copy, Default)]
pub struct ServerStateC {
    /// 0=Off, 1=Booting, 2=Idle, 3=Active, 4=Sleeping, 5=Waking
    pub state_id: u32,
    pub active: u32,
    pub capacity: u32,
    pub boot_progress: f64,
    pub power_w: f64,
    pub energy_kwh: f64,
}

fn with_sim<T>(ptr: *mut Simulation, f: impl FnOnce(&mut Simulation) -> T, fallback: T) -> T {
    if ptr.is_null() {
        return fallback;
    }
    match catch_unwind(AssertUnwindSafe(|| {
        // SAFETY: non-null ownership-checked pointer created by sim_create
        // and only destroyed by sim_destroy; the bridge is single-threaded.
        f(unsafe { &mut *ptr })
    })) {
        Ok(v) => v,
        Err(_) => fallback,
    }
}

/// Creates a simulation. Returns null on invalid config or allocation panic.
#[no_mangle]
pub extern "C" fn sim_create(
    num_servers: u32,
    policy_id: u32,
    config: *const SimConfigC,
) -> *mut Simulation {
    if config.is_null() {
        return std::ptr::null_mut();
    }
    let result = catch_unwind(|| {
        // SAFETY: null-checked above; bridge passes a valid SimConfigC.
        let cfg = unsafe { *config };
        let n = (num_servers.max(1).min(MAX_SERVERS as u32)) as usize;
        let capacity = cfg.server_capacity.max(1);
        let mut workload_cfg = cfg.workload();
        let mut sim = Simulation::new(
            n,
            PolicyId::from_u32(policy_id),
            cfg.hardware(),
            workload_cfg.clone(),
            capacity,
            cfg.seed,
        );
        workload_cfg.diurnal_active = cfg.diurnal_on != 0;
        sim.workload.cfg = workload_cfg;
        sim.workload.traffic_scale = cfg.traffic_scale.max(0.05);
        Box::into_raw(Box::new(sim))
    });
    result.unwrap_or(std::ptr::null_mut())
}

/// Destroys a simulation created by `sim_create`. Null-safe no-op.
#[no_mangle]
pub extern "C" fn sim_destroy(sim: *mut Simulation) {
    if sim.is_null() {
        return;
    }
    let _ = catch_unwind(AssertUnwindSafe(|| {
        // SAFETY: inverse of Box::into_raw in sim_create; called once.
        unsafe {
            drop(Box::from_raw(sim));
        }
    }));
}

/// Advances the event loop to `target_time_s` (no-op if in the past).
#[no_mangle]
pub extern "C" fn sim_step(sim: *mut Simulation, target_time_s: f64) {
    with_sim(sim, |s| s.step(s_to_us(target_time_s)), ());
}

/// Current simulation time in seconds (-1.0 on null).
#[no_mangle]
pub extern "C" fn sim_now(sim: *mut Simulation) -> f64 {
    with_sim(sim, |s| s.now_s(), -1.0)
}

/// Writes a telemetry snapshot into `out`. Returns 0 on success, -1 on null.
#[no_mangle]
pub extern "C" fn sim_get_telemetry(sim: *mut Simulation, out: *mut TelemetryC) -> i32 {
    if sim.is_null() || out.is_null() {
        return -1;
    }
    with_sim(
        sim,
        |s| {
            let snap = s.snapshot();
            // SAFETY: null-checked above; plain-data struct write.
            unsafe {
                *out = TelemetryC::from(snap);
            }
            0
        },
        -1,
    )
}

/// Writes server `server_idx` state into `out`. Returns 0/-1.
#[no_mangle]
pub extern "C" fn sim_get_server_state(
    sim: *mut Simulation,
    server_idx: u32,
    out: *mut ServerStateC,
) -> i32 {
    if sim.is_null() || out.is_null() {
        return -1;
    }
    with_sim(
        sim,
        |s| {
            let idx = server_idx as usize;
            if idx >= s.server_count() {
                return -1;
            }
            let node = &s.servers[idx];
            let state_id = match node.state {
                ServerState::Off => 0,
                ServerState::Booting => 1,
                ServerState::Idle => 2,
                ServerState::Active => 3,
                ServerState::Sleeping => 4,
                ServerState::Waking => 5,
            };
            // SAFETY: null-checked above; plain-data struct write.
            unsafe {
                *out = ServerStateC {
                    state_id,
                    active: node.active,
                    capacity: node.capacity,
                    boot_progress: node.boot_progress(),
                    power_w: node.current_power_w,
                    energy_kwh: node.energy_kwh(),
                };
            }
            0
        },
        -1,
    )
}

/// Hot-swaps the provisioning policy (0-3). Re-runs policy init.
#[no_mangle]
pub extern "C" fn sim_set_policy(sim: *mut Simulation, policy_id: u32) {
    with_sim(sim, |s| s.set_policy(PolicyId::from_u32(policy_id)), ());
}

/// Injects a flash-crowd surge lasting `duration_s` seconds.
#[no_mangle]
pub extern "C" fn sim_trigger_flash_crowd(sim: *mut Simulation, duration_s: f64) {
    with_sim(
        sim,
        |s| {
            let now = s.now_us();
            s.workload
                .trigger_flash_crowd(now, s_to_us(duration_s).max(1));
        },
        (),
    );
}

/// Collapses traffic to the abrupt-drop floor.
#[no_mangle]
pub extern "C" fn sim_trigger_abrupt_drop(sim: *mut Simulation) {
    with_sim(sim, |s| s.workload.trigger_abrupt_drop(), ());
}

/// Clears surge/drop overrides back to the diurnal baseline.
#[no_mangle]
pub extern "C" fn sim_reset_triggers(sim: *mut Simulation) {
    with_sim(sim, |s| s.workload.reset_triggers(), ());
}

/// Sets the UI traffic-volume multiplier.
#[no_mangle]
pub extern "C" fn sim_set_traffic_scale(sim: *mut Simulation, scale: f64) {
    with_sim(
        sim,
        |s| {
            if scale.is_finite() {
                s.workload.traffic_scale = scale.max(0.05);
            }
        },
        (),
    );
}

/// Enables/disables the 24h diurnal cycle (non-zero = on).
#[no_mangle]
pub extern "C" fn sim_set_diurnal(sim: *mut Simulation, on: u8) {
    with_sim(sim, |s| s.workload.cfg.diurnal_active = on != 0, ());
}

/// Resizes the server pool (clamped to 1-10).
#[no_mangle]
pub extern "C" fn sim_set_server_count(sim: *mut Simulation, count: u32) {
    with_sim(sim, |s| s.set_server_count(count as usize), ());
}

/// Live-applies hardware/workload tunables (boot/wake delays, PUE,
/// wattages, rates). Server count / policy keep their dedicated setters.
#[no_mangle]
pub extern "C" fn sim_apply_config(sim: *mut Simulation, config: *const SimConfigC) {
    if sim.is_null() || config.is_null() {
        return;
    }
    with_sim(
        sim,
        |s| {
            // SAFETY: null-checked above; read-only copy of a SimConfigC.
            let cfg = unsafe { *config };
            let scale = s.workload.traffic_scale;
            let flash = (s.workload.flash_active, s.workload.flash_start_us, s.workload.flash_duration_us);
            let abrupt = s.workload.abrupt_drop;
            s.hw = cfg.hardware();
            s.workload.cfg = cfg.workload();
            s.workload.traffic_scale = scale;
            s.workload.flash_active = flash.0;
            s.workload.flash_start_us = flash.1;
            s.workload.flash_duration_us = flash.2;
            s.workload.abrupt_drop = abrupt;
        },
        (),
    );
}
