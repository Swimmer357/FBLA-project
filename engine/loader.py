"""Load and validate JSON data files."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from engine.models import Athlete
from resources import data_path

_DATA_ROOT = data_path()

_cache: dict[str, Any] = {}

_ATHLETE_FIELDS = ("name", "pos", "shooting", "defense", "stamina", "potential", "leadership")
_EFFECT_TYPES = {
    "games_out",
    "morale_all",
    "morale_target",
    "preparation",
    "cohesion",
    "fatigue_all",
    "skip_post_game_fatigue",
    "slump_meeting",
    "mentor_best_skill",
    "rival_bonus",
    "draw_recruit_single",
}
_EVENT_TRIGGERS = {
    "transfer_window",
    "injury_roll",
    "two_losses",
    "random",
    "starter_fatigue_high",
    "grades_starter",
    "rising_star",
    "rival_scout",
}
_EFFECT_REQUIRED_FIELDS = {
    "games_out": ("games",),
    "morale_all": ("delta",),
    "morale_target": ("delta",),
    "preparation": ("delta",),
    "cohesion": ("delta",),
    "fatigue_all": ("delta",),
    "mentor_best_skill": ("delta",),
    "rival_bonus": ("delta",),
}


def _read(name: str) -> Any:
    if name not in _cache:
        path = _DATA_ROOT / name
        if not path.is_file():
            raise FileNotFoundError(f"Missing data file: {path}")
        with path.open(encoding="utf-8") as fh:
            _cache[name] = json.load(fh)
    return _cache[name]


def clear_cache() -> None:
    _cache.clear()


def data_root() -> Path:
    return _DATA_ROOT


def _require_keys(item: dict[str, Any], keys: tuple[str, ...], location: str) -> None:
    missing = [key for key in keys if key not in item]
    if missing:
        raise ValueError(f"{location}: missing {', '.join(missing)}")


def _validate_people(items: Any, location: str) -> list[dict[str, Any]]:
    if not isinstance(items, list) or not items:
        raise ValueError(f"{location}: expected a non-empty list")
    names: set[str] = set()
    for index, item in enumerate(items):
        where = f"{location}[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{where}: expected an object")
        _require_keys(item, _ATHLETE_FIELDS, where)
        name = item["name"]
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{where}: name must be non-empty")
        if name in names:
            raise ValueError(f"{location}: duplicate name {name!r}")
        names.add(name)
        if item["pos"] not in {"G", "F", "C"}:
            raise ValueError(f"{where}: position must be G, F, or C")
        for field in ("shooting", "defense", "stamina", "leadership"):
            value = item[field]
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 100:
                raise ValueError(f"{where}: {field} must be an integer from 0 to 100")
        potential = item["potential"]
        if not isinstance(potential, int) or isinstance(potential, bool) or not 0 <= potential <= 5:
            raise ValueError(f"{where}: potential must be an integer from 0 to 5")
        for field in ("morale", "fatigue"):
            value = item.get(field, 60 if field == "morale" else 10)
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 100:
                raise ValueError(f"{where}: {field} must be an integer from 0 to 100")
    return items


def load_season_config() -> dict[str, Any]:
    cfg = _read("season.json")
    _require_keys(
        cfg,
        (
            "regular_season_games",
            "opponent_ratings",
            "opponent_names",
            "playoff_rounds",
            "playoff_opponents",
            "playoff_ratings",
            "moves_per_week",
            "max_roster",
        ),
        "season.json",
    )
    rs = cfg["regular_season_games"]
    if not isinstance(rs, int) or isinstance(rs, bool) or rs <= 0:
        raise ValueError("season.json: regular_season_games must be a positive integer")
    if len(cfg["opponent_ratings"]) != rs:
        raise ValueError(
            f"season.json: opponent_ratings length {len(cfg['opponent_ratings'])} "
            f"!= regular_season_games {rs}"
        )
    if len(cfg.get("opponent_names", [])) != rs:
        raise ValueError("season.json: opponent_names must match regular_season_games count")
    if len(cfg["playoff_ratings"]) != len(cfg["playoff_rounds"]):
        raise ValueError("season.json: playoff_ratings must match playoff_rounds count")
    if len(cfg["playoff_opponents"]) != len(cfg["playoff_rounds"]):
        raise ValueError("season.json: playoff_opponents must match playoff_rounds count")
    if cfg["moves_per_week"] <= 0 or cfg["max_roster"] < 5:
        raise ValueError("season.json: moves_per_week must be positive and max_roster at least 5")
    return cfg


def load_difficulty() -> dict[str, Any]:
    difficulties = _read("difficulty.json")
    if not isinstance(difficulties, dict) or not difficulties:
        raise ValueError("difficulty.json: expected at least one difficulty")
    for name, item in difficulties.items():
        where = f"difficulty.json[{name!r}]"
        _require_keys(item, ("weekly_tokens", "rating_offset", "event_chance"), where)
        if not isinstance(item["weekly_tokens"], int) or item["weekly_tokens"] < 0:
            raise ValueError(f"{where}: weekly_tokens must be a non-negative integer")
        chance = item["event_chance"]
        if not isinstance(chance, (int, float)) or isinstance(chance, bool) or not 0 <= chance <= 1:
            raise ValueError(f"{where}: event_chance must be from 0 to 1")
    return difficulties


def load_athletes() -> list[Athlete]:
    raw = _validate_people(_read("athletes.json").get("athletes"), "athletes.json.athletes")
    athletes: list[Athlete] = []
    for i, item in enumerate(raw):
        athletes.append(
            Athlete(
                name=item["name"],
                pos=item["pos"],
                shooting=int(item["shooting"]),
                defense=int(item["defense"]),
                stamina=int(item["stamina"]),
                potential=int(item["potential"]),
                leadership=int(item["leadership"]),
                morale=int(item.get("morale", 60)),
                fatigue=int(item.get("fatigue", 10)),
                roster_index=i,
            )
        )
    return athletes


def load_recruit_pool() -> list[dict[str, Any]]:
    return list(
        _validate_people(_read("recruits.json").get("recruits"), "recruits.json.recruits")
    )


def load_events() -> list[dict[str, Any]]:
    events = _read("events.json").get("events")
    if not isinstance(events, list) or not events:
        raise ValueError("events.json.events: expected a non-empty list")
    event_ids: set[str] = set()
    for event_index, event in enumerate(events):
        where = f"events.json.events[{event_index}]"
        _require_keys(event, ("id", "title", "description", "trigger", "responses"), where)
        if event["id"] in event_ids:
            raise ValueError(f"events.json: duplicate event id {event['id']!r}")
        event_ids.add(event["id"])
        if event["trigger"] not in _EVENT_TRIGGERS:
            raise ValueError(f"{where}: unknown trigger {event['trigger']!r}")
        responses = event["responses"]
        if not isinstance(responses, list) or len(responses) < 2:
            raise ValueError(f"{where}: expected at least two responses")
        response_ids: set[str] = set()
        for response_index, response in enumerate(responses):
            response_where = f"{where}.responses[{response_index}]"
            _require_keys(response, ("id", "label", "token_cost", "effects"), response_where)
            if response["id"] in response_ids:
                raise ValueError(f"{where}: duplicate response id {response['id']!r}")
            response_ids.add(response["id"])
            cost = response["token_cost"]
            if not isinstance(cost, int) or isinstance(cost, bool) or cost < 0:
                raise ValueError(f"{response_where}: token_cost must be non-negative")
            if not isinstance(response["effects"], list):
                raise ValueError(f"{response_where}: effects must be a list")
            for effect in response["effects"]:
                if not isinstance(effect, dict) or effect.get("type") not in _EFFECT_TYPES:
                    raise ValueError(f"{response_where}: unknown or malformed effect")
                effect_type = effect["type"]
                _require_keys(
                    effect,
                    _EFFECT_REQUIRED_FIELDS.get(effect_type, ()),
                    f"{response_where}.{effect_type}",
                )
                for field in _EFFECT_REQUIRED_FIELDS.get(effect_type, ()):
                    if not isinstance(effect[field], int) or isinstance(effect[field], bool):
                        raise ValueError(
                            f"{response_where}.{effect_type}: {field} must be an integer"
                        )
    if "injury" not in event_ids:
        raise ValueError("events.json: required injury event is missing")
    return list(events)


def load_explanations() -> dict[str, Any]:
    return _read("explanations.json")


def load_narration() -> dict[str, Any]:
    return _read("narration.json")


def load_howto() -> dict[str, Any]:
    return _read("howto.json")


def load_about() -> dict[str, Any]:
    return _read("about.json")


def load_hub() -> dict[str, Any]:
    return _read("hub.json")


def load_intro() -> dict[str, Any]:
    return _read("intro.json")
