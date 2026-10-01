#!/usr/bin/env python3
"""
Side-by-Side Benchmark CLI: Python (SimPy) vs. Rust (sim_core)

Compares simulation execution throughput, real-time performance, and metric parity
between the reference SimPy discrete-event engine and the compiled Rust accelerator.

Usage:
    python benchmark.py
    python benchmark.py --duration 1h
    python benchmark.py --duration 24h --policy all
    python benchmark.py --duration 1800 --policy sleep-buffer --csv results.csv
"""

import argparse
import ctypes
import os
import sys
import time
from typing import Dict, List, Optional, Tuple

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


def parse_duration(val: str) -> float:
    """Parses duration strings like '300', '300s', '10m', '1h', '24h'."""
    val = val.strip().lower()
    if val.endswith("h"):
        return float(val[:-1]) * 3600.0
    if val.endswith("m"):
        return float(val[:-1]) * 60.0
    if val.endswith("s"):
        return float(val[:-1])
    return float(val)


def get_policy_instances(policy_arg: str):
    mapping = {
        "always-on": [(AlwaysOnPolicy, "Always-On", 0)],
        "threshold": [(ThresholdPolicy, "Threshold-Based", 1)],
        "scheduled": [(ScheduledPolicy, "Scheduled", 2)],
        "sleep-buffer": [(SleepBufferPolicy, "Sleep-Buffer", 3)],
    }
    if policy_arg.lower() == "all":
        return [
            (AlwaysOnPolicy, "Always-On", 0),
            (ThresholdPolicy, "Threshold-Based", 1),
            (ScheduledPolicy, "Scheduled", 2),
            (SleepBufferPolicy, "Sleep-Buffer", 3),
        ]
    chosen = mapping.get(policy_arg.lower())
    if not chosen:
        print(f"Unknown policy '{policy_arg}'. Available: {list(mapping.keys())} or 'all'")
        sys.exit(1)
    return chosen


def run_benchmark(
    policy_cls,
    policy_name: str,
    policy_id: int,
    duration_sec: float,
    num_servers: int,
    lib: Optional[ctypes.CDLL],
) -> Dict[str, dict]:
    cfg = SimConfig(num_servers=num_servers)

    # 1. Pure Python (SimPy)
    py_sim = SimulationEngine(cfg)
    pol_py = policy_cls()
    py_sim.set_policy(pol_py)
    pol_py.on_init()

    t0 = time.perf_counter()
    py_sim.step_simulation(duration_sec)
    t_py = time.perf_counter() - t0

    # 2. Rust Engine (sim_core)
    rust_data = None
    t_rust = None
    if lib is not None:
        rust_sim = RustEngine(cfg, lib, policy_id=policy_id)
        t0 = time.perf_counter()
        rust_sim.step_simulation(duration_sec)
        t_rust = time.perf_counter() - t0

        m_r = rust_sim.metrics
        rust_data = {
            "elapsed_sec": t_rust,
            "arrived": m_r.total_requests_arrived,
            "served": m_r.total_requests_served,
            "dropped": m_r.total_requests_dropped,
            "drop_pct": (m_r.total_requests_dropped / max(1, m_r.total_requests_arrived)) * 100.0,
            "energy_kwh": m_r.facility_cumulative_energy_kwh,
            "cost_php": m_r.estimated_cost_php,
            "sim_speed": duration_sec / max(1e-9, t_rust),
            "events_per_sec": (m_r.total_requests_arrived + m_r.total_requests_served) / max(1e-9, t_rust),
            "final_queue": int(m_r.current_queue_depth),
        }

    m_p = py_sim.metrics
    py_data = {
        "elapsed_sec": t_py,
        "arrived": m_p.total_requests_arrived,
        "served": m_p.total_requests_served,
        "dropped": m_p.total_requests_dropped,
        "drop_pct": (m_p.total_requests_dropped / max(1, m_p.total_requests_arrived)) * 100.0,
        "energy_kwh": m_p.facility_cumulative_energy_kwh,
        "cost_php": m_p.estimated_cost_php,
        "sim_speed": duration_sec / max(1e-9, t_py),
        "events_per_sec": (m_p.total_requests_arrived + m_p.total_requests_served) / max(1e-9, t_py),
        "final_queue": len(py_sim.request_queue),
    }

    return {"Python": py_data, "Rust": rust_data, "policy_name": policy_name}


