"""
Settings Modal & Simulation Run Setup Drawer.
Allows configuring run duration (in simulated minutes/hours),
discrete server pool size (NumberStepper), and hardware/cost parameters.
"""

from typing import Callable, Optional
import pygame
from src.config import SimConfig
from src.ui.widgets import Button, Slider, NumberStepper, DurationInputs, render_cached


class SettingsModal:
    def __init__(self, screen_size: tuple, config: SimConfig, fonts: dict,
                 on_server_count_change: Callable[[int], None],
                 on_start_run: Optional[Callable[[float], None]] = None):
        self.sw, self.sh = screen_size
        self.config = config
        self.fonts = fonts
        self.on_server_count_change = on_server_count_change
        self.on_start_run = on_start_run
        self.is_open = False

        self.run_duration_min = 60.0  # Default 60 simulated minutes

        self.mw, self.mh = 560, 580
        self.rect = pygame.Rect((self.sw - self.mw) // 2, (self.sh - self.mh) // 2, self.mw, self.mh)

        self.close_btn = Button(
            pygame.Rect(self.rect.right - 80, self.rect.y + 14, 66, 26),
            text="✕ Close",
            font=fonts["small"],
            callback=self.close,
            inactive_bg=(40, 40, 48),
            inactive_text=(220, 220, 230),
            border_color=(65, 65, 75)
        )

        sx = self.rect.x + 30
        sw = self.mw - 60
        y_cursor = self.rect.y + 60

        # ---------------------------------------------------------------------
        # 1. Target Run Duration (4 Numeric Input Boxes: months, days, hours, minutes)
        # ---------------------------------------------------------------------
        self.duration_inputs = DurationInputs(
            pygame.Rect(sx, y_cursor, sw, 100),
            fonts=fonts,
            initial_hours=1,
            initial_minutes=0,
            on_change=lambda m: setattr(self, "run_duration_min", m)
        )

        y_cursor += 105

        # ---------------------------------------------------------------------
        # 2. Server Pool Size (Discrete Integer Stepper 3 to 10)
        # ---------------------------------------------------------------------
        self.server_stepper = NumberStepper(
            pygame.Rect(sx, y_cursor, sw, 28),
            min_val=3, max_val=10, initial_val=config.num_servers,
            font=fonts["small"], label="Server Pool Size", unit=" Nodes",
            on_change=on_server_count_change
        )

        y_cursor += 42
        spacing = 44

        # ---------------------------------------------------------------------
        # 3. Hardware & Economic Tuning
        # ---------------------------------------------------------------------
        self.rate_slider = Slider(
            pygame.Rect(sx, y_cursor, sw, 18),
            min_val=4.0, max_val=20.0, initial_val=config.economics.cost_per_kwh_php,
            font=fonts["small"], label="Electricity Rate", unit=" PHP/kWh",
            on_change=lambda v: setattr(config.economics, "cost_per_kwh_php", v)
        )

        self.sla_slider = Slider(
            pygame.Rect(sx, y_cursor + spacing, sw, 18),
            min_val=0.1, max_val=5.0, initial_val=config.economics.cost_per_dropped_req_php,
            font=fonts["small"], label="SLA Penalty per Dropped Req", unit=" PHP",
            on_change=lambda v: setattr(config.economics, "cost_per_dropped_req_php", v)
        )

        self.boot_slider = Slider(
            pygame.Rect(sx, y_cursor + spacing * 2, sw, 18),
            min_val=30.0, max_val=300.0, initial_val=config.hardware.cold_boot_delay_sec,
            font=fonts["small"], label="Physical Cold Boot Delay", unit=" sec", integer_only=True,
            on_change=lambda v: setattr(config.hardware, "cold_boot_delay_sec", v)
        )

        self.wake_slider = Slider(
            pygame.Rect(sx, y_cursor + spacing * 3, sw, 18),
            min_val=1.0, max_val=15.0, initial_val=config.hardware.sleep_wake_delay_sec,
            font=fonts["small"], label="Sleep Wake Latency", unit=" sec",
            on_change=lambda v: setattr(config.hardware, "sleep_wake_delay_sec", v)
        )

        self.pue_slider = Slider(
            pygame.Rect(sx, y_cursor + spacing * 4, sw, 18),
            min_val=1.1, max_val=2.0, initial_val=config.hardware.cooling_pue,
            font=fonts["small"], label="Cooling PUE Multiplier", unit="x",
            on_change=lambda v: setattr(config.hardware, "cooling_pue", v)
        )

        self.sliders = [
            self.rate_slider,
            self.sla_slider,
            self.boot_slider,
            self.wake_slider,
            self.pue_slider,
        ]

        # ---------------------------------------------------------------------
        # 4. Big Action Button (Bottom)
        # ---------------------------------------------------------------------
        self.start_btn = Button(
            pygame.Rect(sx, self.rect.bottom - 48, sw, 36),
            text="▶ Start Simulation Run",
            font=fonts["normal_bold"],
            callback=self._start_run,
            inactive_bg=(40, 95, 60),
            inactive_text=(255, 255, 255),
            border_color=(76, 175, 80)
        )

    def _start_run(self):
        total_m = self.duration_inputs.get_total_minutes()
        # If blank/0, default to 60 minutes
        if total_m <= 0:
            total_m = 60.0
        self.run_duration_min = total_m
        if self.on_start_run:
            self.on_start_run(self.run_duration_min)
        self.close()

    def open(self):
        self.is_open = True

    def close(self):
        self.is_open = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.is_open:
            return False

        if self.close_btn.handle_event(event):
            return True
        if self.start_btn.handle_event(event):
            return True
        if self.duration_inputs.handle_event(event):
            return True
        if self.server_stepper.handle_event(event):
            return True

        for s in self.sliders:
            if s.handle_event(event):
                return True

        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                return True

        return False

    def draw(self, surface: pygame.Surface):
        if not self.is_open:
            return

        # Dimmer overlay
        overlay = pygame.Surface((self.sw, self.sh), pygame.SRCALPHA)
        overlay.fill((10, 10, 14, 190))
        surface.blit(overlay, (0, 0))

        # Modal dialog card
        pygame.draw.rect(surface, (28, 28, 34), self.rect, border_radius=8)
        pygame.draw.rect(surface, (55, 55, 68), self.rect, width=1, border_radius=8)

        # Header title
        title_surf = render_cached(self.fonts["header"], "⚙ Simulation Setup & Run Configuration", (240, 240, 245))
        surface.blit(title_surf, (self.rect.x + 24, self.rect.y + 16))

        self.close_btn.draw(surface)

        pygame.draw.line(surface, (45, 45, 55), (self.rect.x + 20, self.rect.y + 48),
                         (self.rect.right - 20, self.rect.y + 48), 1)

        # Draw Duration Inputs
        self.duration_inputs.draw(surface)

        # Draw Server Stepper
        self.server_stepper.draw(surface)

        # Draw Hardware Sliders
        for s in self.sliders:
            s.draw(surface)

        # Divider above start button
        pygame.draw.line(surface, (45, 45, 55), (self.rect.x + 20, self.rect.bottom - 60),
                         (self.rect.right - 20, self.rect.bottom - 60), 1)

        self.start_btn.draw(surface)
