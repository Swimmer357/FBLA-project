# Hoops Manager

FBLA Computer Game & Simulation Programming — single-season high school basketball program manager.

## Requirements

- Python **3.12.x** (pinned team target; see `requirements.txt`)
- Dependencies: `pip install -r requirements.txt`

## Run (development)

```bash
python main.py
```

## Run in a browser (pygbag)

Install the optional web packager, then serve the project:

```bash
python -m pip install pygbag
python -m pygbag .
```

Open the local URL printed by pygbag. The desktop dependencies in
`requirements.txt` do not require pygbag.

## Tests

```bash
pytest tests/ -q
```

## Balance script (no window)

```bash
python tools/balance.py
```

## Convert sound assets to OGG

The game loads `.ogg` effects for smaller web downloads. To regenerate them
from WAV sources:

```bash
python3 -m pip install soundfile
python3 tools/convert_audio.py
```

The converter keeps the WAV originals by default. Add `--delete-wav` only
after verifying both desktop and web audio.

## Package (macOS example)

Build on the **same OS** judges will use:

```bash
pyinstaller --onefile --windowed --name HoopsManager \
  --add-data "data:data" --add-data "assets:assets" main.py
```

On Windows use `;` instead of `:` in `--add-data`.

## Project layout

- `engine/` — rules, match formula, events (no pygame)
- `screens/` — drawing and input
- `data/` — JSON balance and text
- `theme.py` — colors, sizes, font path
- `assets/` — Inter font + three sound effects

## Credits

- **Inter** — SIL Open Font License 1.1
- Short sound effects generated for this project (CC0-style)
