"""
Top Menu Bar with Dropdown.
Provides application-level navigation and toggles:
- "Show Data Center Racks"
- "Show Real Time Telemetry"
- "Show Controls Hud"
- "Settings"
"""

from typing import Callable
import pygame
from src.ui.layout import Layout


class MenuBar:
    def __init__(self, layout: Layout, fonts: dict,
                 on_toggle_racks: Callable,
                 on_toggle_telemetry: Callable,
                 on_toggle_controls: Callable,
                 on_open_settings: Callable):
        self.layout = layout
        self.fonts = fonts
        self.on_toggle_racks = on_toggle_racks
        self.on_toggle_telemetry = on_toggle_telemetry
        self.on_toggle_controls = on_toggle_controls
        self.on_open_settings = on_open_settings

        # Menu trigger button
        self.menu_btn_rect = pygame.Rect(12, 6, 68, 24)
        self.is_open = False
        self.is_hovered = False

        # Dropdown items
        self.dropdown_w = 230
        self.item_h = 32
        self.items = [
            {"id": "racks", "label": "Show Data Center Racks", "checked": True},
            {"id": "telemetry", "label": "Show Real Time Telemetry", "checked": True},
            {"id": "controls", "label": "Show Controls Hud", "checked": True},
            {"id": "settings", "label": "⚙ Settings", "checked": None},  # Action item
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
            # Click Menu button
            if self.menu_btn_rect.collidepoint(event.pos):
                self.is_open = not self.is_open
                return True

            # Click inside dropdown
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
                    elif item["id"] == "settings":
                        self.is_open = False
                        self.on_open_settings()
                    return True

            # Click outside closes menu
            if self.is_open:
                self.is_open = False
                return True

        return False

    def draw(self, surface: pygame.Surface):
        top_rect = self.layout.top_bar_rect
        border_col = (25, 25, 30)

        # Bar background
        pygame.draw.rect(surface, (245, 247, 250), top_rect)
        pygame.draw.line(surface, border_col, (0, top_rect.bottom), (top_rect.right, top_rect.bottom), 1)

        # Menu Button
        btn_bg = (230, 235, 242) if (self.is_hovered or self.is_open) else (245, 247, 250)
        pygame.draw.rect(surface, btn_bg, self.menu_btn_rect, border_radius=4)
        if self.is_hovered or self.is_open:
            pygame.draw.rect(surface, border_col, self.menu_btn_rect, width=1, border_radius=4)

        btn_txt = self.fonts["normal"].render("Menu ▾", True, (30, 35, 45))
        surface.blit(btn_txt, (self.menu_btn_rect.x + 8, self.menu_btn_rect.y + 4))

        # Title / Project Header in top bar
        title_surf = self.fonts["small_bold"].render(
            "Discrete-Event Server Provisioning Simulator — CSS142",
            True, (100, 105, 115)
        )
        surface.blit(title_surf, (top_rect.centerx - title_surf.get_width() // 2, top_rect.y + 10))

        # Dropdown Menu
        if self.is_open:
            dr = self.dropdown_rect
            # Drop shadow
            shadow_rect = pygame.Rect(dr.x + 3, dr.y + 3, dr.width, dr.height)
            pygame.draw.rect(surface, (180, 185, 195), shadow_rect, border_radius=6)

            # Dropdown body
            pygame.draw.rect(surface, (255, 255, 255), dr, border_radius=6)
            pygame.draw.rect(surface, border_col, dr, width=2, border_radius=6)

            for i, item in enumerate(self.items):
                item_y = dr.y + 4 + i * self.item_h
                item_rect = pygame.Rect(dr.x + 4, item_y, dr.width - 8, self.item_h)

                if i == self.hovered_item_idx:
                    pygame.draw.rect(surface, (235, 240, 248), item_rect, border_radius=4)

                # Checkmark or bullet
                if item["checked"] is True:
                    check_surf = self.fonts["normal_bold"].render("✓", True, (46, 204, 113))
                    surface.blit(check_surf, (item_rect.x + 10, item_rect.y + 6))
                elif item["checked"] is False:
                    box_rect = pygame.Rect(item_rect.x + 10, item_rect.y + 8, 14, 14)
                    pygame.draw.rect(surface, (180, 185, 195), box_rect, width=1, border_radius=2)

                # Label text
                label_color = (25, 30, 40)
                lbl_surf = self.fonts["normal"].render(item["label"], True, label_color)
                surface.blit(lbl_surf, (item_rect.x + 32, item_rect.y + 7))
