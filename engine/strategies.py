"""AI strategies for balance script and fast-forward."""
from __future__ import annotations

from engine import events, loader, match, rules
from engine.models import SeasonState, Skill


def _train_target(state: SeasonState):
    available = [a for a in state.athletes if a.available]
    if not available:
        available = state.athletes
    return max(available, key=lambda a: (a.potential, -min(a.shooting, a.defense)))


def _development_target(state: SeasonState):
    return _train_target(state)


def balanced_week(state: SeasonState) -> None:
    target = _train_target(state)
    skill = Skill.SHOOTING if target.shooting <= target.defense else Skill.DEFENSE
    plan = [
        ("focused_training", {"athlete_index": target.roster_index, "skill": skill.value}),
        ("team_practice", {}),
        ("recovery", {}),
    ]
    for action_id, params in plan:
        actions = {a.action_id: a for a in rules.legal_actions(state)}
        spec = actions.get(action_id)
        if spec and spec.enabled and state.moves_left > 0:
            rules.take_action(state, action_id, params)


def training_heavy_week(state: SeasonState) -> None:
    targets = sorted(
        (athlete for athlete in state.athletes if athlete.available),
        key=lambda a: (-a.potential, min(a.shooting, a.defense)),
    )[:2]
    for t in targets:
        if state.moves_left <= 0:
            break
        actions = {a.action_id: a for a in rules.legal_actions(state)}
        if not actions["focused_training"].enabled:
            break
        skill = Skill.SHOOTING if t.shooting <= t.defense else Skill.DEFENSE
        rules.take_action(
            state,
            "focused_training",
            {"athlete_index": t.roster_index, "skill": skill.value},
        )
    actions = {a.action_id: a for a in rules.legal_actions(state)}
    if state.moves_left and actions["recovery"].enabled:
        avg_f = sum(a.fatigue for a in state.athletes) / len(state.athletes)
        if avg_f >= 50:
            rules.take_action(state, "recovery")


def recovery_heavy_week(state: SeasonState) -> None:
    actions = {a.action_id: a for a in rules.legal_actions(state)}
    if actions["recovery"].enabled:
        rules.take_action(state, "recovery")
    actions = {a.action_id: a for a in rules.legal_actions(state)}
    if state.moves_left and actions["team_building"].enabled:
        rules.take_action(state, "team_building")
    actions = {a.action_id: a for a in rules.legal_actions(state)}
    if state.moves_left and actions["team_practice"].enabled:
        rules.take_action(state, "team_practice")


def recruit_heavy_week(state: SeasonState) -> None:
    actions = {a.action_id: a for a in rules.legal_actions(state)}
    max_roster = loader.load_season_config()["max_roster"]
    if len(state.athletes) < max_roster and actions["scout_recruit"].enabled:
        pair = events.draw_recruit_pair(state)
        if pair:
            rules.take_action(state, "scout_recruit", {"recruit": pair[0]})
    actions = {a.action_id: a for a in rules.legal_actions(state)}
    if state.moves_left and actions["recovery"].enabled:
        rules.take_action(state, "recovery")
    actions = {a.action_id: a for a in rules.legal_actions(state)}
    if state.moves_left and actions["team_practice"].enabled:
        rules.take_action(state, "team_practice")


STRATEGIES = {
    "balanced": balanced_week,
    "training": training_heavy_week,
    "recovery": recovery_heavy_week,
    "recruit": recruit_heavy_week,
}


def auto_event_choice(state: SeasonState) -> str:
    if state.pending_event is None:
        return ""
    for resp in state.pending_event.responses:
        if int(resp["token_cost"]) == 0:
            return resp["id"]
    return state.pending_event.responses[-1]["id"]
