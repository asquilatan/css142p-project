"""
Telemetry View (Left Sidebar).
Renders the Data Center Racks status list, real-time energy/cost telemetry,
and the [Show Graphs] Picture-in-Picture toggle button in minimalist dark aesthetic.
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
            pygame.Rect(0, 0, 160, 30),
            text="[Show Graphs]",
            font=fonts["normal"],
            callback=self._toggle_graphs,
            is_toggle=True,
            active_bg=(138, 180, 248),
            active_text=(20, 20, 25)
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
        border_col = (48, 48, 54)
        panel_bg = (24, 24, 26)

        # ---------------------------------------------------------------------
        # 1. Data Center Racks Section
        # ---------------------------------------------------------------------
        if self.layout.show_racks:
            racks_rect = self.layout.racks_panel_rect
            pygame.draw.rect(surface, panel_bg, racks_rect)
            # 1px border divider on right and bottom
            pygame.draw.line(surface, border_col, (racks_rect.right, racks_rect.y), (racks_rect.right, racks_rect.bottom), 1)
            pygame.draw.line(surface, border_col, (racks_rect.x, racks_rect.bottom), (racks_rect.right, racks_rect.bottom), 1)

            title_surf = self.fonts["header"].render("Data Center Racks", True, (230, 230, 235))
            surface.blit(title_surf, (racks_rect.x + 18, racks_rect.y + 14))

            y_offset = racks_rect.y + 46
            for i, srv in enumerate(sim.servers):
                node_name = f"Node {srv.server_id:02d}"
                state_text = f"[ {srv.state.value} ]"

                dot_color = {
                    ServerState.ACTIVE: (129, 201, 149),
                    ServerState.IDLE: (138, 180, 248),
                    ServerState.BOOTING: (253, 214, 99),
                    ServerState.WAKING: (253, 214, 99),
                    ServerState.SLEEPING: (197, 138, 249),
                    ServerState.OFF: (90, 90, 100),
                }.get(srv.state, (90, 90, 100))

                dot_cy = y_offset + 9
                pygame.draw.circle(surface, dot_color, (racks_rect.x + 18, dot_cy), 4)

                name_surf = self.fonts["normal"].render(node_name, True, (215, 215, 225))
                surface.blit(name_surf, (racks_rect.x + 28, y_offset))

                # Display load per server
                if srv.state in (ServerState.ACTIVE, ServerState.IDLE):
                    load_text = f"{srv.active_request_count}/{srv.capacity}"
                    load_col = (129, 201, 149) if srv.active_request_count > 0 else (140, 145, 155)
                elif srv.state in (ServerState.BOOTING, ServerState.WAKING):
                    load_text = f"{int(srv.get_boot_progress_pct() * 100)}%"
                    load_col = (253, 214, 99)
                else:
                    load_text = "-"
                    load_col = (90, 95, 105)

                load_surf = self.fonts["mono"].render(load_text, True, load_col)
                surface.blit(load_surf, (racks_rect.x + 102, y_offset + 1))

                badge_surf = self.fonts["mono"].render(state_text, True, (160, 165, 175))
                surface.blit(badge_surf, (racks_rect.right - badge_surf.get_width() - 14, y_offset))

                y_offset += 24
                if y_offset > racks_rect.bottom - 22:
                    break

        # ---------------------------------------------------------------------
        # 2. Real Time Telemetry Section
        # ---------------------------------------------------------------------
        if self.layout.show_telemetry:
            tele_rect = self.layout.telemetry_panel_rect
            pygame.draw.rect(surface, panel_bg, tele_rect)
            # 1px border divider on right
            pygame.draw.line(surface, border_col, (tele_rect.right, tele_rect.y), (tele_rect.right, tele_rect.bottom), 1)

            tele_title = self.fonts["header"].render("Real Time Telemetry", True, (230, 230, 235))
            surface.blit(tele_title, (tele_rect.x + 18, tele_rect.y + 14))

            m = sim.metrics
            y_cursor = tele_rect.y + 48

            def draw_metric_row(label: str, value: str, val_color=(230, 230, 235)):
                nonlocal y_cursor
                lbl_surf = self.fonts["normal"].render(label, True, (150, 155, 165))
                val_surf = self.fonts["mono_bold"].render(value, True, val_color)
                surface.blit(lbl_surf, (tele_rect.x + 18, y_cursor))
                surface.blit(val_surf, (tele_rect.right - val_surf.get_width() - 18, y_cursor))
                y_cursor += 24

            draw_metric_row("Queue Depth", f"{m.current_queue_depth} req.",
                            (242, 139, 130) if m.current_queue_depth > 20 else (230, 230, 235))
            draw_metric_row("Dropped Requests", f"{m.total_requests_dropped} req.",
                            (242, 139, 130) if m.total_requests_dropped > 0 else (129, 201, 149))
            draw_metric_row("Instant Power", f"{int(m.facility_instant_power_watts)} W")

            # Energy Section
            y_cursor += 6
            energy_header = self.fonts["small"].render("Energy:", True, (150, 155, 165))
            surface.blit(energy_header, (tele_rect.x + 18, y_cursor))
            y_cursor += 15

            energy_val = f"{m.facility_cumulative_energy_kwh:.2f} kWh"
            energy_surf = self.fonts["large_bold"].render(energy_val, True, (245, 245, 250))
            surface.blit(energy_surf, (tele_rect.x + 18, y_cursor))

            pue_val = f"(PUE: {sim.config.hardware.cooling_pue:.1f})"
            pue_surf = self.fonts["small"].render(pue_val, True, (130, 135, 145))
            surface.blit(pue_surf, (tele_rect.x + 18 + energy_surf.get_width() + 8, y_cursor + 8))

            # Cost Section
            y_cursor += 32
            cost_header = self.fonts["small"].render("Estimated Cost:", True, (150, 155, 165))
            surface.blit(cost_header, (tele_rect.x + 18, y_cursor))
            y_cursor += 15

            cost_val = f"PHP {m.estimated_cost_php:.2f}"
            cost_surf = self.fonts["large_bold"].render(cost_val, True, (245, 245, 250))
            surface.blit(cost_surf, (tele_rect.x + 18, y_cursor))

            # Update & draw [Show Graphs] Button
            btn_w, btn_h = 160, 30
            btn_x = tele_rect.x + (tele_rect.width - btn_w) // 2
            btn_y = tele_rect.bottom - 44
            self.graphs_btn.rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
            self.graphs_btn.draw(surface)

        # ---------------------------------------------------------------------
        # 3. Horizontal Separator between Racks and Telemetry
        # ---------------------------------------------------------------------
        if self.layout.show_racks and self.layout.show_telemetry:
            sep_y = self.layout.racks_panel_rect.bottom
            pygame.draw.line(surface, border_col, (0, sep_y), (self.layout.left_panel_rect.right, sep_y), 1)

