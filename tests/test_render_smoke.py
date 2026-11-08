"""Headless render coverage for every live screen at both text scales."""
from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

import theme
from engine import begin_recruiting, loader, new_season, play_game, start_week
from engine.models import PendingEvent, Phase
from engine.projections import preview_weekly_action
from screens.about import AboutScreen
from screens.captain import CaptainScreen
from screens.difficulty import DifficultyScreen
from screens.event import EventScreen
from screens.howto import HowToScreen
from screens.hub import HubScreen
from screens.intro import IntroScreen
from screens.manager import GameApp
from screens.match import MatchScreen
from screens.modal import ConfirmModal
from screens.planning import PlanningScreen
from screens.report import ReportScreen
from screens.results import ResultsScreen
from screens.roster import RosterScreen
from screens.settings import SettingsScreen
from screens.spend_modal import SpendPreviewModal
from screens.title import TitleScreen
from screens import ui


def _planning_state(seed: int = 301):
    state = new_season("Varsity", 0, seed=seed)
    start_week(state)
    state.pending_event = None
    state.phase = Phase.PLANNING
    return state


def _played_state(seed: int = 302):
    state = _planning_state(seed)
    state.week = 1
    play_game(state)
    return state


def _event_state(seed: int = 303):
    state = _planning_state(seed)
    event = loader.load_events()[0]
    state.pending_event = PendingEvent(
        event_id=event["id"],
        title=event["title"],
        description=event["description"],
        responses=event["responses"],
    )
    state.phase = Phase.EVENT
    return state


@pytest.mark.parametrize("large_text", [False, True])
def test_every_live_screen_renders_and_controls_stay_above_directions(large_text):
    app = GameApp()
    app.ax.large_text = large_text
    app.reload_fonts()

    cases = [
        (TitleScreen(), None),
        (HubScreen(), None),
        (DifficultyScreen(), None),
        (CaptainScreen("Varsity"), None),
        (SettingsScreen(), None),
        (AboutScreen(), None),
        (HowToScreen(), None),
        (IntroScreen(), None),
        (PlanningScreen(), _planning_state()),
        (EventScreen(), _event_state()),
        (MatchScreen(), _played_state()),
        (ResultsScreen(), _played_state(304)),
        (ReportScreen(), _played_state(305)),
        (RosterScreen(), _planning_state(306)),
        (
            ConfirmModal("Leave this screen?", lambda _app: None, lambda _app: None),
            _planning_state(307),
        ),
        (
            SpendPreviewModal(
                preview_weekly_action(_planning_state(308), "recovery"),
                lambda _app: None,
            ),
            _planning_state(308),
        ),
    ]

    for screen, state in cases:
        app.stack.clear()
        app.state = state
        app.push(screen)
        screen.draw(app, app.screen)
        assert all(
            widget["rect"].bottom <= theme.WINDOW_HEIGHT - theme.HINT_H
            for widget in app.focus.widgets
        ), type(screen).__name__

    recruit_state = _planning_state(309)
    planning = PlanningScreen()
    app.stack.clear()
    app.state = recruit_state
    app.push(planning)
    planning.recruits = begin_recruiting(recruit_state)
    planning.sub_mode = "recruit"
    planning.build_focus(app)
    planning.draw(app, app.screen)
    assert all(
        widget["rect"].bottom <= theme.WINDOW_HEIGHT - theme.HINT_H
        for widget in app.focus.widgets
    )
    pygame.quit()


def test_hub_uses_full_briefing_label_and_header_clears_menu():
    app = GameApp()
    app.stack.clear()
    hub = HubScreen()
    app.push(hub)

    briefing = next(widget for widget in app.focus.widgets if widget["id"] == "briefing")
    assert briefing["label"] == "Briefing"
    assert "…" not in briefing["label"] and "..." not in briefing["label"]
    assert min(
        widget["rect"].top
        for widget in app.focus.widgets
        if widget["id"] not in {"help", "settings", "exit"}
    ) > hub._header_bottom(app)
    pygame.quit()


@pytest.mark.parametrize("large_text", [False, True])
def test_hub_header_fits_all_five_starters_and_menu(large_text):
    app = GameApp()
    app.ax.large_text = large_text
    app.reload_fonts()
    app.stack.clear()
    hub = HubScreen()
    app.push(hub)
    hub.draw(app, app.screen)

    assert len(hub._projected_starters()) == 5
    five_line_bottom = hub._header_bottom(app)
    three_line_bottom = ui.measure_screen_header(
        height=theme.WINDOW_HEIGHT,
        font_title=app.font_heading,
        font_body=app.font_tiny,
        font_bold=app.font_bold,
        objective=hub.copy["default_objective"],
        detail_heading=hub.copy["lineup_heading"],
        detail_lines=tuple(hub._projected_starters()[:3]),
    ) - 4
    menu = [w["rect"] for w in app.focus.widgets if w["id"] in {"new", "howto", "about", "briefing"}]
    assert five_line_bottom > three_line_bottom
    assert min(rect.top for rect in menu) > five_line_bottom + app.font_bold.get_linesize()
    assert max(rect.bottom for rect in menu) < theme.WINDOW_HEIGHT - theme.HINT_H
    pygame.quit()


@pytest.mark.parametrize("screen_type", [HowToScreen, AboutScreen])
@pytest.mark.parametrize("large_text", [False, True])
def test_scrollable_information_screens_reach_measured_end(screen_type, large_text):
    app = GameApp()
    app.ax.large_text = large_text
    app.reload_fonts()
    app.stack.clear()
    screen = screen_type()
    app.push(screen)
    screen.draw(app, app.screen)

    assert screen._content_height > screen._viewport_height
    screen.handle_event(
        app,
        pygame.event.Event(pygame.KEYDOWN, key=pygame.K_END, mod=0),
    )
    screen.draw(app, app.screen)
    assert screen.scroll == screen.max_scroll
    assert screen._content_height - screen.scroll == screen._viewport_height
    assert screen._clip_rect.bottom < theme.WINDOW_HEIGHT - theme.HINT_H
    if isinstance(screen, HowToScreen):
        assert screen._controls_content_top - screen.scroll < screen._viewport_height
        screen.scroll = 0
        screen.handle_event(app, pygame.event.Event(pygame.MOUSEWHEEL, y=-1000))
        assert screen.scroll == screen.max_scroll
    pygame.quit()
