"""
Simulation View (Center Canvas).
Renders the cloud traffic generator, queued packets, Load Balancer,
application servers, and animated flying request packets matching the sketch layout.
"""

import math
import time
from typing import List, Tuple
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
        self.next_anim_id = 1
        self.last_anim_spawn_time = 0.0

    def update_and_draw(self, surface: pygame.Surface, sim: SimulationEngine, current_real_time: float):
        canvas_rect = self.layout.center_canvas_rect

        # Calculate server node coordinates dynamically
        server_positions = self.layout.calculate_server_positions(len(sim.servers))

        # 1. Draw Connecting Network Lines (Load Balancer -> Servers)
        lb_right_mid = (self.layout.lb_rect.right, self.layout.lb_rect.centery)
        for i, (sx, sy) in enumerate(server_positions):
            srv = sim.servers[i]
            # Line color based on server status
            if srv.state == ServerState.ACTIVE:
                line_color = (46, 204, 113)  # Green active wire
                line_width = 2
            elif srv.state == ServerState.IDLE:
                line_color = (52, 152, 219)  # Blue wire
                line_width = 2
            elif srv.state in (ServerState.BOOTING, ServerState.WAKING):
                line_color = (243, 156, 18)  # Orange warming wire
                line_width = 1
            else:
                line_color = (190, 195, 205) # Gray dormant wire
                line_width = 1

            pygame.draw.line(surface, line_color, lb_right_mid, (sx - 40, sy), line_width)

        # 2. Draw Wire (Cloud -> Load Balancer)
        cloud_right = (self.layout.cloud_pos[0] + 35, self.layout.cloud_pos[1])
        lb_left_mid = (self.layout.lb_rect.left, self.layout.lb_rect.centery)
        pygame.draw.line(surface, (120, 130, 145), cloud_right, lb_left_mid, 2)

        # 3. Draw Cloud Icon
        cloud_surf = self.assets.get_image("cloud")
        cloud_dest = (self.layout.cloud_pos[0] - cloud_surf.get_width() // 2,
                      self.layout.cloud_pos[1] - cloud_surf.get_height() // 2)
        surface.blit(cloud_surf, cloud_dest)
        cloud_lbl = self.fonts["small"].render("cloud", True, (30, 30, 35))
        surface.blit(cloud_lbl, (self.layout.cloud_pos[0] - cloud_lbl.get_width() // 2,
                                 self.layout.cloud_pos[1] - cloud_lbl.get_height() // 2 + 2))

        # 4. Draw Incoming Queued Packets along the Cloud -> LB path
        queue_count = min(len(sim.request_queue), 6)
        if queue_count > 0:
            packet_img = self.assets.get_image("packet")
            for q_idx in range(queue_count):
                fraction = 0.3 + (q_idx / 8.0)
                px = int(cloud_right[0] + fraction * (lb_left_mid[0] - cloud_right[0]))
                py = int(cloud_right[1] + fraction * (lb_left_mid[1] - cloud_right[1]))
                surface.blit(packet_img, (px - 10, py - 12))

        # 5. Draw Load Balancer
        lb_surf = self.assets.get_image("load_balancer")
        surface.blit(lb_surf, self.layout.lb_rect)
        lb_title1 = self.fonts["small"].render("Load", True, (30, 30, 35))
        lb_title2 = self.fonts["small"].render("Balancer", True, (30, 30, 35))
        surface.blit(lb_title1, (self.layout.lb_rect.centerx - lb_title1.get_width() // 2, self.layout.lb_rect.bottom - 26))
        surface.blit(lb_title2, (self.layout.lb_rect.centerx - lb_title2.get_width() // 2, self.layout.lb_rect.bottom - 14))

        # 6. Draw Application Servers
        for i, (sx, sy) in enumerate(server_positions):
            srv = sim.servers[i]
            srv_surf = self.assets.get_server_surface(srv.state)
            dest_rect = pygame.Rect(sx - srv_surf.get_width() // 2,
                                    sy - srv_surf.get_height() // 2,
                                    srv_surf.get_width(), srv_surf.get_height())
            surface.blit(srv_surf, dest_rect)

            # Server label header
            lbl_line1 = self.fonts["normal"].render("Application", True, (30, 30, 35))
            lbl_line2 = self.fonts["small"].render("server", True, (70, 75, 85))
            surface.blit(lbl_line1, (dest_rect.centerx - lbl_line1.get_width() // 2, dest_rect.y + 12))
            surface.blit(lbl_line2, (dest_rect.centerx - lbl_line2.get_width() // 2, dest_rect.y + 28))

            # Boot / Wake progress bar if transitioning
            if srv.state in (ServerState.BOOTING, ServerState.WAKING):
                progress = srv.get_boot_progress_pct()
                bar_rect = pygame.Rect(dest_rect.x + 10, dest_rect.bottom - 14, dest_rect.width - 20, 6)
                pygame.draw.rect(surface, (210, 215, 220), bar_rect, border_radius=3)
                fill_rect = pygame.Rect(bar_rect.x, bar_rect.y, int(bar_rect.width * progress), bar_rect.height)
                pygame.draw.rect(surface, (243, 156, 18), fill_rect, border_radius=3)
                pygame.draw.rect(surface, (30, 30, 35), bar_rect, width=1, border_radius=3)

        # 7. Spawn & Animate Flying Packets
        self._spawn_visual_packets(sim, current_real_time, lb_right_mid, server_positions)
        self._draw_flying_packets(surface, current_real_time)

    def _spawn_visual_packets(self, sim: SimulationEngine, current_real_time: float,
                              lb_right_mid: Tuple[int, int], server_positions: List[Tuple[int, int]]):
        """Spawns animated flying packets to active servers to represent live throughput."""
        if current_real_time - self.last_anim_spawn_time < 0.12:
            return

        # Find servers currently serving requests
        active_indices = [i for i, s in enumerate(sim.servers) if s.state == ServerState.ACTIVE]
        if active_indices and sim.request_queue or active_indices:
            import random
            target_idx = random.choice(active_indices)
            target_pos = server_positions[target_idx]
            packet = PacketAnimation(
                packet_id=self.next_anim_id,
                start_pos=lb_right_mid,
                end_pos=(target_pos[0] - 30, target_pos[1]),
                start_time=current_real_time,
                duration=0.35,
                server_id=target_idx + 1
            )
            self.next_anim_id += 1
            self.active_packets.append(packet)
            self.last_anim_spawn_time = current_real_time

    def _draw_flying_packets(self, surface: pygame.Surface, current_real_time: float):
        packet_img = self.assets.get_image("packet")
        surviving = []
        for p in self.active_packets:
            if not p.is_finished(current_real_time):
                prog = p.get_progress(current_real_time)
                cur_x = int(p.start_pos[0] + prog * (p.end_pos[0] - p.start_pos[0]))
                cur_y = int(p.start_pos[1] + prog * (p.end_pos[1] - p.start_pos[1]))
                surface.blit(packet_img, (cur_x - 10, cur_y - 12))
                surviving.append(p)
        self.active_packets = surviving
