"""Seeded random draws with fixed call order per season."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Sequence, TypeVar

T = TypeVar("T")


@dataclass
class SeasonRNG:
    seed: int
    _rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def chance(self, probability: float) -> bool:
        return self._rng.random() < probability

    def uniform(self, items: Sequence[T]) -> T:
        return self._rng.choice(list(items))

    def sample_without_replacement(self, items: Sequence[T], k: int) -> list[T]:
        pool = list(items)
        self._rng.shuffle(pool)
        return pool[:k]

    def gauss(self, mu: float, sigma: float) -> float:
        return self._rng.gauss(mu, sigma)

    def weighted_choice(self, items: Sequence[T], weights: Sequence[float]) -> T:
        return self._rng.choices(list(items), weights=list(weights), k=1)[0]

    def randint(self, a: int, b: int) -> int:
        return self._rng.randint(a, b)
