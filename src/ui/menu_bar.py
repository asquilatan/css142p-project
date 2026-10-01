"""
Top Menu Bar with Dropdown.
Provides application-level navigation and toggles in minimalist dark aesthetic.
"""

from typing import Callable, Optional
import pygame
from src.ui.layout import Layout
from src.ui.assets_manager import AssetsManager
from src.ui.widgets import render_cached


class MenuBar:
    def __init__(self, layout: Layout, fonts: dict,
                 on_toggle_racks: Callable,
                 on_toggle_telemetry: Callable,
                 on_toggle_controls: Callable,
                 on_reset_layout: Callable,
                 on_open_settings: Callable,
                 assets: Optional[AssetsManager] = None):
        self.layout = layout
        self.fonts = fonts
        self.assets = assets
        self.on_toggle_racks = on_toggle_racks
        self.on_toggle_telemetry = on_toggle_telemetry
        self.on_toggle_controls = on_toggle_controls
        self.on_reset_layout = on_reset_layout
        self.on_open_settings = on_open_settings

        self.menu_btn_rect = pygame.Rect(12, 6, 78, 24)
        self.is_open = False
        self.is_hovered = False

        self.dropdown_w = 240
        self.item_h = 32
        self.items = [
            {"id": "racks", "label": "Show Data Center Racks", "checked": True},
            {"id": "telemetry", "label": "Show Real Time Telemetry", "checked": True},
            {"id": "controls", "label": "Show Controls Hud", "checked": True},
            {"id": "reset_layout", "label": "↺ Reset Node Positions", "checked": None},
            {"id": "settings", "label": "⚙ Settings", "checked": None},
        ]
        self.hovered_item_idx = -1

    @property
    def dropdown_rect(self) -> pygame.Rect:
        return pygame.Rect(
            self.menu_btn_rect.x,
            self.layout.top_bar_height,
            self.dropdown_w,
            len(self.items) * self.item_h + 8
        )

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            self.is_hovered = self.menu_btn_rect.collidepoint(event.pos)
            if self.is_open:
                dr = self.dropdown_rect
                if dr.collidepoint(event.pos):
                    rel_y = event.pos[1] - (dr.y + 4)
                    self.hovered_item_idx = rel_y // self.item_h
                    if self.hovered_item_idx < 0 or self.hovered_item_idx >= len(self.items):
                        self.hovered_item_idx = -1
                else:
                    self.hovered_item_idx = -1
            return False

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.menu_btn_rect.collidepoint(event.pos):
                self.is_open = not self.is_open
                return True

            if self.is_open and self.dropdown_rect.collidepoint(event.pos):
                if 0 <= self.hovered_item_idx < len(self.items):
                    item = self.items[self.hovered_item_idx]
                    if item["id"] == "racks":
                        item["checked"] = not item["checked"]
                        self.on_toggle_racks(item["checked"])
                    elif item["id"] == "telemetry":
                        item["checked"] = not item["checked"]
                        self.on_toggle_telemetry(item["checked"])
                    elif item["id"] == "controls":
                        item["checked"] = not item["checked"]
                        self.on_toggle_controls(item["checked"])
                    elif item["id"] == "reset_layout":
                        self.is_open = False
                        self.on_reset_layout()
                    elif item["id"] == "settings":
                        self.is_open = False
                        self.on_open_settings()
                    return True

            if self.is_open:
                self.is_open = False
                return True

        return False

    def draw(self, surface: pygame.Surface):
        top_rect = self.layout.top_bar_rect
        border_col = (48, 48, 54)

        # Bar background
        pygame.draw.rect(surface, (24, 24, 26), top_rect)
        pygame.draw.line(surface, border_col, (0, top_rect.bottom), (top_rect.right, top_rect.bottom), 1)

        # Menu Button
        btn_bg = (44, 44, 52) if (self.is_hovered or self.is_open) else (34, 34, 40)
        pygame.draw.rect(surface, btn_bg, self.menu_btn_rect, border_radius=4)
        if self.is_hovered or self.is_open:
            pygame.draw.rect(surface, (80, 80, 95), self.menu_btn_rect, width=1, border_radius=4)

        # Draw icon (from assets if available, or procedural 3-line hamburger icon)
        menu_icon = self.assets.get_icon("icon_menu") if self.assets else None
        if menu_icon:
            surface.blit(menu_icon, (self.menu_btn_rect.x + 8, self.menu_btn_rect.centery - menu_icon.get_height() // 2))
        else:
            ix = self.menu_btn_rect.x + 9
            iy = self.menu_btn_rect.centery
            col = (230, 230, 235)
            pygame.draw.line(surface, col, (ix, iy - 4), (ix + 11, iy - 4), 2)
            pygame.draw.line(surface, col, (ix, iy),     (ix + 11, iy),     2)
            pygame.draw.line(surface, col, (ix, iy + 4), (ix + 11, iy + 4), 2)

        btn_txt = render_cached(self.fonts["normal"], "Menu", (230, 230, 235))
        surface.blit(btn_txt, (self.menu_btn_rect.x + 26, self.menu_btn_rect.y + 4))

        # Title
        title_surf = render_cached(
            self.fonts["small_bold"],
            "Discrete-Event Server Provisioning Simulator — CSS142",
            (140, 145, 155)
        )
        surface.blit(title_surf, (top_rect.centerx - title_surf.get_width() // 2, top_rect.y + 10))

        # Dropdown Menu
        if self.is_open:
            dr = self.dropdown_rect
            shadow_rect = pygame.Rect(dr.x + 3, dr.y + 3, dr.width, dr.height)
            pygame.draw.rect(surface, (10, 10, 12), shadow_rect, border_radius=6)

            pygame.draw.rect(surface, (30, 30, 35), dr, border_radius=6)
            pygame.draw.rect(surface, (60, 60, 70), dr, width=1, border_radius=6)

            for i, item in enumerate(self.items):
                item_y = dr.y + 4 + i * self.item_h
                item_rect = pygame.Rect(dr.x + 4, item_y, dr.width - 8, self.item_h)

                if i == self.hovered_item_idx:
                    pygame.draw.rect(surface, (44, 44, 52), item_rect, border_radius=4)

                if item["checked"] is True:
                    check_surf = render_cached(self.fonts["normal_bold"], "✓", (129, 201, 149))
                    surface.blit(check_surf, (item_rect.x + 10, item_rect.y + 6))
                elif item["checked"] is False:
                    box_rect = pygame.Rect(item_rect.x + 10, item_rect.y + 8, 14, 14)
                    pygame.draw.rect(surface, (80, 80, 90), box_rect, width=1, border_radius=2)

                lbl_surf = render_cached(self.fonts["normal"], item["label"], (225, 225, 230))
                surface.blit(lbl_surf, (item_rect.x + 32, item_rect.y + 7))
