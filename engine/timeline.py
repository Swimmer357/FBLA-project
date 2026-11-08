"""Scripted replay of a finished game. Visual only: the final score is an input.

The timeline is built once, before playback, from its own random.Random so the
season RNG is never touched. Event points always sum to the given final score.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field, replace

from engine import match
from engine.models import GameResult

PERIOD_SECONDS = 480.0
OT_SECONDS = 240.0
QUARTER_REAL = 1.35
OT_REAL = 0.85
BREAK_REAL = 0.25
FINAL_HOLD = 0.6
SHOT_REAL = 0.3
HIGHLIGHT_GAP_REAL = 0.42
CLOCK_START_BUFFER = 4.0
CLOCK_END_BUFFER = 2.0
RUN_MIN, RUN_MAX = 6, 8
RUN_TALENT_GAP = 4.0


@dataclass(frozen=True)
class Player:
    name: str
    shooting: float
    fatigue_penalty: float


@dataclass(frozen=True)
class PlayEvent:
    period: int
    clock: float
    team: str
    kind: str
    points: int
    player: int
    player_name: str
    home_score: int
    away_score: int
    lead_change: bool
    highlight: bool
    text: str


@dataclass
class Timeline:
    events: list[PlayEvent]
    period_lengths: list[float]
    home_final: int
    away_final: int
    home_players: list[Player]
    away_players: list[Player]
    overtime: bool
    period_scores: list[tuple[int, int]] = field(default_factory=list)

    @property
    def periods(self) -> int:
        return len(self.period_lengths)


def period_real(period: int) -> float:
    return QUARTER_REAL if period <= 4 else OT_REAL


def period_start_real(period: int) -> float:
    start = 0.0
    for p in range(1, period):
        start += period_real(p) + BREAK_REAL
    return start


def event_real_time(timeline: Timeline, event: PlayEvent) -> float:
    length = timeline.period_lengths[event.period - 1]
    elapsed = (length - event.clock) / length
    return period_start_real(event.period) + elapsed * period_real(event.period)


def game_end_real(timeline: Timeline) -> float:
    return period_start_real(timeline.periods) + period_real(timeline.periods)


def total_real_time(timeline: Timeline, speed: float = 1.0) -> float:
    """Wall-clock seconds for the whole replay at a speed; 0 means instant."""
    if speed <= 0:
        return 0.0
    return (game_end_real(timeline) + FINAL_HOLD) / speed


def clock_at(timeline: Timeline, t: float) -> tuple[int, float, bool]:
    """(period, seconds remaining, in_break) for playback time t."""
    for period in range(1, timeline.periods + 1):
        start = period_start_real(period)
        end = start + period_real(period)
        if t < end:
            frac = max(0.0, (t - start) / period_real(period))
            return period, timeline.period_lengths[period - 1] * (1.0 - frac), False
        if period < timeline.periods and t < end + BREAK_REAL:
            return period, 0.0, True
    return timeline.periods, 0.0, True


def _split(total: int, weights: list[float]) -> list[int]:
    raw = [total * w / sum(weights) for w in weights]
    parts = [int(x) for x in raw]
    order = sorted(range(len(raw)), key=lambda i: raw[i] - parts[i], reverse=True)
    for i in order[: total - sum(parts)]:
        parts[i] += 1
    return parts


def _plays(points: int, three_rate: float, rng: random.Random) -> list[int]:
    plays: list[int] = []
    remaining = points
    while remaining > 0:
        roll = rng.random()
        if roll < three_rate and remaining >= 3:
            value = 3
        elif roll < three_rate + 0.12 or remaining == 1:
            value = 1
        else:
            value = 2
        plays.append(value)
        remaining -= value
    rng.shuffle(plays)
    return plays


def _merge(home: list[int], away: list[int], run_team: str | None, rng: random.Random) -> list[tuple[str, int]]:
    """Interleave both teams' plays; optionally insert one 6–8 point run."""
    order: list[tuple[str, int]] = []
    queues = {"home": list(home), "away": list(away)}
    total = len(home) + len(away)
    run_at = rng.randint(0, max(0, total - 4)) if run_team else -1
    run_points = 0
    in_run = False
    while queues["home"] or queues["away"]:
        if len(order) == run_at and run_team:
            in_run = True
        if in_run:
            queue = queues[run_team]
            if queue and run_points + queue[0] <= RUN_MAX and (run_points < RUN_MIN or rng.random() < 0.5):
                run_points += queue[0]
                order.append((run_team, queue.pop(0)))
                continue
            in_run = False
            run_team = None
        h, a = len(queues["home"]), len(queues["away"])
        team = "home" if rng.random() < h / (h + a) else "away"
        order.append((team, queues[team].pop(0)))
    return order


def _pick_player(players: list[Player], late: bool, rng: random.Random) -> int:
    weights = [
        max(1.0, p.shooting) * (1.0 - min(0.4, p.fatigue_penalty / 20.0) if late else 1.0)
        for p in players
    ]
    return rng.choices(range(len(players)), weights=weights, k=1)[0]


def _describe(name: str, kind: str, points: int, rng: random.Random) -> str:
    if kind == "turnover":
        return f"Turnover by {name}"
    if kind == "miss":
        return f"{name} misses {rng.choice(('a jumper', 'from deep', 'at the rim'))}"
    if points == 3:
        return f"{name} hits a three"
    if points == 1:
        return f"{name} makes a free throw"
    return f"{name} {rng.choice(('scores inside', 'hits a jumper', 'finishes at the rim'))}"


