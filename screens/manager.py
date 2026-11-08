"""Screen stack, main loop, audio, accessibility."""
from __future__ import annotations

import asyncio

import pygame

import theme
from resources import resource_path
from screens.accessibility import AxSettings, load_settings
from screens.focus import FocusManager

ROSTER_BUTTON_RECT = pygame.Rect(theme.WINDOW_WIDTH - theme.MARGIN_X - 136, 16, 136, 42)


class GameApp:
    def __init__(self) -> None:
        pygame.init()
        pygame.mixer.init()
        self.screen = pygame.display.set_mode((theme.WINDOW_WIDTH, theme.WINDOW_HEIGHT))
        pygame.display.set_caption("Hoops Manager")
        self.clock = pygame.time.Clock()
        self.running = True
        self.muted = False
        self.focus = FocusManager()
        self.ax = load_settings()
        self.intro_complete = False
        self.hub_summary: dict | None = None
        self.state = None
        self._load_fonts()
        self._load_sounds()
        self.stack: list = []
        from screens.intro import IntroScreen

        self.push(IntroScreen())

    def _scale(self, size: int) -> int:
        if self.ax.large_text:
            return int(size * 1.18)
        return size

    def reload_fonts(self) -> None:
        self._load_fonts()

    def _load_fonts(self) -> None:
        path = resource_path(theme.FONT_FILE)
        bold_path = resource_path(theme.FONT_BOLD_FILE)
        if self.ax.readable_font:
            path = None
            bold_path = None
        try:
            if self.ax.readable_font:
                raise FileNotFoundError
            self.font_title = pygame.font.Font(bold_path, self._scale(theme.FONT_TITLE))
            self.font_heading = pygame.font.Font(bold_path, self._scale(theme.FONT_HEADING))
            self.font_body = pygame.font.Font(path, self._scale(theme.FONT_BODY))
            self.font_small = pygame.font.Font(path, self._scale(theme.FONT_SMALL))
            self.font_tiny = pygame.font.Font(path, self._scale(theme.FONT_TINY))
            self.font_button = pygame.font.Font(bold_path, self._scale(theme.FONT_BUTTON))
            self.font_bold = pygame.font.Font(bold_path, self._scale(theme.FONT_BODY))
        except (FileNotFoundError, pygame.error):
            fallback = ["Segoe UI", "Arial"]
            self.font_title = pygame.font.SysFont(fallback, self._scale(theme.FONT_TITLE), bold=True)
            self.font_heading = pygame.font.SysFont(fallback, self._scale(theme.FONT_HEADING), bold=True)
            self.font_body = pygame.font.SysFont(fallback, self._scale(theme.FONT_BODY))
            self.font_small = pygame.font.SysFont(fallback, self._scale(theme.FONT_SMALL))
            self.font_tiny = pygame.font.SysFont(fallback, self._scale(theme.FONT_TINY))
            self.font_button = pygame.font.SysFont(fallback, self._scale(theme.FONT_BUTTON), bold=True)
            self.font_bold = pygame.font.SysFont(fallback, self._scale(theme.FONT_BODY), bold=True)
        theme.reset_theme()
        if self.ax.high_contrast:
            theme.apply_high_contrast()

    def _load_sounds(self) -> None:
        self.sounds = {}
        for key, rel in [
            ("click", theme.SOUND_CLICK),
            ("buzzer", theme.SOUND_BUZZER),
            ("chime", theme.SOUND_CHIME),
        ]:
            try:
                self.sounds[key] = pygame.mixer.Sound(resource_path(rel))
            except pygame.error:
                self.sounds[key] = None

    def play_sound(self, name: str) -> None:
        if self.muted:
            return
        snd = self.sounds.get(name)
        if snd:
            snd.play()

    def push(self, screen) -> None:
        self.stack.append(screen)
        screen.on_enter(self)

    def pop(self) -> None:
        if len(self.stack) > 1:
            self.stack.pop()
            # Every screen owns a different set of focus widgets. Restore the
            # underlying screen's map after an overlay closes.
            self.stack[-1].build_focus(self)

    def replace(self, screen) -> None:
        if self.stack:
            self.stack.pop()
        self.push(screen)

    def _make_hub(self):
        from screens.hub import HubScreen

        return HubScreen()

    def _roster_is_open(self) -> bool:
        return bool(self.stack) and self.stack[-1].__class__.__name__ == "RosterScreen"

    def _toggle_roster(self) -> None:
        if self._roster_is_open():
            self.pop()
            return
        from screens.roster import RosterScreen

        self.push(RosterScreen())

    def _draw_global_roster_button(self) -> None:
        if self._roster_is_open():
            return
        from screens import ui

        ui.draw_quest_button(
            self.screen,
            ROSTER_BUTTON_RECT,
            "Roster [R]",
            self.font_tiny,
            variant="default",
        )

    async def run(self) -> None:
        try:
            while self.running:
                dt = self.clock.tick(60) / 1000.0
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_m:
                            self.muted = not self.muted
                        elif event.key == pygame.K_r:
                            self._toggle_roster()
                        else:
                            self.stack[-1].handle_event(self, event)
                    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if not self._roster_is_open() and ROSTER_BUTTON_RECT.collidepoint(event.pos):
                            self._toggle_roster()
                        else:
                            self.stack[-1].handle_event(self, event)
                    elif event.type == pygame.MOUSEWHEEL:
                        self.stack[-1].handle_event(self, event)
                self.stack[-1].update(self, dt)
                self.draw_frame()
                pygame.display.flip()
                await asyncio.sleep(0)
        finally:
            pygame.quit()

    def draw_frame(self) -> None:
        self.screen.fill(theme.BG_DEEP)
        if len(self.stack) >= 2 and getattr(self.stack[-1], "draw_under_modal", False):
            # Focus is global, but the covered screen still needs its own
            # widget schema while it redraws beneath a modal.
            modal_widgets = self.focus.widgets
            modal_index = self.focus.index
            self.stack[-2].build_focus(self)
            self.stack[-2].draw(self, self.screen)
            self.focus.widgets = modal_widgets
            self.focus.index = modal_index
        self.stack[-1].draw(self, self.screen)
        self._draw_global_roster_button()


class Screen:
    hint = "Arrows/Tab: move · Enter: select · Esc: back · M: mute"

    def on_enter(self, app: GameApp) -> None:
        self.build_focus(app)

    def build_focus(self, app: GameApp) -> None:
        app.focus.set_widgets([])

    def handle_event(self, app: GameApp, event: pygame.event.Event) -> None:
        pass

    def update(self, app: GameApp, dt: float) -> None:
        pass

    def draw(self, app: GameApp, surf: pygame.Surface) -> None:
        pass
