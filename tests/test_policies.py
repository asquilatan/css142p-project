"""Lean tests: all 4 provisioning policies run headless + key behaviors."""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
from src.config import SimConfig
from src.policies import AlwaysOnPolicy, ScheduledPolicy, SleepBufferPolicy, ThresholdPolicy
from src.server import ServerState
from src.simulation import SimulationEngine


def run_policy(policy_cls, duration=20.0, num_servers=3, seed=0):
    np.random.seed(seed)
    cfg = SimConfig(num_servers=num_servers)
    cfg.workload.diurnal_cycle_active = False
    eng = SimulationEngine(cfg)
    eng.set_policy(policy_cls())
    eng.step_simulation(duration)
    return eng


class TestPolicies(unittest.TestCase):
    def test_all_policies_complete_short_run(self):
        for cls in (AlwaysOnPolicy, ThresholdPolicy, ScheduledPolicy, SleepBufferPolicy):
            with self.subTest(policy=cls.__name__):
                eng = run_policy(cls)
                self.assertAlmostEqual(eng.env.now, 20.0, delta=0.6)
                self.assertEqual(len(eng.servers), 3)
                self.assertGreater(eng.metrics.total_requests_served, 0)
                self.assertGreater(
                    sum(s.total_energy_kwh for s in eng.servers), 0.0
                )

    def test_threshold_scale_up_boots_dormant(self):
        np.random.seed(0)
        cfg = SimConfig(num_servers=3)
        eng = SimulationEngine(cfg)
        pol = ThresholdPolicy(q_high=5, min_active_servers=1)
        eng.set_policy(pol)  # on_init: 1 ready, rest OFF
        off_before = [s for s in eng.servers if s.state == ServerState.OFF]
        self.assertGreaterEqual(len(off_before), 1)
        eng.request_queue.extend([eng.env.now] * 10)
        pol.on_tick(eng.env.now)
        booting = [s for s in eng.servers if s.state == ServerState.BOOTING]
        self.assertGreaterEqual(len(booting), 1)

    def test_sleep_buffer_parks_surplus_in_sleep(self):
        np.random.seed(0)
        cfg = SimConfig(num_servers=4)
        eng = SimulationEngine(cfg)
        eng.set_policy(SleepBufferPolicy(min_active_servers=2))
        sleeping = [s for s in eng.servers if s.state == ServerState.SLEEPING]
        self.assertGreaterEqual(len(sleeping), 1)  # surplus parked, not OFF

    def test_always_on_recovers_off_server(self):
        np.random.seed(0)
        cfg = SimConfig(num_servers=3)
        eng = SimulationEngine(cfg)
        pol = AlwaysOnPolicy()
        eng.set_policy(pol)
        eng.servers[0].power_off()
        self.assertEqual(eng.servers[0].state, ServerState.OFF)
        pol.on_tick(eng.env.now)
        self.assertEqual(eng.servers[0].state, ServerState.BOOTING)


if __name__ == "__main__":
    unittest.main()