def format_table(results: List[Dict[str, dict]], duration_sec: float, num_servers: int):
    print("=" * 96)
    print(f" DATA CENTER SIMULATION: SIDE-BY-SIDE BENCHMARK (Python SimPy vs. Rust sim_core)")
    print(f" Simulated Duration: {duration_sec:.0f}s ({duration_sec / 3600.0:.2f} hours) | Node Count: {num_servers} servers")
    print("=" * 96)

    for item in results:
        p_name = item["policy_name"]
        py = item["Python"]
        ru = item["Rust"]

        print(f"\n>>> POLICY: {p_name.upper()}")
        print("-" * 96)
        print(f"{'Metric':<30} | {'Python (SimPy)':<22} | {'Rust (sim_core)':<22} | {'Parity / Ratio':<15}")
        print("-" * 96)

        # Real Execution Time
        t_py_str = f"{py['elapsed_sec']:.4f} s" if py['elapsed_sec'] >= 1.0 else f"{py['elapsed_sec'] * 1000.0:.2f} ms"
        if ru:
            t_ru_str = f"{ru['elapsed_sec']:.4f} s" if ru['elapsed_sec'] >= 1.0 else f"{ru['elapsed_sec'] * 1000.0:.2f} ms"
            speedup = py['elapsed_sec'] / max(1e-9, ru['elapsed_sec'])
            ratio_str = f"{speedup:.1f}x faster"
        else:
            t_ru_str = "N/A"
            ratio_str = "N/A"
        print(f"{'Real Execution Time (IRL)':<30} | {t_py_str:<22} | {t_ru_str:<22} | {ratio_str:<15}")

        # Sim Throughput
        sim_speed_py = f"{py['sim_speed']:,.1f} sim-s / IRL-s"
        sim_speed_ru = f"{ru['sim_speed']:,.1f} sim-s / IRL-s" if ru else "N/A"
        print(f"{'Simulation Throughput':<30} | {sim_speed_py:<22} | {sim_speed_ru:<22} |")

        # Event Throughput
        evt_py = f"{py['events_per_sec']:,.0f} req/s"
        evt_ru = f"{ru['events_per_sec']:,.0f} req/s" if ru else "N/A"
        print(f"{'Request Event Throughput':<30} | {evt_py:<22} | {evt_ru:<22} |")

        # Requests Arrived
        arr_py = f"{py['arrived']:,}"
        arr_ru = f"{ru['arrived']:,}" if ru else "N/A"
        arr_diff = f"{abs(py['arrived'] - ru['arrived']) / max(1, py['arrived']) * 100.0:.2f}% diff" if ru else ""
        print(f"{'Total Requests Arrived':<30} | {arr_py:<22} | {arr_ru:<22} | {arr_diff:<15}")

        # Requests Served
        srv_py = f"{py['served']:,}"
        srv_ru = f"{ru['served']:,}" if ru else "N/A"
        srv_diff = f"{abs(py['served'] - ru['served']) / max(1, py['served']) * 100.0:.2f}% diff" if ru else ""
        print(f"{'Total Requests Served':<30} | {srv_py:<22} | {srv_ru:<22} | {srv_diff:<15}")

        # Requests Dropped
        drp_py = f"{py['dropped']:,} ({py['drop_pct']:.2f}%)"
        drp_ru = f"{ru['dropped']:,} ({ru['drop_pct']:.2f}%)" if ru else "N/A"
        print(f"{'Total Requests Dropped':<30} | {drp_py:<22} | {drp_ru:<22} |")

        # Energy Consumed
        nrg_py = f"{py['energy_kwh']:.4f} kWh"
        nrg_ru = f"{ru['energy_kwh']:.4f} kWh" if ru else "N/A"
        print(f"{'Facility Energy Consumed':<30} | {nrg_py:<22} | {nrg_ru:<22} |")

        # Financial Cost
        cst_py = f"PHP {py['cost_php']:,.2f}"
        cst_ru = f"PHP {ru['cost_php']:,.2f}" if ru else "N/A"
        print(f"{'Total Estimated Cost':<30} | {cst_py:<22} | {cst_ru:<22} |")

        # Queue Depth
        q_py = f"{py['final_queue']} requests"
        q_ru = f"{ru['final_queue']} requests" if ru else "N/A"
        print(f"{'Terminal Queue Depth':<30} | {q_py:<22} | {q_ru:<22} |")


