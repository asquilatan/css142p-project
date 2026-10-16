"""Lean unit tests: WorkloadGenerator rates, surges, drops (seeded, deterministic)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
from src.config import WorkloadConfig
from src.workload import WorkloadGenerator


class TestWorkload(unittest.TestCase):
    def setUp(self):
        np.random.seed(0)
        self.cfg = WorkloadConfig()

    def test_diurnal_trough_and_peak(self):
        w = WorkloadGenerator(self.cfg)
        trough = w.get_current_arrival_rate(10800.0)   # 03:00 trough
        peak = w.get_current_arrival_rate(54000.0)     # 15:00 peak
        self.assertAlmostEqual(trough, 20.0, delta=1.0)
        self.assertAlmostEqual(peak, 80.0, delta=1.0)
        self.assertLess(trough, peak)

    def test_diurnal_disabled_gives_midpoint(self):
        self.cfg.diurnal_cycle_active = False
        w = WorkloadGenerator(self.cfg)
        self.assertAlmostEqual(w.get_current_arrival_rate(0.0), 50.0, delta=0.01)

    def test_flash_crowd_multiplies_then_expires(self):
        w = WorkloadGenerator(self.cfg)
        w.config.diurnal_cycle_active = False  # base 50 rps
        w.trigger_flash_crowd(0.0, duration=10.0)
        self.assertAlmostEqual(w.get_current_arrival_rate(5.0), 50.0 * 3.5, delta=0.01)
        self.assertAlmostEqual(w.get_current_arrival_rate(11.0), 50.0, delta=0.01)  # expired
        self.assertFalse(w.flash_crowd_active)

    def test_abrupt_drop_collapses_traffic(self):
        w = WorkloadGenerator(self.cfg)
        w.trigger_abrupt_drop()
        self.assertAlmostEqual(w.get_current_arrival_rate(0.0), 2.0, delta=0.01)
        w.traffic_scale_factor = 2.0
        self.assertAlmostEqual(w.get_current_arrival_rate(0.0), 4.0, delta=0.01)

    def test_interarrival_positive(self):
        w = WorkloadGenerator(self.cfg)
        for _ in range(20):
            self.assertGreater(w.get_next_interarrival_time(0.0), 0.0)


if __name__ == "__main__":
    unittest.main()
