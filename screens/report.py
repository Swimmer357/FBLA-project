from __future__ import annotations

import pygame

import theme
from engine import loader
from screens.manager import Screen
from screens import ui


class ReportScreen(Screen):
    hint = "New Season or Quit · Enter · M: mute"

    ENDING_TITLES = {
        "state_champion": "State Champion",
        "finalist": "Finalist",
        "playoff_exit": "Playoff Exit",
        "missed_playoffs": "Missed Playoffs",
        "program_collapse": "Program Collapse",
    }

    def build_focus(self, app) -> None:
        app.focus.set_widgets(
            [
                {"id": "new", "rect": pygame.Rect(400, 620, 220, 48), "center": (510, 644), "label": "New Season"},
                {"id": "quit", "rect": pygame.Rect(660, 620, 220, 48), "center": (770, 644), "label": "Program Dashboard"},
            ]
        )

    def handle_event(self, app, event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFT:
                app.focus.move_tab(True)
            elif event.key == pygame.K_RIGHT:
                app.focus.move_tab(False)
            elif event.key == pygame.K_TAB:
                app.focus.move_tab(bool(event.mod & pygame.KMOD_SHIFT))
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._activate(app)
        if event.type == pygame.MOUSEBUTTONDOWN and app.focus.focus_at_point(*event.pos):
            self._activate(app)

    def _save_hub_summary(self, app) -> None:
        state = app.state
        if not state:
            return
        eid = state.ending_id or "missed_playoffs"
        app.hub_summary = {
            "record": f"{state.wins}-{state.losses}",
            "ending": self.ENDING_TITLES.get(eid, "Season Complete"),
            "objective": state.ending_reason or "",
        }

    def _activate(self, app) -> None:
        cur = app.focus.current
        if not cur:
            return
        app.play_sound("click")
        self._save_hub_summary(app)
        if cur["id"] == "quit":
            app.state = None
            app.replace(app._make_hub())
        else:
            from screens.difficulty import DifficultyScreen

            app.state = None
            app.replace(DifficultyScreen())

    def draw(self, app, surf) -> None:
        state = app.state
        ui.draw_background(surf)
        eid = state.ending_id or "missed_playoffs"
        title = self.ENDING_TITLES.get(eid, "Season Complete")
        surf.blit(app.font_title.render(title, True, theme.ORANGE), (64, 40))
        if state.ending_reason:
            surf.blit(app.font_body.render(state.ending_reason, True, theme.WHITE), (64, 100))
        surf.blit(
            app.font_small.render(f"Record {state.wins}-{state.losses} · Seed {state.seed}", True, theme.LIGHT_GRAY),
            (64, 140),
        )
        surf.blit(app.font_body.render("Athlete development", True, theme.WHITE), (64, 180))
        y = 220
        for a in state.athletes:
            start = state.starting_stats.get(a.name, {})
            ds = a.shooting - start.get("shooting", a.shooting)
            dd = a.defense - start.get("defense", a.defense)
            dt = a.stamina - start.get("stamina", a.stamina)
            line = f"{a.name}: Shoot {a.shooting} ({ds:+d}), Def {a.defense} ({dd:+d}), Stam {a.stamina} ({dt:+d})"
            surf.blit(app.font_small.render(line, True, theme.LIGHT_GRAY), (64, y))
            y += 22
        if state.game_log:
            surf.blit(app.font_body.render("Season games", True, theme.WHITE), (640, 180))
            y2 = 220
            for g in state.game_log:
                tag = "W" if g.won else "L"
                surf.blit(
                    app.font_small.render(
                        f"W{g.week} {tag} vs {g.opponent_name} {g.team_score}-{g.opponent_score}",
                        True,
                        theme.LIGHT_GRAY,
                    ),
                    (640, y2),
                )
                y2 += 22
        for w in app.focus.widgets:
            ui.draw_button(surf, w["rect"], w["label"], app.font_body, focused=app.focus.current is w)
        ui.draw_hint_bar(surf, self.hint, app.font_small)
