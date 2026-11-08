"""Post-game wording: picks factor lines, a headline, and a Coach's Tip.

Only wording and selection live here. Every number shown comes from the
GameResult or the current SeasonState; nothing in this module changes them.
"""
from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, replace
from typing import Callable

from engine import loader, match
from engine.models import Athlete, GameResult, SeasonState
from engine.rounding import round_half_up

FACTOR_ORDER = ("talent_gap", "fatigue", "morale", "preparation", "cohesion", "depth", "luck")
WHY_MEMORY = 6
TIP_MEMORY = 5
MIN_SHOWN = 1.0

Fits = Callable[[str], bool]


@dataclass
class WhyLine:
    factor_id: str
    signed_value: float
    display_value: float
    positive: bool
    sentence: str
    pool: str


@dataclass
class Tip:
    tip_id: str
    text: str
    action: str | None
    cost: int


def _bank() -> dict:
    return loader.load_narration()


def plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def size_tier(display_value: float) -> str:
    if display_value < 3.0:
        return "small"
    if display_value <= 8.0:
        return "medium"
    return "large"


def margin_tier(margin: int, overtime: bool) -> str:
    if overtime:
        return "overtime"
    if margin >= 20:
        return "blowout"
    if margin >= 10:
        return "comfortable"
    return "narrow"


def shown_value(value: float) -> float:
    return round(abs(value), 1)


def rank_factors(result: GameResult) -> list[tuple[str, float]]:
    """Top three factors by size; ties keep the fixed FACTOR_ORDER."""
    values = result.factors.as_dict()
    items = [(key, values[key]) for key in FACTOR_ORDER if shown_value(values[key]) >= MIN_SHOWN]
    items.sort(key=lambda kv: (-shown_value(kv[1]), FACTOR_ORDER.index(kv[0])))
    return items[:3]


def _factor_athlete(factor_id: str, positive: bool, result: GameResult) -> str | None:
    starters: list[Athlete] = result.starters
    if factor_id == "depth":
        return result.unavailable_names[0] if result.unavailable_names else None
    if not starters:
        return None
    if factor_id == "talent_gap":
        return max(starters, key=lambda a: (a.overall, -a.roster_index)).name
    if factor_id == "fatigue":
        return max(starters, key=lambda a: (match.fatigue_penalty(a), -a.roster_index)).name
    if factor_id == "morale":
        pick = max if positive else min
        return pick(starters, key=lambda a: (a.morale, -a.roster_index)).name
    return None


