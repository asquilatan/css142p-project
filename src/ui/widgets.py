"""
Interactive UI Widgets for Pygame Control Room.
Styled with the minimalist Dark Theme (#212121) aesthetic.
"""

from typing import Callable, List, Optional
import pygame


class Button:
    def __init__(self, rect: pygame.Rect, text: str, font: pygame.font.Font,
                 callback: Optional[Callable] = None, is_toggle: bool = False,
                 active_bg: tuple = (138, 180, 248), active_text: tuple = (20, 20, 25),
                 inactive_bg: tuple = (40, 40, 46), inactive_text: tuple = (225, 225, 230),
                 border_color: tuple = (60, 60, 70)):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.font = font
        self.callback = callback
        self.is_toggle = is_toggle
        self.is_active = False
        self.is_hovered = False

        self.active_bg = active_bg
        self.active_text = active_text
        self.inactive_bg = inactive_bg
        self.inactive_text = inactive_text
        self.border_color = border_color

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                if self.is_toggle:
                    self.is_active = not self.is_active
                if self.callback:
                    self.callback()
                return True
        return False

    def draw(self, surface: pygame.Surface):
        if self.is_active:
            bg = self.active_bg
            txt_col = self.active_text
        elif self.is_hovered:
            bg = (52, 52, 60)
            txt_col = (255, 255, 255)
        else:
            bg = self.inactive_bg
            txt_col = self.inactive_text

        pygame.draw.rect(surface, bg, self.rect, border_radius=5)
        pygame.draw.rect(surface, self.border_color, self.rect, width=1, border_radius=5)

        text_surf = self.font.render(self.text, True, txt_col)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)


class ButtonGroup:
    """Manages mutually exclusive radio buttons (e.g. Policy)."""
    def __init__(self, buttons: List[Button], initial_index: int = 0, on_change: Optional[Callable] = None):
        self.buttons = buttons
        self.active_index = initial_index
        self.on_change = on_change

        for i, btn in enumerate(self.buttons):
            btn.is_toggle = False
            btn.is_active = (i == initial_index)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            for btn in self.buttons:
                btn.is_hovered = btn.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, btn in enumerate(self.buttons):
                if btn.rect.collidepoint(event.pos):
                    if self.active_index != i:
                        self.active_index = i
                        for j, b in enumerate(self.buttons):
                            b.is_active = (j == i)
                        if self.on_change:
                            self.on_change(i, btn.text)
                        if btn.callback:
                            btn.callback()
                    return True
        return False

    def draw(self, surface: pygame.Surface):
        for btn in self.buttons:
            btn.draw(surface)


class ToggleSwitch:
    """A flip switch matching `Diurnal Auto-Cycle [ flip ]`."""
    def __init__(self, rect: pygame.Rect, label: str, font: pygame.font.Font,
                 initial_state: bool = True, on_toggle: Optional[Callable] = None):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.font = font
        self.is_on = initial_state
        self.on_toggle = on_toggle

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.is_on = not self.is_on
                if self.on_toggle:
                    self.on_toggle(self.is_on)
                return True
        return False

    def draw(self, surface: pygame.Surface):
        label_surf = self.font.render(self.label, True, (220, 225, 235))
        surface.blit(label_surf, (self.rect.x, self.rect.y + 4))

        pill_w, pill_h = 42, 22
        pill_x = self.rect.right - pill_w
        pill_y = self.rect.y + (self.rect.height - pill_h) // 2
        pill_rect = pygame.Rect(pill_x, pill_y, pill_w, pill_h)

        bg_col = (129, 201, 149) if self.is_on else (55, 55, 62)
        pygame.draw.rect(surface, bg_col, pill_rect, border_radius=11)
        pygame.draw.rect(surface, (70, 70, 80), pill_rect, width=1, border_radius=11)

        knob_r = 7
        knob_cx = pill_x + pill_w - 11 if self.is_on else pill_x + 11
        knob_cy = pill_y + 11
        pygame.draw.circle(surface, (255, 255, 255), (knob_cx, knob_cy), knob_r)


class Slider:
    """A horizontal slider with customizable units and integer snapping."""
    def __init__(self, rect: pygame.Rect, min_val: float, max_val: float,
                 initial_val: float, font: pygame.font.Font, label: str = "",
                 unit: str = "x", integer_only: bool = False,
                 on_change: Optional[Callable] = None):
        self.rect = pygame.Rect(rect)
        self.min_val = min_val
        self.max_val = max_val
        self.value = initial_val
        self.font = font
        self.label = label
        self.unit = unit
        self.integer_only = integer_only
        self.on_change = on_change
        self.is_dragging = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.is_dragging = True
                self._update_val(event.pos[0])
                return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.is_dragging:
                self.is_dragging = False
                return True
        elif event.type == pygame.MOUSEMOTION and self.is_dragging:
            self._update_val(event.pos[0])
            return True
        return False

    def _update_val(self, mouse_x: int):
        track_start = self.rect.x + 8
        track_end = self.rect.right - 8
        clamped_x = min(track_end, max(track_start, mouse_x))
        fraction = (clamped_x - track_start) / max(1, track_end - track_start)
        val = self.min_val + fraction * (self.max_val - self.min_val)
        if self.integer_only:
            val = round(val)
        self.value = val
        if self.on_change:
            self.on_change(self.value)

    def draw(self, surface: pygame.Surface):
        if self.label:
            val_str = f"{int(self.value)}" if self.integer_only else f"{self.value:.1f}"
            lbl_surf = self.font.render(f"{self.label}: {val_str}{self.unit}", True, (180, 185, 195))
            surface.blit(lbl_surf, (self.rect.x, self.rect.y - 18))

        track_y = self.rect.centery
        pygame.draw.line(surface, (55, 55, 65), (self.rect.x + 8, track_y), (self.rect.right - 8, track_y), 3)

        fraction = (self.value - self.min_val) / max(0.001, self.max_val - self.min_val)
        handle_x = int(self.rect.x + 8 + fraction * (self.rect.width - 16))
        handle_y = track_y

        pygame.draw.circle(surface, (138, 180, 248), (handle_x, handle_y), 8)
        pygame.draw.circle(surface, (20, 20, 25), (handle_x, handle_y), 3)
