//! Discrete-event engine: exact mirror of `src/simulation.py` + `src/server.py`.
//!
//! Differences from the Python implementation are purely mechanical:
//! - Simulation time is integer microseconds (`u64`) so heap ordering needs
//!   no float wrapper.
//! - Server transition cancellation uses generation tokens instead of
//!   `simpy.Interrupt`.
//! - Energy is integrated analytically on every state mutation plus a
//!   whole-pool sync at the end of each `step()` (identical sums to the
//!   per-event integration, since power is piecewise-constant between
//!   events).

use std::cmp::Reverse;
use std::collections::{BinaryHeap, VecDeque};

use crate::workload::{Workload, WorkloadConfig};

pub const MAX_SERVERS: usize = 10;
pub const POLICY_INTERVAL_US: u64 = 500_000; // must match Python dispatch resolution
pub const J_PER_KWH: f64 = 3_600_000.0;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum ServerState {
    Off = 0,
    Booting = 1,
    Idle = 2,
    Active = 3,
    Sleeping = 4,
    Waking = 5,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum PolicyId {
    AlwaysOn = 0,
    Threshold = 1,
    Scheduled = 2,
    SleepBuffer = 3,
    /// No policy attached yet: init and ticks are no-ops. The Python bridge
    /// creates simulations with this so the first real `set_policy` runs
    /// exactly one init — mirroring SimPy, where no policy acts before
    /// `attach()`.
    None = 4,
}

impl PolicyId {
    pub fn from_u32(v: u32) -> Self {
        match v {
            0 => PolicyId::AlwaysOn,
            2 => PolicyId::Scheduled,
            3 => PolicyId::SleepBuffer,
            4 => PolicyId::None,
            _ => PolicyId::Threshold,
        }
    }
}

#[derive(Clone)]
pub struct HardwareConfig {
    pub peak_w: f64,
    pub idle_w: f64,
    pub sleep_w: f64,
    pub off_w: f64,
    pub boot_w: f64,
    pub cold_boot_us: u64,
    pub wake_us: u64,
    pub pue: f64,
}

impl Default for HardwareConfig {
    fn default() -> Self {
        Self {
            peak_w: 300.0,
            idle_w: 150.0,
            sleep_w: 15.0,
            off_w: 2.0,
            boot_w: 300.0,
            cold_boot_us: 120_000_000,
            wake_us: 4_000_000,
            pue: 1.4,
        }
    }
}

/// Contiguous, stack-friendly server node (mirrors `Server` energy math).
#[derive(Clone)]
pub struct ServerNode {
    pub state: ServerState,
    pub active: u32,
    pub capacity: u32,
    pub served: u64,
    pub power_per_slot: f64,
    pub current_power_w: f64,
    pub energy_j: f64,
    pub last_update_us: u64,
    pub trans_start_us: u64,
    pub trans_dur_us: u64,
    pub trans_gen: u64,
    pub clock_us: u64, // engine time of last sync (for boot-progress reads)
}

impl ServerNode {
    fn new(hw: &HardwareConfig, capacity: u32) -> Self {
        Self {
            state: ServerState::Idle,
            active: 0,
            capacity,
            served: 0,
            power_per_slot: (hw.peak_w - hw.idle_w) / capacity.max(1) as f64,
            current_power_w: hw.idle_w,
            energy_j: 0.0,
            last_update_us: 0,
            trans_start_us: 0,
            trans_dur_us: 0,
            trans_gen: 0,
            clock_us: 0,
        }
    }

    fn sync(&mut self, now_us: u64) {
        self.clock_us = now_us;
        if now_us > self.last_update_us {
            let dt_s = (now_us - self.last_update_us) as f64 / 1_000_000.0;
            self.energy_j += self.current_power_w * dt_s;
            self.last_update_us = now_us;
        }
    }

    pub fn energy_kwh(&self) -> f64 {
        self.energy_j / J_PER_KWH
    }

    pub fn boot_progress(&self) -> f64 {
        match self.state {
            ServerState::Booting | ServerState::Waking if self.trans_dur_us > 0 => {
                let elapsed = self.clock_us.saturating_sub(self.trans_start_us) as f64;
                (elapsed / self.trans_dur_us as f64).clamp(0.0, 1.0)
            }
            _ => 1.0,
        }
    }

    pub fn can_accept(&self) -> bool {
        matches!(self.state, ServerState::Idle | ServerState::Active) && self.active < self.capacity
    }

    fn reserve_slot(&mut self, hw: &HardwareConfig, now_us: u64) {
        self.sync(now_us);
        self.active += 1;
        self.state = ServerState::Active;
        self.current_power_w =
            hw.idle_w + self.power_per_slot * self.active.min(self.capacity) as f64;
    }

    fn release_slot(&mut self, hw: &HardwareConfig, now_us: u64) {
        self.sync(now_us);
        self.active = self.active.saturating_sub(1);
        self.served += 1;
        if self.active == 0 {
            self.state = ServerState::Idle;
            self.current_power_w = hw.idle_w;
        } else {
            self.current_power_w = hw.idle_w + self.power_per_slot * self.active as f64;
        }
    }
}

#[derive(Clone, Copy)]
enum Event {
    Arrival,
    Complete { server: u32 },
    BootDone { server: u32, gen: u64 },
    WakeDone { server: u32, gen: u64 },
    PolicyTick,
}

#[derive(Clone, Copy)]
struct HeapItem {
    time_us: u64,
    seq: u64,
    event: Event,
}

impl PartialEq for HeapItem {
    fn eq(&self, other: &Self) -> bool {
        self.time_us == other.time_us && self.seq == other.seq
    }
}
impl Eq for HeapItem {}
impl PartialOrd for HeapItem {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        Some(self.cmp(other))
    }
}
impl Ord for HeapItem {
    fn cmp(&self, other: &Self) -> std::cmp::Ordering {
        self.time_us
            .cmp(&other.time_us)
            .then(self.seq.cmp(&other.seq))
    }
}

