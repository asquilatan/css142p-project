"""Lean tests: SimulationEngine dispatch, queue drops, server scaling, cost math."""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
from src.config import SimConfig
from src.policies import AlwaysOnPolicy
from src.simulation import SimulationEngine


def make_engine(num_servers=3, seed=0):
    np.random.seed(seed)
    cfg = SimConfig(num_servers=num_servers)
    cfg.workload.diurnal_cycle_active = False  # stable 50 rps for determinism
    eng = SimulationEngine(cfg)
    eng.set_policy(AlwaysOnPolicy())
    return eng


class TestSimulation(unittest.TestCase):
    def test_short_run_serves_and_conserves_requests(self):
        eng = make_engine()
        eng.step_simulation(20.0)
        self.assertAlmostEqual(eng.env.now, 20.0, delta=0.6)
        m = eng.metrics
        self.assertGreater(m.total_requests_arrived, 100)
        self.assertGreater(m.total_requests_served, 100)
        in_service = sum(s.active_request_count for s in eng.servers)
        self.assertEqual(
            m.total_requests_arrived,
            m.total_requests_served + m.total_requests_dropped + len(eng.request_queue) + in_service,
        )

    def test_energy_and_cost_math(self):
        eng = make_engine()
        eng.step_simulation(20.0)
        m = eng.metrics
        m.record_sample(eng.env.now, eng.servers, 50.0)
        self.assertGreater(m.cumulative_energy_kwh, 0.0)
        self.assertAlmostEqual(
            m.facility_cumulative_energy_kwh,
            m.cumulative_energy_kwh * eng.config.hardware.cooling_pue,
            places=9,
        )
        expected = (
            m.facility_cumulative_energy_kwh * eng.config.economics.cost_per_kwh_php
            + m.total_requests_dropped * eng.config.economics.cost_per_dropped_req_php
        )
        self.assertAlmostEqual(m.estimated_cost_php, expected, places=6)

    def test_server_count_clamps_3_to_10(self):
        eng = make_engine(num_servers=5)
        eng.set_num_servers(2)
        self.assertEqual(len(eng.servers), 3)
        eng.set_num_servers(20)
        self.assertEqual(len(eng.servers), 10)
        eng.set_num_servers(5)
        self.assertEqual(len(eng.servers), 5)

    def test_stale_queue_entries_purged_as_drops(self):
        eng = make_engine()
        eng.request_queue.extend([eng.env.now - 10.0] * 3)  # timeout is 3.0s
        dropped_before = eng.metrics.total_requests_dropped
        eng._try_dispatch()
        self.assertEqual(len(eng.request_queue), 0)
        self.assertEqual(eng.metrics.total_requests_dropped, dropped_before + 3)


if __name__ == "__main__":
    unittest.main()
