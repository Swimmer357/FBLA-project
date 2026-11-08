"""Resolve bundled asset paths for dev and PyInstaller builds."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def resource_path(relative: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__)))
    return os.path.join(base, relative)


def data_path(filename: str = "") -> Path:
    """Return one canonical data path in development and frozen builds."""
    root = Path(resource_path("data"))
    return root / filename if filename else root
