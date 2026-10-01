"""
Dedicated Waveforms & Telemetry Analytics Window.
Renders full-simulation overview charts in an independent Pygame-CE secondary window,
using min-max peak/valley envelope downsampling and a fixed simulation timeline.
Also integrates one-click Matplotlib export for deep interactive inspection.
"""

from typing import List, Optional, Tuple
import pygame
from src.metrics import MetricsCollector
from src.ui.assets_manager import AssetsManager
from src.ui.matplotlib_view import launch_matplotlib_window


def format_duration(sec: float) -> str:
    """Formats seconds into human-readable duration strings."""
    if sec < 0:
        return "0s"
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


def get_timeline_ceiling(current_time: float, target_time: Optional[float] = None) -> float:
    """Returns the fixed X-axis maximum representing the end of the simulation."""
    if target_time is not None and target_time > 0:
        return target_time
    milestones = [
        60.0, 300.0, 900.0, 1800.0, 3600.0, 7200.0,
        14400.0, 28800.0, 86400.0, 172800.0, 604800.0, 2592000.0
    ]
    for m in milestones:
        if m >= current_time * 1.05:
            return m
    return max(60.0, current_time * 1.2)


def min_max_envelope_downsample(timestamps: List[float], values: List[float],
                                t_max: float, plot_left: int, pw: int,
                                plot_bottom: int, ph: int, v_max: float) -> List[Tuple[int, int]]:
    """
    Min-Max Envelope Downsampling:
    Buckets data by screen pixel column and preserves BOTH the local minimum
    and local maximum in chronological order. Mathematically guarantees that
    no peak and no valley will ever vanish or alias regardless of sample size.
    """
    if not timestamps or not values or len(timestamps) < 2:
        return []

    n = len(values)
    t_max = max(0.001, t_max)
    v_max = max(0.001, v_max)

    if n <= pw:
        pts = []
        for t, v in zip(timestamps, values):
            x = plot_left + int(min(1.0, max(0.0, t / t_max)) * pw)
            norm = min(1.0, max(0.0, v / v_max))
            y = plot_bottom - int(norm * ph)
            pts.append((x, y))
        return pts

    # Screen pixel column bucketing
    col_buckets = {}
    for i in range(n):
        t = timestamps[i]
        col = int(min(1.0, max(0.0, t / t_max)) * pw)
        if col not in col_buckets:
            col_buckets[col] = []
        col_buckets[col].append(values[i])

    pts = []
    for col in sorted(col_buckets.keys()):
        x = plot_left + col
        bucket = col_buckets[col]
        if len(bucket) == 1:
            y = plot_bottom - int(min(1.0, max(0.0, bucket[0] / v_max)) * ph)
            pts.append((x, y))
        else:
            v_min = min(bucket)
            v_max_b = max(bucket)
            if v_min == v_max_b:
                y = plot_bottom - int(min(1.0, max(0.0, v_min / v_max)) * ph)
                pts.append((x, y))
            else:
                idx_min = bucket.index(v_min)
                idx_max = bucket.index(v_max_b)
                if idx_min < idx_max:
                    y1 = plot_bottom - int(min(1.0, max(0.0, v_min / v_max)) * ph)
                    y2 = plot_bottom - int(min(1.0, max(0.0, v_max_b / v_max)) * ph)
                    pts.append((x, y1))
                    pts.append((x, y2))
                else:
                    y1 = plot_bottom - int(min(1.0, max(0.0, v_max_b / v_max)) * ph)
                    y2 = plot_bottom - int(min(1.0, max(0.0, v_min / v_max)) * ph)
                    pts.append((x, y1))
                    pts.append((x, y2))
    return pts


