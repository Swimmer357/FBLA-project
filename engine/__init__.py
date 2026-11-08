"""Public engine API — no pygame imports."""
from engine.explain import Explanation, explain
from engine.models import Athlete, GameResult, Phase, SeasonState, Skill
from engine.season import (
    advance_after_results,
    begin_recruiting,
    check_ending,
    fast_forward,
    legal_actions,
    new_season,
    play_game as _play_game_internal,
    respond_to_event as _respond_to_event,
    resolve_recruiting,
    season_total_weeks,
    start_week,
    take_action,
    week_label,
)


from engine import events as event_helpers


def respond_to_event(state: SeasonState, choice: str) -> list[str]:
    return _respond_to_event(state, choice)


def play_game(state: SeasonState) -> GameResult:
    return _play_game_internal(state)


__all__ = [
    "Athlete",
    "Explanation",
    "GameResult",
    "Phase",
    "SeasonState",
    "Skill",
    "advance_after_results",
    "begin_recruiting",
    "check_ending",
    "event_helpers",
    "explain",
    "fast_forward",
    "legal_actions",
    "new_season",
    "play_game",
    "respond_to_event",
    "resolve_recruiting",
    "season_total_weeks",
    "start_week",
    "take_action",
    "week_label",
]
