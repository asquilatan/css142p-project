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
from src.simulation import SimulationEngine
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

    # Core Configuration & Simulation Engine
    config = SimConfig(num_servers=5)
    sim = SimulationEngine(config)

    # Initial Provisioning Policy (Threshold-based)
    current_policy = ThresholdPolicy()
    sim.set_policy(current_policy)

    # UI Presentation Components
    layout = Layout(screen_width, screen_height)
    assets = AssetsManager(assets_dir="assets")

    simulation_view = SimulationView(layout, assets, fonts)
    graphs_view = GraphsView(layout, fonts)

    telemetry_view = TelemetryView(
        layout, fonts,
        on_toggle_graphs=lambda visible: graphs_view.set_visible(visible)
    )

    # Control state variables
    sim_speed = 5.0
    is_paused = False

    def on_play_pause(paused: bool):
        nonlocal is_paused
        is_paused = paused

    def on_reset():
        nonlocal sim, current_policy
        sim = SimulationEngine(config)
        policy_class = type(current_policy)
        current_policy = policy_class()
        sim.set_policy(current_policy)

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
        on_server_count_change=on_server_count_change
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
        on_open_settings=settings_modal.open
    )

    # Top Menu Bar with flex visibility toggles & layout reset
    menu_bar = MenuBar(
        layout, fonts,
        on_toggle_racks=lambda v: layout.set_visibility(racks=v),
        on_toggle_telemetry=lambda v: layout.set_visibility(telemetry=v),
        on_toggle_controls=lambda v: layout.set_visibility(controls=v),
        on_reset_layout=simulation_view.reset_positions,
        on_open_settings=settings_modal.open
    )

    running = True
    last_frame_time = time.time()

    while running:
        current_real_time = time.time()
        dt = current_real_time - last_frame_time
        last_frame_time = current_real_time

        dt = min(dt, 0.1)

        # ---------------------------------------------------------------------
        # 1. Event Handling
        # ---------------------------------------------------------------------
        for event in pygame.event.get():
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
                    controls_view._toggle_play_pause()
                elif event.key == pygame.K_f:
                    on_flash_crowd()
                elif event.key == pygame.K_r:
                    on_reset()
                elif event.key == pygame.K_g:
                    graphs_view.set_visible(not graphs_view.is_visible)

        # ---------------------------------------------------------------------
        # 2. Discrete-Event Simulation Step (SimPy + Delta Time)
        # ---------------------------------------------------------------------
        if not is_paused:
            sim_delta_seconds = dt * sim_speed
            target_sim_time = sim.env.now + sim_delta_seconds
            sim.step_simulation(target_sim_time)

        sim.clean_packet_animations(current_real_time)

        # ---------------------------------------------------------------------
        # 3. Seamless Docked 3-Column Rendering Pipeline
        # ---------------------------------------------------------------------
        # Fill base background (#212121)
        screen.fill(config.bg_color)

        # Draw center canvas simulation topology (hardware clipped to center column)
        simulation_view.update_and_draw(screen, sim, current_real_time)

        # Draw Picture-in-Picture live graphs if active
        graphs_view.draw(screen, sim.metrics)

        # Draw left sidebar (Data Center Racks & Real Time Telemetry)
        telemetry_view.draw(screen, sim)

        # Draw right sidebar (Controls HUD)
        controls_view.draw(screen, sim.env.now)

        # Draw top menu bar across the header
        menu_bar.draw(screen)

        # Draw modal settings overlay on top if open
        settings_modal.draw(screen)

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
