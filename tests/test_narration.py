"""Post-game text: truthful numbers, short lines, no repeats, safe edge cases."""
from __future__ import annotations

import re

import pytest

from engine import events, loader, strategies
from engine.explain import explain
from engine.models import Athlete, GameResult, MatchFactors, Phase
from engine.narration import (
    FACTOR_ORDER,
    Narrator,
    margin_tier,
    rank_factors,
    size_tier,
    tip_context,
    tip_triggers,
    tip_values,
)
from engine.season import advance_after_results, check_ending, new_season, play_game

NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _simulated_games(total: int):
    """Yield (result, state) right after each game, as the results screen sees it."""
    seed = 1
    count = 0
    difficulties = ("Rookie", "Varsity", "Championship")
    while count < total:
        state = new_season(difficulties[seed % 3], seed % 8, seed=seed)
        seed += 1
        for _ in range(400):
            if state.ending_id or state.phase == Phase.REPORT:
                break
            if state.pending_event:
                events.respond_to_event(state, strategies.auto_event_choice(state))
                state.phase = Phase.PLANNING
                continue
            if state.phase not in (Phase.PLANNING, Phase.PRESEASON, Phase.EVENT):
                break
            strategies.balanced_week(state)
            if state.week == 0:
                advance_after_results(state)
                continue
            result = play_game(state)
            check_ending(state)
            yield result, state
            count += 1
            if count >= total or state.ending_id:
                break
            advance_after_results(state)


@pytest.fixture(scope="module")
def season_text():
    narrator = Narrator(seed=99)
    rows = []
    for result, state in _simulated_games(1000):
        rows.append((result, explain(result, state=state, narrator=narrator), tip_context(result, state)))
    return rows


def _athlete(name: str, **stats) -> Athlete:
    base = dict(pos="G", shooting=60, defense=60, stamina=60, potential=3, leadership=50, morale=60, fatigue=10)
    base.update(stats)
    return Athlete(name=name, **base)


def _result(factors: MatchFactors, team: int = 70, opp: int = 60, **extra) -> GameResult:
    starters = extra.pop("starters", [_athlete("Marcus Reed"), _athlete("Omar Patel", morale=30, fatigue=60)])
    return GameResult(
        week=1, opponent_name="Oak Valley", opponent_rating=55, won=team > opp,
        team_score=team, opponent_score=opp, margin=float(team - opp), factors=factors,
        starters=starters, avg_starter_fatigue=20.0, mean_r=60.0, preparation=10,
        cohesion=55, available_count=8, **extra,
    )


def _factors(**values) -> MatchFactors:
    return MatchFactors(**{key: values.get(key, 0.0) for key in FACTOR_ORDER})


def test_bank_shape_and_word_limits():
    bank = loader.load_narration()
    for factor in FACTOR_ORDER:
        for direction in ("helped", "hurt"):
            for tier in ("small", "medium", "large"):
                pool = bank["why"][factor][direction][tier]
                assert len(pool) == 4
                assert len({line.split()[0] for line in pool}) == 4, (factor, direction, tier)
                if factor == "luck":
                    assert not any(re.search(r"\byou\b|\byour\b", line, re.I) for line in pool)
    for tip_id, spec in bank["tips"].items():
        assert len(spec["phrasings"]) == 2, tip_id
        assert {"category", "priority", "action", "cost"} <= spec.keys()


def test_no_unfilled_placeholders_and_short_lines(season_text):
    for _, exp, _ in season_text:
        for text in [exp.headline, exp.coach_tip, *(line.sentence for line in exp.lines)]:
            assert "{" not in text and "}" not in text, text
        for line in exp.lines:
            assert len(line.sentence.split()) <= 10, line.sentence
        assert len(exp.coach_tip.split()) <= 18, exp.coach_tip


def test_no_tip_twice_in_a_row_over_1000_games(season_text):
    tips = [exp.coach_tip for _, exp, _ in season_text]
    assert len(tips) == 1000
    assert all(a != b for a, b in zip(tips, tips[1:]))
    assert len({exp.tip_id for _, exp, _ in season_text}) >= 8


