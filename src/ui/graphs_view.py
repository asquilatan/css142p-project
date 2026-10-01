"""
Picture-in-Picture Live Graphs Drawer.
Renders real-time scrolling oscilloscope strip charts docked at the bottom of the center canvas
when [Show Graphs] is active, updating continuously while packets fly.
"""

from typing import Deque
import pygame
from src.metrics import MetricsCollector
from src.ui.layout import Layout


class GraphsView:
    def __init__(self, layout: Layout, fonts: dict):
        self.layout = layout
        self.fonts = fonts
        self.is_visible = False

        # Drawer occupies bottom 210px of the center canvas
        cc = self.layout.center_canvas_rect
        self.drawer_h = 210
        self.drawer_rect = pygame.Rect(cc.x + 10, cc.bottom - self.drawer_h - 10, cc.width - 20, self.drawer_h)

    def set_visible(self, visible: bool):
        self.is_visible = visible

    def draw(self, surface: pygame.Surface, metrics: MetricsCollector):
        if not self.is_visible:
            return

        # Semi-transparent backing panel
        panel_surf = pygame.Surface((self.drawer_rect.width, self.drawer_rect.height), pygame.SRCALPHA)
        panel_surf.fill((255, 255, 255, 240))  # 94% opaque white
        surface.blit(panel_surf, self.drawer_rect.topleft)

        # Border
        pygame.draw.rect(surface, (25, 25, 30), self.drawer_rect, width=2, border_radius=6)

        # Title bar
        title_surf = self.fonts["normal_bold"].render("📈 Live Telemetry Waveforms (Picture-in-Picture)", True, (25, 25, 30))
        surface.blit(title_surf, (self.drawer_rect.x + 16, self.drawer_rect.y + 10))

        # 3 Split Chart Areas
        chart_w = (self.drawer_rect.width - 48) // 3
        chart_h = self.drawer_rect.height - 56
        chart_y = self.drawer_rect.y + 42

        # Chart 1: Queue Depth
        c1_rect = pygame.Rect(self.drawer_rect.x + 16, chart_y, chart_w, chart_h)
        self._draw_single_chart(
            surface, c1_rect,
            title="Request Queue Depth",
            data=metrics.history_queue_depth,
            color=(231, 76, 60),
            unit="req",
            fixed_max=50.0
        )

        # Chart 2: Instant Facility Power (Watts)
        c2_rect = pygame.Rect(self.drawer_rect.x + 24 + chart_w, chart_y, chart_w, chart_h)
        self._draw_single_chart(
            surface, c2_rect,
            title="Facility Power Draw",
            data=metrics.history_power_watts,
            color=(41, 128, 185),
            unit="W",
            fixed_max=2500.0
        )

        # Chart 3: Incoming Arrival Rate
        c3_rect = pygame.Rect(self.drawer_rect.x + 32 + chart_w * 2, chart_y, chart_w, chart_h)
        self._draw_single_chart(
            surface, c3_rect,
            title="Arrival Demand Rate",
            data=metrics.history_arrival_rate,
            color=(46, 204, 113),
            unit="req/s",
            fixed_max=300.0
        )

    def _draw_single_chart(self, surface: pygame.Surface, rect: pygame.Rect,
                           title: str, data: Deque[float], color: tuple, unit: str, fixed_max: float):
        # Background box
        pygame.draw.rect(surface, (248, 249, 252), rect, border_radius=4)
        pygame.draw.rect(surface, (200, 205, 215), rect, width=1, border_radius=4)

        # Header
        current_val = data[-1] if data else 0.0
        header_text = f"{title}: {current_val:.1f} {unit}"
        lbl = self.fonts["small_bold"].render(header_text, True, (40, 45, 55))
        surface.blit(lbl, (rect.x + 8, rect.y + 6))

        if len(data) < 2:
            return

        # Calculate dynamic or fixed maximum
        max_val = max(fixed_max, max(data) * 1.15) if data else fixed_max
        max_val = max(1.0, max_val)

        # Plot waveform points
        points = []
        n = len(data)
        for i, val in enumerate(data):
            x = rect.x + int((i / (n - 1)) * rect.width)
            normalized = min(1.0, max(0.0, val / max_val))
            y = rect.bottom - 8 - int(normalized * (rect.height - 30))
            points.append((x, y))

        if len(points) >= 2:
            pygame.draw.lines(surface, color, False, points, 2)
