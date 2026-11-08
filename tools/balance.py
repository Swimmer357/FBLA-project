#!/usr/bin/env python3
"""Run 1,000 seasons per strategy and difficulty (no window)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import check_ending, new_season, play_game, respond_to_event, start_week
from engine.models import Phase
from engine.season import advance_after_results
from engine import strategies


def simulate_season(difficulty: str, strategy_name: str, seed: int) -> str:
    state = new_season(difficulty, captain_index=0, seed=seed)
    start_week(state)
    strategy = strategies.STRATEGIES[strategy_name]

    for _ in range(500):
        if state.ending_id:
            return state.ending_id
        if state.pending_event:
            respond_to_event(state, strategies.auto_event_choice(state))
            continue
        strategy(state)
        if state.week == 0:
            advance_after_results(state)
            continue
        play_game(state)
        check_ending(state)
        if state.ending_id:
            return state.ending_id
        advance_after_results(state)
        if state.phase == Phase.REPORT:
            break
    return state.ending_id or "unknown"


def main() -> None:
    difficulties = ["Rookie", "Varsity", "Championship"]
    strategies_list = list(strategies.STRATEGIES.keys())
    runs = 1000
    print(f"Balance report ({runs} seasons per cell)\n")
    header = f"{'Strategy':<12} | " + " | ".join(f"{d:^12}" for d in difficulties)
    print(header)
    print("-" * len(header))
    for strat in strategies_list:
        row = f"{strat:<12} | "
        cells = []
        for diff in difficulties:
            outcomes: dict[str, int] = {}
            for s in range(runs):
                end = simulate_season(diff, strat, seed=10_000 + s)
                outcomes[end] = outcomes.get(end, 0) + 1
            playoff = sum(
                v
                for k, v in outcomes.items()
                if k in ("state_champion", "finalist", "playoff_exit")
            )
            title = outcomes.get("state_champion", 0)
            cells.append(f"P{playoff/runs*100:4.0f}% T{title/runs*100:3.0f}%")
        row += " | ".join(cells)
        print(row)
    collapse = sum(
        1
        for s in range(runs)
        if simulate_season("Varsity", "balanced", seed=50_000 + s) == "program_collapse"
    )
    print(f"\nProgram Collapse (balanced Varsity): {collapse/runs*100:.1f}%")


if __name__ == "__main__":
    main()
