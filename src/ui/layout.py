"""
Screen Layout Geometry & Dynamic Topology Coordinates.
Computes bounding boxes and dynamic radial positions for servers matching the sketch layout.
"""

import math
from typing import List, Tuple
import pygame


class Layout:
    def __init__(self, screen_width: int = 1280, screen_height: int = 720):
        self.width = screen_width
        self.height = screen_height

        # Left panel (Racks & Telemetry)
        self.left_panel_w = 260
        self.left_panel_rect = pygame.Rect(0, 0, self.left_panel_w, self.height)
        self.racks_panel_rect = pygame.Rect(0, 0, self.left_panel_w, 290)
        self.telemetry_panel_rect = pygame.Rect(0, 290, self.left_panel_w, self.height - 290)

        # Right panel (Controls HUD)
        self.right_panel_w = 270
        self.right_panel_rect = pygame.Rect(self.width - self.right_panel_w, 0, self.right_panel_w, self.height)

        # Center Canvas (Simulation View)
        self.center_canvas_rect = pygame.Rect(
            self.left_panel_w, 0,
            self.width - self.left_panel_w - self.right_panel_w,
            self.height
        )

        # Fixed Key Topology Anchor Points inside Center Canvas
        self.cloud_pos = (self.center_canvas_rect.x + 65, self.center_canvas_rect.centery + 70)
        self.lb_rect = pygame.Rect(
            self.center_canvas_rect.x + 220,
            self.center_canvas_rect.centery - 60,
            55, 120
        )

    def calculate_server_positions(self, num_servers: int) -> List[Tuple[int, int]]:
        """
        Dynamically calculates (x, y) center coordinates for application servers.
        Fans out neatly to the right of the Load Balancer in an arc or vertical spread.
        """
        positions = []
        center_x = self.lb_rect.right + 180
        center_y = self.center_canvas_rect.centery

        if num_servers <= 1:
            return [(center_x, center_y)]

        # Fan-out arc parameters
        angle_span = math.radians(110)  # Spread across 110 degrees
        start_angle = -angle_span / 2.0
        radius_x = 220
        radius_y = 230

        for i in range(num_servers):
            fraction = i / (num_servers - 1)
            angle = start_angle + fraction * angle_span
            sx = int(self.lb_rect.right + 70 + math.cos(angle) * radius_x)
            sy = int(center_y + math.sin(angle) * radius_y)
            positions.append((sx, sy))

        return positions
