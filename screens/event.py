from __future__ import annotations

import pygame

import theme
from engine import respond_to_event, event_helpers
from engine.projections import preview_event_response
from screens.manager import Screen
from screens import ui


class EventScreen(Screen):
    hint = "Choose a response · Enter · M: mute"

    def __init__(self, summary: list[str] | None = None) -> None:
        self.summary = summary

    def build_focus(self, app) -> None:
        widgets = []
        gx = (theme.WINDOW_WIDTH - 720) // 2
        y = 320 if self.summary is None else theme.MAIN_TOP + 40
        if self.summary is not None:
            widgets.append({"id": "continue", "rect": pygame.Rect(gx, y, 720, theme.BUTTON_H_FEATURED), "center": (theme.WINDOW_WIDTH // 2, y + 32), "label": "Continue", "variant": "gradient"})
        elif app.state.pending_event:
            for resp in app.state.pending_event.responses:
                rect = pygame.Rect(gx, y, 720, theme.BUTTON_H)
                cost = int(resp["token_cost"])
                ok, _ = event_helpers.event_response_affordable(app.state, cost)
                widgets.append(
                    {
                        "id": resp["id"],
                        "rect": rect,
                        "center": rect.center,
                        "label": resp["label"],
                        "enabled": ok,
                    }
                )
                y += theme.BUTTON_H + theme.BUTTON_GAP
        app.focus.set_widgets(widgets)

    def handle_event(self, app, event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_TAB:
                app.focus.move_tab(bool(event.mod & pygame.KMOD_SHIFT))
            elif event.key in (pygame.K_UP, pygame.K_LEFT):
                app.focus.move_tab(True)
            elif event.key in (pygame.K_DOWN, pygame.K_RIGHT):
                app.focus.move_tab(False)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._activate(app)
        if event.type == pygame.MOUSEBUTTONDOWN and app.focus.focus_at_point(*event.pos):
            self._activate(app)

    def _activate(self, app) -> None:
        cur = app.focus.current
        if not cur:
            return
        if self.summary is not None:
            from screens.planning import PlanningScreen

            app.replace(PlanningScreen())
            return
        if not cur.get("enabled", True):
            app.play_sound("buzzer")
            return
        app.play_sound("click")
        choice_id = cur["id"]
        from screens.spend_modal import SpendPreviewModal

        app.push(
            SpendPreviewModal(
                preview_event_response(app.state, choice_id),
                on_confirm=lambda a: self._commit_response(a, choice_id),
            )
        )

    def _commit_response(self, app, choice_id: str) -> None:
        msgs = respond_to_event(app.state, choice_id)
        from screens.event import EventScreen

        app.replace(EventScreen(summary=msgs))

    def draw(self, app, surf) -> None:
        state = app.state
        ui.draw_background(surf)
        if self.summary is not None:
            ui.draw_screen_header(
                surf,
                title="Event Resolved",
                stats_line="Changes applied",
                objective="",
                font_title=app.font_heading,
                font_body=app.font_body,
                font_small=app.font_small,
            )
            y = 220
            for line in self.summary:
                surf.blit(app.font_body.render(line, True, theme.TEXT_WHITE), (theme.MARGIN_X, y))
                y += 32
        elif state.pending_event:
            ev = state.pending_event
            ui.draw_screen_header(
                surf,
                title=ev.title,
                stats_line="Choose a response below",
                objective="",
                font_title=app.font_heading,
                font_body=app.font_body,
                font_small=app.font_small,
            )
            y = theme.MAIN_TOP + 8
            for chunk in self._wrap(app.font_body, ev.description, 900):
                surf.blit(chunk, (theme.MARGIN_X + 40, y))
                y += 26
        for w in app.focus.widgets:
            ui.draw_quest_button(
                surf,
                w["rect"],
                w["label"],
                app.font_button,
                focused=app.focus.current is w,
                enabled=w.get("enabled", True),
                variant=w.get("variant", "default"),
            )
        ui.draw_hint_bar(surf, self.hint, app.font_small)

    def _wrap(self, font, text, width):
        words = text.split()
        lines = []
        cur = ""
        for w in words:
            test = (cur + " " + w).strip()
            if font.size(test)[0] <= width:
                cur = test
            else:
                if cur:
                    lines.append(font.render(cur, True, theme.TEXT_WHITE))
                cur = w
        if cur:
            lines.append(font.render(cur, True, theme.TEXT_WHITE))
        return lines
