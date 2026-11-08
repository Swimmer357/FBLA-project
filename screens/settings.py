"""Display and accessibility — saved for this machine."""
from __future__ import annotations

import pygame

import theme
from screens.accessibility import save_settings
from screens.manager import Screen
from screens import ui


class SettingsScreen(Screen):
    hint = "Enter toggles option · Esc closes · M mute"

    OPTIONS = [
        ("high_contrast", "High contrast"),
        ("large_text", "Larger text"),
        ("readable_font", "Readable system font (Arial)"),
    ]

    def build_focus(self, app) -> None:
        widgets = []
        y = 260
        for key, _label in self.OPTIONS:
            rect = pygame.Rect(theme.MARGIN_X + 80, y, theme.CONTENT_W - 160, theme.BUTTON_H)
            widgets.append({"id": key, "rect": rect, "center": rect.center})
            y += theme.BUTTON_H + theme.BUTTON_GAP
        widgets.append(
            {
                "id": "close",
                "rect": pygame.Rect(
                    (theme.WINDOW_WIDTH - 240) // 2,
                    theme.WINDOW_HEIGHT - theme.HINT_H - theme.BUTTON_H - 10,
                    240,
                    theme.BUTTON_H,
                ),
                "center": (
                    theme.WINDOW_WIDTH // 2,
                    theme.WINDOW_HEIGHT - theme.HINT_H - theme.BUTTON_H // 2 - 10,
                ),
                "label": "Done",
            }
        )
        app.focus.set_widgets(widgets)

    def _is_on(self, app, key: str) -> bool:
        return bool(getattr(app.ax, key))

    def handle_event(self, app, event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                app.pop()
            elif event.key == pygame.K_TAB:
                app.focus.move_tab(bool(event.mod & pygame.KMOD_SHIFT))
            elif event.key == pygame.K_UP:
                app.focus.move_tab(True)
            elif event.key == pygame.K_DOWN:
                app.focus.move_tab(False)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._activate(app)
        if event.type == pygame.MOUSEBUTTONDOWN and app.focus.focus_at_point(*event.pos):
            self._activate(app)

    def _activate(self, app) -> None:
        cur = app.focus.current
        if not cur:
            return
        app.play_sound("click")
        if cur["id"] == "close":
            app.pop()
            return
        key = cur["id"]
        setattr(app.ax, key, not self._is_on(app, key))
        save_settings(app.ax)
        app.reload_fonts()

    def draw(self, app, surf) -> None:
        ui.draw_background(surf)
        ui.draw_screen_header(
            surf,
            title="Display & Accessibility",
            stats_line="For judges, players, and anyone who needs clearer text",
            objective="Settings save automatically on this computer",
            font_title=app.font_heading,
            font_body=app.font_body,
            font_small=app.font_small,
            font_bold=app.font_bold,
        )
        for key, label in self.OPTIONS:
            on = self._is_on(app, key)
            text = f"{'ON' if on else 'OFF'} — {label.upper()}"
            w = next(x for x in app.focus.widgets if x["id"] == key)
            ui.draw_quest_button(
                surf,
                w["rect"],
                text,
                app.font_button,
                focused=app.focus.current is w,
                variant="gradient" if on else "default",
            )
        close = next(w for w in app.focus.widgets if w["id"] == "close")
        ui.draw_quest_button(surf, close["rect"], "Done", app.font_button, focused=app.focus.current is close)
        ui.draw_hint_bar(surf, self.hint, app.font_small)
