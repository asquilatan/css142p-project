//! Deterministic SplitMix64 PRNG + unit-rate exponential sampler.
//!
//! Replaces `random.expovariate` / `fastrand` with zero dependencies:
//! `sample_unit_exp() / rate` is distributionally identical to sampling
//! `Exp(rate)` directly, and vectorized refills are unnecessary at native
//! speed (one sample is a handful of integer ops).

/// SplitMix64 generator (Steele et al.). Period 2^64, excellent statistical
/// quality for simulation workloads, tiny state.
#[derive(Clone)]
pub struct SplitMix64 {
    state: u64,
}

impl SplitMix64 {
    /// Any non-zero seed works; the default is fixed so headless benchmark
    /// runs and Rust-vs-Python parity checks are reproducible.
    pub fn new(seed: u64) -> Self {
        Self { state: seed | 1 }
    }

    #[inline]
    pub fn next_u64(&mut self) -> u64 {
        // SplitMix64 mixing (public-domain, Steele–Lea–Flood).
        self.state = self.state.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.state;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }

    /// Uniform double in [0, 1) with 53 bits of randomness.
    #[inline]
    pub fn next_f64(&mut self) -> f64 {
        const SCALE: f64 = 1.0 / ((1u64 << 53) as f64);
        ((self.next_u64() >> 11) as f64) * SCALE
    }

    /// Unit-rate exponential: `-ln(1 - U)`. Clamps U away from 1.0 so the
    /// result is always finite (mirrors `random.expovariate` semantics).
    #[inline]
    pub fn sample_unit_exp(&mut self) -> f64 {
        let mut u = self.next_f64();
        if u >= 1.0 - f64::EPSILON {
            u = 1.0 - f64::EPSILON;
        }
        -(-u).ln_1p()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn exponential_has_unit_mean() {
        let mut rng = SplitMix64::new(0x1234_5678);
        let n = 200_000usize;
        let mut acc = 0.0;
        for _ in 0..n {
            acc += rng.sample_unit_exp();
        }
        let mean = acc / n as f64;
        assert!((mean - 1.0).abs() < 0.02, "mean was {mean}");
    }

    #[test]
    fn streams_are_deterministic() {
        let mut a = SplitMix64::new(42);
        let mut b = SplitMix64::new(42);
        for _ in 0..1000 {
            assert_eq!(a.next_u64(), b.next_u64());
        }
    }
}