def generate_timeline(
    home_final: int,
    away_final: int,
    home_players: list[Player],
    away_players: list[Player],
    talent_gap: float,
    overtime: bool,
    seed: int,
) -> Timeline:
    rng = random.Random(seed)
    home_players = home_players or [Player("Home #1", 50.0, 0.0)]
    away_players = away_players or [Player("Away #1", 50.0, 0.0)]
    mean_shoot = sum(p.shooting for p in home_players) / len(home_players)
    mean_pen = sum(p.fatigue_penalty for p in home_players) / len(home_players)
    late_drop = min(0.2, mean_pen / 30.0)

    if overtime:
        diff = home_final - away_final
        away_ot = rng.randint(3, 8)
        home_ot = away_ot + diff
        if home_ot < 0:
            home_ot, away_ot = 0, -diff
        home_reg, away_reg = home_final - home_ot, away_final - away_ot
    else:
        home_ot = away_ot = 0
        home_reg, away_reg = home_final, away_final

    home_w = [rng.uniform(0.88, 1.12) for _ in range(4)]
    home_w[2] *= 1.0 - late_drop / 2
    home_w[3] *= 1.0 - late_drop
    away_w = [rng.uniform(0.88, 1.12) for _ in range(4)]
    home_q = _split(home_reg, home_w)
    away_q = _split(away_reg, away_w)
    if overtime:
        home_q.append(home_ot)
        away_q.append(away_ot)
    lengths = [PERIOD_SECONDS] * 4 + ([OT_SECONDS] if overtime else [])

    favored = None
    if talent_gap >= RUN_TALENT_GAP:
        favored = "home"
    elif talent_gap <= -RUN_TALENT_GAP:
        favored = "away"
    run_periods = set(rng.sample(range(4), 2)) if favored else set()

    home_three = max(0.12, min(0.38, 0.22 + (mean_shoot - 55) / 150))
    events: list[PlayEvent] = []
    home_score = away_score = 0
    leader: str | None = None
    period_scores: list[tuple[int, int]] = []

    for index, length in enumerate(lengths):
        period = index + 1
        late = period >= 4
        sequence = _merge(
            _plays(home_q[index], home_three, rng),
            _plays(away_q[index], 0.25, rng),
            favored if index in run_periods else None,
            rng,
        )
        scoring = [("make", team, points) for team, points in sequence]
        extras = rng.randint(1, 2) if period > 4 else rng.randint(2, 3)
        for _ in range(extras):
            kind = rng.choice(("miss", "miss", "turnover"))
            scoring.insert(rng.randint(0, len(scoring)), (kind, rng.choice(("home", "away")), 0))

        slot = (length - CLOCK_START_BUFFER - CLOCK_END_BUFFER) / max(1, len(scoring))
        for i, (kind, team, points) in enumerate(scoring):
            clock = length - CLOCK_START_BUFFER - (i + rng.uniform(0.15, 0.85)) * slot
            roster = home_players if team == "home" else away_players
            player = _pick_player(roster, late and team == "home", rng)
            lead_change = False
            if kind == "make":
                if team == "home":
                    home_score += points
                else:
                    away_score += points
                now = "home" if home_score > away_score else "away" if away_score > home_score else None
                if now is not None and leader is not None and now != leader:
                    lead_change = True
                if now is not None:
                    leader = now
            text = _describe(roster[player].name, kind, points, rng)
            if lead_change:
                text += " to take the lead"
            events.append(
                PlayEvent(period, round(clock, 2), team, kind, points, player, roster[player].name,
                          home_score, away_score, lead_change, False, text)
            )
        period_scores.append((home_score, away_score))

    if (home_score, away_score) != (home_final, away_final):
        raise RuntimeError("Timeline does not match the final score")

    timeline = Timeline(events, lengths, home_final, away_final, home_players, away_players, overtime, period_scores)
    _mark_highlights(timeline)
    return timeline


def _mark_highlights(timeline: Timeline) -> None:
    """Choose a few well-spaced plays per period for the ball to act out."""
    chosen: set[int] = set()
    for period in range(1, timeline.periods + 1):
        idx = [i for i, e in enumerate(timeline.events) if e.period == period]
        limit = 3 if period <= 4 else 2
        rank = sorted(
            idx,
            key=lambda i: (
                not timeline.events[i].lead_change,
                timeline.events[i].points != 3,
                timeline.events[i].kind == "make",
                i,
            ),
        )
        start = period_start_real(period)
        picked: list[float] = []
        for i in rank:
            t = event_real_time(timeline, timeline.events[i])
            if t - start < SHOT_REAL + 0.05:
                continue
            if all(abs(t - other) >= HIGHLIGHT_GAP_REAL for other in picked):
                picked.append(t)
                chosen.add(i)
            if len(picked) >= limit:
                break
    timeline.events = [replace(e, highlight=i in chosen) for i, e in enumerate(timeline.events)]


def timeline_for_result(result: GameResult, school_name: str = "Home") -> Timeline:
    home = [
        Player(a.name or f"{school_name} #{i + 1}", float(a.shooting), match.fatigue_penalty(a))
        for i, a in enumerate(result.starters)
    ]
    opponent = result.opponent_name or "Opponent"
    away = [Player(f"{opponent} #{i + 1}", 50.0, 0.0) for i in range(5)]
    seed = result.week * 7919 + result.team_score * 131 + result.opponent_score * 17
    return generate_timeline(
        result.team_score,
        result.opponent_score,
        home,
        away,
        result.factors.talent_gap,
        result.overtime,
        seed,
    )
