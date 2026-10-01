//! Traffic workload model: exact mirror of `src/workload.py`.
//!
//! - 24h sinusoidal diurnal curve (trough 03:00, peak 15:00)
//! - Flash-crowd surge multiplier with expiry
//! - Abrupt traffic drop override
//! - UI traffic-scale slider factor
//!
//! Times are integer microseconds; the diurnal wave is quantized to whole
//! simulated seconds exactly like the Python 1s-bucket cache.

use crate::rng::SplitMix64;

pub const DAY_US: u64 = 86_400_000_000;

#[derive(Clone)]
pub struct WorkloadConfig {
    pub base_rate: f64,
    pub peak_rate: f64,
    pub surge_multiplier: f64,
    pub service_time_s: f64,
    pub request_timeout_s: f64,
    pub max_queue_capacity: usize,
    pub diurnal_active: bool,
}

impl Default for WorkloadConfig {
    fn default() -> Self {
        Self {
            base_rate: 20.0,
            peak_rate: 80.0,
            surge_multiplier: 3.5,
            service_time_s: 0.08,
            request_timeout_s: 3.0,
            max_queue_capacity: 120,
            diurnal_active: true,
        }
    }
}

pub struct Workload {
    pub cfg: WorkloadConfig,
    pub flash_active: bool,
    pub flash_start_us: u64,
    pub flash_duration_us: u64,
    pub traffic_scale: f64,
    pub abrupt_drop: bool,
    rng: SplitMix64,
    wave_bucket: u64,
    wave_value: f64,
    wave_valid: bool,
}

impl Workload {
    pub fn new(cfg: WorkloadConfig, seed: u64) -> Self {
        Self {
            cfg,
            flash_active: false,
            flash_start_us: 0,
            flash_duration_us: 300_000_000,
            traffic_scale: 1.0,
            abrupt_drop: false,
            rng: SplitMix64::new(seed),
            wave_bucket: 0,
            wave_value: 0.0,
            wave_valid: false,
        }
    }

    pub fn trigger_flash_crowd(&mut self, now_us: u64, duration_us: u64) {
        self.flash_active = true;
        self.flash_start_us = now_us;
        self.flash_duration_us = duration_us;
        self.abrupt_drop = false;
    }

    pub fn trigger_abrupt_drop(&mut self) {
        self.abrupt_drop = true;
        self.flash_active = false;
    }

    pub fn reset_triggers(&mut self) {
        self.flash_active = false;
        self.abrupt_drop = false;
    }

    fn diurnal_wave(&mut self, now_us: u64) -> f64 {
        let bucket = now_us / 1_000_000;
        if !self.wave_valid || bucket != self.wave_bucket {
            let day_s = ((bucket * 1_000_000) % DAY_US) as f64 / 1_000_000.0;
            let radians = 2.0 * std::f64::consts::PI * (day_s - 10_800.0) / 86_400.0;
            self.wave_value = ((radians - std::f64::consts::FRAC_PI_2).sin() + 1.0) / 2.0;
            self.wave_bucket = bucket;
            self.wave_valid = true;
        }
        self.wave_value
    }

    /// Instantaneous Poisson arrival rate (requests/second). Surge/drop
    /// flags are evaluated fresh on every call, exactly like Python.
    pub fn arrival_rate(&mut self, now_us: u64) -> f64 {
        if self.abrupt_drop {
            return 2.0 * self.traffic_scale;
        }
        if self.flash_active && now_us.wrapping_sub(self.flash_start_us) > self.flash_duration_us {
            self.flash_active = false;
        }
        let base = if !self.cfg.diurnal_active {
            (self.cfg.base_rate + self.cfg.peak_rate) / 2.0
        } else {
            let wave = self.diurnal_wave(now_us);
            self.cfg.base_rate + (self.cfg.peak_rate - self.cfg.base_rate) * wave
        };
        let with_surge = if self.flash_active {
            base * self.cfg.surge_multiplier
        } else {
            base
        };
        (with_surge * self.traffic_scale).max(1.0)
    }

    /// Next inter-arrival interval in microseconds.
    pub fn next_interarrival_us(&mut self, now_us: u64) -> u64 {
        let rate = self.arrival_rate(now_us);
        let dt_s = self.rng.sample_unit_exp() / rate;
        (dt_s * 1_000_000.0).round().max(1.0) as u64
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn midnight_rate_matches_python() {
        // t = 0 (midnight): wave = (sin(-0.785 - pi/2) + 1) / 2 ~= 0.1464
        // rate = 20 + 60 * 0.1464 ~= 28.79
        let mut w = Workload::new(WorkloadConfig::default(), 1);
        let rate = w.arrival_rate(0);
        assert!((rate - 28.79).abs() < 0.05, "rate was {rate}");
    }

    #[test]
    fn flash_and_drop_overrides() {
        let mut w = Workload::new(WorkloadConfig::default(), 1);
        w.trigger_flash_crowd(0, 300_000_000);
        let surge = w.arrival_rate(1_000_000);
        assert!(surge > 90.0, "surge rate was {surge}");
        w.trigger_abrupt_drop();
        assert_eq!(w.arrival_rate(2_000_000), 2.0);
        // Flash expiry returns to baseline.
        w.trigger_flash_crowd(0, 300_000_000);
        let after = w.arrival_rate(301_000_000);
        assert!(after < 90.0, "flash did not expire: {after}");
    }
}
