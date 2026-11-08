"""Resolve bundled asset paths for dev and PyInstaller builds."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def resource_path(relative: str) -> str:
    # Web servers and pygbag require URL-style separators. Pygame also accepts
    # forward slashes on desktop platforms, including Windows.
    relative = relative.replace("\\", "/")
    base = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__)))
    return (Path(base) / Path(relative)).as_posix()


def data_path(filename: str = "") -> Path:
    """Return one canonical data path in development and frozen builds."""
    root = Path(resource_path("data"))
    return root / filename if filename else root
