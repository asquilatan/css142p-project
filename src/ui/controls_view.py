"""
Controls View (Right Sidebar HUD).
Implements the control panel with Play/Pause, Reset, Speed slider (1-50 min/sec),
Policy radio group, Workload triggers, Traffic slider, and 24-hour clock display in minimalist dark aesthetic.
"""

from typing import Callable, Optional
import pygame
from src.ui.layout import Layout
from src.ui.widgets import Button, ButtonGroup, ToggleSwitch, Slider, NumberField, render_cached
from src.ui.assets_manager import AssetsManager


class ControlsView:
    def __init__(self, layout: Layout, fonts: dict,
                 on_play_pause: Callable,
                 on_reset: Callable,
                 on_speed_change: Callable,
                 on_policy_change: Callable,
                 on_diurnal_toggle: Callable,
                 on_abrupt_drop: Callable,
                 on_flash_crowd: Callable,
                 on_traffic_volume: Callable,
                 on_start_request: Optional[Callable] = None,
                 assets: Optional[AssetsManager] = None,
                 max_speed: float = 50.0):
        self.layout = layout
        self.fonts = fonts
        self.assets = assets
        self.max_speed = max(1.0, float(max_speed))
        self.is_running = False
        self.is_paused = True
        self.is_completed = False
        self.target_stop_time: Optional[float] = None
        self.on_start_request = on_start_request
        self.on_play_pause = on_play_pause

        panel = self.layout.right_panel_rect
        px = panel.x + 16
        pw = panel.width - 32

        # 1. Reset button with prescribed icon
        reset_icon = assets.get_icon("icon_reset") if assets else None
        self.reset_btn = Button(
            pygame.Rect(panel.right - 80, panel.y + 12, 66, 24),
            text="Reset",
            font=fonts["small"],
            callback=on_reset,
            inactive_bg=(36, 36, 42),
            inactive_text=(180, 185, 195),
            border_color=(55, 55, 65),
            icon=reset_icon
        )

        # 2. Large Main Start / Pause button with prescribed icon
        play_icon = assets.get_icon("icon_play") if assets else None
        self.play_pause_btn = Button(
            pygame.Rect(px, panel.y + 44, pw, 44),
            text="Start Simulation",
            font=fonts["header_large"],
            callback=self._handle_main_button,
            inactive_bg=(40, 95, 60),
            inactive_text=(255, 255, 255),
            border_color=(76, 175, 80),
            icon=play_icon
        )

        # 3. Speed slider (1 to max_speed simulated minutes per real second;
        # max_speed is 500 on the Rust backend, 50 on the SimPy fallback)
        self.speed_slider = Slider(
            pygame.Rect(px, panel.y + 124, pw, 20),
            min_val=1.0,
            max_val=self.max_speed,
            initial_val=min(1.0, self.max_speed),
            font=fonts["small"],
            label="Speed",
            unit=" min/s",
            integer_only=True,
            on_change=self._on_slider_speed
        )
        self.on_speed_change = on_speed_change

        # 3b. Exact speed entry (two-way synced with the slider, same cap)
        self.speed_field = NumberField(
            pygame.Rect(px, panel.y + 146, pw, 22),
            font=fonts["small"],
            initial_value=1,
            min_val=1,
            max_val=int(self.max_speed),
            on_change=self._on_field_speed
        )

        # 4. Policy selector: [ Always-On | Threshold | Scheduled | Sleep-Buffer ]
        policy_labels = ["Always-On", "Threshold", "Scheduled", "Sleep-Buffer"]
        policy_btns = []
        py_start = panel.y + 192
        for i, p_lbl in enumerate(policy_labels):
            col = i % 2
            row = i // 2
            pbw = (pw - 8) // 2
            pbx = px + col * (pbw + 8)
            pby = py_start + row * 32
            policy_btns.append(Button(
                pygame.Rect(pbx, pby, pbw, 28),
                text=p_lbl,
                font=fonts["small"]
            ))
        self.policy_group = ButtonGroup(policy_btns, initial_index=1, on_change=on_policy_change)

        # 5. Workload triggers
        self.diurnal_switch = ToggleSwitch(
            pygame.Rect(px, panel.y + 280, pw, 26),
            label="Diurnal Auto-Cycle",
            font=fonts["normal"],
            initial_state=True,
            on_toggle=on_diurnal_toggle
        )

        drop_icon = assets.get_icon("icon_drop") if assets else None
        self.abrupt_drop_btn = Button(
            pygame.Rect(panel.right - 80, panel.y + 320, 64, 24),
            text="Drop",
            font=fonts["small"],
            callback=on_abrupt_drop,
            inactive_bg=(48, 40, 42),
            inactive_text=(242, 139, 130),
            border_color=(100, 50, 50),
            icon=drop_icon
        )

        surge_icon = assets.get_icon("icon_surge") if assets else None
        self.flash_crowd_btn = Button(
            pygame.Rect(panel.right - 80, panel.y + 356, 64, 24),
            text="Surge",
            font=fonts["small"],
            callback=on_flash_crowd,
            inactive_bg=(52, 44, 34),
            inactive_text=(253, 214, 99),
            border_color=(120, 90, 40),
            icon=surge_icon
        )

        # 6. Traffic volume slider
        self.traffic_slider = Slider(
            pygame.Rect(px, panel.y + 422, pw, 20),
            min_val=0.2,
            max_val=3.0,
            initial_val=1.0,
            font=fonts["small"],
            label="Traffic volume",
            unit="x",
            integer_only=False,
            on_change=on_traffic_volume
        )

    def _on_slider_speed(self, value: float):
        clamped = max(1.0, min(self.max_speed, float(value)))
        self.speed_field.set_value(clamped)
        if self.on_speed_change:
            self.on_speed_change(clamped)

    def _on_field_speed(self, value: float):
        clamped = max(1.0, min(self.max_speed, float(value)))
        self.speed_slider.value = clamped
        if self.on_speed_change:
            self.on_speed_change(clamped)

    def _handle_main_button(self):
        if not self.is_running or self.is_completed:
            if self.on_start_request:
                self.on_start_request()
        else:
            self.is_paused = not self.is_paused
            self.update_button_visuals()
            self.on_play_pause(self.is_paused)

    def set_run_state(self, is_running: bool, is_paused: bool, is_completed: bool = False,
                      target_stop_time: Optional[float] = None):
        self.is_running = is_running
        self.is_paused = is_paused
        self.is_completed = is_completed
        self.target_stop_time = target_stop_time
        self.update_button_visuals()

    def update_button_visuals(self):
        if not self.is_running or self.is_completed:
            self.play_pause_btn.text = "Start Simulation" if not self.is_completed else "Start New Run"
            self.play_pause_btn.icon = self.assets.get_icon("icon_play") if self.assets else None
            self.play_pause_btn.inactive_bg = (40, 95, 60)
            self.play_pause_btn.inactive_text = (255, 255, 255)
            self.play_pause_btn.border_color = (76, 175, 80)
        elif self.is_paused:
            self.play_pause_btn.text = "Resume"
            self.play_pause_btn.icon = self.assets.get_icon("icon_play") if self.assets else None
            self.play_pause_btn.inactive_bg = (48, 48, 56)
            self.play_pause_btn.inactive_text = (240, 240, 245)
            self.play_pause_btn.border_color = (75, 75, 88)
        else:
            self.play_pause_btn.text = "Pause"
            self.play_pause_btn.icon = self.assets.get_icon("icon_pause") if self.assets else None
            self.play_pause_btn.inactive_bg = (44, 44, 52)
            self.play_pause_btn.inactive_text = (240, 240, 245)
            self.play_pause_btn.border_color = (65, 65, 75)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.layout.show_controls:
            return False

        if self.reset_btn.handle_event(event):
            return True
        if self.play_pause_btn.handle_event(event):
            return True
        if self.speed_slider.handle_event(event):
            return True
        if self.speed_field.handle_event(event):
            return True
        if self.policy_group.handle_event(event):
            return True
        if self.diurnal_switch.handle_event(event):
            return True
        if self.abrupt_drop_btn.handle_event(event):
            return True
        if self.flash_crowd_btn.handle_event(event):
            return True
        if self.traffic_slider.handle_event(event):
            return True
        return False

    def draw(self, surface: pygame.Surface, sim_time_seconds: float):
        if not self.layout.show_controls:
            return

        panel = self.layout.right_panel_rect
        border_col = (48, 48, 54)
        panel_bg = (24, 24, 26)

        pygame.draw.rect(surface, panel_bg, panel)
        # 1px border divider on left
        pygame.draw.line(surface, border_col, (panel.x, panel.y), (panel.x, panel.bottom), 1)

        # Header: Controls HUD & Reset
        hud_title = render_cached(self.fonts["header"], "Controls HUD", (230, 230, 235))
        surface.blit(hud_title, (panel.x + 16, panel.y + 12))
        self.reset_btn.draw(surface)

        self.play_pause_btn.draw(surface)

        # Speed Slider + exact entry
        self.speed_slider.draw(surface)
        self.speed_field.draw(surface)

        # Policy Section Header
        policy_lbl = render_cached(self.fonts["normal"], "Policy:", (160, 165, 175))
        surface.blit(policy_lbl, (panel.x + 16, panel.y + 168))
        self.policy_group.draw(surface)

        self.diurnal_switch.draw(surface)

        drop_lbl = render_cached(self.fonts["normal"], "Abrupt Traffic Drop", (210, 215, 225))
        surface.blit(drop_lbl, (panel.x + 16, panel.y + 322))
        self.abrupt_drop_btn.draw(surface)

        flash_lbl = render_cached(self.fonts["normal"], "Flash Crowd", (210, 215, 225))
        surface.blit(flash_lbl, (panel.x + 16, panel.y + 358))
        self.flash_crowd_btn.draw(surface)

        self.traffic_slider.draw(surface)

        self._draw_clock(surface, sim_time_seconds)

    def _draw_clock(self, surface: pygame.Surface, sim_time_seconds: float):
        panel = self.layout.right_panel_rect
        border_col = (48, 48, 54)

        clock_box_y = panel.bottom - 74
        pygame.draw.line(surface, border_col, (panel.x, clock_box_y), (panel.right, clock_box_y), 1)

        day_secs = sim_time_seconds % 86400.0
        hours = int(day_secs // 3600)
        minutes = int((day_secs % 3600) // 60)
        am_pm = "PM" if hours >= 12 else "AM"
        display_hour = hours % 12
        if display_hour == 0:
            display_hour = 12

        time_str = f"{display_hour}:{minutes:02d} {am_pm}"
        is_peak = (9 <= hours <= 18)
        phase_str = "(PEAK)" if is_peak else "(OFF-PEAK)"
        phase_color = (253, 214, 99) if is_peak else (150, 155, 165)

        time_surf = render_cached(self.fonts["large_bold"], time_str, (245, 245, 250))
        phase_surf = render_cached(self.fonts["normal"], phase_str, phase_color)

        surface.blit(time_surf, (panel.x + 16, clock_box_y + 10))
        surface.blit(phase_surf, (panel.right - phase_surf.get_width() - 16, clock_box_y + 16))

        elapsed_hours = sim_time_seconds / 3600.0
        if self.is_completed:
            status_suffix = " (COMPLETED)"
        elif not self.is_running:
            status_suffix = " (READY)"
        elif self.is_paused:
            status_suffix = " (PAUSED)"
        else:
            status_suffix = " (RUNNING)"

        if self.target_stop_time is not None:
            target_hours = self.target_stop_time / 3600.0
            elapsed_str = f"t = {elapsed_hours:.2f}h / {target_hours:.2f}h{status_suffix}"
        else:
            elapsed_str = f"t = {elapsed_hours:.1f} hours{status_suffix}"
        elapsed_surf = render_cached(self.fonts["small"], elapsed_str, (130, 135, 145))
        surface.blit(elapsed_surf, (panel.x + 16, clock_box_y + 44))