class Narrator:
    """Holds its own random.Random and short memories so lines rotate."""

    def __init__(self, seed: int | None = None) -> None:
        self.rng = random.Random(seed)
        self.recent: dict[str, deque[str]] = {}
        self.recent_tips: deque[str] = deque(maxlen=TIP_MEMORY)
        self.last_tip_text: str | None = None

    def _choose(self, pool_key: str, templates: list[str], fill: Callable[[str], str], fits: Fits | None) -> str:
        history = self.recent.setdefault(pool_key, deque(maxlen=WHY_MEMORY))
        filled = [(template, fill(template)) for template in templates]
        usable = [(t, text) for t, text in filled if fits is None or fits(text)]
        if not usable:
            usable = [min(filled, key=lambda pair: len(pair[1]))]
        fresh = [pair for pair in usable if pair[0] not in history]
        if fresh:
            template, text = self.rng.choice(fresh)
        else:
            order = list(history)
            template, text = min(usable, key=lambda pair: order.index(pair[0]))
        history.append(template)
        return text

    def why_lines(self, result: GameResult, fits: Fits | None = None) -> list[WhyLine]:
        bank = _bank()
        ranked = rank_factors(result)
        if not ranked:
            luck = result.factors.luck
            text = self._choose("close", bank["close"], lambda t: t, fits)
            return [WhyLine("luck", luck, shown_value(luck), luck >= 0, text, "close")]

        lines: list[WhyLine] = []
        for factor_id, signed in ranked:
            positive = signed > 0
            direction = "helped" if positive else "hurt"
            display = shown_value(signed)
            tier = size_tier(display)
            athlete = _factor_athlete(factor_id, positive, result)
            templates = bank["why"][factor_id][direction][tier]
            if athlete is None:
                templates = [t for t in templates if "{athlete}" not in t]
            pool = f"{factor_id}.{direction}.{tier}"
            text = self._choose(
                pool,
                templates,
                lambda t: t.format(value=f"{display:.1f}", athlete=athlete or ""),
                fits,
            )
            lines.append(WhyLine(factor_id, signed, display, positive, text, pool))
        return lines

    def headline(self, result: GameResult, fits: Fits | None = None) -> str:
        margin = abs(result.team_score - result.opponent_score)
        outcome = "win" if result.won else "loss"
        tier = margin_tier(margin, result.overtime)
        templates = _bank()["headlines"][outcome][tier]
        return self._choose(
            f"headline.{outcome}.{tier}",
            templates,
            lambda t: t.format(
                margin=margin,
                margin_points=plural(margin, "point"),
                opponent=result.opponent_name,
            ),
            fits,
        )

    def coach_tip(self, result: GameResult, state: SeasonState | None, fits: Fits | None = None) -> Tip:
        tips = _bank()["tips"]
        ctx = tip_context(result, state)
        eligible = [tip_id for tip_id in tips if tip_triggers(tip_id, ctx)]
        if not eligible:
            eligible = ["fallback_next" if ctx["has_next"] else "fallback_final"]

        unused = [tip_id for tip_id in eligible if tip_id not in self.recent_tips]
        if unused:
            best = min(tips[tip_id]["priority"] for tip_id in unused)
            tip_id = self.rng.choice([t for t in unused if tips[t]["priority"] == best])
        else:
            order = list(self.recent_tips)
            tip_id = min(eligible, key=order.index)

        spec = tips[tip_id]
        values = tip_values(tip_id, ctx)
        texts = [phrasing.format(**values) for phrasing in spec["phrasings"]]
        options = [text for text in texts if text != self.last_tip_text]
        fitting = [text for text in options if fits is None or fits(text)]
        text = self.rng.choice(fitting or options or texts)

        self.recent_tips.append(tip_id)
        self.last_tip_text = text
        return Tip(tip_id, text, spec["action"], int(spec["cost"]))


def win_streak(state: SeasonState) -> int:
    streak = 0
    for game in reversed(state.game_log):
        if not game.won:
            break
        streak += 1
    return streak


def next_game(state: SeasonState) -> tuple[str, int, str | None] | None:
    """(opponent, rating, playoff round or None) for the next week, if one exists."""
    cfg = loader.load_season_config()
    rs = cfg["regular_season_games"]
    last_week = rs + len(cfg["playoff_rounds"])
    if state.ending_id or state.week >= last_week:
        return None
    upcoming = replace(state, week=state.week + 1, rival_rating_bonus=0)
    name, rating = match.opponent_rating_for_week(upcoming)
    round_name = None
    if upcoming.week > rs:
        round_name = cfg["playoff_rounds"][upcoming.week - rs - 1]
    return name, rating, round_name