/// Telemetry snapshot (plain data; cost is computed Python-side so live
/// tariff/SLA tuning needs no extra ABI calls).
#[derive(Clone, Copy, Default)]
pub struct Telemetry {
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

pub struct Simulation {
    pub hw: HardwareConfig,
    pub workload: Workload,
    pub policy: PolicyId,
    pub servers: Vec<ServerNode>,
    pub queue: VecDeque<u64>, // arrival timestamps (µs)
    pub arrived: u64,
    pub served: u64,
    pub dropped: u64,
    pub queue_depth: usize,
    now_us: u64,
    heap: BinaryHeap<Reverse<HeapItem>>,
    seq: u64,
    round_robin: usize,
    capacity: u32,
    // Threshold policy hysteresis state (mirrors ThresholdPolicy fields).
    last_scale_down_us: u64,
}

impl Simulation {
    pub fn new(
        num_servers: usize,
        policy: PolicyId,
        hw: HardwareConfig,
        wcfg: WorkloadConfig,
        capacity: u32,
        seed: u64,
    ) -> Self {
        let n = num_servers.clamp(1, MAX_SERVERS);
        let mut sim = Self {
            hw,
            workload: Workload::new(wcfg, seed),
            policy,
            servers: Vec::with_capacity(MAX_SERVERS),
            queue: VecDeque::new(),
            arrived: 0,
            served: 0,
            dropped: 0,
            queue_depth: 0,
            now_us: 0,
            heap: BinaryHeap::new(),
            seq: 0,
            round_robin: 0,
            capacity,
            last_scale_down_us: 0,
        };
        for _ in 0..n {
            sim.servers.push(ServerNode::new(&sim.hw.clone(), capacity));
        }
        let first = sim.workload.next_interarrival_us(0);
        sim.push_event(first, Event::Arrival);
        sim.push_event(0, Event::PolicyTick);
        sim.apply_policy_init();
        sim
    }

