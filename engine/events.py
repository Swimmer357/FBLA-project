"""Event eligibility, selection, and response effects."""
from __future__ import annotations

from typing import Any

from engine import loader, match, rules
from engine.models import Athlete, PendingEvent, Phase, SeasonState


def _avg_starter_fatigue(state: SeasonState) -> float:
    starters = match.pick_starters(state.athletes)
    if not starters:
        return 0.0
    return sum(a.fatigue for a in starters) / len(starters)


def _mean_starter_r(state: SeasonState) -> float:
    starters = match.pick_starters(state.athletes)
    if not starters:
        return 0.0
    return sum((a.shooting + a.defense) / 2.0 for a in starters) / len(starters)


def _next_opponent_base_rating(state: SeasonState) -> int:
    _, rating = match.opponent_rating_for_week(state)
    return rating - state.rival_rating_bonus


def _highest_fatigue_starter(state: SeasonState) -> Athlete | None:
    starters = match.pick_starters(state.athletes)
    if not starters:
        return None
    return max(starters, key=lambda a: a.fatigue)


def _rising_star_bench(state: SeasonState) -> Athlete | None:
    starters = {a.name for a in match.pick_starters(state.athletes)}
    candidates = [
        a
        for a in state.athletes
        if a.name not in starters and a.potential >= 4 and a.available
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda a: (a.potential, -a.roster_index))


