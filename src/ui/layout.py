"""
Flex-like Screen Layout Engine.
Supports dynamic left, center, right columns with togglable visibility
and responsive center canvas sizing.
"""

from typing import List, Tuple
import math
import pygame


class Layout:
    def __init__(self, screen_width: int = 1280, screen_height: int = 720):
        self.width = screen_width
        self.height = screen_height

        # Top Menu Bar
        self.top_bar_height = 36
        self.top_bar_rect = pygame.Rect(0, 0, self.width, self.top_bar_height)

        # Panel Visibility Toggles
        self.show_racks: bool = True
        self.show_telemetry: bool = True
        self.show_controls: bool = True

        # Column base widths
        self.left_col_base_w = 280
        self.right_col_base_w = 300

        self.recalculate()

    def set_visibility(self, racks: bool = None, telemetry: bool = None, controls: bool = None):
        """Updates visibility flags and recalculates flex geometry."""
        if racks is not None:
            self.show_racks = racks
        if telemetry is not None:
            self.show_telemetry = telemetry
        if controls is not None:
            self.show_controls = controls
        self.recalculate()

    def recalculate(self):
        """Flex-like recalculation of column widths and positions."""
        content_y = self.top_bar_height
        content_h = self.height - self.top_bar_height

        # 1. Left Column (Racks + Telemetry)
        has_left = self.show_racks or self.show_telemetry
        left_w = self.left_col_base_w if has_left else 0
        self.left_panel_rect = pygame.Rect(0, content_y, left_w, content_h)

        if self.show_racks and self.show_telemetry:
            # Split left column: racks top 260px, telemetry takes rest
            racks_h = 260
            self.racks_panel_rect = pygame.Rect(0, content_y, left_w, racks_h)
            self.telemetry_panel_rect = pygame.Rect(0, content_y + racks_h, left_w, content_h - racks_h)
        elif self.show_racks:
            self.racks_panel_rect = pygame.Rect(0, content_y, left_w, content_h)
            self.telemetry_panel_rect = pygame.Rect(0, 0, 0, 0)
        elif self.show_telemetry:
            self.racks_panel_rect = pygame.Rect(0, 0, 0, 0)
            self.telemetry_panel_rect = pygame.Rect(0, content_y, left_w, content_h)
        else:
            self.racks_panel_rect = pygame.Rect(0, 0, 0, 0)
            self.telemetry_panel_rect = pygame.Rect(0, 0, 0, 0)

        # 2. Right Column (Controls HUD)
        right_w = self.right_col_base_w if self.show_controls else 0
        self.right_panel_rect = pygame.Rect(self.width - right_w, content_y, right_w, content_h)

        # 3. Center Canvas (Flexes to fill remaining width!)
        center_x = left_w
        center_w = self.width - left_w - right_w
        self.center_canvas_rect = pygame.Rect(center_x, content_y, center_w, content_h)

        # Dynamic Anchor Points inside Center Canvas
        self.cloud_pos = (self.center_canvas_rect.x + int(center_w * 0.12),
                          self.center_canvas_rect.centery + 60)
        self.lb_rect = pygame.Rect(
            self.center_canvas_rect.x + int(center_w * 0.38),
            self.center_canvas_rect.centery - 60,
            60, 120
        )

    def calculate_server_positions(self, num_servers: int) -> List[Tuple[int, int]]:
        """Dynamically calculates server positions in the flex center canvas."""
        positions = []
        center_x = self.center_canvas_rect.x
        center_y = self.center_canvas_rect.centery
        center_w = self.center_canvas_rect.width

        if num_servers <= 1:
            return [(int(center_x + center_w * 0.75), center_y)]

        # Fan-out arc parameters adapted to flex canvas width
        angle_span = math.radians(110)
        start_angle = -angle_span / 2.0
        radius_x = max(160, int(center_w * 0.30))
        radius_y = max(180, int(self.center_canvas_rect.height * 0.36))

        for i in range(num_servers):
            fraction = i / (num_servers - 1)
            angle = start_angle + fraction * angle_span
            sx = int(self.lb_rect.right + 40 + math.cos(angle) * radius_x)
            sy = int(center_y + math.sin(angle) * radius_y)
            positions.append((sx, sy))

        return positions
