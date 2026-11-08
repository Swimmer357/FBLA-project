from __future__ import annotations

import pygame

import theme
from engine import explain, check_ending
from engine.season import advance_after_results
from screens.manager import Screen
from screens import ui

LINE_X = 160
LINE_W = 1216 - 16 - LINE_X
TIP_W = 1152
TIP_LINES = 2


class ResultsScreen(Screen):
    hint = "Enter: continue · Q: quick sim · M: mute"

    def on_enter(self, app) -> None:
        self.build_focus(app)
        self.result = app.state.last_result
        check_ending(app.state)
        self.explanation = explain(
            self.result,
            state=app.state,
            narrator=app.narrator,
            line_fits=lambda text: app.font_body.size(text)[0] <= LINE_W,
            tip_fits=lambda text: len(ui.wrap_text(app.font_small, text, TIP_W)) <= TIP_LINES,
        )

    def handle_event(self, app, event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_q:
            app.quick_sim_state = None if app.quick_sim_state is app.state else app.state
            return
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
        overtime = " (OT)" if r.overtime else ""
        surf.blit(
            app.font_heading.render(
                f"{outcome}{overtime} — {r.team_score} to {r.opponent_score} (now {app.state.wins}-{app.state.losses})",
                True,
                theme.WHITE,
            ),
            (64, 34),
        )
        surf.blit(app.font_small.render(self.explanation.headline, True, theme.LIGHT_GRAY), (64, 84))
        panel = pygame.Rect(64, 120, 1152, 280)
        ui.draw_panel(surf, panel, dark=True, font=app.font_body, title="Why this happened")
        y = 170
        for line in self.explanation.lines:
            color = theme.GOOD_GREEN if line.positive else theme.BAD_RED
            sign = "+" if line.positive else "−"
            tri_y = y + 10
            points = (
                [(64, tri_y - 6), (56, tri_y + 4), (72, tri_y + 4)]
                if line.positive
                else [(64, tri_y + 6), (56, tri_y - 4), (72, tri_y - 4)]
            )
            pygame.draw.polygon(surf, color, points)
            surf.blit(app.font_body.render(f"{sign}{line.display_value:.1f}", True, color), (80, y))
            surf.blit(app.font_body.render(line.sentence, True, theme.WHITE), (LINE_X, y))
            y += 36
        surf.blit(app.font_body.render("Coach's Tip", True, theme.ORANGE), (64, 420))
        y = 452
        for tip_line in ui.wrap_text(app.font_small, self.explanation.coach_tip, TIP_W)[:TIP_LINES]:
            surf.blit(tip_line, (64, y))
            y += app.font_small.get_linesize()
        y = max(y + 12, 512)
        for h in self.explanation.highlights:
            surf.blit(app.font_small.render(h, True, theme.LIGHT_GRAY), (64, y))
            y += 24
        if app.quick_sim_state is app.state:
            note = app.font_tiny.render("QUICK SIM ON (Q to turn off)", True, theme.SECTION_YELLOW)
            surf.blit(note, note.get_rect(topright=(1216, 88)))
        ui.draw_hint_bar(surf, self.hint, app.font_small)