    pub fn now_us(&self) -> u64 {
        self.now_us
    }

    pub fn now_s(&self) -> f64 {
        self.now_us as f64 / 1_000_000.0
    }

    pub fn server_count(&self) -> usize {
        self.servers.len()
    }

    // -- configuration --------------------------------------------------
    pub fn set_policy(&mut self, policy: PolicyId) {
        self.policy = policy;
        self.last_scale_down_us = 0;
        self.apply_policy_init();
    }

    pub fn set_server_count(&mut self, count: usize) {
        let n = count.clamp(1, MAX_SERVERS);
        let cur = self.servers.len();
        if n > cur {
            for _ in cur..n {
                self.servers.push(ServerNode::new(&self.hw.clone(), self.capacity));
            }
        } else {
            while self.servers.len() > n {
                let idx = self.servers.len() - 1;
                self.power_off(idx);
                self.servers.pop();
            }
        }
        self.round_robin = 0;
        self.sync_all();
    }

    // -- event loop -----------------------------------------------------
    fn push_event(&mut self, time_us: u64, event: Event) {
        let seq = self.seq;
        self.seq += 1;
        self.heap.push(Reverse(HeapItem {
            time_us,
            seq,
            event,
        }));
    }

    pub fn step(&mut self, target_us: u64) {
        if target_us <= self.now_us {
            return;
        }
        while let Some(Reverse(top)) = self.heap.peek() {
            if top.time_us > target_us {
                break;
            }
            let Reverse(item) = self.heap.pop().unwrap();
            self.now_us = item.time_us;
            match item.event {
                Event::Arrival => self.on_arrival(),
                Event::Complete { server } => self.on_completion(server as usize),
                Event::BootDone { server, gen } => {
                    let i = server as usize;
                    if i < self.servers.len() {
                        let node = &mut self.servers[i];
                        if gen == node.trans_gen && node.state == ServerState::Booting {
                            let hw_idle = self.hw.idle_w;
                            node.sync(self.now_us);
                            node.state = ServerState::Idle;
                            node.current_power_w = hw_idle;
                        }
                    }
                }
                Event::WakeDone { server, gen } => {
                    let i = server as usize;
                    if i < self.servers.len() {
                        let node = &mut self.servers[i];
                        if gen == node.trans_gen && node.state == ServerState::Waking {
                            let hw_idle = self.hw.idle_w;
                            node.sync(self.now_us);
                            node.state = ServerState::Idle;
                            node.current_power_w = hw_idle;
                        }
                    }
                }
                Event::PolicyTick => {
                    self.purge_expired();
                    self.try_dispatch();
                    self.apply_policy_tick();
                    self.push_event(self.now_us + POLICY_INTERVAL_US, Event::PolicyTick);
                }
            }
        }
        self.now_us = target_us;
        self.sync_all();
    }

    fn sync_all(&mut self) {
        for node in self.servers.iter_mut() {
            node.sync(self.now_us);
        }
    }

    // -- load balancer --------------------------------------------------
    fn find_ready(&mut self) -> Option<usize> {
        let n = self.servers.len();
        if n == 0 {
            return None;
        }
        for offset in 0..n {
            let idx = (self.round_robin + offset) % n;
            if self.servers[idx].can_accept() {
                self.round_robin = (idx + 1) % n;
                return Some(idx);
            }
        }
        None
    }

    fn start_serving(&mut self, idx: usize) {
        let now = self.now_us;
        let hw = self.hw.clone();
        self.servers[idx].reserve_slot(&hw, now);
        let service_us = (self.workload.cfg.service_time_s * 1_000_000.0).round() as u64;
        self.push_event(now + service_us.max(1), Event::Complete { server: idx as u32 });
    }

