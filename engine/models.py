"""Core domain models — no pygame."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Skill(str, Enum):
    SHOOTING = "shooting"
    DEFENSE = "defense"
    STAMINA = "stamina"


class Phase(str, Enum):
    SETUP = "setup"
    PRESEASON = "preseason"
    EVENT = "event"
    PLANNING = "planning"
    MATCH = "match"
    RESULTS = "results"
    REPORT = "report"
    ENDED = "ended"


@dataclass
class Athlete:
    name: str
    pos: str
    shooting: int
    defense: int
    stamina: int
    potential: int
    leadership: int
    morale: int = 60
    fatigue: int = 10
    games_out: int = 0
    roster_index: int = 0

    def clone(self) -> Athlete:
        return Athlete(
            name=self.name,
            pos=self.pos,
            shooting=self.shooting,
            defense=self.defense,
            stamina=self.stamina,
            potential=self.potential,
            leadership=self.leadership,
            morale=self.morale,
            fatigue=self.fatigue,
            games_out=self.games_out,
            roster_index=self.roster_index,
        )

    @property
    def overall(self) -> float:
        return (self.shooting + self.defense) / 2.0

    @property
    def available(self) -> bool:
        return self.games_out == 0


@dataclass
class PendingEvent:
    event_id: str
    title: str
    description: str
    responses: list[dict[str, Any]]
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class MatchFactors:
    talent_gap: float
    fatigue: float
    morale: float
    preparation: float
    cohesion: float
    depth: float
    luck: float

    @property
    def margin(self) -> float:
        return (
            self.talent_gap
            + self.fatigue
            + self.morale
            + self.preparation
            + self.cohesion
            + self.depth
            + self.luck
        )

    def as_dict(self) -> dict[str, float]:
        return {
            "talent_gap": self.talent_gap,
            "fatigue": self.fatigue,
            "morale": self.morale,
            "preparation": self.preparation,
            "cohesion": self.cohesion,
            "depth": self.depth,
            "luck": self.luck,
        }


@dataclass
class GameResult:
    week: int
    opponent_name: str
    opponent_rating: int
    won: bool
    team_score: int
    opponent_score: int
    margin: float
    factors: MatchFactors
    starters: list[Athlete]
    avg_starter_fatigue: float
    mean_r: float
    preparation: int
    cohesion: int
    available_count: int
    skip_fatigue_this_game: bool = False
    leading_scorer: str | None = None
    defensive_standout: str | None = None
    fatigue_flags: list[str] = field(default_factory=list)
    overtime: bool = False
    unavailable_names: list[str] = field(default_factory=list)


@dataclass
class SeasonState:
    difficulty: str
    seed: int
    week: int
    phase: Phase
    athletes: list[Athlete]
    captain_index: int
    cohesion: int
    preparation: int
    reserve: int
    wins: int
    losses: int
    tokens_budget: int
    tokens_left: int
    moves_left: int
    moves_used: int
    pending_event: PendingEvent | None
    last_result: GameResult | None
    ending_id: str | None
    ending_reason: str | None
    offered_recruit_names: set[str]
    active_recruit_names: set[str]
    loss_streak: int
    collapse_bad_weeks: int
    skip_post_game_fatigue: bool
    rival_rating_bonus: int
    game_log: list[GameResult]
    week_action_log: dict[int, list[str]]
    starting_stats: dict[str, dict[str, int]]
    rng: Any  # SeasonRNG — typed loosely to avoid circular import in dataclass
