"""
Controls View (Right Sidebar HUD).
Implements the control panel with Play/Pause, Reset, Speed selector,
Policy radio group, Workload triggers, Traffic slider, and 24-hour clock display matching the sketch.
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
                 on_traffic_volume: Callable,
                 on_open_settings: Callable):
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
            callback=on_reset
        )

        # 2. Large Play/Pause button
        self.play_pause_btn = Button(
            pygame.Rect(px, panel.y + 44, pw, 46),
            text="|| Pause",
            font=fonts["header_large"],
            callback=self._toggle_play_pause,
            active_bg=(245, 245, 248),
            active_text=(30, 30, 35)
        )
        self.on_play_pause = on_play_pause

        # 3. Speed selector: [ 1x | 5x | 20x | 50x ]
        speed_labels = ["1x", "5x", "20x", "50x"]
        speed_btns = []
        bw = (pw - 12) // 4
        sy = panel.y + 126
        for i, s_lbl in enumerate(speed_labels):
            bx = px + i * (bw + 4)
            speed_btns.append(Button(
                pygame.Rect(bx, sy, bw, 26),
                text=s_lbl,
                font=fonts["small"]
            ))
        self.speed_group = ButtonGroup(speed_btns, initial_index=1, on_change=self._handle_speed_change)
        self.on_speed_change = on_speed_change

        # 4. Policy selector: [ Always-On | Threshold | Scheduled | Sleep-Buffer ]
        policy_labels = ["Always-On", "Threshold", "Scheduled", "Sleep-Buffer"]
        policy_btns = []
        py_start = panel.y + 188
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
        # Diurnal Auto-Cycle flip switch
        self.diurnal_switch = ToggleSwitch(
            pygame.Rect(px, panel.y + 280, pw, 26),
            label="Diurnal Auto-Cycle",
            font=fonts["normal"],
            initial_state=True,
            on_toggle=on_diurnal_toggle
        )

        # Abrupt Traffic Drop button
        self.abrupt_drop_btn = Button(
            pygame.Rect(panel.right - 70, panel.y + 316, 54, 24),
            text="[ btn ]",
            font=fonts["small"],
            callback=on_abrupt_drop
        )

        # Flash Crowd surge button
        self.flash_crowd_btn = Button(
            pygame.Rect(panel.right - 70, panel.y + 348, 54, 24),
            text="[ btn ]",
            font=fonts["small"],
            callback=on_flash_crowd,
            active_bg=(231, 76, 60),
            active_text=(255, 255, 255)
        )

        # 6. Traffic volume slider
        self.traffic_slider = Slider(
            pygame.Rect(px, panel.y + 412, pw, 22),
            min_val=0.2,
            max_val=3.0,
            initial_val=1.0,
            font=fonts["small"],
            label="Traffic volume",
            on_change=on_traffic_volume
        )

        # 7. [ ⚙ Settings ] button
        self.settings_btn = Button(
            pygame.Rect(px, panel.y + 460, pw, 28),
            text="⚙ Hardware & Cost Settings",
            font=fonts["normal"],
            callback=on_open_settings
        )

    def _toggle_play_pause(self):
        self.is_paused = not self.is_paused
        self.play_pause_btn.text = "> Resume" if self.is_paused else "|| Pause"
        self.on_play_pause(self.is_paused)

    def _handle_speed_change(self, index: int, text: str):
        speed_map = {"1x": 1.0, "5x": 5.0, "20x": 20.0, "50x": 50.0}
        mult = speed_map.get(text, 5.0)
        self.on_speed_change(mult)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.layout.show_controls:
            return False

        if self.reset_btn.handle_event(event):
            return True
        if self.play_pause_btn.handle_event(event):
            return True
        if self.speed_group.handle_event(event):
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
        if self.settings_btn.handle_event(event):
            return True
        return False

    def draw(self, surface: pygame.Surface, sim_time_seconds: float):
        if not self.layout.show_controls:
            return

        panel = self.layout.right_panel_rect
        border_col = (25, 25, 30)

        pygame.draw.rect(surface, (255, 255, 255), panel)
        pygame.draw.rect(surface, border_col, panel, width=2)

        # Header: Controls HUD & Reset
        hud_title = self.fonts["header"].render("Controls HUD", True, border_col)
        surface.blit(hud_title, (panel.x + 16, panel.y + 12))
        self.reset_btn.draw(surface)

        # Big Play/Pause
        self.play_pause_btn.draw(surface)

        # Speed Section Header
        speed_lbl = self.fonts["normal"].render("Speed:", True, (50, 55, 65))
        surface.blit(speed_lbl, (panel.x + 16, panel.y + 104))
        self.speed_group.draw(surface)

        # Policy Section Header
        policy_lbl = self.fonts["normal"].render("Policy:", True, (50, 55, 65))
        surface.blit(policy_lbl, (panel.x + 16, panel.y + 164))
        self.policy_group.draw(surface)

        # Workload Triggers
        self.diurnal_switch.draw(surface)

        drop_lbl = self.fonts["normal"].render("Abrupt Traffic Drop", True, (40, 45, 55))
        surface.blit(drop_lbl, (panel.x + 16, panel.y + 318))
        self.abrupt_drop_btn.draw(surface)

        flash_lbl = self.fonts["normal"].render("Flash Crowd", True, (40, 45, 55))
        surface.blit(flash_lbl, (panel.x + 16, panel.y + 350))
        self.flash_crowd_btn.draw(surface)

        # Traffic Volume Slider
        self.traffic_slider.draw(surface)

        # Settings Button
        self.settings_btn.draw(surface)

        # Bottom Clock & Elapsed Time
        self._draw_clock(surface, sim_time_seconds)

    def _draw_clock(self, surface: pygame.Surface, sim_time_seconds: float):
        panel = self.layout.right_panel_rect
        border_col = (25, 25, 30)

        # Dividing line above clock
        clock_box_y = panel.bottom - 74
        pygame.draw.line(surface, border_col, (panel.x, clock_box_y), (panel.right, clock_box_y), 2)

        # Calculate time of day (0:00 to 24:00)
        day_secs = sim_time_seconds % 86400.0
        hours = int(day_secs // 3600)
        minutes = int((day_secs % 3600) // 60)
        am_pm = "PM" if hours >= 12 else "AM"
        display_hour = hours % 12
        if display_hour == 0:
            display_hour = 12

        time_str = f"{display_hour}:{minutes:02d} {am_pm}"
        phase_str = "(PEAK)" if 9 <= hours <= 18 else "(OFF-PEAK)"

        time_surf = self.fonts["large_bold"].render(time_str, True, border_col)
        phase_surf = self.fonts["normal"].render(phase_str, True, (80, 85, 95))

        surface.blit(time_surf, (panel.x + 16, clock_box_y + 10))
        surface.blit(phase_surf, (panel.right - phase_surf.get_width() - 16, clock_box_y + 16))

        # Elapsed hours and pause state
        elapsed_hours = sim_time_seconds / 3600.0
        status_suffix = " (PAUSED)" if self.is_paused else ""
        elapsed_str = f"t = {elapsed_hours:.1f} hours{status_suffix}"
        elapsed_surf = self.fonts["small"].render(elapsed_str, True, (100, 105, 115))
        surface.blit(elapsed_surf, (panel.x + 16, clock_box_y + 44))
