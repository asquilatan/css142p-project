"""
Asset Manager.
Loads custom PNG sprites from assets/ with automatic procedural
2D vector fallback rendering matching the architectural sketch aesthetic.
"""

import os
import pygame
from src.server import ServerState


class AssetsManager:
    def __init__(self, assets_dir: str = "assets"):
        self.assets_dir = assets_dir
        self.images = {}
        self._load_or_generate_assets()

    def _load_or_generate_assets(self):
        """Attempts to load PNG files from assets_dir, otherwise generates procedural fallback surfaces."""
        asset_keys = [
            "server_active",
            "server_idle",
            "server_boot",
            "server_sleep",
            "server_off",
            "load_balancer",
            "cloud",
            "packet",
        ]

        for key in asset_keys:
            path = os.path.join(self.assets_dir, f"{key}.png")
            if os.path.exists(path):
                try:
                    surf = pygame.image.load(path).convert_alpha()
                    self.images[key] = surf
                    continue
                except Exception as e:
                    print(f"Warning: Failed to load {path}: {e}")

            # Generate high-quality procedural vector fallback
            self.images[key] = self._create_procedural_fallback(key)

    def _create_procedural_fallback(self, key: str) -> pygame.Surface:
        """Procedurally draws vector components matching the architectural sketch."""
        if key.startswith("server_"):
            return self._draw_server_fallback(key)
        elif key == "load_balancer":
            return self._draw_load_balancer_fallback()
        elif key == "cloud":
            return self._draw_cloud_fallback()
        elif key == "packet":
            return self._draw_packet_fallback()

        surf = pygame.Surface((64, 64), pygame.SRCALPHA)
        surf.fill((200, 200, 200))
        return surf

    def _draw_server_fallback(self, key: str) -> pygame.Surface:
        w, h = 100, 70
        surf = pygame.Surface((w, h), pygame.SRCALPHA)

        # Base chassis rectangle
        bg_color = (245, 245, 248)
        border_color = (25, 25, 30)
        pygame.draw.rect(surf, bg_color, (2, 2, w - 4, h - 4), border_radius=4)
        pygame.draw.rect(surf, border_color, (2, 2, w - 4, h - 4), width=2, border_radius=4)

        # Grill lines
        for y in range(16, h - 16, 8):
            pygame.draw.line(surf, (210, 215, 225), (12, y), (w - 32, y), 1)

        # Status LED indicator
        led_color = {
            "server_active": (46, 204, 113),  # Vivid Green
            "server_idle": (52, 152, 219),    # Blue
            "server_boot": (243, 156, 18),    # Amber
            "server_sleep": (155, 89, 182),   # Purple
            "server_off": (149, 165, 166),    # Gray
        }.get(key, (149, 165, 166))

        pygame.draw.circle(surf, led_color, (w - 18, 18), 5)
        pygame.draw.circle(surf, border_color, (w - 18, 18), 5, 1)

        return surf

    def _draw_load_balancer_fallback(self) -> pygame.Surface:
        w, h = 60, 110
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(surf, (240, 242, 245), (2, 2, w - 4, h - 4), border_radius=4)
        pygame.draw.rect(surf, (25, 25, 30), (2, 2, w - 4, h - 4), width=2, border_radius=4)

        # Internal distributor circles and routing arrows
        cx = w // 2
        nodes = [(cx, 30), (cx, 55), (cx, 80)]
        for nx, ny in nodes:
            pygame.draw.circle(surf, (100, 110, 130), (nx, ny), 6)
            pygame.draw.circle(surf, (25, 25, 30), (nx, ny), 6, 1)

        # Connecting routing arrows
        pygame.draw.line(surf, (50, 50, 60), (cx, 36), (cx, 49), 2)
        pygame.draw.line(surf, (50, 50, 60), (cx, 61), (cx, 74), 2)

        return surf

    def _draw_cloud_fallback(self) -> pygame.Surface:
        w, h = 80, 50
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        # Cloud puffs
        puffs = [
            (28, 28, 16),
            (44, 22, 18),
            (56, 30, 14),
            (38, 34, 15),
            (24, 34, 12),
        ]
        for px, py, r in puffs:
            pygame.draw.circle(surf, (215, 228, 240), (px, py), r)
        for px, py, r in puffs:
            pygame.draw.circle(surf, (25, 25, 30), (px, py), r, 2)
        return surf

    def _draw_packet_fallback(self) -> pygame.Surface:
        w, h = 20, 24
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        # Document sheet icon
        pygame.draw.rect(surf, (255, 255, 255), (2, 2, w - 4, h - 4), border_radius=2)
        pygame.draw.rect(surf, (30, 30, 40), (2, 2, w - 4, h - 4), width=1, border_radius=2)
        # Text lines
        pygame.draw.line(surf, (120, 130, 145), (5, 7), (w - 5, 7), 1)
        pygame.draw.line(surf, (120, 130, 145), (5, 11), (w - 5, 11), 1)
        pygame.draw.line(surf, (120, 130, 145), (5, 15), (w - 8, 15), 1)
        return surf

    def get_server_surface(self, state: ServerState) -> pygame.Surface:
        mapping = {
            ServerState.ACTIVE: "server_active",
            ServerState.IDLE: "server_idle",
            ServerState.BOOTING: "server_boot",
            ServerState.WAKING: "server_boot",
            ServerState.SLEEPING: "server_sleep",
            ServerState.OFF: "server_off",
        }
        key = mapping.get(state, "server_off")
        return self.images.get(key, self.images["server_off"])

    def get_image(self, key: str) -> pygame.Surface:
        return self.images.get(key, self.images.get("server_off"))
