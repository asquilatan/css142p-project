"""
Picture-in-Picture Live Graphs Drawer.
Renders full-simulation overview charts in minimalist dark aesthetic.
"""

from typing import List
import pygame
from src.metrics import MetricsCollector
from src.ui.layout import Layout


def format_time_label(sec: float) -> str:
    """Formats simulation timestamp into a compact human-readable duration."""
    if sec < 60:
        return f"{sec:.0f}s"
    elif sec < 3600:
        m = int(sec // 60)
        s = int(sec % 60)
        return f"{m}m {s}s" if s > 0 else f"{m}m"
    elif sec < 86400:
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        return f"{h}h {m}m" if m > 0 else f"{h}h"
    else:
        d = int(sec // 86400)
        h = int((sec % 86400) // 3600)
        return f"{d}d {h}h" if h > 0 else f"{d}d"


class GraphsView:
    def __init__(self, layout: Layout, fonts: dict):
        self.layout = layout
        self.fonts = fonts
        self.is_visible = False

        cc = self.layout.center_canvas_rect
        self.drawer_h = 220
        self.drawer_rect = pygame.Rect(cc.x + 12, cc.bottom - self.drawer_h - 12, cc.width - 24, self.drawer_h)

    def set_visible(self, visible: bool):
        self.is_visible = visible

    def draw(self, surface: pygame.Surface, metrics: MetricsCollector):
        if not self.is_visible:
            return

        # Dynamically position drawer inside center canvas
        cc = self.layout.center_canvas_rect
        self.drawer_rect = pygame.Rect(cc.x + 12, cc.bottom - self.drawer_h - 12, cc.width - 24, self.drawer_h)

        # Semi-transparent dark backing panel (#1A1A1E)
        panel_surf = pygame.Surface((self.drawer_rect.width, self.drawer_rect.height), pygame.SRCALPHA)
        panel_surf.fill((26, 26, 30, 245))
        surface.blit(panel_surf, self.drawer_rect.topleft)

        pygame.draw.rect(surface, (55, 55, 65), self.drawer_rect, width=1, border_radius=6)

        title_surf = self.fonts["normal_bold"].render("📈 Full-Timeline Telemetry (Simulation Overview)", True, (230, 230, 235))
        surface.blit(title_surf, (self.drawer_rect.x + 16, self.drawer_rect.y + 10))

        chart_w = (self.drawer_rect.width - 48) // 3
        chart_h = self.drawer_rect.height - 48
        chart_y = self.drawer_rect.y + 36

        # 1. Queue Depth
        c1_rect = pygame.Rect(self.drawer_rect.x + 16, chart_y, chart_w, chart_h)
        self._draw_single_chart(
            surface, c1_rect,
            title="Queue Depth",
            timestamps=metrics.history_timestamps,
            data=metrics.history_queue_depth,
            color=(242, 139, 130),
            unit="req",
            fixed_max=20.0
        )

        # 2. Facility Power Draw
        c2_rect = pygame.Rect(self.drawer_rect.x + 24 + chart_w, chart_y, chart_w, chart_h)
        self._draw_single_chart(
            surface, c2_rect,
            title="Facility Power",
            timestamps=metrics.history_timestamps,
            data=metrics.history_power_watts,
            color=(138, 180, 248),
            unit="W",
            fixed_max=2500.0
        )

        # 3. Arrival Demand Rate
        c3_rect = pygame.Rect(self.drawer_rect.x + 32 + chart_w * 2, chart_y, chart_w, chart_h)
        self._draw_single_chart(
            surface, c3_rect,
            title="Arrival Demand",
            timestamps=metrics.history_timestamps,
            data=metrics.history_arrival_rate,
            color=(129, 201, 149),
            unit="req/s",
            fixed_max=150.0
        )

    def _draw_single_chart(self, surface: pygame.Surface, rect: pygame.Rect,
                           title: str, timestamps: List[float], data: List[float],
                           color: tuple, unit: str, fixed_max: float):
        pygame.draw.rect(surface, (34, 34, 40), rect, border_radius=4)
        pygame.draw.rect(surface, (50, 50, 60), rect, width=1, border_radius=4)

        if not data:
            header_text = f"{title}: -- {unit}"
            lbl = self.fonts["small_bold"].render(header_text, True, (215, 215, 225))
            surface.blit(lbl, (rect.x + 8, rect.y + 6))
            empty_lbl = self.fonts["small"].render("Awaiting simulation data...", True, (120, 120, 130))
            surface.blit(empty_lbl, (rect.x + 8, rect.y + 30))
            return

        current_val = data[-1]
        max_in_data = max(data)
        header_text = f"{title}: {current_val:.1f} {unit}"
        lbl = self.fonts["small_bold"].render(header_text, True, (215, 215, 225))
        surface.blit(lbl, (rect.x + 8, rect.y + 6))

        peak_text = f"Peak: {max_in_data:.1f} {unit}"
        peak_lbl = self.fonts["small"].render(peak_text, True, (140, 145, 155))
        surface.blit(peak_lbl, (rect.right - peak_lbl.get_width() - 8, rect.y + 6))

        if len(data) < 2 or not timestamps:
            return

        max_val = max(fixed_max, max_in_data * 1.15)
        max_val = max(1.0, max_val)

        # Plot area boundaries
        plot_left = rect.x + 8
        plot_right = rect.right - 8
        plot_top = rect.y + 26
        plot_bottom = rect.bottom - 20
        pw = max(10, plot_right - plot_left)
        ph = max(10, plot_bottom - plot_top)

        # Subtle reference lines (midline and baseline)
        mid_y = plot_top + ph // 2
        pygame.draw.line(surface, (42, 42, 50), (plot_left, mid_y), (plot_right, mid_y), 1)
        pygame.draw.line(surface, (48, 48, 58), (plot_left, plot_bottom), (plot_right, plot_bottom), 1)

        t_start = timestamps[0]
        t_end = timestamps[-1]
        t_span = max(0.001, t_end - t_start)

        # Dynamic downsampling for high-speed runs (render max ~250 points)
        n = len(data)
        if n > 250:
            stride = max(1, n // 250)
            sample_indices = list(range(0, n, stride))
            if sample_indices[-1] != n - 1:
                sample_indices.append(n - 1)
        else:
            sample_indices = list(range(n))

        points = []
        for i in sample_indices:
            t = timestamps[i] if i < len(timestamps) else t_end
            val = data[i]
            x = plot_left + int(((t - t_start) / t_span) * pw)
            norm_val = min(1.0, max(0.0, val / max_val))
            y = plot_bottom - int(norm_val * ph)
            points.append((x, y))

        if len(points) >= 2:
            pygame.draw.lines(surface, color, False, points, 2)

        # Time range labels at bottom
        t_start_lbl = self.fonts["small"].render(format_time_label(t_start), True, (130, 135, 145))
        t_end_lbl = self.fonts["small"].render(format_time_label(t_end), True, (130, 135, 145))
        surface.blit(t_start_lbl, (plot_left, plot_bottom + 4))
        surface.blit(t_end_lbl, (plot_right - t_end_lbl.get_width(), plot_bottom + 4))

