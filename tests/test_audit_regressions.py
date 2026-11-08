"""Regression coverage for the engine/data audit and scenario diversity."""
from __future__ import annotations

import asyncio
import copy
import json

import pytest

from engine import (
    begin_recruiting,
    fast_forward,
    loader,
    new_season,
    play_game,
    respond_to_event,
    resolve_recruiting,
    start_week,
    take_action,
)
from engine.events import draw_recruit_pair
from engine.match import MAX_SCORE, MIN_SCORE, unique_score_pair
from engine.models import Athlete, PendingEvent, Phase
from engine.season import advance_after_results
from engine.strategies import training_heavy_week


def _pending(state, event_id: str) -> None:
    event = next(item for item in loader.load_events() if item["id"] == event_id)
    state.pending_event = PendingEvent(
        event_id=event["id"],
        title=event["title"],
        description=event["description"],
        responses=copy.deepcopy(event["responses"]),
    )
    state.phase = Phase.EVENT


def test_score_collision_resolution_is_bounded_and_margin_preserving():
    previous = {(70, 60), (71, 61), (69, 59)}

    resolved = unique_score_pair(70, 60, previous)

    assert resolved == (72, 62)
    assert resolved[0] - resolved[1] == 10
    assert MIN_SCORE <= resolved[0] <= MAX_SCORE
    assert MIN_SCORE <= resolved[1] <= MAX_SCORE


def test_every_fast_forwarded_season_has_unique_plausible_scores_and_replays():
    for seed in range(40):
        first = fast_forward(new_season("Varsity", 0, seed=seed))
        replay = fast_forward(new_season("Varsity", 0, seed=seed))
        scores = [(game.team_score, game.opponent_score) for game in first.game_log]

        assert len(scores) == len(set(scores))
        assert scores == [(game.team_score, game.opponent_score) for game in replay.game_log]
        for game in first.game_log:
            assert MIN_SCORE <= game.team_score <= MAX_SCORE
            assert MIN_SCORE <= game.opponent_score <= MAX_SCORE
            assert (game.team_score > game.opponent_score) is game.won


def test_week_game_and_action_phase_guards_block_replays_and_skips():
    state = new_season("Varsity", 0, seed=12)
    start_week(state)
    with pytest.raises(ValueError, match="Cannot start"):
        start_week(state)

    advance_after_results(state)
    with pytest.raises(ValueError, match="advance"):
        advance_after_results(state)

    state.pending_event = None
    state.phase = Phase.PLANNING
    take_action(state, "recovery")
    play_game(state)
    with pytest.raises(ValueError, match="already been played|Cannot play"):
        play_game(state)
    with pytest.raises(ValueError, match="unavailable during results"):
        take_action(state, "recovery")


def test_training_uses_roster_id_and_rejects_injured_or_unknown_player():
    state = new_season("Varsity", 0, seed=13)
    start_week(state)
    state.athletes[0].roster_index = 40
    before = state.athletes[0].shooting
    take_action(state, "focused_training", {"athlete_index": 40, "skill": "shooting"})
    assert state.athletes[0].shooting > before

    state.athletes[1].games_out = 1
    with pytest.raises(ValueError, match="unavailable"):
        take_action(
            state,
            "focused_training",
            {"athlete_index": state.athletes[1].roster_index, "skill": "defense"},
        )
    with pytest.raises(ValueError, match="Unknown roster index"):
        take_action(state, "focused_training", {"athlete_index": -1, "skill": "defense"})


def test_training_strategy_skips_unavailable_targets():
    state = new_season("Varsity", 0, seed=130)
    start_week(state)
    highest_potential = max(state.athletes, key=lambda athlete: athlete.potential)
    highest_potential.games_out = 1

    training_heavy_week(state)

    assert all(highest_potential.name not in action for action in state.week_action_log[0])


def test_fabricated_recruit_and_unknown_event_response_are_rejected_cleanly():
    state = new_season("Varsity", 0, seed=14)
    start_week(state)
    fake = Athlete("Made Up Star", "G", 99, 99, 99, 5, 99)
    with pytest.raises(ValueError, match="eligible recruit pool"):
        take_action(state, "scout_recruit", {"recruit": fake})

    state = new_season("Varsity", 0, seed=15)
    state.week = 2
    state.tokens_left = 8
    _pending(state, "full_court_press")
    with pytest.raises(ValueError, match="Unknown response"):
        respond_to_event(state, "not_a_choice")


