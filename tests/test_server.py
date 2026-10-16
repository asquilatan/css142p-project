"""Lean unit tests: Server state machine + energy integrator (unittest, stdlib only)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import simpy
from src.config import HardwareConfig
from src.server import Server, ServerState


def make_server(cold_boot=2.0, wake=1.0, capacity=2):
    hw = HardwareConfig(cold_boot_delay_sec=cold_boot, sleep_wake_delay_sec=wake)
    env = simpy.Environment()
    return env, Server(env, server_id=1, hw_config=hw, capacity=capacity)


class TestServerStateMachine(unittest.TestCase):
    def test_initial_state_idle_with_idle_power(self):
        env, srv = make_server()
        self.assertEqual(srv.state, ServerState.IDLE)
        self.assertTrue(srv.can_accept_request())
        self.assertAlmostEqual(srv.get_instantaneous_power_watts(), 150.0)

    def test_reserve_release_slot_power_and_load(self):
        env, srv = make_server()
        srv.reserve_slot()
        self.assertEqual(srv.state, ServerState.ACTIVE)
        self.assertEqual(srv.active_request_count, 1)
        self.assertAlmostEqual(srv.get_load_pct(), 50.0)  # 1 of 2 slots
        # idle 150W + (150W span / 2 slots) * 1 = 225W
        self.assertAlmostEqual(srv.get_instantaneous_power_watts(), 225.0)
        srv.release_slot()
        self.assertEqual(srv.state, ServerState.IDLE)
        self.assertEqual(srv.total_served_count, 1)
        self.assertAlmostEqual(srv.get_load_pct(), 0.0)

    def test_no_sleep_or_off_while_busy(self):
        env, srv = make_server()
        srv.reserve_slot()
        srv.sleep()
        self.assertEqual(srv.state, ServerState.ACTIVE)  # refused
        srv.power_off()
        self.assertEqual(srv.state, ServerState.ACTIVE)  # refused

    def test_sleep_wake_cycle(self):
        env, srv = make_server(wake=1.0)
        srv.sleep()
        self.assertEqual(srv.state, ServerState.SLEEPING)
        self.assertAlmostEqual(srv.get_instantaneous_power_watts(), 15.0)
        self.assertFalse(srv.can_accept_request())
        srv.wake()
        self.assertEqual(srv.state, ServerState.WAKING)
        self.assertLess(srv.get_boot_progress_pct(), 1.0)
        env.run(until=2.0)
        self.assertEqual(srv.state, ServerState.IDLE)

    def test_power_off_boot_cycle(self):
        env, srv = make_server(cold_boot=2.0)
        srv.power_off()
        self.assertEqual(srv.state, ServerState.OFF)
        self.assertAlmostEqual(srv.get_instantaneous_power_watts(), 2.0)
        srv.boot()
        self.assertEqual(srv.state, ServerState.BOOTING)
        env.run(until=3.0)
        self.assertEqual(srv.state, ServerState.IDLE)

    def test_energy_integration_idle_10s(self):
        env, srv = make_server()
        env.run(until=10.0)
        # 150W * 10s = 1500J = 1500/3.6M kWh
        self.assertAlmostEqual(srv.energy_joules_consumed, 0.0)  # lazy until read
        self.assertAlmostEqual(srv.total_energy_kwh, 1500.0 / 3_600_000.0, places=9)


if __name__ == "__main__":
    unittest.main()