    fn purge_expired(&mut self) {
        let timeout_us = (self.workload.cfg.request_timeout_s * 1_000_000.0).round() as u64;
        let mut dropped = 0u64;
        while let Some(&front) = self.queue.front() {
            if self.now_us.wrapping_sub(front) > timeout_us {
                self.queue.pop_front();
                dropped += 1;
            } else {
                break;
            }
        }
        self.dropped += dropped;
    }

    fn on_arrival(&mut self) {
        self.arrived += 1;
        let gap = self.workload.next_interarrival_us(self.now_us);
        self.push_event(self.now_us + gap.max(1), Event::Arrival);

        if self.queue.len() >= self.workload.cfg.max_queue_capacity {
            self.dropped += 1;
            return;
        }
        if self.queue.is_empty() {
            if let Some(idx) = self.find_ready() {
                self.start_serving(idx);
                return;
            }
        }
        self.queue.push_back(self.now_us);
        self.queue_depth = self.queue.len();
    }

    fn on_completion(&mut self, idx: usize) {
        if idx >= self.servers.len() {
            return;
        }
        let hw = self.hw.clone();
        self.servers[idx].release_slot(&hw, self.now_us);
        self.served += 1;
        self.purge_expired();
        if !self.queue.is_empty() && self.servers[idx].can_accept() {
            self.queue.pop_front();
            self.start_serving(idx);
        }
        self.queue_depth = self.queue.len();
    }

    fn try_dispatch(&mut self) {
        if self.servers.is_empty() || self.queue.is_empty() {
            self.queue_depth = self.queue.len();
            return;
        }
        while !self.queue.is_empty() {
            match self.find_ready() {
                Some(idx) => {
                    self.queue.pop_front();
                    self.start_serving(idx);
                }
                None => break,
            }
        }
        self.queue_depth = self.queue.len();
    }

    // -- server transitions ---------------------------------------------
    fn boot(&mut self, idx: usize) {
        if idx >= self.servers.len() {
            return;
        }
        let hw = self.hw.clone();
        let node = &mut self.servers[idx];
        node.sync(self.now_us);
        match node.state {
            ServerState::Idle | ServerState::Active | ServerState::Booting => return,
            _ => {}
        }
        node.state = ServerState::Booting;
        node.current_power_w = hw.boot_w;
        node.trans_start_us = self.now_us;
        node.trans_dur_us = hw.cold_boot_us;
        node.trans_gen += 1;
        let gen = node.trans_gen;
        self.push_event(self.now_us + hw.cold_boot_us, Event::BootDone { server: idx as u32, gen });
    }

    fn wake(&mut self, idx: usize) {
        if idx >= self.servers.len() {
            return;
        }
        let hw = self.hw.clone();
        let node = &mut self.servers[idx];
        node.sync(self.now_us);
        match node.state {
            ServerState::Idle | ServerState::Active | ServerState::Waking => return,
            _ => {}
        }
        node.state = ServerState::Waking;
        node.current_power_w = hw.boot_w;
        node.trans_start_us = self.now_us;
        node.trans_dur_us = hw.wake_us;
        node.trans_gen += 1;
        let gen = node.trans_gen;
        self.push_event(self.now_us + hw.wake_us, Event::WakeDone { server: idx as u32, gen });
    }

    fn sleep_node(&mut self, idx: usize) {
        if idx >= self.servers.len() {
            return;
        }
        let node = &mut self.servers[idx];
        node.sync(self.now_us);
        if node.active > 0 {
            return;
        }
        if matches!(node.state, ServerState::Booting | ServerState::Waking) {
            node.trans_gen += 1;
        }
        let hw_sleep = self.hw.sleep_w;
        node.state = ServerState::Sleeping;
        node.current_power_w = hw_sleep;
    }

