"""
Interactive UI Widgets for Pygame Control Room.
Styled with the minimalist Dark Theme (#212121) aesthetic.
"""

from typing import Callable, Dict, List, Optional, Tuple
import pygame


# -------------------------------------------------------------------------
# Shared font-render cache.
# font.render() rasterizes glyphs on the CPU every call; view draw methods
# run at 60 FPS, so identical (font, text, color) triples are memoized here.
# Call sites are behavior-identical: same Surface content, far fewer raster ops.
# -------------------------------------------------------------------------
_render_cache: Dict[Tuple[int, str, Tuple[int, int, int]], pygame.Surface] = {}
_RENDER_CACHE_MAX = 1024


def render_cached(font: pygame.font.Font, text: str, color: tuple) -> pygame.Surface:
    """Returns a cached raster of font.render(text, True, color)."""
    key = (id(font), text, tuple(color))
    surf = _render_cache.get(key)
    if surf is None:
        surf = font.render(text, True, tuple(color))
        if len(_render_cache) >= _RENDER_CACHE_MAX:
            _render_cache.clear()
        _render_cache[key] = surf
    return surf


def clear_render_cache() -> None:
    """Drops all cached text surfaces (e.g. after a font reload)."""
    _render_cache.clear()


class Button:
    def __init__(self, rect: pygame.Rect, text: str, font: pygame.font.Font,
                 callback: Optional[Callable] = None, is_toggle: bool = False,
                 active_bg: tuple = (138, 180, 248), active_text: tuple = (20, 20, 25),
                 inactive_bg: tuple = (40, 40, 46), inactive_text: tuple = (225, 225, 230),
                 border_color: tuple = (60, 60, 70),
                 icon: Optional[pygame.Surface] = None):
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
        self.icon = icon

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

        if self.icon:
            if self.text:
                iw = self.icon.get_width()
                text_surf = render_cached(self.font, self.text, txt_col)
                tw = text_surf.get_width()
                total_w = iw + 6 + tw
                start_x = self.rect.centerx - total_w // 2
                surface.blit(self.icon, (start_x, self.rect.centery - self.icon.get_height() // 2))
                surface.blit(text_surf, (start_x + iw + 6, self.rect.centery - text_surf.get_height() // 2))
            else:
                surface.blit(self.icon, self.icon.get_rect(center=self.rect.center))
        else:
            text_surf = render_cached(self.font, self.text, txt_col)
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
        label_surf = render_cached(self.font, self.label, (220, 225, 235))
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
            lbl_surf = render_cached(self.font, f"{self.label}: {val_str}{self.unit}", (180, 185, 195))
            surface.blit(lbl_surf, (self.rect.x, self.rect.y - 18))

        track_y = self.rect.centery
        pygame.draw.line(surface, (55, 55, 65), (self.rect.x + 8, track_y), (self.rect.right - 8, track_y), 3)

        fraction = (self.value - self.min_val) / max(0.001, self.max_val - self.min_val)
        handle_x = int(self.rect.x + 8 + fraction * (self.rect.width - 16))
        handle_y = track_y

        pygame.draw.circle(surface, (138, 180, 248), (handle_x, handle_y), 8)
        pygame.draw.circle(surface, (20, 20, 25), (handle_x, handle_y), 3)


class NumberField:
    """A single numeric text field: click to focus, type digits, Enter to
    commit, Escape to revert. While focused it consumes ALL key presses so
    global shortcuts (Space, F, G, ...) never fire mid-typing."""
    def __init__(self, rect: pygame.Rect, font: pygame.font.Font,
                 initial_value: int = 1, min_val: int = 1, max_val: int = 500,
                 on_change: Optional[Callable[[float], None]] = None):
        self.rect = pygame.Rect(rect)
        self.font = font
        self.min_val = int(min_val)
        self.max_val = int(max_val)
        self.value = max(self.min_val, min(self.max_val, int(initial_value)))
        self.text = str(self.value)
        self.on_change = on_change
        self.is_focused = False

    def set_value(self, value: float, notify: bool = False):
        clamped = max(self.min_val, min(self.max_val, int(value)))
        self.value = clamped
        self.text = str(clamped)
        if notify and self.on_change:
            self.on_change(float(clamped))

    def _commit(self):
        raw = "".join(ch for ch in self.text if ch.isdigit())
        self.set_value(int(raw) if raw else self.min_val, notify=True)
        self.is_focused = False

    def _revert(self):
        self.text = str(self.value)
        self.is_focused = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.is_focused = True
                return True
            if self.is_focused:
                self._revert()
            return False
        if event.type == pygame.KEYDOWN and self.is_focused:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._commit()
            elif event.key == pygame.K_ESCAPE:
                self._revert()
            elif event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.unicode and event.unicode.isdigit() and len(self.text) < 4:
                self.text += event.unicode
            return True
        return False

    def draw(self, surface: pygame.Surface):
        bg = (30, 30, 38) if self.is_focused else (26, 26, 32)
        border = (138, 180, 248) if self.is_focused else (55, 55, 65)
        pygame.draw.rect(surface, bg, self.rect, border_radius=4)
        pygame.draw.rect(surface, border, self.rect, width=1 if not self.is_focused else 2,
                         border_radius=4)

        shown = self.text if (self.is_focused or self.text) else str(self.value)
        txt_surf = render_cached(self.font, shown if shown else " ", (240, 240, 250))
        surface.blit(txt_surf, (self.rect.x + 8, self.rect.centery - txt_surf.get_height() // 2))

        if self.is_focused:
            import time
            if int(time.time() * 2) % 2 == 0:
                cx = self.rect.x + 8 + txt_surf.get_width() + 2
                pygame.draw.line(surface, (138, 180, 248),
                                 (cx, self.rect.y + 5), (cx, self.rect.bottom - 5), 2)


class NumberStepper:
    """An integer number stepper with [-] and [+] buttons and clear integer display."""
    def __init__(self, rect: pygame.Rect, min_val: int, max_val: int, initial_val: int,
                 font: pygame.font.Font, label: str = "", unit: str = " Nodes",
                 on_change: Optional[Callable[[int], None]] = None):
        self.rect = pygame.Rect(rect)
        self.min_val = int(min_val)
        self.max_val = int(max_val)
        self.value = int(initial_val)
        self.font = font
        self.label = label
        self.unit = unit
        self.on_change = on_change

        btn_w = 30
        self.dec_btn = Button(
            pygame.Rect(self.rect.right - btn_w * 2 - 86, self.rect.y, btn_w, self.rect.height),
            text="-",
            font=font,
            callback=self.decrement,
            inactive_bg=(40, 40, 48),
            inactive_text=(220, 220, 230),
            border_color=(65, 65, 75)
        )
        self.val_rect = pygame.Rect(self.rect.right - btn_w - 82, self.rect.y, 78, self.rect.height)
        self.inc_btn = Button(
            pygame.Rect(self.rect.right - btn_w, self.rect.y, btn_w, self.rect.height),
            text="+",
            font=font,
            callback=self.increment,
            inactive_bg=(40, 40, 48),
            inactive_text=(220, 220, 230),
            border_color=(65, 65, 75)
        )

    def decrement(self):
        if self.value > self.min_val:
            self.value -= 1
            if self.on_change:
                self.on_change(self.value)

    def increment(self):
        if self.value < self.max_val:
            self.value += 1
            if self.on_change:
                self.on_change(self.value)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if self.dec_btn.handle_event(event):
            return True
        if self.inc_btn.handle_event(event):
            return True
        return False

    def draw(self, surface: pygame.Surface):
        if self.label:
            lbl_surf = render_cached(self.font, self.label, (180, 185, 195))
            surface.blit(lbl_surf, (self.rect.x, self.rect.centery - lbl_surf.get_height() // 2))

        # Centered value display
        pygame.draw.rect(surface, (30, 30, 36), self.val_rect, border_radius=4)
        pygame.draw.rect(surface, (55, 55, 65), self.val_rect, width=1, border_radius=4)
        val_surf = render_cached(self.font, f"{self.value}{self.unit}", (240, 240, 250))
        surface.blit(val_surf, val_surf.get_rect(center=self.val_rect.center))

        self.dec_btn.draw(surface)
        self.inc_btn.draw(surface)


class DurationInputs:
    """
    4-field numeric duration input widget:
    [ _ ] months   [ _ ] days   [ _ ] hours   [ _ ] minutes
    Defaults to zero if blank.
    """
    def __init__(self, rect: pygame.Rect, fonts: dict,
                 initial_hours: int = 1, initial_minutes: int = 0,
                 on_change: Optional[Callable[[float], None]] = None):
        self.rect = pygame.Rect(rect)
        self.fonts = fonts
        self.on_change = on_change

        self.labels = ["Months", "Days", "Hours", "Minutes"]
        # String representation allows typing, backspace, blank
        self.values = ["0", "0", str(initial_hours), str(initial_minutes)]
        self.active_field: Optional[int] = None

        field_count = 4
        gap = 12
        total_w = self.rect.width
        box_w = (total_w - (field_count - 1) * gap) // field_count
        box_h = 32

        self.field_rects = []
        for i in range(field_count):
            fx = self.rect.x + i * (box_w + gap)
            fy = self.rect.y + 24
            self.field_rects.append(pygame.Rect(fx, fy, box_w, box_h))

    def get_total_minutes(self) -> float:
        mo = int(self.values[0]) if self.values[0].strip().isdigit() else 0
        d = int(self.values[1]) if self.values[1].strip().isdigit() else 0
        h = int(self.values[2]) if self.values[2].strip().isdigit() else 0
        m = int(self.values[3]) if self.values[3].strip().isdigit() else 0
        return float((mo * 30 * 24 * 60) + (d * 24 * 60) + (h * 60) + m)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            clicked_any = False
            for i, r in enumerate(self.field_rects):
                if r.collidepoint(event.pos):
                    self.active_field = i
                    clicked_any = True
                    return True
            if not clicked_any and self.rect.collidepoint(event.pos):
                self.active_field = None
                return True
            elif not clicked_any:
                self.active_field = None

        elif event.type == pygame.KEYDOWN and self.active_field is not None:
            idx = self.active_field
            if event.key == pygame.K_BACKSPACE:
                self.values[idx] = self.values[idx][:-1]
                if self.on_change:
                    self.on_change(self.get_total_minutes())
                return True
            elif event.key == pygame.K_TAB:
                self.active_field = (idx + 1) % 4
                return True
            elif event.key in (pygame.K_RIGHT, pygame.K_DOWN):
                self.active_field = (idx + 1) % 4
                return True
            elif event.key in (pygame.K_LEFT, pygame.K_UP):
                self.active_field = (idx - 1) % 4
                return True
            elif event.unicode.isdigit():
                if len(self.values[idx]) < 4:
                    if self.values[idx] == "0":
                        self.values[idx] = event.unicode
                    else:
                        self.values[idx] += event.unicode
                    if self.on_change:
                        self.on_change(self.get_total_minutes())
                    return True

        return False

    def draw(self, surface: pygame.Surface):
        # Section title
        title_surf = render_cached(
            self.fonts["normal"],
            "Target Run Duration (defaults to 0 if blank):", (215, 220, 230)
        )
        surface.blit(title_surf, (self.rect.x, self.rect.y))

        import time
        now = time.time()
        show_cursor = int(now * 2) % 2 == 0

        for i, (r, lbl) in enumerate(zip(self.field_rects, self.labels)):
            is_active = (self.active_field == i)

            bg_col = (38, 38, 46) if is_active else (30, 30, 36)
            border_col = (138, 180, 248) if is_active else (55, 55, 65)

            pygame.draw.rect(surface, bg_col, r, border_radius=4)
            pygame.draw.rect(surface, border_col, r, width=1 if not is_active else 2, border_radius=4)

            val_str = self.values[i]
            if val_str:
                txt_surf = render_cached(self.fonts["normal_bold"], val_str, (245, 245, 250))
            else:
                txt_surf = render_cached(self.fonts["normal"], "0", (90, 95, 105))

            txt_rect = txt_surf.get_rect(center=r.center)
            surface.blit(txt_surf, txt_rect)

            if is_active and show_cursor:
                cursor_x = txt_rect.right + 2
                pygame.draw.line(surface, (138, 180, 248), (cursor_x, r.y + 6), (cursor_x, r.bottom - 6), 2)

            lbl_surf = render_cached(self.fonts["small"], lbl, (160, 165, 175))
            surface.blit(lbl_surf, (r.centerx - lbl_surf.get_width() // 2, r.bottom + 4))

        # Live summary text
        total_m = self.get_total_minutes()
        total_hours = total_m / 60.0
        summary_str = f"= Total: {total_m:,.0f} simulated minutes ({total_hours:,.1f} hours)"
        summary_surf = render_cached(
            self.fonts["mono"],
            summary_str, (129, 201, 149) if total_m > 0 else (140, 140, 150)
        )
        surface.blit(summary_surf, (self.rect.x, self.rect.y + 78))
