# Hoops Manager

FBLA Computer Game & Simulation Programming — single-season high school basketball program manager.

## Requirements

- Python **3.12.x** (pinned team target; see `requirements.txt`)
- Dependencies: `pip install -r requirements.txt`

## Run (development)

```bash
python main.py
```

## Tests

```bash
pytest tests/ -q
```

## Balance script (no window)

```bash
python tools/balance.py
```

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
