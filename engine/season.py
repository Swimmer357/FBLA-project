"""Season state machine and public engine API."""
from __future__ import annotations

import copy
from typing import Any

from engine import endings, events, explain, loader, match, rules, strategies
from engine.models import GameResult, Phase, SeasonState
from engine.rng import SeasonRNG


def _snapshot_stats(athletes) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for a in athletes:
        out[a.name] = {
            "shooting": a.shooting,
            "defense": a.defense,
            "stamina": a.stamina,
        }
    return out


def new_season(difficulty: str, captain_index: int, seed: int | None = None) -> SeasonState:
    diffs = loader.load_difficulty()
    if difficulty not in diffs:
        raise ValueError(f"Unknown difficulty {difficulty}")
    cfg = loader.load_season_config()
    athletes = loader.load_athletes()
    if captain_index < 0 or captain_index >= len(athletes):
        raise ValueError("Invalid captain")
    import random as _random

    actual_seed = seed if seed is not None else _random.randint(1, 999_999)
    rng = SeasonRNG(seed=actual_seed)

    tokens = int(diffs[difficulty]["weekly_tokens"])
    state = SeasonState(
        difficulty=difficulty,
        seed=actual_seed,
        week=0,
        phase=Phase.PRESEASON,
        athletes=athletes,
        captain_index=captain_index,
        cohesion=int(cfg["starting_cohesion"]),
        preparation=int(cfg["starting_preparation"]),
        reserve=0,
        wins=0,
        losses=0,
        tokens_budget=tokens,
        tokens_left=tokens,
        moves_left=int(cfg["moves_per_week"]),
        moves_used=0,
        pending_event=None,
        last_result=None,
        ending_id=None,
        ending_reason=None,
        offered_recruit_names=set(),
        active_recruit_names=set(),
        loss_streak=0,
        collapse_bad_weeks=0,
        skip_post_game_fatigue=False,
        rival_rating_bonus=0,
        game_log=[],
        week_action_log={},
        starting_stats=_snapshot_stats(athletes),
        rng=rng,
    )
    return state


def _reset_weekly_budget(state: SeasonState) -> None:
    diff = loader.load_difficulty()[state.difficulty]
    cfg = loader.load_season_config()
    state.tokens_budget = int(diff["weekly_tokens"])
    state.tokens_left = state.tokens_budget
    state.moves_left = int(cfg["moves_per_week"])
    state.skip_post_game_fatigue = False
    state.rival_rating_bonus = 0


def start_week(state: SeasonState) -> PendingEvent | None:
    from engine.models import PendingEvent

    cfg = loader.load_season_config()
    if state.phase == Phase.ENDED:
        return None
    if state.phase not in (Phase.PRESEASON, Phase.RESULTS):
        raise ValueError(f"Cannot start a week during {state.phase.value}")

    for a in state.athletes:
        a.fatigue = rules.clamp(a.fatigue - int(cfg["weekly_fatigue_rest"]), 0, 100)

    state.pending_event = events.roll_event(state)
    state.phase = Phase.EVENT if state.pending_event else Phase.PLANNING
    return state.pending_event


def respond_to_event(state: SeasonState, choice: str) -> list[str]:
    return events.respond_to_event(state, choice)


def legal_actions(state: SeasonState):
    return rules.legal_actions(state)


def take_action(state: SeasonState, action: str, params: dict | None = None) -> None:
    rules.take_action(state, action, params)


def begin_recruiting(state: SeasonState):
    return rules.begin_recruiting(state)


def resolve_recruiting(state: SeasonState, recruit=None) -> None:
    rules.resolve_recruiting(state, recruit)


def _highlight_names(state: SeasonState, starters) -> tuple[str | None, str | None, list[str]]:
    if not starters:
        return None, None, []
    scorer = state.rng.weighted_choice(starters, [max(1, a.shooting) for a in starters])
    defender = max(starters, key=lambda a: a.defense - match.fatigue_penalty(a))
    flags = [
        a.name for a in starters if match.fatigue_penalty(a) >= 6.0
    ]
    return scorer.name, defender.name, flags