def export_csv(results: List[Dict[str, dict]], filepath: str, duration_sec: float):
    import csv

    rows = []
    fieldnames = [
        "policy",
        "backend",
        "duration_sec",
        "elapsed_irl_sec",
        "speedup_vs_py",
        "sim_sec_per_irl_sec",
        "events_per_sec",
        "requests_arrived",
        "requests_served",
        "requests_dropped",
        "drop_percent",
        "facility_energy_kwh",
        "estimated_cost_php",
        "final_queue",
    ]

    for item in results:
        pol = item["policy_name"]
        py = item["Python"]
        ru = item["Rust"]

        # Python row
        rows.append({
            "policy": pol,
            "backend": "Python_SimPy",
            "duration_sec": duration_sec,
            "elapsed_irl_sec": py["elapsed_sec"],
            "speedup_vs_py": 1.0,
            "sim_sec_per_irl_sec": py["sim_speed"],
            "events_per_sec": py["events_per_sec"],
            "requests_arrived": py["arrived"],
            "requests_served": py["served"],
            "requests_dropped": py["dropped"],
            "drop_percent": py["drop_pct"],
            "facility_energy_kwh": py["energy_kwh"],
            "estimated_cost_php": py["cost_php"],
            "final_queue": py["final_queue"],
        })

        if ru:
            speedup = py["elapsed_sec"] / max(1e-9, ru["elapsed_sec"])
            rows.append({
                "policy": pol,
                "backend": "Rust_sim_core",
                "duration_sec": duration_sec,
                "elapsed_irl_sec": ru["elapsed_sec"],
                "speedup_vs_py": speedup,
                "sim_sec_per_irl_sec": ru["sim_speed"],
                "events_per_sec": ru["events_per_sec"],
                "requests_arrived": ru["arrived"],
                "requests_served": ru["served"],
                "requests_dropped": ru["dropped"],
                "drop_percent": ru["drop_pct"],
                "facility_energy_kwh": ru["energy_kwh"],
                "estimated_cost_php": ru["cost_php"],
                "final_queue": ru["final_queue"],
            })

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n[OK] Benchmark results successfully exported to {filepath}")


def main():
    parser = argparse.ArgumentParser(
        description="Side-by-side benchmark test runner: Python (SimPy) vs. Rust (sim_core)"
    )
    parser.add_argument(
        "--duration",
        "-d",
        type=str,
        default="1h",
        help="Simulated time duration to run (e.g., 300s, 30m, 1h, 24h). Default: 1h",
    )
    parser.add_argument(
        "--policy",
        "-p",
        type=str,
        default="threshold",
        help="Policy to benchmark ('threshold', 'always-on', 'scheduled', 'sleep-buffer', or 'all'). Default: threshold",
    )
    parser.add_argument(
        "--servers",
        "-s",
        type=int,
        default=5,
        help="Server node count (3-10). Default: 5",
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="Optional path to output results to a CSV file.",
    )

    args = parser.parse_args()
    duration_sec = parse_duration(args.duration)
    policies = get_policy_instances(args.policy)

    lib = None
    if rust_available():
        path = _find_library()
        lib = ctypes.CDLL(path)
        _bind_library(lib)
    else:
        print("[WARN] Rust sim_core.dll not detected. Benchmarking Python only.")

    results = []
    for pol_cls, name, pid in policies:
        print(f"Benchmarking {name} ({duration_sec:.0f}s sim time)...", file=sys.stderr)
        res = run_benchmark(pol_cls, name, pid, duration_sec, args.servers, lib)
        results.append(res)

    format_table(results, duration_sec, args.servers)

    if args.csv:
        export_csv(results, args.csv, duration_sec)


if __name__ == "__main__":
    main()
