"""Match simulation: seven factors, margin, scores."""
from __future__ import annotations

from engine.models import Athlete, MatchFactors, SeasonState
from engine.rounding import round_half_up
from engine import loader

MIN_SCORE = 30
MAX_SCORE = 120
MAX_COLLISION_SHIFT = 10


def fatigue_penalty(athlete: Athlete) -> float:
    return athlete.fatigue * (1.0 - athlete.stamina / 200.0) * 0.25


def morale_effect(athlete: Athlete) -> float:
    return (athlete.morale - 50) * 0.10


def starter_score(athlete: Athlete) -> float:
    return (athlete.shooting + athlete.defense) / 2.0 - fatigue_penalty(athlete) + morale_effect(athlete)


def pick_starters(athletes: list[Athlete]) -> list[Athlete]:
    available = [a for a in athletes if a.available]
    ranked = sorted(
        available,
        key=lambda a: (-starter_score(a), -a.overall, a.roster_index),
    )
    return ranked[:5]


def available_count(athletes: list[Athlete]) -> int:
    return sum(1 for a in athletes if a.available)


def opponent_rating_for_week(state: SeasonState) -> tuple[str, int]:
    cfg = loader.load_season_config()
    diff = loader.load_difficulty()[state.difficulty]
    offset = int(diff["rating_offset"])
    week = state.week
    if week == 0:
        return ("—", 0)
    rs = cfg["regular_season_games"]
    if week <= rs:
        idx = week - 1
        name = cfg["opponent_names"][idx]
        rating = int(cfg["opponent_ratings"][idx]) + offset + state.rival_rating_bonus
        return (name, rating)
    playoff_idx = week - rs - 1
    if playoff_idx < len(cfg["playoff_ratings"]):
        name = cfg["playoff_opponents"][playoff_idx]
        rating = int(cfg["playoff_ratings"][playoff_idx]) + offset + state.rival_rating_bonus
        return (name, rating)
    return ("Opponent", 60 + offset)


def compute_factors(
    starters: list[Athlete],
    opponent_rating: int,
    preparation: int,
    cohesion: int,
    n_available: int,
    luck: float,
) -> MatchFactors:
    if not starters:
        mean_r = 0.0
        mean_f = 0.0
        mean_m = 0.0
        mean_shoot = 0.0
    else:
        rs = [(a.shooting + a.defense) / 2.0 for a in starters]
        mean_r = sum(rs) / len(starters)
        mean_f = sum(fatigue_penalty(a) for a in starters) / len(starters)
        mean_m = sum(morale_effect(a) for a in starters) / len(starters)
        mean_shoot = sum(a.shooting for a in starters) / len(starters)

    talent = mean_r - opponent_rating
    fatigue_factor = -mean_f
    morale_factor = mean_m
    prep_factor = 0.4 * preparation
    cohesion_factor = 0.1 * (cohesion - 50)
    depth_factor = -3.0 * max(0, 7 - n_available)

    return MatchFactors(
        talent_gap=talent,
        fatigue=fatigue_factor,
        morale=morale_factor,
        preparation=prep_factor,
        cohesion=cohesion_factor,
        depth=depth_factor,
        luck=luck,
    )


def resolve_margin(factors: MatchFactors) -> tuple[float, bool]:
    m = factors.margin
    if round_half_up(m) == 0:
        if factors.luck > 0:
            m = 1.0
        else:
            m = -1.0
        return m, True
    return m, False


def compute_scores(starters: list[Athlete], margin: float) -> tuple[int, int]:
    if starters:
        mean_shoot = sum(a.shooting for a in starters) / len(starters)
    else:
        mean_shoot = 50.0
    team = round_half_up(60 + 0.4 * (mean_shoot - 50) + margin / 2.0)
    team = max(MIN_SCORE, min(MAX_SCORE, team))
    opp = team - round_half_up(margin)
    opp = max(MIN_SCORE, min(MAX_SCORE, opp))
    if margin > 0 and team <= opp:
        team = min(MAX_SCORE, opp + 1)
    elif margin < 0 and team >= opp:
        opp = min(MAX_SCORE, team + 1)
    return team, opp


def unique_score_pair(
    team_score: int,
    opponent_score: int,
    previous_pairs: set[tuple[int, int]],
) -> tuple[int, int]:
    """Resolve an in-season score collision without changing the game margin.

    The original pair is retained whenever possible. On collision, both scores
    move together by +1, -1, +2, -2, ... up to ten points, staying within the
    plausible 30–120 range. A season has at most nine games, so the bounded
    candidate set always has room unless handed an invalid oversized history.
    """
    pair = (team_score, opponent_score)
    if pair not in previous_pairs:
        return pair

    for distance in range(1, MAX_COLLISION_SHIFT + 1):
        for offset in (distance, -distance):
            candidate = (team_score + offset, opponent_score + offset)
            if (
                MIN_SCORE <= candidate[0] <= MAX_SCORE
                and MIN_SCORE <= candidate[1] <= MAX_SCORE
                and candidate not in previous_pairs
            ):
                return candidate
    raise RuntimeError("Could not resolve duplicate score within bounded score range")