def tip_context(result: GameResult, state: SeasonState | None) -> dict:
    margin = abs(result.team_score - result.opponent_score)
    ctx: dict = {
        "won": result.won,
        "margin": margin,
        "margin_points": plural(margin, "point"),
        "factors": result.factors.as_dict(),
        "has_next": False,
        "games": len(state.game_log) if state else 1,
    }
    ctx["games_text"] = plural(ctx["games"], "game")
    if state is None:
        return ctx

    cfg = loader.load_season_config()
    athletes = state.athletes
    starters = match.pick_starters(athletes)
    available = match.available_count(athletes)
    upcoming = next_game(state)
    tired = max(
        (a for a in athletes if a.available),
        key=lambda a: (a.fatigue, -a.roster_index),
        default=None,
    )
    ctx.update(
        has_next=upcoming is not None,
        fatigue=round_half_up(sum(a.fatigue for a in starters) / len(starters)) if starters else 0,
        tired_name=tired.name if tired else "",
        tired_fatigue=tired.fatigue if tired else 0,
        cohesion=state.cohesion,
        morale=round_half_up(sum(a.morale for a in athletes) / len(athletes)) if athletes else 0,
        prep=state.preparation,
        available=available,
        available_players=plural(available, "player"),
        roster_open=len(athletes) < cfg["max_roster"],
        tokens=state.tokens_left,
        tokens_text=plural(state.tokens_left, "token"),
        reserve_open=state.reserve < cfg["max_reserve"],
        streak=win_streak(state),
    )
    ctx["streak_wins"] = plural(ctx["streak"], "win")
    ctx["athlete"] = ctx["tired_name"]
    ctx["game_prep"] = result.preparation
    roster_names = {a.name for a in athletes}
    ctx["recruit_available"] = any(
        r["name"] not in roster_names and r["name"] not in state.offered_recruit_names
        for r in loader.load_recruit_pool()
    )

    rs = cfg["regular_season_games"]
    wins_needed = max(0, cfg["wins_to_qualify"] - state.wins)
    ctx["wins_needed_count"] = wins_needed
    ctx["wins_word"] = "win" if wins_needed == 1 else "wins"
    ctx["regular_games_left"] = max(0, rs - state.week)

    if upcoming:
        name, rating, round_name = upcoming
        mean_r = sum(a.overall for a in starters) / len(starters) if starters else 0.0
        ctx.update(opponent=name, rating=rating, round=round_name or "", signed_gap=mean_r - rating)
        ctx["gap"] = abs(round_half_up(ctx["signed_gap"]))
    else:
        ctx.update(opponent="", rating=0, round="", signed_gap=0.0, gap=0)
    return ctx


def tip_values(tip_id: str, ctx: dict) -> dict:
    """Placeholder values for one tip; the at-risk tip names one athlete's Fatigue."""
    if tip_id == "at_risk_athlete":
        return {**ctx, "athlete": ctx["tired_name"], "fatigue": ctx["tired_fatigue"]}
    return ctx


def tip_triggers(tip_id: str, ctx: dict) -> bool:
    """True only when the tip's claim holds for the real numbers in ctx."""
    f = ctx["factors"]
    nxt = ctx["has_next"]
    if tip_id == "at_risk_athlete":
        return nxt and ctx["tired_fatigue"] >= 70
    if tip_id == "weak_fatigue":
        return nxt and f["fatigue"] <= -2.0 and ctx["fatigue"] >= 25
    if tip_id == "weak_depth":
        return nxt and ctx["available"] < 7 and ctx["roster_open"] and ctx["recruit_available"]
    if tip_id == "weak_cohesion":
        return nxt and f["cohesion"] <= -1.0 and ctx["cohesion"] < 50
    if tip_id == "weak_morale":
        return nxt and f["morale"] <= -1.0 and ctx["morale"] < 50
    if tip_id == "talent_matchup":
        return nxt and ctx["signed_gap"] <= -2 and ctx["gap"] >= 2
    if tip_id == "favorable_matchup":
        return nxt and ctx["signed_gap"] >= 3 and ctx["gap"] >= 3
    if tip_id == "protect_streak":
        return nxt and ctx["streak"] >= 2
    if tip_id == "need_wins":
        return (
            nxt
            and not ctx["round"]
            and ctx["wins_needed_count"] > 0
            and ctx["regular_games_left"] >= ctx["wins_needed_count"]
        )
    if tip_id == "playoffs_next":
        return nxt and bool(ctx["round"])
    if tip_id == "weak_prep":
        return nxt and ctx["game_prep"] >= 2 and ctx["prep"] < 10
    if tip_id == "spare_tokens":
        return nxt and ctx["tokens"] >= 2 and ctx["reserve_open"]
    if tip_id == "praise":
        return nxt and ctx["won"] and ctx["margin"] >= 10 and min(f.values()) > -3.0
    if tip_id == "fallback_next":
        return nxt
    if tip_id == "fallback_final":
        return not nxt
    return False