    fn power_off(&mut self, idx: usize) {
        if idx >= self.servers.len() {
            return;
        }
        let node = &mut self.servers[idx];
        node.sync(self.now_us);
        if node.active > 0 {
            return;
        }
        if matches!(node.state, ServerState::Booting | ServerState::Waking) {
            node.trans_gen += 1;
        }
        let hw_off = self.hw.off_w;
        node.state = ServerState::Off;
        node.current_power_w = hw_off;
    }

    fn ready_count(&self) -> usize {
        self.servers
            .iter()
            .filter(|s| matches!(s.state, ServerState::Idle | ServerState::Active))
            .count()
    }

    fn first_in_state(&self, state: ServerState) -> Option<usize> {
        self.servers.iter().position(|s| s.state == state)
    }

    fn last_idle(&self) -> Option<usize> {
        self.servers
            .iter()
            .rposition(|s| s.state == ServerState::Idle && s.active == 0)
    }

    // -- provisioning policies (mirrors src/policies/*.py) -------------
    fn apply_policy_init(&mut self) {
        match self.policy {
            PolicyId::None => {}
            PolicyId::AlwaysOn => {
                for i in 0..self.servers.len() {
                    if matches!(self.servers[i].state, ServerState::Off | ServerState::Sleeping) {
                        self.boot(i);
                    }
                }
            }
            PolicyId::Threshold => {
                // min_active_servers = 1
                let mut kept = 0;
                for i in 0..self.servers.len() {
                    if kept < 1 {
                        if self.servers[i].state == ServerState::Off {
                            self.boot(i);
                        }
                        kept += 1;
                    } else {
                        self.power_off(i);
                    }
                }
            }
            PolicyId::Scheduled => {
                self.evaluate_schedule();
            }
            PolicyId::SleepBuffer => {
                // min_active_servers = 2
                let mut kept = 0;
                for i in 0..self.servers.len() {
                    if kept < 2 {
                        match self.servers[i].state {
                            ServerState::Off => self.boot(i),
                            ServerState::Sleeping => self.wake(i),
                            _ => {}
                        }
                        kept += 1;
                    } else {
                        self.sleep_node(i);
                    }
                }
            }
        }
    }

    fn evaluate_schedule(&mut self) {
        // Mirrors ScheduledPolicy(peak 9-18h, pre-boot 20min, min_night 1).
        let hour = (self.now_us % 86_400_000_000) as f64 / 3_600_000_000.0;
        let pre_boot_hour = 9.0 - (20.0 / 60.0);
        if pre_boot_hour <= hour && hour <= 18.0 {
            for i in 0..self.servers.len() {
                match self.servers[i].state {
                    ServerState::Off => self.boot(i),
                    ServerState::Sleeping => self.wake(i),
                    _ => {}
                }
            }
        } else {
            let mut kept = 0;
            for i in 0..self.servers.len() {
                if kept < 1 {
                    if self.servers[i].state == ServerState::Off {
                        self.boot(i);
                    }
                    kept += 1;
                } else if matches!(
                    self.servers[i].state,
                    ServerState::Idle | ServerState::Sleeping
                ) && self.servers[i].active == 0
                {
                    self.power_off(i);
                }
            }
        }
    }

