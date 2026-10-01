"""
Settings Modal.
Pure configuration drawer (run length, server pool, compute backend,
speed unlock, hardware/cost parameters). Starting runs happens from the
main Start button; this modal never starts anything itself.
"""

from typing import Callable, Optional
import pygame
from src.config import SimConfig
from src.ui.widgets import (
    Button, ButtonGroup, Slider, NumberStepper, DurationInputs,
    ToggleSwitch, render_cached,
)


class SettingsModal:
    def __init__(self, screen_size: tuple, config: SimConfig, fonts: dict,
                 on_server_count_change: Callable[[int], None],
                 backend: str = "rust",
                 rust_available: bool = True,
                 ultra_enabled: bool = False,
                 on_backend_change: Optional[Callable[[str], None]] = None,
                 on_ultra_toggle: Optional[Callable[[bool], None]] = None):
        self.sw, self.sh = screen_size
        self.config = config
        self.fonts = fonts
        self.on_server_count_change = on_server_count_change
        self.on_backend_change = on_backend_change
        self.on_ultra_toggle = on_ultra_toggle
        self.rust_available = rust_available
        self.ultra_enabled = ultra_enabled
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

        y_cursor += 44

        # ---------------------------------------------------------------------
        # 3. Compute Backend (Rust accelerator vs pure-Python SimPy)
        # ---------------------------------------------------------------------
        self.backend_label_y = y_cursor
        bw = (sw - 8) // 2
        backend_btns = [
            Button(pygame.Rect(sx, y_cursor + 18, bw, 28), text="Rust",
                   font=fonts["small"]),
            Button(pygame.Rect(sx + bw + 8, y_cursor + 18, bw, 28), text="PySim",
                   font=fonts["small"]),
        ]
        initial_backend = 0 if backend == "rust" else 1
        if backend == "rust" and not rust_available:
            initial_backend = 1
        self.backend_group = ButtonGroup(
            backend_btns, initial_index=initial_backend,
            on_change=self._on_backend_select,
        )
        self.backend_status_y = y_cursor + 50

        y_cursor += 72

        # ---------------------------------------------------------------------
        # 4. Ultra Speed Unlock (Rust only, up to 1440 min/s = 1 day/sec)
        # ---------------------------------------------------------------------
        self.ultra_switch = ToggleSwitch(
            pygame.Rect(sx, y_cursor, sw, 26),
            label="Unlock 1 day/sec speed",
            font=fonts["normal"],
            initial_state=ultra_enabled,
            on_toggle=self._on_ultra_switch,
        )
        self.ultra_warning_y = y_cursor + 28

        y_cursor += 50

        # ---------------------------------------------------------------------
        # 5. Hardware & Economic Tuning
        # ---------------------------------------------------------------------
        spacing = 38
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

    def _on_backend_select(self, index: int, name: str):
        if name == "Rust" and not self.rust_available:
            # Rust unavailable on this machine: revert the radio selection.
            for j, b in enumerate(self.backend_group.buttons):
                b.is_active = (j == 1)
            self.backend_group.active_index = 1
            return
        if self.on_backend_change:
            self.on_backend_change("rust" if name == "Rust" else "pysim")

    def _on_ultra_switch(self, enabled: bool):
        self.ultra_enabled = enabled
        if self.on_ultra_toggle:
            self.on_ultra_toggle(enabled)

    def open(self):
        self.is_open = True

    def close(self):
        self.is_open = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.is_open:
            return False

        if self.close_btn.handle_event(event):
            return True
        if self.duration_inputs.handle_event(event):
            return True
        if self.server_stepper.handle_event(event):
            return True
        if self.backend_group.handle_event(event):
            return True
        if self.ultra_switch.handle_event(event):
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

        # Compute Backend section
        backend_lbl = render_cached(self.fonts["normal"], "Compute Backend:", (160, 165, 175))
        surface.blit(backend_lbl, (self.rect.x + 30, self.backend_label_y))
        self.backend_group.draw(surface)
        if self.rust_available:
            status_text = "sim_core detected — Rust accelerator ready"
            status_col = (129, 201, 149)
        else:
            status_text = "sim_core not found — Rust unavailable, PySim only"
            status_col = (242, 139, 130)
        status_surf = render_cached(self.fonts["small"], status_text, status_col)
        surface.blit(status_surf, (self.rect.x + 30, self.backend_status_y))

        # Ultra speed section (with up-front warning)
        self.ultra_switch.draw(surface)
        warn_surf = render_cached(
            self.fonts["small"],
            "⚠ Rust only: visuals blur past ~500 min/s; use for fast-forwarding.",
            (253, 214, 99),
        )
        surface.blit(warn_surf, (self.rect.x + 30, self.ultra_warning_y))

        # Draw Hardware Sliders
        for s in self.sliders:
            s.draw(surface)
