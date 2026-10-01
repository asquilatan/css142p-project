"""
Telemetry View (Left Sidebar).
Renders the Data Center Racks status list, real-time energy/cost telemetry,
and the [Show Graphs] Picture-in-Picture toggle button with flex visibility.
"""

from typing import Callable, Optional
import pygame
from src.simulation import SimulationEngine
from src.server import ServerState
from src.ui.layout import Layout
from src.ui.widgets import Button


class TelemetryView:
    def __init__(self, layout: Layout, fonts: dict, on_toggle_graphs: Optional[Callable] = None):
        self.layout = layout
        self.fonts = fonts
        self.show_graphs_active = False

        self.graphs_btn = Button(
            pygame.Rect(0, 0, 160, 32),
            text="[Show Graphs]",
            font=fonts["normal"],
            callback=self._toggle_graphs,
            is_toggle=True
        )
        self.on_toggle_graphs = on_toggle_graphs

    def _toggle_graphs(self):
        self.show_graphs_active = self.graphs_btn.is_active
        if self.on_toggle_graphs:
            self.on_toggle_graphs(self.show_graphs_active)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.layout.show_telemetry:
            return False
        return self.graphs_btn.handle_event(event)

    def draw(self, surface: pygame.Surface, sim: SimulationEngine):
        border_col = (25, 25, 30)

        # ---------------------------------------------------------------------
        # 1. Data Center Racks Section
        # ---------------------------------------------------------------------
        if self.layout.show_racks:
            racks_rect = self.layout.racks_panel_rect
            pygame.draw.rect(surface, (255, 255, 255), racks_rect)
            pygame.draw.rect(surface, border_col, racks_rect, width=2)

            title_surf = self.fonts["header"].render("Data Center Racks", True, border_col)
            surface.blit(title_surf, (racks_rect.x + 18, racks_rect.y + 14))

            # Render list of node statuses
            y_offset = racks_rect.y + 46
            for i, srv in enumerate(sim.servers):
                node_name = f"Node {srv.server_id:02d}"
                state_text = f"[ {srv.state.value} ]"

                dot_color = {
                    ServerState.ACTIVE: (46, 204, 113),
                    ServerState.IDLE: (52, 152, 219),
                    ServerState.BOOTING: (243, 156, 18),
                    ServerState.WAKING: (243, 156, 18),
                    ServerState.SLEEPING: (155, 89, 182),
                    ServerState.OFF: (160, 165, 175),
                }.get(srv.state, (160, 165, 175))

                dot_cy = y_offset + 9
                pygame.draw.circle(surface, dot_color, (racks_rect.x + 22, dot_cy), 4)

                name_surf = self.fonts["normal"].render(node_name, True, (40, 45, 55))
                surface.blit(name_surf, (racks_rect.x + 34, y_offset))

                badge_surf = self.fonts["mono"].render(state_text, True, (30, 35, 45))
                surface.blit(badge_surf, (racks_rect.right - badge_surf.get_width() - 18, y_offset))

                y_offset += 24
                if y_offset > racks_rect.bottom - 22:
                    break

        # ---------------------------------------------------------------------
        # 2. Real Time Telemetry Section
        # ---------------------------------------------------------------------
        if self.layout.show_telemetry:
            tele_rect = self.layout.telemetry_panel_rect
            pygame.draw.rect(surface, (255, 255, 255), tele_rect)
            pygame.draw.rect(surface, border_col, tele_rect, width=2)

            tele_title = self.fonts["header"].render("Real Time Telemetry", True, border_col)
            surface.blit(tele_title, (tele_rect.x + 18, tele_rect.y + 14))

            m = sim.metrics
            y_cursor = tele_rect.y + 48

            def draw_metric_row(label: str, value: str, val_color=(30, 35, 45)):
                nonlocal y_cursor
                lbl_surf = self.fonts["normal"].render(label, True, (60, 65, 75))
                val_surf = self.fonts["mono_bold"].render(value, True, val_color)
                surface.blit(lbl_surf, (tele_rect.x + 18, y_cursor))
                surface.blit(val_surf, (tele_rect.right - val_surf.get_width() - 18, y_cursor))
                y_cursor += 24

            draw_metric_row("Queue Depth", f"{m.current_queue_depth} req.",
                            (231, 76, 60) if m.current_queue_depth > 20 else (30, 35, 45))
            draw_metric_row("Dropped Requests", f"{m.total_requests_dropped} req.",
                            (231, 76, 60) if m.total_requests_dropped > 0 else (46, 204, 113))
            draw_metric_row("Instant Power", f"{int(m.facility_instant_power_watts)} W")

            # Energy Section
            y_cursor += 4
            energy_header = self.fonts["small"].render("Energy:", True, (80, 85, 95))
            surface.blit(energy_header, (tele_rect.x + 18, y_cursor))
            y_cursor += 15

            energy_val = f"{m.facility_cumulative_energy_kwh:.2f} kWh"
            energy_surf = self.fonts["large_bold"].render(energy_val, True, (25, 30, 40))
            surface.blit(energy_surf, (tele_rect.x + 18, y_cursor))

            pue_val = f"(PUE: {sim.config.hardware.cooling_pue:.1f})"
            pue_surf = self.fonts["small"].render(pue_val, True, (100, 105, 115))
            surface.blit(pue_surf, (tele_rect.x + 20 + energy_surf.get_width(), y_cursor + 8))

            # Cost Section
            y_cursor += 32
            cost_header = self.fonts["small"].render("Estimated Cost:", True, (80, 85, 95))
            surface.blit(cost_header, (tele_rect.x + 18, y_cursor))
            y_cursor += 15

            cost_val = f"PHP {m.estimated_cost_php:.2f}"
            cost_surf = self.fonts["large_bold"].render(cost_val, True, (25, 30, 40))
            surface.blit(cost_surf, (tele_rect.x + 18, y_cursor))

            # Update & draw [Show Graphs] Button
            btn_w, btn_h = 160, 30
            btn_x = tele_rect.x + (tele_rect.width - btn_w) // 2
            btn_y = tele_rect.bottom - 44
            self.graphs_btn.rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
            self.graphs_btn.draw(surface)
