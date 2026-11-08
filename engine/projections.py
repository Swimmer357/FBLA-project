"""Pure previews for token-spending decisions; never mutates season state."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine import loader, match, rules
from engine.models import Athlete, SeasonState, Skill


@dataclass(frozen=True)
class SpendPreview:
    title: str
    summary: str
    cost: tuple[str, ...]
    benefits: tuple[str, ...]
    drawbacks: tuple[str, ...]
    projection: tuple[str, ...] = ()
    confirm_label: str = "Confirm"


def _athlete(state: SeasonState, roster_index: int) -> Athlete:
    return next(a for a in state.athletes if a.roster_index == roster_index)


def preview_weekly_action(
    state: SeasonState,
    action_id: str,
    params: dict[str, Any] | None = None,
) -> SpendPreview:
    params = params or {}
    spec = next(a for a in rules.legal_actions(state) if a.action_id == action_id)
    cost = spec.token_cost
    base_cost = (f"Weekly tokens: {state.tokens_left} → {state.tokens_left - cost}", f"Moves: {state.moves_left} → {state.moves_left - 1}")

    if action_id == "focused_training":
        athlete = _athlete(state, int(params["athlete_index"]))
        skill = Skill(params["skill"])
        before = int(getattr(athlete, skill.value))
        gain = rules.training_gain(athlete)
        after = rules.clamp(before + gain, 0, 100)
        fatigue_after = rules.clamp(athlete.fatigue + 10, 0, 100)
        cfg = loader.load_season_config()
        total_weeks = cfg["regular_season_games"] + len(cfg["playoff_rounds"])
        sessions_left = max(0, total_weeks - state.week)
        future = min(100, after + gain * sessions_left)
        old_score = match.starter_score(athlete)
        clone = athlete.clone()
        setattr(clone, skill.value, after)
        clone.fatigue = fatigue_after
        new_score = match.starter_score(clone)
        tired = "Gain is halved because fatigue is 80+." if athlete.fatigue >= 80 else "High fatigue can reduce future training gains."
        return SpendPreview(
            title=f"Train {athlete.name}: {skill.value.title()}",
            summary=f"Spend 3 tokens and 1 move to upgrade {athlete.name}'s {skill.value}. Review the immediate improvement, workload cost, and optimistic weekly-training projection before confirming.",
            cost=base_cost,
            benefits=(f"{skill.value.title()}: {before} → {after} (+{after - before})", f"Lineup score: {old_score:.1f} → {new_score:.1f}"),
            drawbacks=(f"Fatigue: {athlete.fatigue} → {fatigue_after}", tired),
            projection=(f"If trained weekly: {skill.value.title()} could reach about {future}.", f"Potential rating: {athlete.potential} · Skill cap: 100"),
            confirm_label="Confirm Training — 3T",
        )

    if action_id == "team_practice":
        return SpendPreview(
            "Team Practice",
            "Spend 3 tokens and 1 move on a full-team practice. Preparation helps the next game, but the eight most-used athletes take on extra fatigue.",
            base_cost,
            (f"Preparation: {state.preparation} → {min(20, state.preparation + 10)}", f"Cohesion: {state.cohesion} → {min(100, state.cohesion + 2)}"),
            ("Top 8 fatigue: +4", "Preparation halves after each game"),
            confirm_label="Confirm Practice — 3T",
        )
    if action_id == "recovery":
        return SpendPreview(
            "Recovery and Wellness",
            "Spend 2 tokens and 1 move to reduce fatigue and improve morale across the entire roster.",
            base_cost,
            ("Every athlete fatigue: −15", "Every athlete morale: +2"),
            ("Uses one of this week's three moves", "Does not directly improve player skills"),
            confirm_label="Confirm Recovery — 2T",
        )
    if action_id == "team_building":
        captain = state.athletes[state.captain_index]
        cohesion_gain = 8 if captain.leadership >= 60 else 6
        return SpendPreview(
            "Team Culture",
            "Spend 2 tokens and 1 move on team-building. Captain leadership determines the final cohesion gain.",
            base_cost,
            (f"Cohesion: {state.cohesion} → {min(100, state.cohesion + cohesion_gain)}", "Every athlete morale: +3"),
            ("No direct skill increase", f"Captain leadership: {captain.leadership}"),
            confirm_label="Confirm Culture — 2T",
        )
    if action_id == "scout_recruit":
        recruit = params.get("recruit")
        if recruit is None and not params.get("decline"):
            return SpendPreview(
                "Recruiting Visit",
                "Confirming Recruit immediately spends 5 weekly tokens and 1 move, then reveals the available recruits.",
                base_cost,
                ("See up to two eligible recruits", "You may sign one or decline"),
                (
                    "The cost is non-refundable whether you sign or decline",
                    "Esc after the reveal counts as decline",
                ),
                confirm_label="Confirm Visit — 5T",
            )
        if params.get("decline"):
            return SpendPreview(
                "Decline Scouting Results",
                "End this scouting visit without signing a player. The 5-token scouting cost and one move are still spent and are not refunded.",
                base_cost,
                ("Roster remains unchanged",),
                ("No player signed", "Scouting cost is not refunded"),
                confirm_label="Confirm Decline — 5T",
            )
        if isinstance(recruit, Athlete):
            return SpendPreview(
                f"Sign {recruit.name}",
                f"Spend 5 tokens and 1 move to add {recruit.name} ({recruit.pos}) to the roster. Recruiting adds depth but temporarily disrupts team chemistry.",
                base_cost,
                (f"Shooting {recruit.shooting} · Defense {recruit.defense}", f"Stamina {recruit.stamina} · Potential {recruit.potential}"),
                (f"Cohesion: {state.cohesion} → {max(0, state.cohesion - 5)}", "Roster slot permanently used"),
                projection=(f"Current overall: {recruit.overall:.1f}", f"Future training gain: +{4 + recruit.potential} per session"),
                confirm_label="Confirm Signing — 5T",
            )
    if action_id == "bank_tokens":
        amount = min(int(params["amount"]), state.tokens_left, loader.load_season_config()["max_reserve"] - state.reserve)
        return SpendPreview(
            "Bank Emergency Tokens",
            f"Move {amount} token(s) from this week's budget into the persistent event reserve. Reserve tokens can fund event responses, but not weekly actions.",
            (f"Weekly tokens: {state.tokens_left} → {state.tokens_left - amount}", f"Moves: {state.moves_left} → {state.moves_left - 1}"),
            (f"Reserve: {state.reserve} → {state.reserve + amount}", "Protection against future events"),
            ("Fewer tokens for this week's actions", "Unused weekly tokens expire after the week"),
            confirm_label=f"Confirm Bank — {amount}T",
        )
    raise ValueError(f"No preview for action {action_id}")


def preview_event_response(state: SeasonState, response_id: str) -> SpendPreview:
    if state.pending_event is None:
        raise ValueError("No pending event")
    response = next(r for r in state.pending_event.responses if r["id"] == response_id)
    cost = int(response["token_cost"])
    weekly_used = min(state.tokens_left, cost)
    reserve_used = cost - weekly_used
    benefits: list[str] = []
    drawbacks: list[str] = []
    for effect in response["effects"]:
        delta = int(effect.get("delta", 0))
        description = {
            "draw_recruit_single": "Add one eligible transfer",
            "games_out": f"Player unavailable: {effect.get('games', 0)} game(s)",
            "morale_all": f"Team morale: {delta:+d}",
            "morale_target": f"Player morale: {delta:+d}",
            "preparation": f"Preparation: {delta:+d}",
            "cohesion": f"Cohesion: {delta:+d}",
            "fatigue_all": f"Team fatigue: {delta:+d}",
            "skip_post_game_fatigue": "Skip post-game fatigue",
            "slump_meeting": "Captain-led morale meeting",
            "mentor_best_skill": f"Best skill: +{effect.get('delta', 5)}",
            "rival_bonus": f"Opponent rating: +{effect.get('delta', 0)}",
        }.get(effect["type"], effect["type"].replace("_", " ").title())
        (benefits if delta >= 0 and effect["type"] not in {"games_out", "fatigue_all", "rival_bonus"} else drawbacks).append(description)
    if not benefits:
        benefits.append("Avoids the alternative outcome")
    if not drawbacks:
        drawbacks.append("No direct rating drawback")
    return SpendPreview(
        title=state.pending_event.title,
        summary=f"Confirm “{response['label']}”. Event costs draw from weekly tokens first, then the emergency reserve.",
        cost=(f"Total cost: {cost} token(s)", f"Weekly used: {weekly_used}", f"Reserve used: {reserve_used}"),
        benefits=tuple(benefits[:3]),
        drawbacks=tuple(drawbacks[:3]),
        confirm_label="Confirm Decision" if cost == 0 else f"Confirm Spend — {cost}T",
    )
