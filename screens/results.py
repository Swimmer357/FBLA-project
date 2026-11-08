from __future__ import annotations

import pygame

import theme
from engine import explain, check_ending
from engine.season import advance_after_results
from screens.manager import Screen
from screens import ui


class ResultsScreen(Screen):
    hint = "Enter: continue · M: mute"

    def on_enter(self, app) -> None:
        self.build_focus(app)
        self.result = app.state.last_result
        self.explanation = explain(self.result)
        check_ending(app.state)

    def handle_event(self, app, event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._continue(app)
        if event.type == pygame.MOUSEBUTTONDOWN:
            self._continue(app)

    def _continue(self, app) -> None:
        state = app.state
        if state.ending_id or state.phase.name == "REPORT":
            from screens.report import ReportScreen

            app.replace(ReportScreen())
            return
        advance_after_results(state)
        if state.ending_id or state.phase.name == "REPORT":
            from screens.report import ReportScreen

            app.replace(ReportScreen())
            return
        from screens.planning import PlanningScreen

        app.replace(PlanningScreen())

    def draw(self, app, surf) -> None:
        r = self.result
        ui.draw_background(surf)
        outcome = "Win" if r.won else "Loss"
        surf.blit(
            app.font_heading.render(
                f"{outcome} — {r.team_score} to {r.opponent_score} (now {app.state.wins}-{app.state.losses})",
                True,
                theme.WHITE,
            ),
            (64, 48),
        )
        panel = pygame.Rect(64, 120, 1152, 280)
        ui.draw_panel(surf, panel, dark=True, font=app.font_body, title="Why this happened")
        y = 170
        for line in self.explanation.lines:
            color = theme.GOOD_GREEN if line.positive else theme.BAD_RED
            sign = "+" if line.signed_value >= 0 else "−"
            tri_y = y + 10
            points = (
                [(64, tri_y - 6), (56, tri_y + 4), (72, tri_y + 4)]
                if line.positive
                else [(64, tri_y + 6), (56, tri_y - 4), (72, tri_y - 4)]
            )
            pygame.draw.polygon(surf, color, points)
            surf.blit(app.font_body.render(f"{sign}{line.display_value:.1f}", True, color), (80, y))
            surf.blit(app.font_body.render(line.sentence, True, theme.WHITE), (160, y))
            y += 36
        surf.blit(app.font_body.render("Coach's Tip", True, theme.ORANGE), (64, 420))
        surf.blit(app.font_small.render(self.explanation.coach_tip, True, theme.LIGHT_GRAY), (64, 452))
        y = 500
        for h in self.explanation.highlights:
            surf.blit(app.font_small.render(h, True, theme.LIGHT_GRAY), (64, y))
            y += 24
        ui.draw_hint_bar(surf, self.hint, app.font_small)
