from __future__ import annotations

import pygame

import theme
from engine import (
    begin_recruiting,
    event_helpers,
    legal_actions,
    match,
    resolve_recruiting,
    take_action,
    week_label,
)
from engine.models import Skill
from engine.projections import preview_weekly_action
from engine.season import finish_planning_and_play
from screens.manager import Screen
from screens import ui

ACTION_SHORT = {
    "focused_training": "Train Player",
    "team_practice": "Practice",
    "recovery": "Recovery",
    "team_building": "Team Culture",
    "scout_recruit": "Recruit",
    "bank_tokens": "Bank Tokens",
}


class PlanningScreen(Screen):
    hint = "Plan your week · F: fast-forward · Enter · Esc · M: mute"

    def __init__(self) -> None:
        self.sub_mode: str | None = None
        self.recruits = []
        self.train_athlete_index: int | None = None
        self.ff_confirm = False

    def _content_top(self) -> int:
        return 236

    def _action_area(self) -> tuple[int, int, int]:
        x = theme.MARGIN_X + theme.ROSTER_W + theme.BUTTON_GAP * 2
        w = theme.WINDOW_WIDTH - theme.MARGIN_X - x
        y = self._content_top()
        return x, y, w

    def on_enter(self, app) -> None:
        state = app.state
        if state.phase.name == "EVENT" and state.pending_event:
            from screens.event import EventScreen

            app.replace(EventScreen())
            return
        self.build_focus(app)

    def build_focus(self, app) -> None:
        if self.ff_confirm:
            cx = theme.WINDOW_WIDTH // 2
            app.focus.set_widgets(
                [
                    {"id": "ff_yes", "rect": pygame.Rect(cx - 220, 360, 200, theme.BUTTON_H), "center": (cx - 120, 388), "label": "Yes"},
                    {"id": "ff_no", "rect": pygame.Rect(cx + 20, 360, 200, theme.BUTTON_H), "center": (cx + 120, 388), "label": "No"},
                ]
            )
            return
        if self.sub_mode:
            self._build_sub_focus(app)
            return
        widgets = []
        specs = list(legal_actions(app.state))
        ax, ay, aw = self._action_area()
        rects = ui.grid_button_rects(len(specs) + 1, x=ax, y=ay, width=aw, featured_full_width_index=len(specs))
        for spec, rect in zip(specs, rects[:-1]):
            widgets.append({"id": spec.action_id, "rect": rect, "center": rect.center, "spec": spec})
        widgets.append({"id": "start_game", "rect": rects[-1], "center": rects[-1].center, "label": "Start Game", "variant": "gradient"})
        app.focus.set_widgets(widgets)

    def _build_sub_focus(self, app) -> None:
        ax, ay, aw = self._action_area()
        widgets = []
        if self.sub_mode == "recruit":
            y = ay
            for i, r in enumerate(self.recruits):
                rect = pygame.Rect(ax, y, aw, theme.BUTTON_H)
                widgets.append({"id": f"rec_{i}", "rect": rect, "center": rect.center, "recruit": r})
                y += theme.BUTTON_H + theme.BUTTON_GAP
            widgets.append({"id": "decline", "rect": pygame.Rect(ax, y, 220, theme.BUTTON_H), "center": (ax + 110, y + 28)})
        elif self.sub_mode == "bank":
            x = ax
            for amt in (1, 2, 3):
                widgets.append({"id": str(amt), "rect": pygame.Rect(x, ay + 80, 120, theme.BUTTON_H), "center": (x + 60, ay + 108)})
                x += 136
        elif self.sub_mode == "train_pick":
            y = ay
            for a in app.state.athletes:
                rect = pygame.Rect(ax, y, aw, 44)
                widgets.append({"id": f"ath_{a.roster_index}", "rect": rect, "center": rect.center, "athlete": a})
                y += 48
        app.focus.set_widgets(widgets)

    def handle_event(self, app, event) -> None:
        if self.sub_mode == "train_pick":
            self._sub_train(app, event)
            return
        if self.sub_mode == "recruit":
            self._sub_recruit(app, event)
            return
        if self.sub_mode == "bank":
            self._sub_bank(app, event)
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_f:
            self.ff_confirm = True
            self.build_focus(app)
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE and self.ff_confirm:
                self.ff_confirm = False
                self.build_focus(app)
                return
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
        if self.ff_confirm:
            cur = app.focus.current
            if cur and cur["id"] == "ff_yes":
                from engine import fast_forward
                from screens.report import ReportScreen

                fast_forward(app.state)
                app.replace(ReportScreen())
            else:
                self.ff_confirm = False
                self.build_focus(app)
            return
        cur = app.focus.current
        if not cur:
            return
        if cur["id"] == "start_game":
            app.play_sound("click")
            if app.state.week == 0:
                from engine.season import advance_after_results

                advance_after_results(app.state)
                if app.state.pending_event:
                    from screens.event import EventScreen

                    app.replace(EventScreen())
                else:
                    self.build_focus(app)
                return
            from screens.match import MatchScreen

            finish_planning_and_play(app.state)
            app.replace(MatchScreen())
            return
        spec = cur.get("spec")
        if spec and not spec.enabled:
            app.play_sound("buzzer")
            return
        app.play_sound("click")
        aid = cur["id"]
        if aid == "focused_training":
            self.sub_mode = "train_pick"
            self._build_sub_focus(app)
        elif aid == "scout_recruit":
            self._open_spend_preview(app, "scout_recruit", {})
        elif aid == "bank_tokens":
            self.sub_mode = "bank"
            self._build_sub_focus(app)
        else:
            self._open_spend_preview(app, aid, {})

    def _open_spend_preview(self, app, action_id: str, params: dict) -> None:
        from screens.spend_modal import SpendPreviewModal

        preview = preview_weekly_action(app.state, action_id, params)
        on_confirm = (
            self._begin_recruiting
            if action_id == "scout_recruit" and not params
            else lambda a: self._commit_action(a, action_id, params)
        )
        app.push(
            SpendPreviewModal(
                preview,
                on_confirm=on_confirm,
            )
        )

    def _commit_action(self, app, action_id: str, params: dict) -> None:
        try:
            take_action(app.state, action_id, params)
        except ValueError:
            app.play_sound("buzzer")
            return
        self.sub_mode = None
        self.train_athlete_index = None
        self.build_focus(app)

    def _begin_recruiting(self, app) -> None:
        try:
            self.recruits = begin_recruiting(app.state)
        except ValueError:
            app.play_sound("buzzer")
            return
        self.sub_mode = "recruit"
        self._build_sub_focus(app)

    def _sub_train(self, app, event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.sub_mode = None
            self.train_athlete_index = None
            self.build_focus(app)
            return
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_UP, pygame.K_LEFT, pygame.K_TAB):
            app.focus.move_tab(bool(event.mod & pygame.KMOD_SHIFT))
            return
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_DOWN, pygame.K_RIGHT):
            app.focus.move_tab(False)
            return
        activate = event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE)
        if event.type == pygame.MOUSEBUTTONDOWN:
            activate = app.focus.focus_at_point(*event.pos)
        if activate:
            cur = app.focus.current
            if cur and self.train_athlete_index is None and "ath_" in cur["id"]:
                self.train_athlete_index = int(cur["id"].split("_")[1])
                ax, ay, aw = self._action_area()
                widgets = []
                y = ay
                for sk in Skill:
                    rect = pygame.Rect(ax, y, min(aw, 320), theme.BUTTON_H)
                    widgets.append({"id": sk.value, "rect": rect, "center": rect.center})
                    y += theme.BUTTON_H + theme.BUTTON_GAP
                app.focus.set_widgets(widgets)
            elif cur and self.train_athlete_index is not None:
                self._open_spend_preview(
                    app,
                    "focused_training",
                    {"athlete_index": self.train_athlete_index, "skill": cur["id"]},
                )

    def _sub_recruit(self, app, event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._resolve_recruiting(app, None)
            return
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_UP, pygame.K_LEFT, pygame.K_TAB):
            app.focus.move_tab(bool(event.mod & pygame.KMOD_SHIFT))
            return
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_DOWN, pygame.K_RIGHT):
            app.focus.move_tab(False)
            return
        activate = event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE)
        if event.type == pygame.MOUSEBUTTONDOWN:
            activate = app.focus.focus_at_point(*event.pos)
        if activate:
            cur = app.focus.current
            if not cur:
                return
            if cur["id"] == "decline":
                recruit = None
            else:
                i = int(cur["id"].split("_")[1])
                recruit = self.recruits[i]
            self._resolve_recruiting(app, recruit)

    def _resolve_recruiting(self, app, recruit) -> None:
        try:
            resolve_recruiting(app.state, recruit)
        except ValueError:
            app.play_sound("buzzer")
            return
        self.sub_mode = None
        self.recruits = []
        self.build_focus(app)

    def _sub_bank(self, app, event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.sub_mode = None
            self.build_focus(app)
            return
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_LEFT, pygame.K_UP, pygame.K_TAB):
            app.focus.move_tab(bool(event.mod & pygame.KMOD_SHIFT))
            return
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RIGHT, pygame.K_DOWN):
            app.focus.move_tab(False)
            return
        activate = event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE)
        if event.type == pygame.MOUSEBUTTONDOWN:
            activate = app.focus.focus_at_point(*event.pos)
        if activate:
            cur = app.focus.current
            if cur:
                try:
                    amount = int(cur["id"])
                except ValueError:
                    app.play_sound("buzzer")
                    return
                self._open_spend_preview(app, "bank_tokens", {"amount": amount})

    def _status_message(self, app) -> str:
        cur = app.focus.current
        if cur and cur.get("spec") and not cur["spec"].enabled:
            return cur["spec"].disabled_reason or ""
        if self.sub_mode == "train_pick":
            return "Pick an athlete, then a skill to train."
        if self.sub_mode == "recruit":
            return "Sign a recruit or decline (tokens are not refunded)."
        if self.sub_mode == "bank":
            return "Bank 1–3 tokens into your reserve (max 6)."
        return "Pick up to 3 actions, then Start Game."

    def draw(self, app, surf) -> None:
        state = app.state
        ui.draw_background(surf)
        opp, rating = match.opponent_rating_for_week(state)
        opp_line = f"vs {opp} ({rating})" if state.week > 0 else "Preseason — no game this week"
        ui.draw_screen_header(
            surf,
            title="Weekly Plan",
            stats_line=f"{week_label(state)}  ·  Record {state.wins}-{state.losses}  ·  {opp_line}",
            objective=f"Tokens {state.tokens_left}  ·  Moves {state.moves_left}  ·  Reserve {state.reserve}  ·  Cohesion {state.cohesion}  ·  Prep {state.preparation}",
            font_title=app.font_heading,
            font_body=app.font_body,
            font_small=app.font_small,
            font_bold=app.font_bold,
        )

        if self.ff_confirm:
            surf.blit(app.font_heading.render("FAST-FORWARD SEASON?", True, theme.TITLE_CYAN), (theme.MARGIN_X, 240))
            surf.blit(
                app.font_body.render("Auto-play with balanced training, practice, and recovery?", True, theme.TEXT_DIM),
                (theme.MARGIN_X, 290),
            )
            for w in app.focus.widgets:
                ui.draw_quest_button(surf, w["rect"], w["label"], app.font_body, focused=app.focus.current is w)
            ui.draw_hint_bar(surf, "Enter = yes · Esc = no", app.font_small)
            return

        top = self._content_top()
        roster_rect = pygame.Rect(theme.MARGIN_X, top, theme.ROSTER_W, theme.FOOTER_Y - top - 48)
        ui.draw_planning_roster_table(
            surf,
            roster_rect,
            state.athletes,
            captain_index=state.captain_index,
            font=app.font_small,
            font_bold=app.font_bold,
        )

        font_btn = getattr(app, "font_button", app.font_small)
        if self.sub_mode == "recruit":
            for w in app.focus.widgets:
                if "recruit" in w:
                    r = w["recruit"]
                    label = f"Sign {r.name} — {(r.shooting + r.defense) / 2:.0f} OVR"
                    ui.draw_quest_button(surf, w["rect"], label, font_btn, focused=app.focus.current is w)
                elif w["id"] == "decline":
                    ui.draw_quest_button(surf, w["rect"], "Decline", font_btn, focused=app.focus.current is w)
        elif self.sub_mode == "bank":
            for w in app.focus.widgets:
                ui.draw_quest_button(surf, w["rect"], w["id"] + " token(s)", font_btn, focused=app.focus.current is w)
        elif self.sub_mode == "train_pick":
            for w in app.focus.widgets:
                if "athlete" in w:
                    athlete = w["athlete"]
                    label = f"{athlete.name} · OVR {athlete.overall:.0f} · Fatigue {athlete.fatigue}"
                    ui.draw_quest_button(surf, w["rect"], label, font_btn, focused=app.focus.current is w)
                else:
                    ui.draw_quest_button(surf, w["rect"], w["id"], font_btn, focused=app.focus.current is w)
        else:
            for w in app.focus.widgets:
                if w["id"] == "start_game":
                    ui.draw_quest_button(
                        surf, w["rect"], "Start Game", font_btn, focused=app.focus.current is w, variant="gradient"
                    )
                else:
                    spec = w["spec"]
                    short = ACTION_SHORT.get(spec.action_id, spec.label)
                    cost = f" ({spec.token_cost}T)" if spec.token_cost else ""
                    ui.draw_quest_button(
                        surf,
                        w["rect"],
                        short + cost,
                        font_btn,
                        focused=app.focus.current is w,
                        enabled=spec.enabled,
                    )

        ui.draw_status_strip(surf, self._status_message(app), app.font_small)
        ui.draw_hint_bar(surf, self.hint, app.font_small)
