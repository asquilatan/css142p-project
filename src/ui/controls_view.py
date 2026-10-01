"""
Controls View (Right Sidebar HUD).
Implements the control panel with Play/Pause, Reset, Speed slider (1-50 min/sec),
Policy radio group, Workload triggers, Traffic slider, and 24-hour clock display in minimalist dark aesthetic.
"""

from typing import Callable, Optional
import pygame
from src.ui.layout import Layout
from src.ui.widgets import Button, ButtonGroup, ToggleSwitch, Slider


class ControlsView:
    def __init__(self, layout: Layout, fonts: dict,
                 on_play_pause: Callable,
                 on_reset: Callable,
                 on_speed_change: Callable,
                 on_policy_change: Callable,
                 on_diurnal_toggle: Callable,
                 on_abrupt_drop: Callable,
                 on_flash_crowd: Callable,
                 on_traffic_volume: Callable):
        self.layout = layout
        self.fonts = fonts
        self.is_paused = False

        panel = self.layout.right_panel_rect
        px = panel.x + 16
        pw = panel.width - 32

        # 1. Reset button (top right header)
        self.reset_btn = Button(
            pygame.Rect(panel.right - 64, panel.y + 12, 50, 24),
            text="Reset",
            font=fonts["small"],
            callback=on_reset,
            inactive_bg=(36, 36, 42),
            inactive_text=(180, 185, 195),
            border_color=(55, 55, 65)
        )

        # 2. Large Play/Pause button
        self.play_pause_btn = Button(
            pygame.Rect(px, panel.y + 44, pw, 44),
            text="|| Pause",
            font=fonts["header_large"],
            callback=self._toggle_play_pause,
            inactive_bg=(44, 44, 52),
            inactive_text=(240, 240, 245),
            border_color=(65, 65, 75)
        )
        self.on_play_pause = on_play_pause

        # 3. Speed slider (1 to 50 simulated minutes per real second)
        self.speed_slider = Slider(
            pygame.Rect(px, panel.y + 124, pw, 20),
            min_val=1.0,
            max_val=50.0,
            initial_val=1.0,
            font=fonts["small"],
            label="Speed",
            unit=" min/s",
            integer_only=True,
            on_change=on_speed_change
        )
        self.on_speed_change = on_speed_change

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

        self.abrupt_drop_btn = Button(
            pygame.Rect(panel.right - 70, panel.y + 320, 54, 24),
            text="[ btn ]",
            font=fonts["small"],
            callback=on_abrupt_drop
        )

        self.flash_crowd_btn = Button(
            pygame.Rect(panel.right - 70, panel.y + 356, 54, 24),
            text="[ btn ]",
            font=fonts["small"],
            callback=on_flash_crowd,
            inactive_bg=(48, 40, 42),
            inactive_text=(242, 139, 130),
            border_color=(120, 50, 50)
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

    def _toggle_play_pause(self):
        self.is_paused = not self.is_paused
        self.play_pause_btn.text = "> Resume" if self.is_paused else "|| Pause"
        self.on_play_pause(self.is_paused)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.layout.show_controls:
            return False

        if self.reset_btn.handle_event(event):
            return True
        if self.play_pause_btn.handle_event(event):
            return True
        if self.speed_slider.handle_event(event):
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
        hud_title = self.fonts["header"].render("Controls HUD", True, (230, 230, 235))
        surface.blit(hud_title, (panel.x + 16, panel.y + 12))
        self.reset_btn.draw(surface)

        self.play_pause_btn.draw(surface)

        # Speed Slider
        self.speed_slider.draw(surface)

        # Policy Section Header
        policy_lbl = self.fonts["normal"].render("Policy:", True, (160, 165, 175))
        surface.blit(policy_lbl, (panel.x + 16, panel.y + 168))
        self.policy_group.draw(surface)

        self.diurnal_switch.draw(surface)

        drop_lbl = self.fonts["normal"].render("Abrupt Traffic Drop", True, (210, 215, 225))
        surface.blit(drop_lbl, (panel.x + 16, panel.y + 322))
        self.abrupt_drop_btn.draw(surface)

        flash_lbl = self.fonts["normal"].render("Flash Crowd", True, (210, 215, 225))
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

        time_surf = self.fonts["large_bold"].render(time_str, True, (245, 245, 250))
        phase_surf = self.fonts["normal"].render(phase_str, True, phase_color)

        surface.blit(time_surf, (panel.x + 16, clock_box_y + 10))
        surface.blit(phase_surf, (panel.right - phase_surf.get_width() - 16, clock_box_y + 16))

        elapsed_hours = sim_time_seconds / 3600.0
        status_suffix = " (PAUSED)" if self.is_paused else ""
        elapsed_str = f"t = {elapsed_hours:.1f} hours{status_suffix}"
        elapsed_surf = self.fonts["small"].render(elapsed_str, True, (130, 135, 145))
        surface.blit(elapsed_surf, (panel.x + 16, clock_box_y + 44))
