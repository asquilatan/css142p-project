"""
Settings Modal & Runtime Hardware/Cost Tuning Drawer.
Allows live interactive adjustment of server pool size (3-10),
power parameters, transition latencies, and economic costs.
"""

from typing import Callable, Optional
import pygame
from src.config import SimConfig
from src.ui.widgets import Button, Slider


class SettingsModal:
    def __init__(self, screen_size: tuple, config: SimConfig, fonts: dict, on_server_count_change: Callable):
        self.sw, self.sh = screen_size
        self.config = config
        self.fonts = fonts
        self.on_server_count_change = on_server_count_change
        self.is_open = False

        # Modal window dimensions
        self.mw, self.mh = 540, 480
        self.rect = pygame.Rect((self.sw - self.mw) // 2, (self.sh - self.mh) // 2, self.mw, self.mh)

        # Close button
        self.close_btn = Button(
            pygame.Rect(self.rect.right - 80, self.rect.y + 14, 66, 26),
            text="Close",
            font=fonts["small"],
            callback=self.close
        )

        # Parameter Sliders
        sx = self.rect.x + 30
        sw = self.mw - 60
        y_start = self.rect.y + 70
        spacing = 54

        # 1. Server Pool Size (3 to 10)
        self.server_slider = Slider(
            pygame.Rect(sx, y_start, sw, 20),
            min_val=3.0, max_val=10.0, initial_val=float(config.num_servers),
            font=fonts["small"], label="Server Pool Size (Nodes)",
            on_change=lambda v: on_server_count_change(int(round(v)))
        )

        # 2. Electricity Rate (PHP / kWh)
        self.rate_slider = Slider(
            pygame.Rect(sx, y_start + spacing, sw, 20),
            min_val=4.0, max_val=20.0, initial_val=config.economics.cost_per_kwh_php,
            font=fonts["small"], label="Electricity Rate (PHP / kWh)",
            on_change=lambda v: setattr(config.economics, "cost_per_kwh_php", v)
        )

        # 3. SLA Drop Penalty (PHP / drop)
        self.sla_slider = Slider(
            pygame.Rect(sx, y_start + spacing * 2, sw, 20),
            min_val=0.1, max_val=5.0, initial_val=config.economics.cost_per_dropped_req_php,
            font=fonts["small"], label="SLA Penalty per Dropped Request (PHP)",
            on_change=lambda v: setattr(config.economics, "cost_per_dropped_req_php", v)
        )

        # 4. Cold Boot Delay (seconds)
        self.boot_slider = Slider(
            pygame.Rect(sx, y_start + spacing * 3, sw, 20),
            min_val=30.0, max_val=300.0, initial_val=config.hardware.cold_boot_delay_sec,
            font=fonts["small"], label="Physical Cold Boot Delay (sec)",
            on_change=lambda v: setattr(config.hardware, "cold_boot_delay_sec", v)
        )

        # 5. Sleep Wake Delay (seconds)
        self.wake_slider = Slider(
            pygame.Rect(sx, y_start + spacing * 4, sw, 20),
            min_val=1.0, max_val=15.0, initial_val=config.hardware.sleep_wake_delay_sec,
            font=fonts["small"], label="Sleep Wake Latency (sec)",
            on_change=lambda v: setattr(config.hardware, "sleep_wake_delay_sec", v)
        )

        # 6. Cooling PUE Multiplier (1.1 to 2.0)
        self.pue_slider = Slider(
            pygame.Rect(sx, y_start + spacing * 5, sw, 20),
            min_val=1.1, max_val=2.0, initial_val=config.hardware.cooling_pue,
            font=fonts["small"], label="Cooling PUE Multiplier",
            on_change=lambda v: setattr(config.hardware, "cooling_pue", v)
        )

        self.sliders = [
            self.server_slider,
            self.rate_slider,
            self.sla_slider,
            self.boot_slider,
            self.wake_slider,
            self.pue_slider,
        ]

    def open(self):
        self.is_open = True

    def close(self):
        self.is_open = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.is_open:
            return False

        if self.close_btn.handle_event(event):
            return True

        for s in self.sliders:
            if s.handle_event(event):
                return True

        # Consume clicks inside modal to prevent clicking through to canvas
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                return True

        return False

    def draw(self, surface: pygame.Surface):
        if not self.is_open:
            return

        # Dimmer overlay over entire window
        overlay = pygame.Surface((self.sw, self.sh), pygame.SRCALPHA)
        overlay.fill((10, 15, 20, 130))
        surface.blit(overlay, (0, 0))

        # Modal dialog box
        pygame.draw.rect(surface, (255, 255, 255), self.rect, border_radius=8)
        pygame.draw.rect(surface, (25, 25, 30), self.rect, width=2, border_radius=8)

        # Header title
        title_surf = self.fonts["header"].render("⚙ Hardware & Cost Configuration", True, (25, 25, 30))
        surface.blit(title_surf, (self.rect.x + 24, self.rect.y + 16))

        # Close button
        self.close_btn.draw(surface)

        # Dividing line
        pygame.draw.line(surface, (220, 225, 235), (self.rect.x + 20, self.rect.y + 48),
                         (self.rect.right - 20, self.rect.y + 48), 1)

        # Draw all sliders
        for s in self.sliders:
            s.draw(surface)
