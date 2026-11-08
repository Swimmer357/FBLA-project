"""Ending checks and report text."""
from __future__ import annotations

from engine import loader
from engine.models import SeasonState


def _avg_morale(state: SeasonState) -> float:
    if not state.athletes:
        return 0.0
    return sum(a.morale for a in state.athletes) / len(state.athletes)


def _avg_fatigue(state: SeasonState) -> float:
    if not state.athletes:
        return 0.0
    return sum(a.fatigue for a in state.athletes) / len(state.athletes)


def _available_count(state: SeasonState) -> int:
    return sum(1 for a in state.athletes if a.available)


def update_collapse_counter(state: SeasonState) -> None:
    cfg = loader.load_season_config()
    if state.week < cfg["collapse_start_week"]:
        return
    bad = _available_count(state) < 5 or (
        _avg_morale(state) <= 25 and _avg_fatigue(state) >= 75
    )
    if bad:
        state.collapse_bad_weeks += 1
    else:
        state.collapse_bad_weeks = 0


def check_program_collapse(state: SeasonState) -> tuple[str, str] | None:
    cfg = loader.load_season_config()
    if state.week < cfg["collapse_start_week"]:
        return None
    if state.collapse_bad_weeks >= 2:
        exp = loader.load_explanations()["endings"]["program_collapse"]
        reason = exp.format(
            morale=round(_avg_morale(state)),
            fatigue=round(_avg_fatigue(state)),
        )
        return ("program_collapse", reason)
    return None


def check_ending(state: SeasonState) -> tuple[str, str] | None:
    collapse = check_program_collapse(state)
    if collapse:
        return collapse

    cfg = loader.load_season_config()
    rs = cfg["regular_season_games"]
    if state.phase.value == "ended" or state.ending_id:
        return None

    # After last game played
    if state.last_result is None:
        return None

    week = state.last_result.week
    if week <= rs:
        return None

    if week == rs + 1 and not state.last_result.won:
        exp = loader.load_explanations()["endings"]["playoff_exit"]
        return ("playoff_exit", exp)

    if week == rs + 2:
        if state.last_result.won:
            return ("state_champion", loader.load_explanations()["endings"]["state_champion"])
        return ("finalist", loader.load_explanations()["endings"]["finalist"])

    return None


def check_missed_playoffs(state: SeasonState) -> tuple[str, str] | None:
    cfg = loader.load_season_config()
    rs = cfg["regular_season_games"]
    if state.week != rs:
        return None
    if state.wins >= cfg["wins_to_qualify"]:
        return None
    exp = loader.load_explanations()["endings"]["missed_playoffs"]
    reason = exp.format(
        wins=state.wins,
        games=rs,
        needed=cfg["wins_to_qualify"],
    )
    return ("missed_playoffs", reason)
