"""Single source for the scalable, flat high-contrast visual system."""

# —— Palette ——
HEADER_BG = (28, 28, 40)       # #1C1C28
BG_DEEP = (15, 15, 26)         # #0F0F1A
PANEL_BG = (26, 26, 48)        # #1A1A30
TITLE_CYAN = (79, 195, 247)    # #4FC3F7
TEXT_WHITE = (255, 255, 255)
TEXT_DIM = (204, 204, 204)     # #CCCCCC
ACCENT_BLUE = (68, 85, 221)    # #4455DD
ACCENT_PURPLE = (139, 61, 214)
ACCENT_PINK = (202, 52, 184)
OBJECTIVE_GREEN = (63, 224, 63)  # #3FE03F
SECTION_YELLOW = (255, 215, 0) # #FFD700
BORDER_BLUE = ACCENT_BLUE
BTN_DANGER = (224, 49, 49)

GOOD_GREEN = (95, 211, 108)    # #5FD36C
BUTTON_GREEN = GOOD_GREEN
BUTTON_GREEN_EDGE = (72, 176, 85)  # #48B055
BAD_RED = (255, 107, 107)

NAVY = PANEL_BG
ORANGE = SECTION_YELLOW
WHITE = TEXT_WHITE
LIGHT_GRAY = TEXT_DIM
MID_GRAY = (100, 108, 128)

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
REFERENCE_WIDTH = 1920
REFERENCE_HEIGHT = 949
GRID = 8


def sx(value: float) -> int:
    """Scale reference-canvas horizontal geometry to the live window."""
    return round(value * WINDOW_WIDTH / REFERENCE_WIDTH)


def sy(value: float) -> int:
    """Scale reference-canvas vertical geometry to the live window."""
    return round(value * WINDOW_HEIGHT / REFERENCE_HEIGHT)


def rx(x: float, y: float, width: float, height: float):
    """Return a pygame Rect expressed in 1920×949 reference coordinates."""
    import pygame

    return pygame.Rect(sx(x), sy(y), sx(width), sy(height))

# Typography: bundled Inter with system sans-serif fallbacks in manager.py.
FONT_FILE = "assets/Inter-Regular.ttf"
FONT_BOLD_FILE = "assets/Inter-Bold.ttf"
FONT_TITLE = 52
FONT_HEADING = 34
FONT_BODY = 24
FONT_SMALL = 20
FONT_TINY = 16
FONT_BUTTON = 22

MARGIN_X = sx(84)
CONTENT_W = WINDOW_WIDTH - MARGIN_X * 2
HEADER_TOP = sy(28)
HEADER_H = sy(275)
MAIN_TOP = HEADER_H + sy(22)
HINT_H = 44
FOOTER_Y = 612

PANEL_RADIUS = 0
BUTTON_H = sy(97)
BUTTON_H_FEATURED = sy(97)
BUTTON_GAP = sx(25)
COLS = 3
FOCUS_RING = 2
ROSTER_W = 340
ROSTER_H = 400

SOUND_CLICK = "assets/sounds/click.wav"
SOUND_BUZZER = "assets/sounds/buzzer.wav"
SOUND_CHIME = "assets/sounds/chime.wav"

_DEFAULTS: dict[str, tuple[int, int, int] | int | str] = {}


def _snapshot_defaults() -> None:
    global _DEFAULTS
    if _DEFAULTS:
        return
    for name in (
        "BG_DEEP",
        "HEADER_BG",
        "PANEL_BG",
        "TITLE_CYAN",
        "TEXT_WHITE",
        "TEXT_DIM",
        "BORDER_BLUE",
        "OBJECTIVE_GREEN",
        "SECTION_YELLOW",
    ):
        _DEFAULTS[name] = globals()[name]


def apply_high_contrast() -> None:
    _snapshot_defaults()
    globals()["BG_DEEP"] = (0, 0, 0)
    globals()["HEADER_BG"] = (0, 0, 0)
    globals()["PANEL_BG"] = (0, 0, 0)
    globals()["TITLE_CYAN"] = (0, 255, 0)
    globals()["TEXT_WHITE"] = (255, 255, 255)
    globals()["TEXT_DIM"] = (200, 200, 200)
    globals()["BORDER_BLUE"] = (255, 255, 255)
    globals()["OBJECTIVE_GREEN"] = (0, 255, 0)
    globals()["SECTION_YELLOW"] = (255, 255, 0)


def reset_theme() -> None:
    _snapshot_defaults()
    for k, v in _DEFAULTS.items():
        globals()[k] = v
