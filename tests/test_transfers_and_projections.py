"""Regression tests for spending previews, event outcomes, and transfers."""
from __future__ import annotations

import copy

import pytest

from engine import legal_actions, loader, new_season, respond_to_event, take_action
from engine.events import draw_recruit_pair
from engine.models import PendingEvent, Phase
from engine.projections import preview_event_response, preview_weekly_action
from engine.rules import apply_recruit_sign


def _planning_state(seed: int = 7):
    state = new_season("Varsity", 0, seed=seed)
    state.week = 3
    state.phase = Phase.PLANNING
    state.tokens_left = 8
    state.moves_left = 3
    return state


def test_empty_effect_event_still_returns_visible_summary():
    state = _planning_state()
    event = next(e for e in loader.load_events() if e["id"] == "transfer_available")
    state.pending_event = PendingEvent(
        event_id=event["id"],
        title=event["title"],
        description=event["description"],
        responses=event["responses"],
    )
    state.phase = Phase.EVENT

    messages = respond_to_event(state, "pass")

    assert messages == ["Decision recorded. No ratings changed."]
    assert state.pending_event is None
    assert state.phase is Phase.PLANNING


def test_training_preview_matches_applied_upgrade():
    state = _planning_state()
    athlete = state.athletes[0]
    params = {"athlete_index": athlete.roster_index, "skill": "shooting"}
    preview = preview_weekly_action(state, "focused_training", params)
    clone = copy.deepcopy(state)

    take_action(clone, "focused_training", params)

    assert f"Shooting: {athlete.shooting} → {clone.athletes[0].shooting}" in preview.benefits[0]
    assert clone.tokens_left == state.tokens_left - 3
    assert clone.moves_left == state.moves_left - 1
    assert "Fatigue" in preview.drawbacks[0]
    assert preview.projection


def test_scout_sign_has_unique_index_and_duplicate_guard():
    state = _planning_state()
    recruit = draw_recruit_pair(state)[0]
    original_size = len(state.athletes)

    take_action(state, "scout_recruit", {"recruit": recruit})

    assert len(state.athletes) == original_size + 1
    assert state.athletes[-1].roster_index == original_size
    assert len({a.name for a in state.athletes}) == len(state.athletes)
    with pytest.raises(ValueError, match="already on the roster"):
        apply_recruit_sign(state, recruit)


def test_transfer_preview_labels_weekly_and_reserve_payment():
    state = _planning_state()
    state.tokens_left = 1
    state.reserve = 4
    event = next(e for e in loader.load_events() if e["id"] == "transfer_available")
    state.pending_event = PendingEvent(
        event_id=event["id"],
        title=event["title"],
        description=event["description"],
        responses=event["responses"],
    )

    preview = preview_event_response(state, "recruit_now")

    assert "Weekly used: 1" in preview.cost
    assert "Reserve used: 2" in preview.cost
    assert any("transfer" in item.lower() for item in preview.benefits)


def test_recruit_pool_never_offers_current_roster_name():
    state = _planning_state()
    first = draw_recruit_pair(state)[0]
    state.athletes.append(first)
    state.offered_recruit_names.clear()

    offered = draw_recruit_pair(state)

    assert all(candidate.name != first.name for candidate in offered)


def test_transfer_event_adds_unique_player_and_charges_cost():
    state = _planning_state(seed=19)
    event = next(e for e in loader.load_events() if e["id"] == "transfer_available")
    state.pending_event = PendingEvent(
        event_id=event["id"],
        title=event["title"],
        description=event["description"],
        responses=event["responses"],
    )
    state.phase = Phase.EVENT
    before_size = len(state.athletes)
    before_cohesion = state.cohesion

    messages = respond_to_event(state, "recruit_now")

    assert len(state.athletes) == before_size + 1
    assert state.athletes[-1].roster_index == before_size
    assert state.tokens_left == 5
    assert state.cohesion == before_cohesion - 4
    assert any("Added transfer" in message for message in messages)


def test_scout_is_disabled_at_configured_roster_cap():
    state = _planning_state()
    max_roster = loader.load_season_config()["max_roster"]
    while len(state.athletes) < max_roster:
        recruit = draw_recruit_pair(state)[0]
        recruit.roster_index = len(state.athletes)
        state.athletes.append(recruit)
        state.offered_recruit_names.add(recruit.name)

    scout = next(action for action in legal_actions(state) if action.action_id == "scout_recruit")

    assert scout.enabled is False
    assert "Roster is full" in (scout.disabled_reason or "")
