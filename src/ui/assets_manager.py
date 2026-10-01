"""
Asset Manager.
Loads custom PNG sprites from assets/ with automatic procedural
2D vector fallback rendering matching the minimal dark aesthetic.
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
        """Procedurally draws vector components matching the minimal dark aesthetic."""
        if key.startswith("server_"):
            return self._draw_server_fallback(key)
        elif key == "load_balancer":
            return self._draw_load_balancer_fallback()
        elif key == "cloud":
            return self._draw_cloud_fallback()
        elif key == "packet":
            return self._draw_packet_fallback()

        surf = pygame.Surface((64, 64), pygame.SRCALPHA)
        surf.fill((40, 40, 45))
        return surf

    def _draw_server_fallback(self, key: str) -> pygame.Surface:
        w, h = 110, 68
        surf = pygame.Surface((w, h), pygame.SRCALPHA)

        # Base chassis card in dark mode
        card_bg = (38, 38, 44)
        border_color = (60, 60, 70)
        pygame.draw.rect(surf, card_bg, (1, 1, w - 2, h - 2), border_radius=6)
        pygame.draw.rect(surf, border_color, (1, 1, w - 2, h - 2), width=1, border_radius=6)

        # Status LED indicator (glowing dot)
        led_color = {
            "server_active": (129, 201, 149), # Soft Emerald Green
            "server_idle": (138, 180, 248),   # Soft Blue
            "server_boot": (253, 214, 99),    # Amber
            "server_sleep": (197, 138, 249),  # Lavender Purple
            "server_off": (100, 100, 110),    # Slate Gray
        }.get(key, (100, 100, 110))


        # LED halo glow and core
        pygame.draw.circle(surf, (*led_color, 60), (w - 18, 18), 7)
        pygame.draw.circle(surf, led_color, (w - 18, 18), 4)

        # Minimal grill slot accent
        for y in range(40, 52, 5):
            pygame.draw.line(surf, (50, 50, 60), (14, y), (w - 32, y), 1)

        return surf

    def _draw_load_balancer_fallback(self) -> pygame.Surface:
        w, h = 64, 110
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(surf, (36, 36, 42), (1, 1, w - 2, h - 2), border_radius=6)
        pygame.draw.rect(surf, (60, 60, 70), (1, 1, w - 2, h - 2), width=1, border_radius=6)

        # Router distribution nodes
        cx = w // 2
        nodes = [(cx, 28), (cx, 55), (cx, 82)]
        for nx, ny in nodes:
            pygame.draw.circle(surf, (138, 180, 248), (nx, ny), 5)
            pygame.draw.circle(surf, (20, 20, 25), (nx, ny), 5, 1)

        # Connecting link line
        pygame.draw.line(surf, (70, 80, 100), (cx, 33), (cx, 50), 2)
        pygame.draw.line(surf, (70, 80, 100), (cx, 60), (cx, 77), 2)

        return surf

    def _draw_cloud_fallback(self) -> pygame.Surface:
        w, h = 84, 52
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        cloud_color = (40, 44, 52)
        border_color = (80, 90, 110)

        puffs = [
            (30, 30, 16),
            (46, 24, 18),
            (60, 32, 14),
            (42, 36, 15),
            (26, 36, 12),
        ]
        for px, py, r in puffs:
            pygame.draw.circle(surf, cloud_color, (px, py), r)
        for px, py, r in puffs:
            pygame.draw.circle(surf, border_color, (px, py), r, 1)
        return surf

    def _draw_packet_fallback(self) -> pygame.Surface:
        w, h = 18, 22
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        # Minimalist glowing packet card
        pygame.draw.rect(surf, (50, 55, 68), (1, 1, w - 2, h - 2), border_radius=3)
        pygame.draw.rect(surf, (138, 180, 248), (1, 1, w - 2, h - 2), width=1, border_radius=3)
        # Data accent bars
        pygame.draw.line(surf, (138, 180, 248), (4, 6), (w - 4, 6), 1)
        pygame.draw.line(surf, (100, 115, 140), (4, 10), (w - 4, 10), 1)
        pygame.draw.line(surf, (100, 115, 140), (4, 14), (w - 7, 14), 1)
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