def is_eligible(state: SeasonState, event: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    cfg = loader.load_season_config()
    trigger = event["trigger"]
    context: dict[str, Any] = {}

    if trigger == "transfer_window":
        lo, hi = cfg["transfer_window"]
        if not (lo <= state.week <= hi):
            return False, context
        if len(state.athletes) >= cfg["max_roster"]:
            return False, context
        roster_names = {a.name for a in state.athletes}
        if not any(
            item["name"] not in roster_names and item["name"] not in state.offered_recruit_names
            for item in loader.load_recruit_pool()
        ):
            return False, context
        return True, context

    if trigger == "injury_roll":
        return False, context  # handled separately in roll

    if trigger == "two_losses":
        return state.loss_streak >= 2, {"captain": state.athletes[state.captain_index].name}

    if trigger == "random":
        return True, context

    if trigger == "starter_fatigue_high":
        avg = _avg_starter_fatigue(state)
        if avg < 55:
            return False, context
        return True, {"avg_fatigue": round(avg, 1)}

    if trigger == "grades_starter":
        athlete = _highest_fatigue_starter(state)
        if athlete is None:
            return False, context
        context["athlete"] = athlete
        return True, context

    if trigger == "rising_star":
        athlete = _rising_star_bench(state)
        if athlete is None:
            return False, context
        context["athlete"] = athlete
        return True, context

    if trigger == "rival_scout":
        opp = _next_opponent_base_rating(state)
        mean_r = _mean_starter_r(state)
        if opp < mean_r + 3:
            return False, context
        return True, context

    return False, context


def _injury_eligible(state: SeasonState) -> tuple[bool, dict[str, Any]]:
    athletes = state.athletes
    if not athletes:
        return False, {}
    most_tired = max(athletes, key=lambda a: a.fatigue)
    if most_tired.fatigue >= 70:
        if state.rng.chance(0.35):
            return True, {"athlete": most_tired}
        return False, {}
    starters = match.pick_starters(athletes)
    if starters and state.rng.chance(0.05):
        target = state.rng.uniform(starters)
        return True, {"athlete": target}
    return False, {}


def roll_event(state: SeasonState) -> PendingEvent | None:
    if state.week == 0:
        return None
    diff = loader.load_difficulty()[state.difficulty]
    if not state.rng.chance(float(diff["event_chance"])):
        return None

    events = loader.load_events()
    injury_event = next(e for e in events if e["id"] == "injury")
    eligible: list[tuple[dict[str, Any], dict[str, Any]]] = []

    ok, ctx = _injury_eligible(state)
    if ok:
        eligible.append((injury_event, ctx))

    for event in events:
        if event["id"] == "injury":
            continue
        ok, ctx = is_eligible(state, event)
        if ok:
            eligible.append((event, ctx))

    if not eligible:
        return None

    priority = [pair for pair in eligible if pair[0].get("priority")]
    if priority:
        event, ctx = priority[0]
    else:
        event, ctx = state.rng.uniform(eligible)

    return _build_pending(event, ctx, state)


def _build_pending(event: dict[str, Any], context: dict[str, Any], state: SeasonState) -> PendingEvent:
    desc = event["description"]
    for key, val in context.items():
        if isinstance(val, Athlete):
            desc = desc.replace("{athlete}", val.name)
        else:
            desc = desc.replace("{" + key + "}", str(val))
    desc = desc.replace("{captain}", state.athletes[state.captain_index].name)
    return PendingEvent(
        event_id=event["id"],
        title=event["title"],
        description=desc,
        responses=list(event["responses"]),
        context=context,
    )


def event_response_affordable(state: SeasonState, cost: int) -> tuple[bool, str | None]:
    if cost == 0:
        return True, None
    weekly = state.tokens_left
    if weekly + state.reserve >= cost:
        return True, None
    return False, f"Needs {cost} tokens; you have {weekly} this week and {state.reserve} in the reserve."


def pay_event_cost(state: SeasonState, cost: int) -> None:
    if cost <= 0:
        return
    from_weekly = min(state.tokens_left, cost)
    state.tokens_left -= from_weekly
    remaining = cost - from_weekly
    state.reserve -= remaining


def _draw_recruits(state: SeasonState, count: int) -> list[Athlete]:
    pool = loader.load_recruit_pool()
    roster_names = {a.name for a in state.athletes}
    available = [
        r
        for r in pool
        if r["name"] not in state.offered_recruit_names and r["name"] not in roster_names
    ]
    picked = state.rng.sample_without_replacement(available, min(count, len(available)))
    return [rules.recruit_from_template(state, p) for p in picked]


def apply_effects(state: SeasonState, effects: list[dict[str, Any]], context: dict[str, Any]) -> list[str]:
    messages: list[str] = []
    target = context.get("athlete")
    for eff in effects:
        et = eff["type"]
        if et == "games_out":
            if isinstance(target, Athlete):
                target.games_out = int(eff["games"])
                messages.append(f"{target.name} out {eff['games']} game(s)")
        elif et == "morale_all":
            delta = int(eff["delta"])
            for a in state.athletes:
                a.morale = rules.clamp(a.morale + delta, 0, 100)
            messages.append(f"All morale {'+' if delta > 0 else ''}{delta}")
        elif et == "morale_target":
            if isinstance(target, Athlete):
                delta = int(eff["delta"])
                target.morale = rules.clamp(target.morale + delta, 0, 100)
                messages.append(f"{target.name} morale {delta:+d}")
        elif et == "preparation":
            delta = int(eff["delta"])
            state.preparation = rules.clamp(state.preparation + delta, 0, 20)
            messages.append(f"Preparation {delta:+d}")
        elif et == "cohesion":
            delta = int(eff["delta"])
            state.cohesion = rules.clamp(state.cohesion + delta, 0, 100)
            messages.append(f"Cohesion {delta:+d}")
        elif et == "fatigue_all":
            delta = int(eff["delta"])
            for a in state.athletes:
                a.fatigue = rules.clamp(a.fatigue + delta, 0, 100)
            messages.append(f"All fatigue {delta:+d}")
        elif et == "skip_post_game_fatigue":
            state.skip_post_game_fatigue = True
            messages.append("Post-game fatigue skipped this week")
        elif et == "slump_meeting":
            captain = state.athletes[state.captain_index]
            if captain.leadership >= 60:
                for a in state.athletes:
                    a.morale = rules.clamp(a.morale + 5, 0, 100)
                messages.append("Captain led a positive meeting (+5 morale)")
            else:
                for a in state.athletes:
                    a.morale = rules.clamp(a.morale - 2, 0, 100)
                messages.append("Meeting backfired (−2 morale)")
        elif et == "mentor_best_skill":
            if isinstance(target, Athlete):
                skills = {
                    "shooting": target.shooting,
                    "defense": target.defense,
                    "stamina": target.stamina,
                }
                best = max(skills, key=skills.get)
                delta = int(eff.get("delta", 5))
                new_val = rules.clamp(getattr(target, best) + delta, 0, 100)
                setattr(target, best, new_val)
                messages.append(f"{target.name} {best} +{delta}")
        elif et == "rival_bonus":
            state.rival_rating_bonus += int(eff["delta"])
            messages.append(f"Opponent rating +{eff['delta']} this week")
        elif et == "draw_recruit_single":
            recruits = _draw_recruits(state, 1)
            if recruits:
                r = recruits[0]
                if len(state.athletes) < loader.load_season_config()["max_roster"]:
                    state.athletes.append(r)
                    state.offered_recruit_names.add(r.name)
                    r.roster_index = len(state.athletes) - 1
                    messages.append(f"Added transfer {r.name}")
                else:
                    messages.append("Roster full; transfer could not join")
            else:
                messages.append("No eligible transfer was available")
    return messages


def respond_to_event(state: SeasonState, choice_id: str) -> list[str]:
    if state.pending_event is None:
        raise ValueError("No pending event")
    if state.phase != Phase.EVENT:
        raise ValueError(f"Cannot resolve an event during {state.phase.value}")
    response = next(
        (r for r in state.pending_event.responses if r["id"] == choice_id),
        None,
    )
    if response is None:
        raise ValueError(f"Unknown response {choice_id!r}")
    cost = int(response["token_cost"])
    ok, reason = event_response_affordable(state, cost)
    if not ok:
        raise ValueError(reason or "Cannot afford response")
    pay_event_cost(state, cost)
    msgs = apply_effects(state, response["effects"], state.pending_event.context)
    if not msgs:
        msgs.append("Decision recorded. No ratings changed.")
    state.pending_event = None
    state.phase = Phase.PLANNING
    return msgs


def draw_recruit_pair(state: SeasonState) -> list[Athlete]:
    return _draw_recruits(state, 2)
