"""
Picture-in-Picture Live Graphs Drawer.
Renders real-time scrolling oscilloscope strip charts in minimalist dark aesthetic.
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

        cc = self.layout.center_canvas_rect
        self.drawer_h = 200
        self.drawer_rect = pygame.Rect(cc.x + 12, cc.bottom - self.drawer_h - 12, cc.width - 24, self.drawer_h)

    def set_visible(self, visible: bool):
        self.is_visible = visible

    def draw(self, surface: pygame.Surface, metrics: MetricsCollector):
        if not self.is_visible:
            return

        # Dynamically position drawer inside center canvas
        cc = self.layout.center_canvas_rect
        self.drawer_rect = pygame.Rect(cc.x + 12, cc.bottom - self.drawer_h - 12, cc.width - 24, self.drawer_h)

        # Semi-transparent dark backing panel
        panel_surf = pygame.Surface((self.drawer_rect.width, self.drawer_rect.height), pygame.SRCALPHA)
        panel_surf.fill((26, 26, 30, 240))
        surface.blit(panel_surf, self.drawer_rect.topleft)

        pygame.draw.rect(surface, (55, 55, 65), self.drawer_rect, width=1, border_radius=6)

        title_surf = self.fonts["normal_bold"].render("📈 Live Telemetry Waveforms", True, (230, 230, 235))
        surface.blit(title_surf, (self.drawer_rect.x + 16, self.drawer_rect.y + 10))

        chart_w = (self.drawer_rect.width - 48) // 3
        chart_h = self.drawer_rect.height - 52
        chart_y = self.drawer_rect.y + 38

        # 1. Queue Depth
        c1_rect = pygame.Rect(self.drawer_rect.x + 16, chart_y, chart_w, chart_h)
        self._draw_single_chart(
            surface, c1_rect,
            title="Queue Depth",
            data=metrics.history_queue_depth,
            color=(242, 139, 130),
            unit="req",
            fixed_max=50.0
        )

        # 2. Power Draw
        c2_rect = pygame.Rect(self.drawer_rect.x + 24 + chart_w, chart_y, chart_w, chart_h)
        self._draw_single_chart(
            surface, c2_rect,
            title="Facility Power",
            data=metrics.history_power_watts,
            color=(138, 180, 248),
            unit="W",
            fixed_max=2500.0
        )

        # 3. Demand Rate
        c3_rect = pygame.Rect(self.drawer_rect.x + 32 + chart_w * 2, chart_y, chart_w, chart_h)
        self._draw_single_chart(
            surface, c3_rect,
            title="Arrival Demand",
            data=metrics.history_arrival_rate,
            color=(129, 201, 149),
            unit="req/s",
            fixed_max=300.0
        )

    def _draw_single_chart(self, surface: pygame.Surface, rect: pygame.Rect,
                           title: str, data: Deque[float], color: tuple, unit: str, fixed_max: float):
        pygame.draw.rect(surface, (34, 34, 40), rect, border_radius=4)
        pygame.draw.rect(surface, (50, 50, 60), rect, width=1, border_radius=4)

        current_val = data[-1] if data else 0.0
        header_text = f"{title}: {current_val:.1f} {unit}"
        lbl = self.fonts["small_bold"].render(header_text, True, (215, 215, 225))
        surface.blit(lbl, (rect.x + 8, rect.y + 6))

        if len(data) < 2:
            return

        max_val = max(fixed_max, max(data) * 1.15) if data else fixed_max
        max_val = max(1.0, max_val)

        points = []
        n = len(data)
        for i, val in enumerate(data):
            x = rect.x + int((i / (n - 1)) * rect.width)
            normalized = min(1.0, max(0.0, val / max_val))
            y = rect.bottom - 8 - int(normalized * (rect.height - 28))
            points.append((x, y))

        if len(points) >= 2:
            pygame.draw.lines(surface, color, False, points, 2)
