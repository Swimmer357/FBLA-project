#!/usr/bin/env python3
"""Convert every WAV sound asset to OGG/Vorbis.

Install the one-time tooling dependency with:
    python3 -m pip install soundfile

WAV sources are retained by default. Pass --delete-wav only after verifying the
OGG files on desktop and web builds.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import soundfile as sf


ROOT = Path(__file__).resolve().parents[1]
SOUND_DIR = ROOT / "assets" / "sounds"


def convert_all(*, delete_wav: bool = False) -> list[Path]:
    outputs: list[Path] = []
    for wav_path in sorted(SOUND_DIR.glob("*.wav")):
        ogg_path = wav_path.with_suffix(".ogg")
        audio, sample_rate = sf.read(wav_path)
        sf.write(ogg_path, audio, sample_rate, format="OGG", subtype="VORBIS")
        outputs.append(ogg_path)
        print(f"Converted {wav_path.name} -> {ogg_path.name}")
        if delete_wav:
            wav_path.unlink()
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--delete-wav",
        action="store_true",
        help="Delete WAV sources after successful conversion.",
    )
    args = parser.parse_args()
    outputs = convert_all(delete_wav=args.delete_wav)
    if not outputs:
        raise SystemExit(f"No WAV files found in {SOUND_DIR}")
    print(f"Created {len(outputs)} OGG file(s) in {SOUND_DIR}")


if __name__ == "__main__":
    main()
