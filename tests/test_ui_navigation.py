"""Regression tests for focus restoration and reachable controls."""
from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

import theme
from engine import new_season, respond_to_event, start_week
from engine.models import Phase
from screens.captain import CaptainScreen
from screens.hub import HubScreen
from screens.event import EventScreen
from screens.intro import IntroScreen
from screens.manager import GameApp
from screens.match import MatchScreen
from screens.planning import PlanningScreen
from screens.report import ReportScreen
from screens.results import ResultsScreen
from screens.settings import SettingsScreen
from screens.spend_modal import SpendPreviewModal


def _app() -> GameApp:
    app = GameApp()
    app.stack.clear()
    return app


def test_pop_restores_underlying_button_map():
    app = _app()
    app.push(HubScreen())
    expected_ids = [widget["id"] for widget in app.focus.widgets]

    app.push(SettingsScreen())
    assert expected_ids != [widget["id"] for widget in app.focus.widgets]

    app.pop()
    assert [widget["id"] for widget in app.focus.widgets] == expected_ids
    pygame.quit()


def test_briefing_return_does_not_duplicate_hub():
    app = _app()
    app.push(HubScreen())
    app.push(IntroScreen(return_to_hub=True))
    app.focus.index = next(i for i, widget in enumerate(app.focus.widgets) if widget["id"] == "skip")

    app.stack[-1].handle_event(
        app,
        pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0),
    )

    assert len(app.stack) == 1
    assert isinstance(app.stack[-1], HubScreen)
    pygame.quit()


def test_all_captain_buttons_are_above_hint_bar():
    app = _app()
    screen = CaptainScreen("Varsity")
    app.push(screen)

    assert len(app.focus.widgets) == len(screen.athletes)
    assert max(widget["rect"].bottom for widget in app.focus.widgets) < theme.WINDOW_HEIGHT - theme.HINT_H
    pygame.quit()


def test_recruit_warning_cancel_and_confirm_flow_and_modal_redraw():
    app = _app()
    app.state = new_season("Varsity", 0, seed=42)
    start_week(app.state)
    app.state.pending_event = None
    app.state.phase = Phase.PLANNING
    planning = PlanningScreen()
    app.push(planning)
    recruit_index = next(
        i for i, widget in enumerate(app.focus.widgets) if widget["id"] == "scout_recruit"
    )
    app.focus.index = recruit_index
    before = (app.state.tokens_left, app.state.moves_left)

    planning._activate(app)
    assert isinstance(app.stack[-1], SpendPreviewModal)
    assert "non-refundable" in " ".join(app.stack[-1].preview.drawbacks).lower()
    app.draw_frame()  # Regression: underlying PlanningScreen once crashed with KeyError.

    app.focus.index = 0
    app.stack[-1]._activate(app)
    assert (app.state.tokens_left, app.state.moves_left) == before
    assert app.stack[-1] is planning

    app.focus.index = recruit_index
    planning._activate(app)
    app.focus.index = 1
    app.stack[-1]._activate(app)
    assert planning.sub_mode == "recruit"
    assert (app.state.tokens_left, app.state.moves_left) == (before[0] - 5, before[1] - 1)
    pygame.quit()


def test_automated_multi_week_screen_flow_does_not_exit_or_break_phase():
    app = _app()
    app.state = new_season("Varsity", 0, seed=77)
    start_week(app.state)
    app.push(PlanningScreen())

    for _ in range(30):
        screen = app.stack[-1]
        if isinstance(screen, EventScreen):
            response = next(
                item
                for item in app.state.pending_event.responses
                if int(item["token_cost"]) <= app.state.tokens_left + app.state.reserve
            )
            respond_to_event(app.state, response["id"])
            app.replace(PlanningScreen())
        elif isinstance(screen, PlanningScreen):
            app.focus.index = next(
                i for i, widget in enumerate(app.focus.widgets) if widget["id"] == "start_game"
            )
            screen._activate(app)
        elif isinstance(screen, MatchScreen):
            screen._finish(app)
        elif isinstance(screen, ResultsScreen):
            screen._continue(app)
        elif isinstance(screen, ReportScreen):
            break
        app.draw_frame()
    else:
        pytest.fail("multi-week UI flow did not reach the season report")

    assert app.running
    assert app.state.game_log
    assert app.state.phase in {Phase.ENDED, Phase.REPORT}
    pygame.quit()
