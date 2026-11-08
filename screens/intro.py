"""Cinematic, perspective-scrolling tutorial before the program dashboard."""
from __future__ import annotations

import pygame

import theme
from engine import loader
from screens.accessibility import save_settings
from screens.manager import Screen
from screens import ui


def _load_intro() -> dict:
    return loader.load_intro()


class IntroScreen(Screen):
    hint = "Space: pause · Up/Down: speed · Tab: buttons · Esc: skip · M: mute"

    def __init__(self, return_to_hub: bool = False) -> None:
        self.data = _load_intro()
        self.return_to_hub = return_to_hub
        self.paused = False
        self.speed = float(self.data.get("scroll_speed", 42))
        self.scroll_y = 646.0
        self.entries: list[tuple[pygame.Surface, float]] = []
        self.total_height = 0.0

    def on_enter(self, app) -> None:
        self._build_crawl(app)
        self.build_focus(app)

    def build_focus(self, app) -> None:
        app.focus.set_widgets(
            [
                {
                    "id": "pause",
                    "rect": pygame.Rect(theme.MARGIN_X, 618, 180, 48),
                    "center": (theme.MARGIN_X + 90, 642),
                    "label": "Pause",
                },
                {
                    "id": "skip",
                    "rect": pygame.Rect(theme.WINDOW_WIDTH - theme.MARGIN_X - 250, 618, 250, 48),
                    "center": (theme.WINDOW_WIDTH - theme.MARGIN_X - 125, 642),
                    "label": self.data["skip_label"],
                },
            ]
        )

    @staticmethod
    def _wrap_strings(font: pygame.font.Font, text: str, width: int) -> list[str]:
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            test = f"{current} {word}".strip()
            if font.size(test)[0] <= width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def _build_crawl(self, app) -> None:
        self.entries = []
        cursor = 0.0
        school = loader.load_season_config()["school_name"]

        def add(text: str, font: pygame.font.Font, color, width: int, gap: int) -> None:
            nonlocal cursor
            for line in self._wrap_strings(font, text.format(school_name=school), width):
                rendered = font.render(line, True, color)
                self.entries.append((rendered, cursor))
                cursor += rendered.get_height() + gap

        add(self.data["opening"], app.font_small, theme.TITLE_CYAN, 760, 8)
        cursor += 22
        add(self.data["title"], app.font_title, theme.SECTION_YELLOW, 820, 12)
        cursor += 34
        for section in self.data["sections"]:
            add(section["heading"], app.font_heading, theme.SECTION_YELLOW, 820, 10)
            cursor += 8
            add(section["text"], app.font_body, theme.TEXT_WHITE, 850, 12)
            cursor += 34
        add(self.data["closing"], app.font_heading, theme.TITLE_CYAN, 820, 10)
        self.total_height = cursor + 80

    def _finish(self, app) -> None:
        app.intro_complete = True
        app.ax.intro_seen = True
        save_settings(app.ax)
        if self.return_to_hub:
            app.pop()
            return
        from screens.hub import HubScreen

        app.replace(HubScreen())

    def handle_event(self, app, event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._finish(app)
            elif event.key == pygame.K_TAB:
                app.focus.move_tab(bool(event.mod & pygame.KMOD_SHIFT))
            elif event.key == pygame.K_SPACE:
                self._toggle_pause()
            elif event.key in (pygame.K_UP, pygame.K_RIGHT):
                self.speed = min(100.0, self.speed + 8.0)
            elif event.key in (pygame.K_DOWN, pygame.K_LEFT):
                self.speed = max(20.0, self.speed - 8.0)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._activate(app)
        if event.type == pygame.MOUSEBUTTONDOWN and app.focus.focus_at_point(*event.pos):
            self._activate(app)

    def _toggle_pause(self) -> None:
        self.paused = not self.paused

    def _activate(self, app) -> None:
        cur = app.focus.current
        if not cur:
            return
        app.play_sound("click")
        if cur["id"] == "pause":
            self._toggle_pause()
        else:
            self._finish(app)

    def update(self, app, dt: float) -> None:
        if not self.paused:
            self.scroll_y -= self.speed * dt
        if self.scroll_y + self.total_height < 145:
            self._finish(app)

    def draw(self, app, surf) -> None:
        surf.fill((1, 3, 14))
        for i in range(90):
            x = (i * 97 + 31) % theme.WINDOW_WIDTH
            y = (i * 53 + 17) % 610
            shade = 100 + (i * 29) % 155
            pygame.draw.circle(surf, (shade, shade, min(255, shade + 20)), (x, y), 1 + (i % 13 == 0))

        horizon = 132
        bottom = 606
        glow = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (*theme.ACCENT_BLUE, 28), (-100, horizon - 50, 1480, 170))
        pygame.draw.line(glow, (*theme.TITLE_CYAN, 90), (180, horizon), (1100, horizon), 2)
        surf.blit(glow, (0, 0))

        old_clip = surf.get_clip()
        surf.set_clip(pygame.Rect(0, horizon, theme.WINDOW_WIDTH, bottom - horizon))
        for rendered, offset in self.entries:
            y = self.scroll_y + offset
            if y < horizon - 50 or y > bottom + 70:
                continue
            depth = max(0.0, min(1.0, (y - horizon) / (bottom - horizon)))
            scale = 0.34 + depth * 0.66
            width = max(1, int(rendered.get_width() * scale))
            height = max(1, int(rendered.get_height() * scale))
            line = pygame.transform.smoothscale(rendered, (width, height))
            if depth < 0.18:
                line.set_alpha(int(255 * depth / 0.18))
            surf.blit(line, line.get_rect(midtop=(theme.WINDOW_WIDTH // 2, int(y))))
        surf.set_clip(old_clip)

        pygame.draw.rect(surf, (1, 3, 14), pygame.Rect(0, 606, theme.WINDOW_WIDTH, 70))
        status = f"{'PAUSED' if self.paused else 'TUTORIAL CRAWL'}  ·  SPEED {int(self.speed)}"
        status_s = app.font_small.render(status, True, theme.TEXT_DIM)
        surf.blit(status_s, status_s.get_rect(midtop=(theme.WINDOW_WIDTH // 2, 626)))
        for w in app.focus.widgets:
            label = "Resume" if w["id"] == "pause" and self.paused else w["label"]
            ui.draw_quest_button(
                surf,
                w["rect"],
                label,
                app.font_button,
                focused=app.focus.current is w,
                variant="gradient" if w["id"] == "skip" else "default",
            )
        ui.draw_hint_bar(surf, self.hint, app.font_small)
