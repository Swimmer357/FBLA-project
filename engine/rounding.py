"""Round-half-up helper (not Python banker's rounding)."""
from __future__ import annotations

import math


def round_half_up(value: float) -> int:
    if value >= 0:
        return int(math.floor(value + 0.5))
    return int(math.ceil(value - 0.5))
