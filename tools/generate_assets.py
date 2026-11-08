#!/usr/bin/env python3
"""Generate CC0-style WAV effects and ensure assets dirs exist."""
from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOUND_DIR = ROOT / "assets" / "sounds"


def write_tone(path: Path, freq: float, duration: float, volume: float = 0.3) -> None:
    rate = 22050
    n = int(rate * duration)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        for i in range(n):
            t = i / rate
            sample = volume * math.sin(2 * math.pi * freq * t)
            wf.writeframes(struct.pack("<h", int(sample * 32767)))


def main() -> None:
    SOUND_DIR.mkdir(parents=True, exist_ok=True)
    write_tone(SOUND_DIR / "click.wav", 880, 0.05, 0.2)
    write_tone(SOUND_DIR / "buzzer.wav", 110, 0.35, 0.35)
    write_tone(SOUND_DIR / "chime.wav", 660, 0.2, 0.25)
    print("Wrote sound effects to", SOUND_DIR)


if __name__ == "__main__":
    main()
