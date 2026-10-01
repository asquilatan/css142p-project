"""
Main Entry Point — Data Center Server Provisioning Simulation.
Minimalist Dark Theme (#212121) with Google Sans typography,
draggable movable nodes, and flex-like docked 3-column control room.
"""

import os
import sys
import time
import pygame
from src.config import SimConfig
from src.engine_bridge import create_engine
from src.policies import AlwaysOnPolicy, ThresholdPolicy, ScheduledPolicy, SleepBufferPolicy
from src.ui.layout import Layout
from src.ui.assets_manager import AssetsManager
from src.ui.simulation_view import SimulationView
from src.ui.telemetry_view import TelemetryView
from src.ui.controls_view import ControlsView
from src.ui.graphs_view import GraphsView
from src.ui.settings_modal import SettingsModal
from src.ui.menu_bar import MenuBar


def init_fonts():
    pygame.font.init()

    # Load Google Sans directly from assets/fonts/ (clean sans typography)
    gs_regular = "assets/fonts/GoogleSans-Regular.ttf"
    gs_medium = "assets/fonts/GoogleSans-Medium.ttf"
    gs_bold = "assets/fonts/GoogleSans-Bold.ttf"

    def get_font(path, fallback_names, size, bold=False):
        if os.path.exists(path):
            try:
                return pygame.font.Font(path, size)
            except Exception:
                pass
        # Fallback to system fonts
        for n in fallback_names:
            try:
                f = pygame.font.SysFont(n, size, bold=bold)
                if f:
                    return f
            except Exception:
                continue
        return pygame.font.Font(None, size)

    fallbacks = ["helvetica", "arial", "dejavusans", None]
    mono_fallbacks = ["consolas", "couriernew", "dejavusansmono", None]

    return {
        "small": get_font(gs_regular, fallbacks, 13),
        "small_bold": get_font(gs_bold, fallbacks, 13, bold=True),
        "normal": get_font(gs_regular, fallbacks, 15),
        "normal_bold": get_font(gs_bold, fallbacks, 15, bold=True),
        "header": get_font(gs_bold, fallbacks, 18, bold=True),
        "header_large": get_font(gs_bold, fallbacks, 22, bold=True),
        "large_bold": get_font(gs_bold, fallbacks, 26, bold=True),
        "mono": get_font(gs_regular, mono_fallbacks, 13),
        "mono_bold": get_font(gs_bold, mono_fallbacks, 14, bold=True),
    }


