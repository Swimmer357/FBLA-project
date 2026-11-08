"""Explanation panel: factor ranking, sentences, coach tip, highlights."""
from __future__ import annotations

from dataclasses import dataclass, field

from engine import narration
from engine.models import GameResult, SeasonState
from engine.narration import Fits, Narrator, WhyLine

ExplanationLine = WhyLine


@dataclass
class Explanation:
    lines: list[WhyLine]
    coach_tip: str
    highlights: list[str]
    headline: str = ""
    tip_id: str = ""
    tip_action: str | None = None
    tip_cost: int = 0
    pools: list[str] = field(default_factory=list)


def rank_factors(result: GameResult) -> list[tuple[str, float]]:
    return narration.rank_factors(result)


def explain(
    result: GameResult,
    state: SeasonState | None = None,
    narrator: Narrator | None = None,
    line_fits: Fits | None = None,
    tip_fits: Fits | None = None,
) -> Explanation:
    """Build the post-game panel. Pass the same Narrator each game to avoid repeats."""
    if narrator is None:
        narrator = Narrator(seed=result.week * 1009 + result.team_score * 31 + result.opponent_score)
    lines = narrator.why_lines(result, fits=line_fits)
    headline = narrator.headline(result, fits=line_fits)
    tip = narrator.coach_tip(result, state, fits=tip_fits)
    return Explanation(
        lines=lines,
        coach_tip=tip.text,
        highlights=_highlights(result),
        headline=headline,
        tip_id=tip.tip_id,
        tip_action=tip.action,
        tip_cost=tip.cost,
        pools=[line.pool for line in lines],
    )


def _highlights(result: GameResult) -> list[str]:
    lines: list[str] = []
    if result.leading_scorer:
        lines.append(f"Leading scorer: {result.leading_scorer}")
    if result.defensive_standout:
        lines.append(f"Defensive standout: {result.defensive_standout}")
    for name in result.fatigue_flags:
        lines.append(f"{name} was running on empty")
    if not lines:
        lines.append("No standout highlights this game.")
    return lines