def test_tip_trigger_is_true_and_adds_a_new_number(season_text):
    for _, exp, ctx in season_text:
        assert tip_triggers(exp.tip_id, ctx), exp.tip_id
        why_numbers = {f"{line.display_value:.1f}" for line in exp.lines}
        assert not why_numbers & set(NUMBER.findall(exp.coach_tip)), exp.coach_tip


def test_tip_numbers_match_real_state(season_text):
    for result, exp, ctx in season_text:
        values = tip_values(exp.tip_id, ctx)
        if exp.tip_id in ("at_risk_athlete", "weak_fatigue"):
            assert str(values["fatigue"]) in NUMBER.findall(exp.coach_tip)
        if exp.tip_id == "weak_cohesion":
            assert str(ctx["cohesion"]) in exp.coach_tip
        if exp.tip_id in ("talent_matchup", "favorable_matchup"):
            assert str(ctx["gap"]) in exp.coach_tip and ctx["opponent"] in exp.coach_tip
        if exp.tip_action:
            assert f"({exp.tip_cost} tokens)" in exp.coach_tip or "(free)" in exp.coach_tip


def test_line_direction_and_numbers_match_real_values(season_text):
    for result, exp, _ in season_text:
        values = result.factors.as_dict()
        for line in exp.lines:
            if line.pool == "close":
                continue
            factor, direction, tier = line.pool.split(".")
            assert line.signed_value == values[factor]
            assert direction == ("helped" if line.signed_value > 0 else "hurt")
            assert tier == size_tier(line.display_value)
            shown = NUMBER.findall(line.sentence)
            assert all(number == f"{line.display_value:.1f}" for number in shown), line.sentence
        assert str(abs(result.team_score - result.opponent_score)) in exp.headline or "overtime" in exp.headline


def test_why_lines_rotate_within_a_pool():
    narrator = Narrator(seed=5)
    result = _result(_factors(luck=5.0))
    seen = [narrator.why_lines(result)[0].sentence for _ in range(4)]
    assert len(set(seen)) == 4
    assert narrator.why_lines(result)[0].sentence != seen[-1]


def test_edge_cases_fewer_factors_ties_zero_and_first_game():
    narrator = Narrator(seed=3)
    assert narrator.why_lines(_result(_factors()))[0].pool == "close"

    lines = narrator.why_lines(_result(_factors(morale=4.0, cohesion=-4.0)))
    assert [line.factor_id for line in lines] == ["morale", "cohesion"]

    tied = rank_factors(_result(_factors(luck=5.0, talent_gap=-5.0, fatigue=-5.0, depth=-6.0)))
    assert [k for k, _ in tied] == ["depth", "talent_gap", "fatigue"]

    exp = explain(_result(_factors(luck=2.0)), state=None, narrator=narrator)
    assert exp.tip_id == "fallback_final" and "{" not in exp.coach_tip


def test_injured_athlete_named_and_overtime_headline():
    narrator = Narrator(seed=8)
    lines = narrator.why_lines(
        _result(_factors(depth=-9.0), unavailable_names=["Noah Kim"], starters=[])
    )
    assert all("{" not in line.sentence for line in lines)
    named = [narrator.why_lines(_result(_factors(depth=-9.0), unavailable_names=["Noah Kim"])) for _ in range(6)]
    assert any("Noah Kim" in batch[0].sentence for batch in named)

    ot = _result(_factors(luck=0.4), team=61, opp=60, overtime=True)
    assert margin_tier(1, True) == "overtime"
    assert "overtime" in narrator.headline(ot).lower()


def test_singular_plural_and_long_text_fallback():
    narrator = Narrator(seed=2)
    heads = {narrator.headline(_result(_factors(), team=61, opp=60)) for _ in range(8)}
    assert not any("1 points" in head for head in heads)
    tiny = narrator.why_lines(_result(_factors(luck=12.0)), fits=lambda text: len(text) < 5)
    pool = loader.load_narration()["why"]["luck"]["helped"]["large"]
    assert len(tiny[0].sentence) == min(len(t.format(value="12.0")) for t in pool)
    chosen = narrator.why_lines(_result(_factors(luck=12.0)), fits=lambda text: len(text) <= 36)
    assert len(chosen[0].sentence) <= 36
