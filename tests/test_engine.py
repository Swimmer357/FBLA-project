"""pytest suite for engine rules and match math."""
from __future__ import annotations

import copy

import pytest

from engine import (
    check_ending,
    legal_actions,
    new_season,
    play_game,
    start_week,
    take_action,
)
from engine import loader
from engine.match import compute_factors, pick_starters, resolve_margin
from engine.models import Phase, Skill
from engine.rounding import round_half_up
from engine.rng import SeasonRNG
from engine.season import advance_after_results


def test_round_half_up():
    assert round_half_up(2.5) == 3
    assert round_half_up(-2.5) == -3
    assert round_half_up(2.4) == 2


def test_seven_factors_sum_to_margin():
    rng = SeasonRNG(42)
    for _ in range(1000):
        starters = loader.load_athletes()[:5]
        luck = rng.gauss(0, 8)
        factors = compute_factors(starters, 56, 10, 55, 8, luck)
        assert abs(factors.margin - sum(factors.as_dict().values())) < 1e-6


def test_starter_selection_excludes_unavailable():
    state = new_season("Varsity", 0, seed=1)
    state.athletes[0].games_out = 2
    starters = pick_starters(state.athletes)
    assert all(a.available for a in starters)
    assert state.athletes[0] not in starters


def test_training_gain_and_cap():
    state = new_season("Varsity", 0, seed=2)
    start_week(state)
    athlete = state.athletes[6]  # Noah Kim potential 5
    take_action(
        state,
        "focused_training",
        {"athlete_index": athlete.roster_index, "skill": Skill.SHOOTING.value},
    )
    assert athlete.shooting == 50 + 9
    athlete.fatigue = 85
    take_action(
        state,
        "focused_training",
        {"athlete_index": athlete.roster_index, "skill": Skill.SHOOTING.value},
    )
    assert athlete.shooting == 59 + 4  # halved gain from 9


def test_action_validation_moves_and_tokens():
    state = new_season("Varsity", 0, seed=3)
    start_week(state)
    for _ in range(3):
        take_action(state, "recovery")
    with pytest.raises(ValueError):
        take_action(state, "recovery")


def test_reserve_cap():
    state = new_season("Varsity", 0, seed=4)
    start_week(state)
    take_action(state, "bank_tokens", {"amount": 3})
    assert state.reserve == 3
    take_action(state, "bank_tokens", {"amount": 3})
    assert state.reserve == 6
    specs = {a.action_id: a for a in legal_actions(state)}
    assert specs["bank_tokens"].enabled is False


def test_overtime_rule():
    from engine.models import MatchFactors

    factors = MatchFactors(0, 0, 0, 0, 0, 0, 0.4)
    m, ot = resolve_margin(factors)
    assert ot and m == 1.0
    factors2 = MatchFactors(0, 0, 0, 0, 0, 0, -0.4)
    m2, ot2 = resolve_margin(factors2)
    assert ot2 and m2 == -1.0


def test_seeded_replay():
    s1 = new_season("Varsity", 0, seed=999)
    s2 = new_season("Varsity", 0, seed=999)
    s1.week = s2.week = 1
    start_week(s1)
    start_week(s2)
    take_action(s1, "team_practice")
    take_action(s2, "team_practice")
    r1 = play_game(s1)
    r2 = play_game(s2)
    assert r1.team_score == r2.team_score
    assert r1.opponent_score == r2.opponent_score


def test_qualification_transition():
    state = new_season("Varsity", 0, seed=100)
    state.week = 7
    state.wins = 4
    state.losses = 3
    state.phase = Phase.RESULTS
    advance_after_results(state)
    assert state.week == 8


def test_loader_validation(tmp_path, monkeypatch):
    bad = tmp_path / "season.json"
    bad.write_text('{"regular_season_games": 7, "opponent_ratings": [50]}', encoding="utf-8")
    monkeypatch.setattr(loader, "_DATA_ROOT", tmp_path)
    loader.clear_cache()
    with pytest.raises(ValueError):
        loader.load_season_config()
    loader.clear_cache()
    monkeypatch.setattr(loader, "_DATA_ROOT", loader.data_root())


def test_forced_program_collapse():
    state = new_season("Varsity", 0, seed=200)
    state.week = 3
    for a in state.athletes:
        a.morale = 20
        a.fatigue = 80
    state.collapse_bad_weeks = 1
    from engine.endings import update_collapse_counter, check_program_collapse

    update_collapse_counter(state)
    result = check_program_collapse(state)
    assert result is not None
