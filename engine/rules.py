"""Weekly action validation and application."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine import loader, match
from engine.models import Athlete, Phase, SeasonState, Skill


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def training_gain(athlete: Athlete) -> int:
    gain = 4 + athlete.potential
    if athlete.fatigue >= 80:
        gain //= 2
    return gain


def sorted_by_starter_score(athletes: list[Athlete]) -> list[Athlete]:
    return sorted(
        athletes,
        key=lambda a: (-match.starter_score(a), -a.overall, a.roster_index),
    )


@dataclass
class ActionSpec:
    action_id: str
    label: str
    token_cost: int
    effect: str
    enabled: bool
    disabled_reason: str | None


ACTION_DEFS = [
    ("focused_training", "Focused Training", 3, "Train one athlete in Shooting, Defense, or Stamina (+4 + Potential)."),
    ("team_practice", "Team Practice", 3, "Preparation +10 (max 20), Cohesion +2, Fatigue +4 for top 8 by starter score."),
    ("recovery", "Recovery and Wellness", 2, "All athletes: Fatigue −15, Morale +2."),
    ("team_building", "Team-Building", 2, "Cohesion +6, all Morale +3; +2 Cohesion if captain Leadership ≥ 60."),
    ("scout_recruit", "Scout and Recruit", 5, "See 2 recruits; sign one (Cohesion −5) or decline (no refund)."),
    ("bank_tokens", "Bank Tokens", 0, "Move 1–3 tokens into reserve (costs 1 move; pick amount)."),
]


def _moves_used(state: SeasonState) -> int:
    cfg = loader.load_season_config()
    return cfg["moves_per_week"] - state.moves_left


def _can_afford(state: SeasonState, cost: int) -> bool:
    return state.tokens_left >= cost


def _move_cap_reached(state: SeasonState) -> bool:
    return state.moves_left <= 0


def legal_actions(state: SeasonState) -> list[ActionSpec]:
    cfg = loader.load_season_config()
    specs: list[ActionSpec] = []
    for action_id, label, cost, effect in ACTION_DEFS:
        enabled = True
        reason: str | None = None
        if state.phase not in (Phase.PRESEASON, Phase.PLANNING):
            enabled = False
            reason = f"Actions are unavailable during {state.phase.value}."
        elif action_id == "bank_tokens":
            cost = 0
            if _move_cap_reached(state):
                enabled = False
                reason = "No moves left this week."
            elif state.tokens_left <= 0:
                enabled = False
                reason = "No tokens left to bank."
            elif state.reserve >= cfg["max_reserve"]:
                enabled = False
                reason = f"Reserve is full ({cfg['max_reserve']} of {cfg['max_reserve']})."
        else:
            if _move_cap_reached(state):
                enabled = False
                reason = "No moves left this week."
            elif not _can_afford(state, cost):
                enabled = False
                reason = f"Needs {cost} tokens; you have {state.tokens_left} this week."
            elif action_id == "scout_recruit" and len(state.athletes) >= cfg["max_roster"]:
                enabled = False
                reason = f"Roster is full: {cfg['max_roster']} of {cfg['max_roster']}."
            elif action_id == "scout_recruit":
                roster_names = {a.name for a in state.athletes}
                available = [
                    r
                    for r in loader.load_recruit_pool()
                    if r["name"] not in roster_names and r["name"] not in state.offered_recruit_names
                ]
                if not available:
                    enabled = False
                    reason = "No eligible recruits remain in the pool."
        specs.append(
            ActionSpec(
                action_id=action_id,
                label=label,
                token_cost=cost if action_id != "bank_tokens" else 0,
                effect=effect,
                enabled=enabled,
                disabled_reason=reason,
            )
        )
    return specs


def apply_focused_training(state: SeasonState, athlete_index: int, skill: Skill) -> None:
    athlete = next(
        (candidate for candidate in state.athletes if candidate.roster_index == athlete_index),
        None,
    )
    if athlete is None:
        raise ValueError(f"Unknown roster index {athlete_index}")
    if not athlete.available:
        raise ValueError(f"{athlete.name} is unavailable and cannot train")
    gain = training_gain(athlete)
    current = getattr(athlete, skill.value)
    setattr(athlete, skill.value, clamp(current + gain, 0, 100))
    athlete.fatigue = clamp(athlete.fatigue + 10, 0, 100)
    state.tokens_left -= 3
    state.moves_left -= 1
    state.week_action_log.setdefault(state.week, []).append(
        f"Focused Training: {athlete.name} {skill.value} +{gain}"
    )


def apply_team_practice(state: SeasonState) -> None:
    cfg = loader.load_season_config()
    state.preparation = clamp(state.preparation + 10, 0, 20)
    state.cohesion = clamp(state.cohesion + 2, 0, 100)
    top = sorted_by_starter_score(state.athletes)[:8]
    for a in top:
        a.fatigue = clamp(a.fatigue + 4, 0, 100)
    state.tokens_left -= 3
    state.moves_left -= 1
    state.week_action_log.setdefault(state.week, []).append("Team Practice")


def apply_recovery(state: SeasonState) -> None:
    for a in state.athletes:
        a.fatigue = clamp(a.fatigue - 15, 0, 100)
        a.morale = clamp(a.morale + 2, 0, 100)
    state.tokens_left -= 2
    state.moves_left -= 1
    state.week_action_log.setdefault(state.week, []).append("Recovery and Wellness")


def apply_team_building(state: SeasonState) -> None:
    captain = state.athletes[state.captain_index]
    bonus = 2 if captain.leadership >= 60 else 0
    state.cohesion = clamp(state.cohesion + 6 + bonus, 0, 100)
    for a in state.athletes:
        a.morale = clamp(a.morale + 3, 0, 100)
    state.tokens_left -= 2
    state.moves_left -= 1
    state.week_action_log.setdefault(state.week, []).append("Team-Building")


def recruit_from_template(state: SeasonState, template: dict[str, Any]) -> Athlete:
    idx = len(state.athletes)
    return Athlete(
        name=template["name"],
        pos=template["pos"],
        shooting=int(template["shooting"]),
        defense=int(template["defense"]),
        stamina=int(template["stamina"]),
        potential=int(template["potential"]),
        leadership=int(template["leadership"]),
        morale=55,
        fatigue=0,
        roster_index=idx,
    )


def _validate_recruit(state: SeasonState, recruit: Athlete) -> None:
    cfg = loader.load_season_config()
    if len(state.athletes) >= cfg["max_roster"]:
        raise ValueError("Roster full")
    if any(a.name == recruit.name for a in state.athletes):
        raise ValueError(f"{recruit.name} is already on the roster")
    template = next(
        (item for item in loader.load_recruit_pool() if item["name"] == recruit.name),
        None,
    )
    if template is None:
        raise ValueError("Recruit is not from the eligible recruit pool")
    expected = (
        template["pos"],
        int(template["shooting"]),
        int(template["defense"]),
        int(template["stamina"]),
        int(template["potential"]),
        int(template["leadership"]),
    )
    actual = (
        recruit.pos,
        recruit.shooting,
        recruit.defense,
        recruit.stamina,
        recruit.potential,
        recruit.leadership,
    )
    if actual != expected:
        raise ValueError("Recruit is not currently eligible")


def apply_recruit_sign(state: SeasonState, recruit: Athlete) -> None:
    _validate_recruit(state, recruit)
    recruit.roster_index = len(state.athletes)
    state.athletes.append(recruit)
    state.cohesion = clamp(state.cohesion - 5, 0, 100)
    state.offered_recruit_names.add(recruit.name)
    state.week_action_log.setdefault(state.week, []).append(f"Signed recruit {recruit.name}")


def apply_scout_recruit_decline(state: SeasonState) -> None:
    state.week_action_log.setdefault(state.week, []).append("Scout and Recruit (declined)")


def _charge_recruit_visit(state: SeasonState) -> None:
    state.tokens_left -= 5
    state.moves_left -= 1


def begin_recruiting(state: SeasonState) -> list[Athlete]:
    """Charge one non-refundable scouting visit, then return its candidates."""
    if state.active_recruit_names:
        raise ValueError("A recruiting visit is already active")
    spec = next(action for action in legal_actions(state) if action.action_id == "scout_recruit")
    if not spec.enabled:
        raise ValueError(spec.disabled_reason or "Recruiting is unavailable")
    from engine.events import draw_recruit_pair

    recruits = draw_recruit_pair(state)
    if not recruits:
        raise ValueError("No eligible recruits remain in the pool")
    _charge_recruit_visit(state)
    state.active_recruit_names = {recruit.name for recruit in recruits}
    state.offered_recruit_names.update(state.active_recruit_names)
    state.week_action_log.setdefault(state.week, []).append("Scout and Recruit (visit confirmed)")
    return recruits


def resolve_recruiting(state: SeasonState, recruit: Athlete | None = None) -> None:
    """Resolve a paid visit without charging tokens or moves again."""
    if not state.active_recruit_names:
        raise ValueError("No recruiting visit is active")
    if recruit is None:
        apply_scout_recruit_decline(state)
    else:
        if recruit.name not in state.active_recruit_names:
            raise ValueError("Recruit was not offered in the active visit")
        apply_recruit_sign(state, recruit)
    state.active_recruit_names.clear()


def apply_bank_tokens(state: SeasonState, amount: int) -> None:
    cfg = loader.load_season_config()
    if amount < 1 or amount > 3:
        raise ValueError("Bank amount must be 1–3")
    if state.moves_left <= 0:
        raise ValueError("No moves left")
    space = cfg["max_reserve"] - state.reserve
    amount = min(amount, state.tokens_left, space)
    if amount <= 0:
        raise ValueError("Cannot bank tokens")
    state.tokens_left -= amount
    state.reserve += amount
    state.moves_left -= 1
    state.week_action_log.setdefault(state.week, []).append(f"Banked {amount} token(s)")


def take_action(state: SeasonState, action_id: str, params: dict[str, Any] | None = None) -> None:
    params = params or {}
    legal = {a.action_id: a for a in legal_actions(state)}
    spec = legal.get(action_id)
    if spec is None:
        raise ValueError(f"Unknown action {action_id}")
    if not spec.enabled:
        raise ValueError(spec.disabled_reason or "Action disabled")

    if action_id == "focused_training":
        apply_focused_training(state, int(params["athlete_index"]), Skill(params["skill"]))
    elif action_id == "team_practice":
        apply_team_practice(state)
    elif action_id == "recovery":
        apply_recovery(state)
    elif action_id == "team_building":
        apply_team_building(state)
    elif action_id == "scout_recruit":
        # Backward-compatible atomic engine action. The live UI uses
        # begin_recruiting/resolve_recruiting so payment happens before reveal.
        if params.get("decline"):
            _charge_recruit_visit(state)
            apply_scout_recruit_decline(state)
        else:
            recruit = params.get("recruit")
            if not isinstance(recruit, Athlete):
                raise ValueError("Recruit required")
            _validate_recruit(state, recruit)
            _charge_recruit_visit(state)
            apply_recruit_sign(state, recruit)
    elif action_id == "bank_tokens":
        apply_bank_tokens(state, int(params["amount"]))
    else:
        raise ValueError(f"Unhandled action {action_id}")
