"""Explanation panel: factor ranking, sentences, coach tip, highlights."""
from __future__ import annotations

from dataclasses import dataclass

from engine import loader, match
from engine.models import GameResult, MatchFactors


@dataclass
class ExplanationLine:
    factor_id: str
    signed_value: float
    display_value: float
    positive: bool
    sentence: str


@dataclass
class Explanation:
    lines: list[ExplanationLine]
    coach_tip: str
    highlights: list[str]


def _format_value(val: float) -> str:
    return f"{abs(val):.1f}"


def _sentence_for_factor(
    factor_id: str,
    signed: float,
    result: GameResult,
) -> str:
    data = loader.load_explanations()["factors"][factor_id]
    positive = signed >= 0
    template = data["positive"] if positive else data["negative"]
    display = abs(signed)
    ctx = {
        "value": _format_value(display),
        "mean_r": f"{result.mean_r:.1f}",
        "opp": str(result.opponent_rating),
        "avg_fatigue": f"{result.avg_starter_fatigue:.1f}",
        "prep": str(result.preparation),
        "cohesion": str(result.cohesion),
        "available": str(result.available_count),
    }
    return template.format(**ctx)


def rank_factors(factors: MatchFactors) -> list[tuple[str, float]]:
    items = list(factors.as_dict().items())
    filtered = [(k, v) for k, v in items if abs(v) >= 1.0]
    filtered.sort(key=lambda kv: abs(kv[1]), reverse=True)
    return filtered[:3]


def explain(result: GameResult) -> Explanation:
    exp_data = loader.load_explanations()
    ranked = rank_factors(result.factors)
    lines: list[ExplanationLine] = []
    if not ranked:
        lines.append(
            ExplanationLine(
                factor_id="luck",
                signed_value=result.factors.luck,
                display_value=abs(result.factors.luck),
                positive=result.factors.luck >= 0,
                sentence=exp_data["close_game"],
            )
        )
    else:
        for factor_id, signed in ranked:
            lines.append(
                ExplanationLine(
                    factor_id=factor_id,
                    signed_value=signed,
                    display_value=abs(signed),
                    positive=signed >= 0,
                    sentence=_sentence_for_factor(factor_id, signed, result),
                )
            )

    coach_tip = _coach_tip(result.factors)
    highlights = _highlights(result)
    return Explanation(lines=lines, coach_tip=coach_tip, highlights=highlights)


def _coach_tip(factors: MatchFactors) -> str:
    tips = loader.load_explanations()["coach_tips"]
    controllable = [
        ("fatigue", factors.fatigue),
        ("morale", factors.morale),
        ("cohesion", factors.cohesion),
        ("preparation", factors.preparation),
        ("depth", factors.depth),
        ("talent_gap", factors.talent_gap),
    ]
    negatives = [(k, v) for k, v in controllable if v < -0.5]
    if not negatives:
        return "Keep balancing training, practice, and recovery each week."
    factor_id, _ = min(negatives, key=lambda kv: kv[1])
    return tips.get(factor_id, tips["fatigue"])


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