def test_new_press_scenario_has_distinct_balanced_branches():
    drills = new_season("Varsity", 0, seed=16)
    drills.week = 2
    drills.tokens_left = 8
    _pending(drills, "full_court_press")
    trust = copy.deepcopy(drills)

    respond_to_event(drills, "press_break_drills")
    respond_to_event(trust, "trust_guards")

    assert drills.preparation == 6
    assert all(athlete.fatigue == 13 for athlete in drills.athletes)
    assert drills.tokens_left == 6
    assert trust.preparation == 0
    assert trust.cohesion == 58
    assert trust.tokens_left == 8


def test_new_showcase_scenario_trades_morale_fatigue_and_preparation():
    clinic = new_season("Varsity", 0, seed=17)
    clinic.week = 2
    _pending(clinic, "community_showcase")
    practice = copy.deepcopy(clinic)

    respond_to_event(clinic, "host_clinic")
    respond_to_event(practice, "protect_practice")

    assert all(athlete.morale == 64 and athlete.fatigue == 12 for athlete in clinic.athletes)
    assert practice.preparation == 4
    assert all(athlete.morale == 58 for athlete in practice.athletes)


def test_loader_rejects_duplicate_people_and_unknown_effect(tmp_path, monkeypatch):
    athletes = json.loads((loader.data_root() / "athletes.json").read_text(encoding="utf-8"))
    athletes["athletes"].append(copy.deepcopy(athletes["athletes"][0]))
    (tmp_path / "athletes.json").write_text(json.dumps(athletes), encoding="utf-8")
    monkeypatch.setattr(loader, "_DATA_ROOT", tmp_path)
    loader.clear_cache()
    with pytest.raises(ValueError, match="duplicate name"):
        loader.load_athletes()

    events = {
        "events": [
            {
                "id": "bad",
                "title": "Bad",
                "description": "Bad",
                "trigger": "random",
                "responses": [
                    {
                        "id": "a",
                        "label": "A",
                        "token_cost": 0,
                        "effects": [{"type": "not_real"}],
                    },
                    {"id": "b", "label": "B", "token_cost": 0, "effects": []},
                ],
            }
        ]
    }
    (tmp_path / "events.json").write_text(json.dumps(events), encoding="utf-8")
    loader.clear_cache()
    with pytest.raises(ValueError, match="unknown or malformed effect"):
        loader.load_events()
    loader.clear_cache()


def test_drawn_recruit_remains_valid_for_signing():
    state = new_season("Varsity", 0, seed=18)
    start_week(state)
    recruit = draw_recruit_pair(state)[0]
    take_action(state, "scout_recruit", {"recruit": recruit})
    assert state.athletes[-1].name == recruit.name


def test_recruit_visit_charges_once_before_reveal_then_signs_without_charge():
    state = new_season("Varsity", 0, seed=181)
    start_week(state)
    before = (state.tokens_left, state.moves_left)

    recruits = begin_recruiting(state)

    assert (state.tokens_left, state.moves_left) == (before[0] - 5, before[1] - 1)
    charged = (state.tokens_left, state.moves_left)
    resolve_recruiting(state, recruits[0])
    assert (state.tokens_left, state.moves_left) == charged
    assert state.athletes[-1].name == recruits[0].name


@pytest.mark.parametrize("escape_style", [False, True])
def test_recruit_decline_or_escape_resolution_never_charges_twice(escape_style):
    state = new_season("Varsity", 0, seed=182 + int(escape_style))
    start_week(state)
    begin_recruiting(state)
    charged = (state.tokens_left, state.moves_left)

    resolve_recruiting(state, None)

    assert (state.tokens_left, state.moves_left) == charged
    assert not state.active_recruit_names


def test_unconfirmed_recruit_preview_spends_nothing():
    state = new_season("Varsity", 0, seed=184)
    start_week(state)
    before = (state.tokens_left, state.moves_left, state.rng._rng.getstate())

    from engine.projections import preview_weekly_action

    preview = preview_weekly_action(state, "scout_recruit", {})
    assert "non-refundable" in " ".join(preview.drawbacks).lower()
    assert (state.tokens_left, state.moves_left, state.rng._rng.getstate()) == before


def test_top_level_crash_log_preserves_traceback(tmp_path, monkeypatch):
    import main as entrypoint

    class BrokenApp:
        async def run(self):
            raise RuntimeError("render transition failed")

    monkeypatch.setattr(entrypoint, "ROOT", tmp_path)
    monkeypatch.setattr(entrypoint, "GameApp", BrokenApp)

    with pytest.raises(RuntimeError, match="render transition failed"):
        asyncio.run(entrypoint.main())

    crash = (tmp_path / "crash.log").read_text(encoding="utf-8")
    assert "RuntimeError: render transition failed" in crash
    assert "Traceback (most recent call last)" in crash
