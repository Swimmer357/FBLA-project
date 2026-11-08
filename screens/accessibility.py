"""Accessibility settings (persisted locally)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

_SETTINGS_PATH = Path(__file__).resolve().parents[1] / "settings.json"


@dataclass
class AxSettings:
    high_contrast: bool = False
    large_text: bool = False
    readable_font: bool = False
    intro_seen: bool = False


def load_settings() -> AxSettings:
    if not _SETTINGS_PATH.is_file():
        return AxSettings()
    try:
        raw = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
        return AxSettings(
            high_contrast=bool(raw.get("high_contrast", False)),
            large_text=bool(raw.get("large_text", False)),
            readable_font=bool(raw.get("readable_font", False)),
            intro_seen=bool(raw.get("intro_seen", False)),
        )
    except (json.JSONDecodeError, OSError):
        return AxSettings()


def save_settings(settings: AxSettings) -> None:
    _SETTINGS_PATH.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
