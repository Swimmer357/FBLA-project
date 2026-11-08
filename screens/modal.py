"""Confirmation overlays (exit, etc.)."""
from __future__ import annotations

import pygame

import theme
from screens.manager import Screen
from screens import ui


class ConfirmModal(Screen):
    draw_under_modal = True
    hint = "Enter: confirm · Esc: cancel"

    def __init__(self, message: str, on_yes, on_no, *, yes_label: str = "Yes", no_label: str = "No") -> None:
        self.message = message
        self.on_yes = on_yes
        self.on_no = on_no
        self.yes_label = yes_label
        self.no_label = no_label

    def build_focus(self, app) -> None:
        cx = theme.WINDOW_WIDTH // 2
        app.focus.set_widgets(
            [
                {"id": "yes", "rect": pygame.Rect(cx - 220, 380, 200, theme.BUTTON_H), "center": (cx - 120, 408), "label": self.yes_label},
                {"id": "no", "rect": pygame.Rect(cx + 20, 380, 200, theme.BUTTON_H), "center": (cx + 120, 408), "label": self.no_label},
            ]
        )

    def handle_event(self, app, event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._cancel(app)
            elif event.key == pygame.K_LEFT:
                app.focus.move_tab(True)
            elif event.key == pygame.K_RIGHT:
                app.focus.move_tab(False)
            elif event.key == pygame.K_TAB:
                app.focus.move_tab(bool(event.mod & pygame.KMOD_SHIFT))
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._activate(app)
        if event.type == pygame.MOUSEBUTTONDOWN and app.focus.focus_at_point(*event.pos):
            self._activate(app)

    def _activate(self, app) -> None:
        cur = app.focus.current
        if not cur:
            return
        app.play_sound("click")
        app.pop()
        if cur["id"] == "yes":
            self.on_yes(app)
        else:
            self.on_no(app)

    def _cancel(self, app) -> None:
        app.pop()
        self.on_no(app)

    def draw(self, app, surf) -> None:
        overlay = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        surf.blit(overlay, (0, 0))
        panel = pygame.Rect(240, 220, 800, 280)
        ui.draw_panel(surf, panel, font=app.font_small, title="Confirm", font_bold=app.font_bold)
        msg = app.font_body.render(self.message, True, theme.SECTION_YELLOW)
        surf.blit(msg, msg.get_rect(center=(theme.WINDOW_WIDTH // 2, 300)))
        for w in app.focus.widgets:
            variant = "danger" if w["id"] == "yes" and "exit" in self.message.lower() else "default"
            if w["id"] == "no":
                variant = "default"
            ui.draw_quest_button(surf, w["rect"], w["label"], app.font_button, focused=app.focus.current is w, variant=variant)
        ui.draw_hint_bar(surf, self.hint, app.font_small)