def play_game(state: SeasonState) -> GameResult:
    if state.week <= 0:
        raise ValueError("Preseason has no game")
    if state.phase not in (Phase.PLANNING, Phase.MATCH):
        raise ValueError(f"Cannot play a game during {state.phase.value}")
    if state.pending_event is not None:
        raise ValueError("Resolve the pending event before playing")
    if any(result.week == state.week for result in state.game_log):
        raise ValueError(f"Week {state.week} has already been played")

    cfg = loader.load_season_config()
    opp_name, opp_rating = match.opponent_rating_for_week(state)
    starters = match.pick_starters(state.athletes)
    n_avail = match.available_count(state.athletes)
    luck = state.rng.gauss(0, 8)
    factors = match.compute_factors(
        starters,
        opp_rating,
        state.preparation,
        state.cohesion,
        n_avail,
        luck,
    )
    margin, overtime = match.resolve_margin(factors)
    unavailable_names = [a.name for a in state.athletes if not a.available]
    team_score, opp_score = match.compute_scores(starters, margin)
    previous_pairs = {(game.team_score, game.opponent_score) for game in state.game_log}
    team_score, opp_score = match.unique_score_pair(team_score, opp_score, previous_pairs)
    won = margin > 0

    avg_fat = sum(a.fatigue for a in starters) / len(starters) if starters else 0.0
    mean_r = (
        sum((a.shooting + a.defense) / 2.0 for a in starters) / len(starters)
        if starters
        else 0.0
    )
    ls, ds, flags = _highlight_names(state, starters)
    result = GameResult(
        week=state.week,
        opponent_name=opp_name,
        opponent_rating=opp_rating,
        won=won,
        team_score=team_score,
        opponent_score=opp_score,
        margin=margin,
        factors=factors,
        starters=[a.clone() for a in starters],
        avg_starter_fatigue=avg_fat,
        mean_r=mean_r,
        preparation=state.preparation,
        cohesion=state.cohesion,
        available_count=n_avail,
        skip_fatigue_this_game=state.skip_post_game_fatigue,
        leading_scorer=ls,
        defensive_standout=ds,
        fatigue_flags=flags,
        overtime=overtime,
        unavailable_names=unavailable_names,
    )

    if won:
        state.wins += 1
        state.loss_streak = 0
    else:
        state.losses += 1
        state.loss_streak += 1

    state.preparation //= 2
    if not state.skip_post_game_fatigue:
        starter_set = {a.name for a in starters}
        for a in starters:
            a.fatigue = rules.clamp(a.fatigue + int(cfg["starter_fatigue_game"]), 0, 100)
        bench = [
            a
            for a in rules.sorted_by_starter_score(state.athletes)
            if a.available and a.name not in starter_set
        ][: int(cfg["bench_depth_count"])]
        for a in bench:
            a.fatigue = rules.clamp(a.fatigue + int(cfg["bench_fatigue_game"]), 0, 100)

    morale_delta = int(cfg["morale_win"] if won else cfg["morale_loss"])
    for a in state.athletes:
        a.morale = rules.clamp(a.morale + morale_delta, 0, 100)
    coh_delta = int(cfg["cohesion_win"] if won else cfg["cohesion_loss"])
    state.cohesion = rules.clamp(state.cohesion + coh_delta, 0, 100)

    played = {s.name for s in starters}
    for a in state.athletes:
        if a.name not in played and a.games_out > 0:
            a.games_out -= 1

    state.game_log.append(result)
    state.last_result = result
    endings.update_collapse_counter(state)
    state.phase = Phase.RESULTS
    return result


def explain_result(result: GameResult):
    return explain.explain(result)


def check_ending(state: SeasonState):
    collapse = endings.check_program_collapse(state)
    if collapse:
        state.ending_id, state.ending_reason = collapse
        state.phase = Phase.ENDED
        return collapse
    missed = endings.check_missed_playoffs(state)
    if missed and state.week == loader.load_season_config()["regular_season_games"]:
        state.ending_id, state.ending_reason = missed
        state.phase = Phase.ENDED
        return missed
    normal = endings.check_ending(state)
    if normal:
        state.ending_id, state.ending_reason = normal
        state.phase = Phase.ENDED
    return normal


def advance_after_results(state: SeasonState) -> None:
    if state.ending_id:
        state.phase = Phase.REPORT
        return

    cfg = loader.load_season_config()
    rs = cfg["regular_season_games"]
    playoff_count = len(cfg["playoff_rounds"])
    last_week = rs + playoff_count

    if state.week == 0:
        if state.phase not in (Phase.PRESEASON, Phase.PLANNING):
            raise ValueError(f"Cannot finish preseason during {state.phase.value}")
        state.week = 1
        _reset_weekly_budget(state)
        state.phase = Phase.RESULTS
        start_week(state)
        return

    if state.phase != Phase.RESULTS:
        raise ValueError(f"Cannot advance before week {state.week} results")

    if state.week == rs:
        if state.wins < cfg["wins_to_qualify"]:
            missed = endings.check_missed_playoffs(state)
            if missed:
                state.ending_id, state.ending_reason = missed
            state.phase = Phase.REPORT
            return

    if state.week >= last_week:
        state.phase = Phase.REPORT
        return

    state.week += 1
    _reset_weekly_budget(state)
    start_week(state)


def complete_preseason_planning(state: SeasonState) -> None:
    """After week 0 planning with no game."""
    state.week = 0
    advance_after_results(state)


def finish_planning_and_play(state: SeasonState) -> GameResult:
    return play_game(state)


def fast_forward(state: SeasonState) -> SeasonState:
    for _ in range(400):
        if state.ending_id:
            break
        if state.pending_event:
            events.respond_to_event(state, strategies.auto_event_choice(state))
            state.phase = Phase.PLANNING
            continue
        if state.phase in (Phase.PLANNING, Phase.PRESEASON, Phase.EVENT):
            if state.pending_event:
                continue
            strategies.balanced_week(state)
            if state.week == 0:
                advance_after_results(state)
                continue
            play_game(state)
            check_ending(state)
            if state.ending_id:
                break
            advance_after_results(state)
            if state.phase == Phase.REPORT:
                break
            continue
        break
    state.phase = Phase.REPORT
    return state


def season_total_weeks() -> int:
    cfg = loader.load_season_config()
    return cfg["regular_season_games"] + len(cfg["playoff_rounds"])


def week_label(state: SeasonState) -> str:
    cfg = loader.load_season_config()
    total = season_total_weeks()
    if state.week == 0:
        return f"Week 0 of {total}: Preseason planning"
    rs = cfg["regular_season_games"]
    if state.week <= rs:
        return f"Week {state.week} of {total}: Game {state.week}"
    playoff_idx = state.week - rs
    round_name = cfg["playoff_rounds"][playoff_idx - 1]
    return f"Week {state.week} of {total}: {round_name}"


def clone_state(state: SeasonState) -> SeasonState:
    return copy.deepcopy(state)