def main():
    pygame.init()
    screen_width, screen_height = 1280, 720
    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption("Data Center Server Provisioning — Control Room")

    clock = pygame.time.Clock()
    fonts = init_fonts()

    # Core Configuration & Simulation Engine (Rust-accelerated when available)
    config = SimConfig(num_servers=5)
    sim = create_engine(config)
    pygame.display.set_caption(
        "Data Center Server Provisioning — Control Room"
        + ("  [RUST ACCELERATED]" if sim.is_rust_accelerated else "  [SIMPY FALLBACK]")
    )

    # Initial Provisioning Policy (Threshold-based)
    current_policy = ThresholdPolicy()
    sim.set_policy(current_policy)

    # UI Presentation Components
    layout = Layout(screen_width, screen_height)
    assets = AssetsManager(assets_dir="assets")

    simulation_view = SimulationView(layout, assets, fonts)
    graphs_view = GraphsView(
        fonts=fonts,
        assets=assets,
        on_close=lambda vis: telemetry_view.set_graphs_active(vis)
    )

    telemetry_view = TelemetryView(
        layout, fonts,
        on_toggle_graphs=lambda visible: graphs_view.set_visible(visible),
        assets=assets
    )

    # Control state variables
    sim_speed = 5.0
    is_paused = True
    is_running = False
    target_sim_stop_time: Optional[float] = None

    def on_play_pause(paused: bool):
        nonlocal is_paused
        is_paused = paused
        controls_view.set_run_state(is_running=is_running, is_paused=is_paused,
                                   is_completed=False, target_stop_time=target_sim_stop_time)

    def on_reset():
        nonlocal sim, current_policy, is_running, is_paused, target_sim_stop_time
        sim = create_engine(config)
        pygame.display.set_caption(
            "Data Center Server Provisioning — Control Room"
            + ("  [RUST ACCELERATED]" if sim.is_rust_accelerated else "  [SIMPY FALLBACK]")
        )
        policy_class = type(current_policy)
        current_policy = policy_class()
        sim.set_policy(current_policy)
        simulation_view.active_packets.clear()
        is_running = False
        is_paused = True
        target_sim_stop_time = None
        controls_view.set_run_state(is_running=False, is_paused=True,
                                   is_completed=False, target_stop_time=None)

    def on_start_run(duration_minutes: float):
        nonlocal is_running, is_paused, target_sim_stop_time
        is_running = True
        is_paused = False
        target_sim_stop_time = sim.env.now + duration_minutes * 60.0
        controls_view.set_run_state(is_running=True, is_paused=False,
                                   is_completed=False, target_stop_time=target_sim_stop_time)

    def on_speed_change(multiplier: float):
        nonlocal sim_speed
        sim_speed = multiplier

    def on_policy_change(index: int, name: str):
        nonlocal current_policy
        if name == "Always-On":
            current_policy = AlwaysOnPolicy()
        elif name == "Threshold":
            current_policy = ThresholdPolicy()
        elif name == "Scheduled":
            current_policy = ScheduledPolicy()
        elif name == "Sleep-Buffer":
            current_policy = SleepBufferPolicy()
        sim.set_policy(current_policy)

    def on_diurnal_toggle(state: bool):
        config.workload.diurnal_cycle_active = state

    def on_abrupt_drop():
        sim.workload.trigger_abrupt_drop()

    def on_flash_crowd():
        sim.workload.trigger_flash_crowd(sim.env.now, duration=300.0)

    def on_traffic_volume(scale: float):
        sim.workload.traffic_scale_factor = scale

    def on_server_count_change(new_count: int):
        sim.set_num_servers(new_count)

    settings_modal = SettingsModal(
        (screen_width, screen_height), config, fonts,
        on_server_count_change=on_server_count_change,
        on_start_run=on_start_run
    )

    controls_view = ControlsView(
        layout, fonts,
        on_play_pause=on_play_pause,
        on_reset=on_reset,
        on_speed_change=on_speed_change,
        on_policy_change=on_policy_change,
        on_diurnal_toggle=on_diurnal_toggle,
        on_abrupt_drop=on_abrupt_drop,
        on_flash_crowd=on_flash_crowd,
        on_traffic_volume=on_traffic_volume,
        on_start_request=settings_modal.open,
        assets=assets
    )

    # Top Menu Bar with flex visibility toggles & layout reset
    menu_bar = MenuBar(
        layout, fonts,
        on_toggle_racks=lambda v: layout.set_visibility(racks=v),
        on_toggle_telemetry=lambda v: layout.set_visibility(telemetry=v),
        on_toggle_controls=lambda v: layout.set_visibility(controls=v),
        on_reset_layout=simulation_view.reset_positions,
        on_open_settings=settings_modal.open,
        assets=assets
    )

    running = True
    last_frame_time = time.time()

    while running:
        current_real_time = time.time()
        dt = current_real_time - last_frame_time
        last_frame_time = current_real_time

        # Clamp dt to 100ms (prevents lag death spirals while maintaining accurate real-time simulation pace)
        dt = min(dt, 0.1)

        # ---------------------------------------------------------------------
        # 1. Event Handling
        # ---------------------------------------------------------------------
        for event in pygame.event.get():
            # Handle secondary telemetry window events first
            if graphs_view.handle_event(event):
                continue

            if event.type == pygame.QUIT:
                running = False
                break

            # Modal handles events first if open
            if settings_modal.is_open:
                if settings_modal.handle_event(event):
                    continue

            # Top menu bar handles events
            if menu_bar.handle_event(event):
                continue

            # Route events to subviews
            if controls_view.handle_event(event):
                continue
            if telemetry_view.handle_event(event):
                continue

            # Movable node drag-and-drop handling
            if simulation_view.handle_event(event, len(sim.servers)):
                continue

            # Keyboard shortcuts
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    controls_view._handle_main_button()
                elif event.key == pygame.K_f:
                    on_flash_crowd()
                elif event.key == pygame.K_r:
                    on_reset()
                elif event.key == pygame.K_g:
                    graphs_view.toggle_visible()
                elif event.key in (pygame.K_x, pygame.K_ESCAPE):
                    if graphs_view.is_visible:
                        graphs_view.set_visible(False)
                    elif settings_modal.is_open:
                        settings_modal.close()

        # ---------------------------------------------------------------------
        # 2. Discrete-Event Simulation Step (SimPy + Delta Time)
        # ---------------------------------------------------------------------
        if is_running and not is_paused:
            # 1 speed unit = 1 simulated minute (60 seconds) per real second
            sim_delta_seconds = dt * sim_speed * 60.0
            next_sim_time = sim.env.now + sim_delta_seconds

            if target_sim_stop_time is not None and next_sim_time >= target_sim_stop_time:
                # Simulation reached target duration!
                sim.step_simulation(target_sim_stop_time)
                is_running = False
                is_paused = True
                controls_view.set_run_state(is_running=False, is_paused=True,
                                           is_completed=True, target_stop_time=target_sim_stop_time)
            else:
                sim.step_simulation(next_sim_time)

        # ---------------------------------------------------------------------
        # 3. Seamless Docked 3-Column Rendering Pipeline
        # ---------------------------------------------------------------------
        # Fill base background (#212121)
        screen.fill(config.bg_color)

        # Draw center canvas simulation topology (hardware clipped to center column)
        simulation_view.update_and_draw(screen, sim, current_real_time, dt, is_paused)

        # Draw left sidebar (Data Center Racks & Real Time Telemetry)
        telemetry_view.draw(screen, sim)

        # Draw right sidebar (Controls HUD)
        controls_view.draw(screen, sim.env.now)

        # Draw top menu bar across the header
        menu_bar.draw(screen)

        # Draw modal settings overlay on top if open
        settings_modal.draw(screen)

        pygame.display.flip()

        # Update and render dedicated secondary graphs window if active
        graphs_view.update_and_draw(sim.metrics, sim.env.now, target_sim_stop_time)

        clock.tick(60)

    graphs_view.window.destroy()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