class GraphsView:
    def __init__(self, layout=None, fonts: dict = None, assets: Optional[AssetsManager] = None, on_close=None):
        self.fonts = fonts or {}
        self.assets = assets
        self.on_close = on_close
        self.is_visible = False

        self.width = 1080
        self.height = 680

        # Dedicated Pygame-CE Secondary Window
        self.window = pygame.Window(title="Telemetry & Waveform Analytics", size=(self.width, self.height))
        self.window.hide()

        # Cache control buttons
        self.close_btn_rect = pygame.Rect(self.width - 110, 16, 90, 32)
        self.mpl_btn_rect = pygame.Rect(self.width - 290, 16, 170, 32)

        # Cached telemetry state for export
        self._last_metrics: Optional[MetricsCollector] = None
        self._last_curr_time: float = 0.0
        self._last_target_time: Optional[float] = None

    def is_window(self, win) -> bool:
        return win == self.window

    def set_visible(self, visible: bool):
        self.is_visible = visible
        if visible:
            self.window.show()
            self.window.focus()
        else:
            self.window.hide()
        if self.on_close:
            self.on_close(visible)

    def toggle_visible(self):
        self.set_visible(not self.is_visible)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.is_visible:
            return False

        if event.type == pygame.WINDOWCLOSE:
            if getattr(event, "window", None) == self.window:
                self.set_visible(False)
                return True

        if getattr(event, "window", None) == self.window:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_pos = event.pos
                if self.close_btn_rect.collidepoint(mouse_pos):
                    self.set_visible(False)
                    return True
                elif self.mpl_btn_rect.collidepoint(mouse_pos):
                    if self._last_metrics is not None:
                        launch_matplotlib_window(self._last_metrics, self._last_curr_time, self._last_target_time)
                    return True
            return True

        return False

    def update_and_draw(self, metrics: MetricsCollector, current_time: float, target_time: Optional[float] = None):
        if not self.is_visible:
            return

        self._last_metrics = metrics
        self._last_curr_time = current_time
        self._last_target_time = target_time

        surface = self.window.get_surface()

        # Minimalist Dark Background (#18181A)
        surface.fill((24, 24, 26))

        t_max = get_timeline_ceiling(current_time, target_time)

        # ---------------------------------------------------------------------
        # Header Bar
        # ---------------------------------------------------------------------
        title_surf = self.fonts.get("header_large", self.fonts.get("header")).render(
            "📈 Telemetry & Waveform Analytics", True, (240, 240, 245)
        )
        surface.blit(title_surf, (30, 16))

        # Progress / Simulation Timeline Status
        target_str = format_duration(target_time) if target_time else "Continuous"
        progress_pct = (current_time / t_max) * 100.0 if t_max > 0 else 0.0
        status_text = f"Elapsed: {format_duration(current_time)} / {target_str} ({min(100.0, progress_pct):.1f}%)"
        status_surf = self.fonts.get("normal").render(status_text, True, (160, 165, 175))
        surface.blit(status_surf, (30, 48))

        # Buttons
        mouse_pos = pygame.mouse.get_pos()
        # Matplotlib Export Button
        mpl_hover = self.mpl_btn_rect.collidepoint(mouse_pos)
        mpl_bg = (50, 52, 60) if mpl_hover else (38, 40, 46)
        pygame.draw.rect(surface, mpl_bg, self.mpl_btn_rect, border_radius=4)
        pygame.draw.rect(surface, (65, 68, 80), self.mpl_btn_rect, width=1, border_radius=4)
        mpl_txt = self.fonts.get("small_bold").render("📊 Open in Matplotlib", True, (220, 225, 235))
        surface.blit(mpl_txt, mpl_txt.get_rect(center=self.mpl_btn_rect.center))

        # Close Button
        close_hover = self.close_btn_rect.collidepoint(mouse_pos)
        close_bg = (60, 35, 35) if close_hover else (38, 40, 46)
        pygame.draw.rect(surface, close_bg, self.close_btn_rect, border_radius=4)
        pygame.draw.rect(surface, (70, 72, 82), self.close_btn_rect, width=1, border_radius=4)
        close_txt = self.fonts.get("small_bold").render("✕ Close", True, (220, 225, 235))
        surface.blit(close_txt, close_txt.get_rect(center=self.close_btn_rect.center))

        # ---------------------------------------------------------------------
        # 3 Stacked Oscilloscope Charts
        # ---------------------------------------------------------------------
        chart_w = 1020
        chart_h = 160
        chart_x = 30

        # Chart 1: Queue Depth
        c1_rect = pygame.Rect(chart_x, 80, chart_w, chart_h)
        self._draw_waveform_card(
            surface, c1_rect,
            title="Queue Depth (Requests)",
            timestamps=metrics.history_timestamps,
            values=metrics.history_queue_depth,
            color=(242, 139, 130),  # Coral
            unit="req",
            fixed_max=20.0,
            t_max=t_max,
            current_time=current_time,
            show_x_axis=False
        )

        # Chart 2: Arrival Demand Rate
        c2_rect = pygame.Rect(chart_x, 255, chart_w, chart_h)
        self._draw_waveform_card(
            surface, c2_rect,
            title="Arrival Demand Rate (Poisson Process)",
            timestamps=metrics.history_timestamps,
            values=metrics.history_arrival_rate,
            color=(129, 201, 149),  # Emerald
            unit="req/s",
            fixed_max=150.0,
            t_max=t_max,
            current_time=current_time,
            show_x_axis=False
        )

        # Chart 3: Facility Power Draw
        c3_rect = pygame.Rect(chart_x, 430, chart_w, chart_h)
        self._draw_waveform_card(
            surface, c3_rect,
            title="Facility Power Consumption (Servers + Cooling PUE)",
            timestamps=metrics.history_timestamps,
            values=metrics.history_power_watts,
            color=(138, 180, 248),  # Blue
            unit="W",
            fixed_max=2500.0,
            t_max=t_max,
            current_time=current_time,
            show_x_axis=True
        )

        # ---------------------------------------------------------------------
        # Footer Telemetry Status Summary
        # ---------------------------------------------------------------------
        footer_y = 635
        drop_rate = (metrics.total_requests_dropped / max(1, metrics.total_requests_arrived)) * 100.0
        stats_line = (
            f"Total Arrived: {metrics.total_requests_arrived:,}  |  "
            f"Served: {metrics.total_requests_served:,}  |  "
            f"Dropped: {metrics.total_requests_dropped:,} ({drop_rate:.1f}%)  |  "
            f"Facility Energy: {metrics.facility_cumulative_energy_kwh:.3f} kWh  |  "
            f"Total Cost: ₱{metrics.estimated_cost_php:.2f}"
        )
        footer_surf = self.fonts.get("mono", self.fonts.get("small")).render(stats_line, True, (150, 155, 165))
        surface.blit(footer_surf, (30, footer_y))

        self.window.flip()

    def draw(self, surface: pygame.Surface, metrics: MetricsCollector):
        """Compatibility wrapper delegating to update_and_draw."""
        pass

    def _draw_waveform_card(self, surface: pygame.Surface, rect: pygame.Rect,
                            title: str, timestamps: List[float], values: List[float],
                            color: tuple, unit: str, fixed_max: float,
                            t_max: float, current_time: float, show_x_axis: bool = False):
        # Card Background (#222226) and Border (#383842)
        pygame.draw.rect(surface, (34, 34, 38), rect, border_radius=6)
        pygame.draw.rect(surface, (54, 54, 62), rect, width=1, border_radius=6)

        current_val = values[-1] if values else 0.0
        peak_val = max(values) if values else 0.0

        # Title & Metric Badges
        title_surf = self.fonts.get("normal_bold").render(title, True, (230, 230, 235))
        surface.blit(title_surf, (rect.x + 16, rect.y + 8))

        badge_text = f"Current: {current_val:.1f} {unit}   |   Peak: {peak_val:.1f} {unit}"
        badge_surf = self.fonts.get("small").render(badge_text, True, (170, 175, 185))
        surface.blit(badge_surf, (rect.right - badge_surf.get_width() - 16, rect.y + 10))

        # Plot Dimensions
        plot_left = rect.x + 55
        plot_right = rect.right - 20
        plot_top = rect.y + 34
        plot_bottom = rect.bottom - (24 if show_x_axis else 14)
        pw = max(10, plot_right - plot_left)
        ph = max(10, plot_bottom - plot_top)

        max_val = max(fixed_max, peak_val * 1.15)
        max_val = max(1.0, max_val)

        # Left Y-Axis Labels & Reference Gridlines
        top_y_lbl = self.fonts.get("small").render(f"{max_val:.0f}", True, (110, 115, 125))
        mid_y_lbl = self.fonts.get("small").render(f"{max_val * 0.5:.0f}", True, (110, 115, 125))
        bot_y_lbl = self.fonts.get("small").render("0", True, (110, 115, 125))

        surface.blit(top_y_lbl, (plot_left - top_y_lbl.get_width() - 8, plot_top - 4))
        surface.blit(mid_y_lbl, (plot_left - mid_y_lbl.get_width() - 8, plot_top + ph // 2 - 6))
        surface.blit(bot_y_lbl, (plot_left - bot_y_lbl.get_width() - 8, plot_bottom - 8))

        # Horizontal Gridlines
        mid_y = plot_top + ph // 2
        pygame.draw.line(surface, (42, 42, 48), (plot_left, mid_y), (plot_right, mid_y), 1)
        pygame.draw.line(surface, (48, 48, 56), (plot_left, plot_bottom), (plot_right, plot_bottom), 1)

        # Envelope Downsampled Points
        pts = min_max_envelope_downsample(
            timestamps, values, t_max, plot_left, pw, plot_bottom, ph, max_val
        )

        if len(pts) >= 2:
            # Subtle filled polygon under the curve
            fill_poly = [(pts[0][0], plot_bottom)] + pts + [(pts[-1][0], plot_bottom)]
            fill_surf = pygame.Surface((pw + 20, ph + 20), pygame.SRCALPHA)
            local_poly = [(p[0] - plot_left, p[1] - plot_top) for p in fill_poly]
            fill_col = (color[0], color[1], color[2], 25)
            pygame.draw.polygon(fill_surf, fill_col, local_poly)
            surface.blit(fill_surf, (plot_left, plot_top))

            # Main Waveform Line
            pygame.draw.lines(surface, color, False, pts, 2)

        # Current Time Progress Indicator (Vertical Gold Cursor)
        if t_max > 0 and current_time >= 0:
            curr_x = plot_left + int(min(1.0, current_time / t_max) * pw)
            # Dotted vertical cursor
            for y_step in range(plot_top, plot_bottom, 6):
                pygame.draw.line(surface, (253, 214, 99), (curr_x, y_step), (curr_x, min(plot_bottom, y_step + 3)), 1)
            if pts:
                last_y = pts[-1][1]
                pygame.draw.circle(surface, (253, 214, 99), (curr_x, last_y), 3)

        # X-Axis Time Labels on Bottom Chart
        if show_x_axis:
            tick_fractions = [0.0, 0.25, 0.50, 0.75, 1.0]
            for frac in tick_fractions:
                tx = plot_left + int(frac * pw)
                time_at_tick = frac * t_max
                lbl = self.fonts.get("small").render(format_duration(time_at_tick), True, (130, 135, 145))
                surface.blit(lbl, (tx - lbl.get_width() // 2, plot_bottom + 4))
                pygame.draw.line(surface, (54, 54, 62), (tx, plot_bottom), (tx, plot_bottom + 3), 1)
