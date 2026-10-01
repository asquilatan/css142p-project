"""
Interactive Matplotlib Telemetry & Analytics Window.
Runs in an independent subprocess to provide full pan, zoom, grid,
and publication-grade vector export without blocking the simulation loop.
"""

import sys
import os
import json
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker


def format_duration(sec: float, pos=None) -> str:
    """Formats seconds into human-readable duration strings for axis ticks."""
    if sec < 0:
        return "0s"
    if sec < 60:
        return f"{sec:.0f}s"
    elif sec < 3600:
        m = int(sec // 60)
        s = int(sec % 60)
        return f"{m}m {s}s" if s > 0 else f"{m}m"
    elif sec < 86400:
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        return f"{h}h {m}m" if m > 0 else f"{h}h"
    else:
        d = int(sec // 86400)
        h = int((sec % 86400) // 3600)
        return f"{d}d {h}h" if h > 0 else f"{d}d"


def render_plot_from_file(json_path: str):
    """Loads snapshot data and displays an interactive dark-themed Matplotlib figure."""
    if not os.path.exists(json_path):
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    timestamps = data.get("timestamps", [])
    queue_depth = data.get("queue_depth", [])
    arrival_rate = data.get("arrival_rate", [])
    power_watts = data.get("power_watts", [])
    target_time = data.get("target_time", None)
    current_time = data.get("current_time", 0.0)
    stats = data.get("stats", {})

    if not timestamps:
        timestamps = [0.0]
        queue_depth = [0.0]
        arrival_rate = [0.0]
        power_watts = [0.0]

    # Dark Minimalist Theme Configuration
    plt.style.use("dark_background")
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(11, 7.5), sharex=True)
    fig.patch.set_facecolor("#18181A")

    title_str = (
        f"Data Center Telemetry Waveforms — Elapsed: {format_duration(current_time)} | "
        f"Served: {stats.get('served', 0):,} | Dropped: {stats.get('dropped', 0):,} | "
        f"Energy: {stats.get('energy_kwh', 0.0):.3f} kWh | Cost: ₱{stats.get('cost_php', 0.0):.2f}"
    )
    fig.suptitle(title_str, fontsize=12, fontweight="bold", color="#E6E6EB", y=0.98)

    # 1. Queue Depth
    ax1.set_facecolor("#212121")
    ax1.plot(timestamps, queue_depth, color="#F28B82", linewidth=1.5, label="Queue Depth (req)")
    ax1.set_ylabel("Queue Depth", fontsize=10, color="#E6E6EB")
    ax1.grid(True, color="#333338", linestyle="--", alpha=0.6)
    ax1.legend(loc="upper right", framealpha=0.4, fontsize=9)

    # 2. Arrival Demand Rate
    ax2.set_facecolor("#212121")
    ax2.plot(timestamps, arrival_rate, color="#81C995", linewidth=1.5, label="Arrival Rate (req/s)")
    ax2.set_ylabel("Demand (req/s)", fontsize=10, color="#E6E6EB")
    ax2.grid(True, color="#333338", linestyle="--", alpha=0.6)
    ax2.legend(loc="upper right", framealpha=0.4, fontsize=9)

    # 3. Facility Power Draw
    ax3.set_facecolor("#212121")
    ax3.plot(timestamps, power_watts, color="#8AB4F8", linewidth=1.5, label="Facility Power (W)")
    ax3.set_ylabel("Power (W)", fontsize=10, color="#E6E6EB")
    ax3.set_xlabel("Simulation Timeline", fontsize=10, color="#E6E6EB")
    ax3.grid(True, color="#333338", linestyle="--", alpha=0.6)
    ax3.legend(loc="upper right", framealpha=0.4, fontsize=9)

    # Formatter for time axis
    ax3.xaxis.set_major_formatter(ticker.FuncFormatter(format_duration))

    # X-Axis Bounds: Target End of Simulation if configured
    x_max = target_time if (target_time and target_time > 0) else max(timestamps[-1], 60.0)
    ax3.set_xlim(0, x_max)

    # Mark Current Time Progress Line
    for ax in (ax1, ax2, ax3):
        ax.axvline(x=current_time, color="#FDD663", linestyle=":", linewidth=1.2, alpha=0.8)
        for spine in ax.spines.values():
            spine.set_color("#3A3A42")

    plt.tight_layout(rect=[0, 0.02, 1, 0.96])
    plt.show()

    # Clean up temp file when closed
    try:
        if os.path.exists(json_path):
            os.remove(json_path)
    except Exception:
        pass


def launch_matplotlib_window(metrics, current_time: float, target_time=None):
    """Exports snapshot data and launches interactive Matplotlib subprocess."""
    import subprocess
    import tempfile

    stats = {
        "served": metrics.total_requests_served,
        "dropped": metrics.total_requests_dropped,
        "energy_kwh": metrics.facility_cumulative_energy_kwh,
        "cost_php": metrics.estimated_cost_php
    }

    payload = {
        "timestamps": list(metrics.history_timestamps),
        "queue_depth": list(metrics.history_queue_depth),
        "arrival_rate": list(metrics.history_arrival_rate),
        "power_watts": list(metrics.history_power_watts),
        "target_time": target_time,
        "current_time": current_time,
        "stats": stats
    }

    fd, path = tempfile.mkstemp(prefix="telemetry_snapshot_", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(payload, f)

    subprocess.Popen([sys.executable, "-m", "src.ui.matplotlib_view", path])


if __name__ == "__main__":
    if len(sys.argv) > 1:
        render_plot_from_file(sys.argv[1])
