from __future__ import annotations

import pygame

import theme
from engine import loader, new_season, start_week
from screens.manager import Screen
from screens import ui


class CaptainScreen(Screen):
    def __init__(self, difficulty: str) -> None:
        self.difficulty = difficulty
        self.athletes = loader.load_athletes()

    hint = "Pick captain · Enter · Esc: back · M: mute"

    def build_focus(self, app) -> None:
        widgets = []
        gx = theme.MARGIN_X
        y = theme.MAIN_TOP
        gap = theme.BUTTON_GAP
        col_w = (theme.CONTENT_W - gap) // 2
        for i, a in enumerate(self.athletes):
            col = i % 2
            row = i // 2
            rect = pygame.Rect(gx + col * (col_w + gap), y + row * (theme.BUTTON_H + 14), col_w, theme.BUTTON_H)
            widgets.append({"id": i, "rect": rect, "center": rect.center, "athlete": a})
        app.focus.set_widgets(widgets)

    def handle_event(self, app, event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                app.pop()
            elif event.key == pygame.K_TAB:
                app.focus.move_tab(bool(event.mod & pygame.KMOD_SHIFT))
            elif event.key == pygame.K_UP:
                app.focus.move_dir(0, -1)
            elif event.key == pygame.K_DOWN:
                app.focus.move_dir(0, 1)
            elif event.key == pygame.K_LEFT:
                app.focus.move_dir(-1, 0)
            elif event.key == pygame.K_RIGHT:
                app.focus.move_dir(1, 0)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._confirm(app)
        if event.type == pygame.MOUSEBUTTONDOWN and app.focus.focus_at_point(*event.pos):
            self._confirm(app)

    def _confirm(self, app) -> None:
        cur = app.focus.current
        if not cur:
            return
        app.play_sound("click")
        state = new_season(self.difficulty, int(cur["id"]))
        start_week(state)
        app.state = state
        from screens.planning import PlanningScreen

        app.replace(PlanningScreen())

    def draw(self, app, surf) -> None:
        ui.draw_background(surf)
        ui.draw_screen_header(
            surf,
            title="Team Captain",
            stats_line=f"Difficulty: {self.difficulty}",
            objective="Leadership 60+ improves Team-Building and slump meetings",
            font_title=app.font_title,
            font_body=app.font_body,
            font_small=app.font_small,
        )
        for w in app.focus.widgets:
            a = w["athlete"]
            label = f"{a.name}  ·  {a.pos}  ·  Leadership {a.leadership}"
            ui.draw_quest_button(surf, w["rect"], label, app.font_button, focused=app.focus.current is w)
        ui.draw_hint_bar(surf, self.hint, app.font_small)
