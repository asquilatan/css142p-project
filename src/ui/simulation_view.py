"""
Simulation View (Center Canvas).
Implements movable/draggable server nodes, Load Balancer, and Cloud,
with dynamic stretching network wires and animated flying packets in minimalist dark aesthetic.
"""

import math
import time
from typing import Dict, List, Optional, Tuple
import pygame
from src.simulation import SimulationEngine, PacketAnimation
from src.server import ServerState
from src.ui.layout import Layout
from src.ui.assets_manager import AssetsManager


class SimulationView:
    def __init__(self, layout: Layout, assets: AssetsManager, fonts: dict):
        self.layout = layout
        self.assets = assets
        self.fonts = fonts

        self.active_packets: List[PacketAnimation] = []
        self.max_active_packets = 10  # Hard cap on in-flight animated packets
        self.next_anim_id = 1
        self.last_anim_spawn_time = 0.0

        # Movable / Draggable Node Tracking
        self.custom_server_positions: Dict[int, Tuple[int, int]] = {}
        self.custom_lb_pos: Optional[Tuple[int, int]] = None
        self.custom_cloud_pos: Optional[Tuple[int, int]] = None

        self.dragging_node: Optional[str] = None  # "cloud", "lb", or "server_N"
        self.drag_offset: Tuple[int, int] = (0, 0)

    def reset_positions(self):
        """Clears all custom drag positions and snaps nodes back to standard layout."""
        self.custom_server_positions.clear()
        self.custom_lb_pos = None
        self.custom_cloud_pos = None

    def get_cloud_pos(self) -> Tuple[int, int]:
        return self.custom_cloud_pos or self.layout.cloud_pos

    def get_lb_rect(self) -> pygame.Rect:
        if self.custom_lb_pos:
            w, h = self.layout.lb_rect.width, self.layout.lb_rect.height
            return pygame.Rect(self.custom_lb_pos[0] - w // 2, self.custom_lb_pos[1] - h // 2, w, h)
        return self.layout.lb_rect

    def get_server_positions(self, num_servers: int) -> List[Tuple[int, int]]:
        default_positions = self.layout.calculate_server_positions(num_servers)
        final_positions = []
        for i in range(num_servers):
            if i in self.custom_server_positions:
                final_positions.append(self.custom_server_positions[i])
            else:
                final_positions.append(default_positions[i])
        return final_positions

    def handle_event(self, event: pygame.event.Event, num_servers: int) -> bool:
        """Handles mouse drag-and-drop for movable nodes."""
        if not self.layout.center_canvas_rect.collidepoint(pygame.mouse.get_pos()) and not self.dragging_node:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos

            # Check servers
            server_positions = self.get_server_positions(num_servers)
            for i, (sx, sy) in enumerate(server_positions):
                srv_surf = self.assets.get_image("server_active")
                s_rect = pygame.Rect(sx - srv_surf.get_width() // 2, sy - srv_surf.get_height() // 2,
                                     srv_surf.get_width(), srv_surf.get_height())
                if s_rect.collidepoint((mx, my)):
                    self.dragging_node = f"server_{i}"
                    self.drag_offset = (sx - mx, sy - my)
                    return True

            # Check Load Balancer
            lb_rect = self.get_lb_rect()
            if lb_rect.collidepoint((mx, my)):
                self.dragging_node = "lb"
                self.drag_offset = (lb_rect.centerx - mx, lb_rect.centery - my)
                return True

            # Check Cloud
            c_pos = self.get_cloud_pos()
            cloud_rect = pygame.Rect(c_pos[0] - 40, c_pos[1] - 25, 80, 50)
            if cloud_rect.collidepoint((mx, my)):
                self.dragging_node = "cloud"
                self.drag_offset = (c_pos[0] - mx, c_pos[1] - my)
                return True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging_node:
                self.dragging_node = None
                return True

        elif event.type == pygame.MOUSEMOTION and self.dragging_node:
            mx, my = event.pos
            ox, oy = self.drag_offset
            # Clamp inside center canvas with margin
            cc = self.layout.center_canvas_rect
            nx = min(cc.right - 60, max(cc.left + 60, mx + ox))
            ny = min(cc.bottom - 45, max(cc.top + 45, my + oy))

            if self.dragging_node == "cloud":
                self.custom_cloud_pos = (nx, ny)
            elif self.dragging_node == "lb":
                self.custom_lb_pos = (nx, ny)
            elif self.dragging_node.startswith("server_"):
                idx = int(self.dragging_node.split("_")[1])
                self.custom_server_positions[idx] = (nx, ny)
            return True

        return False

    def update_and_draw(self, surface: pygame.Surface, sim: SimulationEngine, current_real_time: float,
                        dt: float = 0.016, is_paused: bool = False):
        canvas_rect = self.layout.center_canvas_rect

        # Set hardware clipping so canvas elements NEVER bleed under sidebars
        prev_clip = surface.get_clip()
        surface.set_clip(canvas_rect)

        # Background fill for workspace
        pygame.draw.rect(surface, (33, 33, 33), canvas_rect)

        cloud_pos = self.get_cloud_pos()
        lb_rect = self.get_lb_rect()
        server_positions = self.get_server_positions(len(sim.servers))

        lb_right_mid = (lb_rect.right, lb_rect.centery)
        lb_left_mid = (lb_rect.left, lb_rect.centery)
        cloud_right = (cloud_pos[0] + 38, cloud_pos[1])

        # 1. Draw Network Wires (LB -> Servers)
        for i, (sx, sy) in enumerate(server_positions):
            srv = sim.servers[i]
            if srv.state == ServerState.ACTIVE:
                line_color = (129, 201, 149)  # Soft Emerald
                line_width = 2
            elif srv.state == ServerState.IDLE:
                line_color = (138, 180, 248)  # Soft Blue
                line_width = 2
            elif srv.state in (ServerState.BOOTING, ServerState.WAKING):
                line_color = (253, 214, 99)   # Amber
                line_width = 1
            else:
                line_color = (60, 60, 70)     # Dim dark wire
                line_width = 1

            pygame.draw.line(surface, line_color, lb_right_mid, (sx - 45, sy), line_width)

        # 2. Draw Wire (Cloud -> LB)
        pygame.draw.line(surface, (90, 100, 120), cloud_right, lb_left_mid, 2)

        # 3. Draw Cloud
        cloud_surf = self.assets.get_image("cloud")
        cloud_dest = (cloud_pos[0] - cloud_surf.get_width() // 2,
                      cloud_pos[1] - cloud_surf.get_height() // 2)
        surface.blit(cloud_surf, cloud_dest)
        cloud_lbl = self.fonts["small_bold"].render("Cloud", True, (210, 215, 225))
        surface.blit(cloud_lbl, (cloud_pos[0] - cloud_lbl.get_width() // 2, cloud_pos[1] - 8))

        # 4. Draw Incoming Queued Packets (Cloud -> LB)
        queue_count = min(len(sim.request_queue), 6)
        if queue_count > 0:
            packet_img = self.assets.get_image("packet")
            pw, ph = packet_img.get_width(), packet_img.get_height()
            for q_idx in range(queue_count):
                fraction = 0.25 + (q_idx / 8.5)
                px = int(cloud_right[0] + fraction * (lb_left_mid[0] - cloud_right[0]))
                py = int(cloud_right[1] + fraction * (lb_left_mid[1] - cloud_right[1]))
                surface.blit(packet_img, (px - pw // 2, py - ph // 2))

        # 5. Draw Load Balancer
        lb_surf = self.assets.get_image("load_balancer")
        surface.blit(lb_surf, lb_rect)
        lb_title1 = self.fonts["small_bold"].render("Load", True, (220, 225, 235))
        lb_title2 = self.fonts["small_bold"].render("Balancer", True, (220, 225, 235))
        surface.blit(lb_title1, (lb_rect.centerx - lb_title1.get_width() // 2, lb_rect.bottom - 28))
        surface.blit(lb_title2, (lb_rect.centerx - lb_title2.get_width() // 2, lb_rect.bottom - 15))

        # 6. Draw Application Servers
        for i, (sx, sy) in enumerate(server_positions):
            srv = sim.servers[i]
            srv_surf = self.assets.get_server_surface(srv.state)
            dest_rect = pygame.Rect(sx - srv_surf.get_width() // 2,
                                    sy - srv_surf.get_height() // 2,
                                    srv_surf.get_width(), srv_surf.get_height())
            surface.blit(srv_surf, dest_rect)

            # Node labels
            name_text = f"Server {srv.server_id:02d}"
            lbl_line1 = self.fonts["normal_bold"].render(name_text, True, (230, 230, 235))
            lbl_line2 = self.fonts["small"].render(srv.state.value, True, (160, 165, 175))
            surface.blit(lbl_line1, (dest_rect.x + 12, dest_rect.y + 10))
            surface.blit(lbl_line2, (dest_rect.x + 12, dest_rect.y + 27))

            # Real-time Load display
            if srv.state in (ServerState.ACTIVE, ServerState.IDLE):
                load_str = f"Load: {srv.active_request_count}/{srv.capacity}"
                load_col = (129, 201, 149) if srv.active_request_count > 0 else (145, 150, 160)
            elif srv.state in (ServerState.BOOTING, ServerState.WAKING):
                load_str = f"Boot: {int(srv.get_boot_progress_pct() * 100)}%"
                load_col = (253, 214, 99)
            else:
                load_str = "Offline"
                load_col = (100, 105, 115)

            lbl_load = self.fonts["small"].render(load_str, True, load_col)
            surface.blit(lbl_load, (dest_rect.x + 12, dest_rect.y + 43))

            # Boot / Wake progress bar
            if srv.state in (ServerState.BOOTING, ServerState.WAKING):
                progress = srv.get_boot_progress_pct()
                bar_rect = pygame.Rect(dest_rect.x + 12, dest_rect.bottom - 10, dest_rect.width - 24, 4)
                pygame.draw.rect(surface, (50, 50, 60), bar_rect, border_radius=2)
                fill_rect = pygame.Rect(bar_rect.x, bar_rect.y, int(bar_rect.width * progress), bar_rect.height)
                pygame.draw.rect(surface, (253, 214, 99), fill_rect, border_radius=2)

        # 7. Spawn & Animate Flying Packets (only spawn and advance when unpaused)
        if not is_paused:
            self._spawn_visual_packets(sim, current_real_time, lb_right_mid, server_positions)
        self._draw_flying_packets(surface, dt, is_paused)

        # Reset clip
        surface.set_clip(prev_clip)

    def _spawn_visual_packets(self, sim: SimulationEngine, current_real_time: float,
                              lb_right_mid: Tuple[int, int], server_positions: List[Tuple[int, int]]):
        # Strict cap on active in-flight packets to prevent performance degradation
        if len(self.active_packets) >= self.max_active_packets:
            return

        if current_real_time - self.last_anim_spawn_time < 0.12:
            return

        active_indices = [i for i, s in enumerate(sim.servers) if s.state == ServerState.ACTIVE]
        if active_indices:
            import random
            target_idx = random.choice(active_indices)
            target_pos = server_positions[target_idx]
            packet = PacketAnimation(
                packet_id=self.next_anim_id,
                start_pos=lb_right_mid,
                end_pos=(target_pos[0] - 30, target_pos[1]),
                start_time=current_real_time,
                duration=0.35,
                server_id=target_idx + 1,
                progress=0.0
            )
            self.next_anim_id += 1
            self.active_packets.append(packet)
            self.last_anim_spawn_time = current_real_time

    def _draw_flying_packets(self, surface: pygame.Surface, dt: float, is_paused: bool):
        packet_img = self.assets.get_image("packet")
        pw, ph = packet_img.get_width(), packet_img.get_height()
        surviving = []
        for p in self.active_packets:
            if not is_paused:
                p.progress += dt / p.duration
            if p.progress < 1.0:
                cur_x = int(p.start_pos[0] + p.progress * (p.end_pos[0] - p.start_pos[0]))
                cur_y = int(p.start_pos[1] + p.progress * (p.end_pos[1] - p.start_pos[1]))
                surface.blit(packet_img, (cur_x - pw // 2, cur_y - ph // 2))
                surviving.append(p)
        self.active_packets = surviving