    fn apply_policy_tick(&mut self) {
        match self.policy {
            PolicyId::None => {}
            PolicyId::AlwaysOn => {
                for i in 0..self.servers.len() {
                    match self.servers[i].state {
                        ServerState::Off => self.boot(i),
                        ServerState::Sleeping => self.wake(i),
                        _ => {}
                    }
                }
            }
            PolicyId::Threshold => {
                // q_high = 5, q_low = 0, cooldown = 20s, min_active = 1
                let qlen = self.queue.len();
                if qlen >= 5 {
                    if let Some(i) = self.first_in_state(ServerState::Off) {
                        self.boot(i);
                    }
                } else if qlen == 0
                    && self.now_us.wrapping_sub(self.last_scale_down_us) > 20_000_000
                {
                    if self.ready_count() > 1 {
                        if let Some(i) = self.last_idle() {
                            self.power_off(i);
                            self.last_scale_down_us = self.now_us;
                        }
                    }
                }
            }
            PolicyId::Scheduled => {
                self.evaluate_schedule();
            }
            PolicyId::SleepBuffer => {
                // wake_threshold = 3, sleep_cooldown = 12s, min_active = 2
                let qlen = self.queue.len();
                if qlen >= 3 {
                    if let Some(i) = self.first_in_state(ServerState::Sleeping) {
                        self.wake(i);
                    } else if let Some(i) = self.first_in_state(ServerState::Off) {
                        self.boot(i);
                    }
                } else if qlen == 0
                    && self.now_us.wrapping_sub(self.last_scale_down_us) > 12_000_000
                {
                    if self.ready_count() > 2 {
                        if let Some(i) = self.last_idle() {
                            self.sleep_node(i);
                            self.last_scale_down_us = self.now_us;
                        }
                    }
                }
            }
        }
    }

    // -- telemetry ------------------------------------------------------
    /// Provisioned facility power model: exact mirror of
    /// MetricsCollector.record_sample's step-wise estimate.
    pub fn snapshot(&mut self) -> Telemetry {
        self.sync_all();
        let mut step_w = 0.0;
        for node in self.servers.iter() {
            let load = (node.active.min(node.capacity) as f64) / node.capacity.max(1) as f64;
            step_w += match node.state {
                ServerState::Off => self.hw.off_w,
                ServerState::Sleeping => self.hw.sleep_w,
                ServerState::Booting | ServerState::Waking => self.hw.boot_w,
                ServerState::Idle | ServerState::Active => {
                    self.hw.idle_w + (self.hw.peak_w - self.hw.idle_w) * (0.4 + 0.6 * load.min(1.0))
                }
            };
        }
        let energy_kwh: f64 = self.servers.iter().map(|s| s.energy_kwh()).sum();
        Telemetry {
            now_s: self.now_s(),
            arrived: self.arrived,
            served: self.served,
            dropped: self.dropped,
            queue_depth: self.queue.len() as u32,
            instant_w: step_w,
            facility_instant_w: step_w * self.hw.pue,
            energy_kwh,
            facility_energy_kwh: energy_kwh * self.hw.pue,
            arrival_rate: self.workload.arrival_rate(self.now_us),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_sim(policy: PolicyId) -> Simulation {
        Simulation::new(
            5,
            policy,
            HardwareConfig::default(),
            WorkloadConfig::default(),
            2,
            0xC0FFEE,
        )
    }

    #[test]
    fn all_policies_serve_traffic() {
        for policy in [
            PolicyId::AlwaysOn,
            PolicyId::Threshold,
            PolicyId::Scheduled,
            PolicyId::SleepBuffer,
        ] {
            let mut sim = test_sim(policy);
            sim.step(600_000_000);
            assert!(sim.arrived > 1000, "{policy:?}: no arrivals");
            assert!(sim.served > 0, "{policy:?}: nothing served");
            assert!(
                sim.served + sim.dropped <= sim.arrived,
                "{policy:?}: conservation violated"
            );
        }
    }

    #[test]
    fn threshold_scales_up_under_load() {
        let mut sim = test_sim(PolicyId::Threshold);
        sim.workload.traffic_scale = 3.0;
        sim.step(300_000_000);
        let online = sim
            .servers
            .iter()
            .filter(|s| {
                matches!(
                    s.state,
                    ServerState::Idle | ServerState::Active | ServerState::Booting
                )
            })
            .count();
        assert!(online > 1, "threshold never scaled up ({online} online)");
    }

    #[test]
    fn energy_is_conserved_and_positive() {
        let mut sim = test_sim(PolicyId::AlwaysOn);
        sim.step(120_000_000);
        let snap = sim.snapshot();
        assert!(snap.energy_kwh > 0.0);
        assert!(snap.facility_energy_kwh >= snap.energy_kwh);
    }
}
