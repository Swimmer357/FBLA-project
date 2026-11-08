"""Replay timeline: scores always match, clocks stay legal, playback stays quick."""
from __future__ import annotations

import os
import random
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from engine import new_season, play_game, start_week
from engine.models import Phase
from engine.timeline import (
    Player,
    event_real_time,
    game_end_real,
    generate_timeline,
    period_real,
    period_start_real,
    total_real_time,
)


def _random_timeline(rng: random.Random):
    overtime = rng.random() < 0.1
    if overtime:
        away = rng.randint(35, 115)
        home = away + rng.choice((1, -1))
    else:
        home, away = rng.randint(30, 120), rng.randint(30, 120)
        if home == away:
            home += 1 if home < 120 else -1
    roster_size = rng.choice((0, 3, 4, 5, 5, 5))
    home_players = [
        Player(rng.choice(("Marcus Reed", "", "Noah Kim")) or f"Home #{i + 1}", rng.uniform(40, 80), rng.uniform(0, 12))
        for i in range(roster_size)
    ]
    away_players = [Player(f"Opp #{i + 1}", 50.0, 0.0) for i in range(5)]
    timeline = generate_timeline(home, away, home_players, away_players, rng.uniform(-15, 15), overtime, rng.randint(0, 10**9))
    return timeline, home, away


def test_1000_timelines_match_score_and_clock_rules():
    rng = random.Random(2024)
    for _ in range(1000):
        timeline, home, away = _random_timeline(rng)
        makes = [e for e in timeline.events if e.kind == "make"]
        assert sum(e.points for e in makes if e.team == "home") == home
        assert sum(e.points for e in makes if e.team == "away") == away
        assert (timeline.events[-1].home_score, timeline.events[-1].away_score) == (home, away)
        assert all(e.points in (1, 2, 3) for e in makes)
        assert all(e.points == 0 for e in timeline.events if e.kind != "make")
        if timeline.overtime:
            assert timeline.period_scores[3][0] == timeline.period_scores[3][1]
        previous = {}
        for e in timeline.events:
            length = timeline.period_lengths[e.period - 1]
            assert 0 < e.clock < length
            assert e.clock > 1.0
            assert previous.get(e.period, length) > e.clock
            previous[e.period] = e.clock
            t = event_real_time(timeline, e)
            assert period_start_real(e.period) <= t <= period_start_real(e.period) + period_real(e.period)


def test_playback_time_targets_at_every_speed():
    rng = random.Random(7)
    for _ in range(1000):
        timeline, _, _ = _random_timeline(rng)
        normal = total_real_time(timeline, 1)
        assert 6.0 <= normal <= 8.0
        if not timeline.overtime:
            assert normal == pytest.approx(6.75)
        assert total_real_time(timeline, 2) == pytest.approx(normal / 2)
        assert total_real_time(timeline, 0) == 0.0


def test_runs_highlights_and_build_speed():
    rng = random.Random(11)
    start = time.perf_counter()
    worst = 0.0
    for _ in range(200):
        t0 = time.perf_counter()
        timeline, _, _ = _random_timeline(rng)
        worst = max(worst, time.perf_counter() - t0)
        for period in range(1, timeline.periods + 1):
            picks = [e for e in timeline.events if e.period == period and e.highlight]
            assert len(picks) <= 3
    assert worst < 0.010
    assert time.perf_counter() - start < 2.0

    favored = generate_timeline(80, 50, [Player(f"P{i}", 60, 1) for i in range(5)],
                                [Player(f"O{i}", 50, 0) for i in range(5)], 12.0, False, 5)
    longest = 0
    current = 0
    for e in favored.events:
        if e.kind != "make":
            continue
        current = current + e.points if e.team == "home" else 0
        longest = max(longest, current)
    assert longest >= 6


def _match_app():
    from screens.manager import GameApp
    from screens.match import MatchScreen

    app = GameApp()
    app.stack.clear()
    state = new_season("Varsity", 0, seed=55)
    start_week(state)
    state.pending_event = None
    state.phase = Phase.PLANNING
    state.week = 1
    play_game(state)
    app.state = state
    screen = MatchScreen()
    app.push(screen)
    return app, screen


@pytest.mark.parametrize("speed, limit", [(1, 8.0), (2, 4.0), (0, 1.0)])
def test_match_screen_finishes_with_correct_score_at_each_speed(speed, limit):
    from screens.results import ResultsScreen

    app, screen = _match_app()
    app.match_speed = speed
    if speed == 0:
        screen._skip_to_end()
    elapsed = 0.0
    while app.stack[-1] is screen:
        screen.update(app, 1 / 60)
        screen.draw(app, app.screen)
        elapsed += 1 / 60
        assert screen.home_score <= app.state.last_result.team_score
        assert elapsed < limit + 0.1
    assert isinstance(app.stack[-1], ResultsScreen)
    assert (screen.home_score, screen.away_score) == (
        app.state.last_result.team_score,
        app.state.last_result.opponent_score,
    )
    pygame.quit()


def test_skip_speed_change_and_long_frame_keep_score_correct():
    app, screen = _match_app()
    for _ in range(60):
        screen.update(app, 1 / 60)
    screen._cycle_speed(app)
    assert app.match_speed == 2
    screen.update(app, 30.0)
    result = app.state.last_result
    assert (screen.home_score, screen.away_score) == (result.team_score, result.opponent_score)
    pygame.quit()

    app, screen = _match_app()
    screen.update(app, 0.5)
    screen.handle_event(app, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0))
    assert screen.play_t >= game_end_real(screen.timeline)
    assert (screen.home_score, screen.away_score) == (
        app.state.last_result.team_score,
        app.state.last_result.opponent_score,
    )
    assert screen._clock_label().startswith("FINAL")
    pygame.quit()


def test_players_never_overlap_or_leave_court_and_quick_sim_skips():
    from screens.match import MIN_GAP
    from screens.results import ResultsScreen

    app, screen = _match_app()
    frame_times = []
    for _ in range(300):
        t0 = time.perf_counter()
        screen.update(app, 1 / 60)
        screen.draw(app, app.screen)
        frame_times.append(time.perf_counter() - t0)
        if app.stack[-1] is not screen:
            break
        bodies = screen.pos["home"] + screen.pos["away"]
        for i in range(len(bodies)):
            assert screen.bounds.inflate(2, 2).collidepoint(bodies[i].x, bodies[i].y)
            for j in range(i + 1, len(bodies)):
                assert bodies[i].distance_to(bodies[j]) >= MIN_GAP - 2.5
    frame_times.sort()
    assert frame_times[len(frame_times) // 2] < 1 / 60
    pygame.quit()

    app, screen = _match_app()
    screen._toggle_quick(app)
    assert app.quick_sim_state is app.state
    screen.update(app, 1 / 60)
    assert isinstance(app.stack[-1], ResultsScreen)
    pygame.quit()
