"""
Automated unit & parity benchmark test suite: Python (SimPy) vs. Rust (sim_core).

Verifies algorithmic parity, invariant satisfaction, and benchmarks execution speed
between the reference SimPy engine and the compiled Rust accelerator.
"""

import ctypes
import os
import sys
import time
import unittest

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.config import SimConfig
from src.engine_bridge import (
    RustEngine,
    _bind_library,
    _find_library,
    policy_id_for,
    rust_available,
)
from src.policies import (
    AlwaysOnPolicy,
    ScheduledPolicy,
    SleepBufferPolicy,
    ThresholdPolicy,
)
from src.simulation import SimulationEngine


class TestPythonVsRustBenchmark(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rust_present = rust_available()
        if cls.rust_present:
            dll_path = _find_library()
            cls.lib = ctypes.CDLL(dll_path)
            _bind_library(cls.lib)
        else:
            cls.lib = None

    def _run_python_sim(self, config: SimConfig, policy_cls, duration_sec: float):
        """Runs the reference Python/SimPy engine."""
        py_engine = SimulationEngine(config)
        policy = policy_cls()
        py_engine.set_policy(policy)
        policy.on_init()

        t0 = time.perf_counter()
        py_engine.step_simulation(duration_sec)
        elapsed = time.perf_counter() - t0

        return py_engine, elapsed

    def _run_rust_sim(self, config: SimConfig, policy_cls, duration_sec: float):
        """Runs the compiled Rust engine."""
        policy = policy_cls()
        pid = policy_id_for(policy)
        rust_engine = RustEngine(config, self.lib, policy_id=pid)

        t0 = time.perf_counter()
        rust_engine.step_simulation(duration_sec)
        elapsed = time.perf_counter() - t0

        return rust_engine, elapsed

    def test_benchmark_short_run_parity(self):
        """Runs a 300-second simulation and benchmarks timing and macroscopic parity."""
        if not self.rust_present:
            self.skipTest("Rust binary (sim_core) not available.")

        sim_duration = 300.0
        cfg = SimConfig(num_servers=5)

        py_sim, t_py = self._run_python_sim(cfg, ThresholdPolicy, sim_duration)
        rust_sim, t_rust = self._run_rust_sim(cfg, ThresholdPolicy, sim_duration)

        # Basic invariant checks
        self.assertAlmostEqual(py_sim.env.now, sim_duration, delta=0.1)
        self.assertAlmostEqual(rust_sim.env.now, sim_duration, delta=0.1)

        # Non-negative metrics
        self.assertGreater(py_sim.metrics.total_requests_arrived, 0)
        self.assertGreater(rust_sim.metrics.total_requests_arrived, 0)
        self.assertGreater(py_sim.metrics.facility_cumulative_energy_kwh, 0.0)
        self.assertGreater(rust_sim.metrics.facility_cumulative_energy_kwh, 0.0)

        # Macroscopic arrival rate check (Poisson arrivals should be within 15% across engines)
        arr_ratio = abs(
            py_sim.metrics.total_requests_arrived - rust_sim.metrics.total_requests_arrived
        ) / py_sim.metrics.total_requests_arrived
        self.assertLess(
            arr_ratio,
            0.15,
            f"Arrival disparity {arr_ratio:.2%} exceeded stochastic tolerance",
        )

        # Timing and speedup
        speedup = t_py / max(1e-9, t_rust)
        print(f"\n[Side-by-Side 300s Run]")
        print(f"  Python (SimPy) Time : {t_py * 1000:.2f} ms ({py_sim.metrics.total_requests_served} served)")
        print(f"  Rust (sim_core) Time: {t_rust * 1000:.2f} ms ({rust_sim.metrics.total_requests_served} served)")
        print(f"  Rust Speedup        : {speedup:.1f}x faster")

        self.assertGreater(
            speedup,
            5.0,
            f"Expected Rust to be at least 5x faster, got {speedup:.1f}x",
        )

    def test_benchmark_all_policies_execution(self):
        """Tests all 4 provisioning policies side-by-side to guarantee both engines run without failure."""
        if not self.rust_present:
            self.skipTest("Rust binary (sim_core) not available.")

        sim_duration = 300.0
        policies = [
            (AlwaysOnPolicy, "Always-On"),
            (ThresholdPolicy, "Threshold"),
            (ScheduledPolicy, "Scheduled"),
            (SleepBufferPolicy, "Sleep-Buffer"),
        ]

        print(f"\n{'Policy':<15} | {'Py Time':<10} | {'Rust Time':<10} | {'Speedup':<8} | {'Py Served':<10} | {'Rust Served':<10}")
        print("-" * 75)

        for pol_cls, name in policies:
            cfg = SimConfig(num_servers=5)
            py_sim, t_py = self._run_python_sim(cfg, pol_cls, sim_duration)
            rust_sim, t_rust = self._run_rust_sim(cfg, pol_cls, sim_duration)

            speedup = t_py / max(1e-9, t_rust)

            print(
                f"{name:<15} | {t_py * 1000:7.2f} ms | {t_rust * 1000:7.2f} ms | "
                f"{speedup:6.1f}x | {py_sim.metrics.total_requests_served:<10} | "
                f"{rust_sim.metrics.total_requests_served:<10}"
            )

            # Both engines should have served requests
            self.assertGreater(py_sim.metrics.total_requests_served, 0)
            self.assertGreater(rust_sim.metrics.total_requests_served, 0)

            # Both engines should maintain server population
            self.assertEqual(len(py_sim.servers), 5)
            self.assertEqual(len(rust_sim.servers), 5)

    def test_surge_injection_parity(self):
        """Tests flash-crowd surge injection behavior across both engines."""
        if not self.rust_present:
            self.skipTest("Rust binary (sim_core) not available.")

        cfg = SimConfig(num_servers=5)
        # Step 60s normal
        py_sim, _ = self._run_python_sim(cfg, ThresholdPolicy, 60.0)
        rust_sim, _ = self._run_rust_sim(cfg, ThresholdPolicy, 60.0)

        # Trigger flash crowd
        py_sim.workload.trigger_flash_crowd(py_sim.env.now, duration=120.0)
        rust_sim.workload.trigger_flash_crowd(rust_sim.env.now, duration=120.0)

        # Step through surge
        py_sim.step_simulation(180.0)
        rust_sim.step_simulation(180.0)

        # Both engines should have experienced queue buildup and served significantly more requests
        self.assertGreater(py_sim.metrics.total_requests_arrived, 3000)
        self.assertGreater(rust_sim.metrics.total_requests_arrived, 3000)


if __name__ == "__main__":
    unittest.main()
