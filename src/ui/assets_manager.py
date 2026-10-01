"""
Asset Manager.
Loads custom PNG sprites from assets/ with plain geometric square fallbacks.
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
        """Attempts to load PNG files from assets_dir, otherwise generates plain square fallback surfaces."""
        asset_keys = [
            "server_active",
            "server_idle",
            "server_boot",
            "server_sleep",
            "server_off",
            "load_balancer",
            "cloud",
            "packet",
            "icon_menu",
            "icon_play",
            "icon_pause",
            "icon_reset",
            "icon_drop",
            "icon_surge",
            "icon_graphs",
            "icon_settings",
            "icon_close",
        ]

        for key in asset_keys:
            path = os.path.join(self.assets_dir, f"{key}.png")
            if os.path.exists(path):
                try:
                    surf = pygame.image.load(path)
                    if pygame.display.get_surface():
                        surf = surf.convert_alpha()
                    if key == "packet":
                        # 0.5x scale for request packet
                        new_w = max(1, int(surf.get_width() * 0.5))
                        new_h = max(1, int(surf.get_height() * 0.5))
                        surf = pygame.transform.smoothscale(surf, (new_w, new_h))
                    self.images[key] = surf
                    continue
                except Exception as e:
                    print(f"Warning: Failed to load {path}: {e}")

            # Generate plain square vector fallback
            self.images[key] = self._create_procedural_fallback(key)

    def _create_procedural_fallback(self, key: str) -> pygame.Surface:
        """Procedurally draws plain square components with clean 1px borders."""
        if key.startswith("server_"):
            return self._draw_server_fallback(key)
        elif key == "load_balancer":
            return self._draw_load_balancer_fallback()
        elif key == "cloud":
            return self._draw_cloud_fallback()
        elif key == "packet":
            return self._draw_packet_fallback()
        elif key.startswith("icon_"):
            return self._create_icon_fallback(key)

        surf = pygame.Surface((64, 64), pygame.SRCALPHA)
        surf.fill((36, 36, 42))
        pygame.draw.rect(surf, (65, 65, 75), (0, 0, 64, 64), 1)
        return surf

    def _create_icon_fallback(self, key: str) -> pygame.Surface:
        surf = pygame.Surface((16, 16), pygame.SRCALPHA)
        col = (220, 225, 235)
        if key == "icon_menu":
            pygame.draw.line(surf, col, (2, 4), (14, 4), 2)
            pygame.draw.line(surf, col, (2, 8), (14, 8), 2)
            pygame.draw.line(surf, col, (2, 12), (14, 12), 2)
        elif key == "icon_play":
            pygame.draw.polygon(surf, (129, 201, 149), [(4, 2), (13, 8), (4, 14)])
        elif key == "icon_pause":
            pygame.draw.line(surf, (240, 240, 245), (5, 3), (5, 13), 2)
            pygame.draw.line(surf, (240, 240, 245), (11, 3), (11, 13), 2)
        elif key == "icon_reset":
            pygame.draw.arc(surf, (180, 185, 195), (2, 2, 12, 12), 0.5, 5.5, 2)
            pygame.draw.polygon(surf, (180, 185, 195), [(10, 2), (14, 5), (10, 8)])
        elif key == "icon_drop":
            pygame.draw.polygon(surf, (242, 139, 130), [(3, 4), (13, 4), (8, 12)])
        elif key == "icon_surge":
            pygame.draw.polygon(surf, (253, 214, 99), [(9, 1), (4, 8), (8, 8), (7, 15), (12, 7), (8, 7)])
        elif key == "icon_graphs":
            pygame.draw.lines(surf, (138, 180, 248), False, [(2, 12), (6, 5), (10, 9), (14, 3)], 2)
        elif key == "icon_settings":
            pygame.draw.rect(surf, (180, 185, 195), (4, 4, 8, 8), 1)
            pygame.draw.circle(surf, (180, 185, 195), (8, 8), 2)
        elif key == "icon_close":
            pygame.draw.line(surf, (200, 200, 210), (3, 3), (13, 13), 2)
            pygame.draw.line(surf, (200, 200, 210), (13, 3), (3, 13), 2)
        return surf

    def get_icon(self, key: str) -> Optional[pygame.Surface]:
        return self.images.get(key)

    def _draw_server_fallback(self, key: str) -> pygame.Surface:
        # Plain square for server node
        w, h = 112, 72
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        card_bg = (38, 38, 44)

        # Subtle state-tinted border
        border_color = {
            "server_active": (129, 201, 149),
            "server_idle": (138, 180, 248),
            "server_boot": (253, 214, 99),
            "server_sleep": (197, 138, 249),
            "server_off": (65, 65, 75),
        }.get(key, (65, 65, 75))

        pygame.draw.rect(surf, card_bg, (0, 0, w, h), border_radius=4)
        pygame.draw.rect(surf, border_color, (0, 0, w, h), width=1, border_radius=4)
        return surf

    def _draw_load_balancer_fallback(self) -> pygame.Surface:
        # Plain vertical box for Load Balancer
        w, h = 64, 110
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(surf, (34, 34, 40), (0, 0, w, h), border_radius=4)
        pygame.draw.rect(surf, (138, 180, 248), (0, 0, w, h), width=1, border_radius=4)
        return surf

    def _draw_cloud_fallback(self) -> pygame.Surface:
        # Plain box for Cloud
        w, h = 84, 52
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(surf, (36, 36, 42), (0, 0, w, h), border_radius=4)
        pygame.draw.rect(surf, (80, 85, 95), (0, 0, w, h), width=1, border_radius=4)
        return surf

    def _draw_packet_fallback(self) -> pygame.Surface:
        # Plain small square for packet (0.5x size)
        w, h = 9, 9
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(surf, (138, 180, 248), (0, 0, w, h), border_radius=1)
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
