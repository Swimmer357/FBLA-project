from __future__ import annotations

import pygame

import theme
from engine import loader
from screens.manager import Screen
from screens import ui


class HowToScreen(Screen):
    hint = "Up/Down or wheel: scroll  ·  Enter/Esc: back  ·  M: mute"

    def __init__(self) -> None:
        self.scroll = 0
        self._content_height = 0
        self._viewport_height = 0
        self._clip_rect = pygame.Rect(0, 0, 0, 0)
        self._controls_content_top = 0

    @property
    def max_scroll(self) -> int:
        return max(0, self._content_height - self._viewport_height)

    def _scroll_by(self, amount: int) -> None:
        self.scroll = max(0, min(self.scroll + amount, self.max_scroll))

    def build_focus(self, app) -> None:
        rect = pygame.Rect(theme.WINDOW_WIDTH - theme.MARGIN_X - 296, 18, 140, 48)
        app.focus.set_widgets([{"id": "done", "rect": rect, "center": rect.center, "label": "Done"}])

    def handle_event(self, app, event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                app.pop()
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                app.pop()
            elif event.key == pygame.K_DOWN:
                self._scroll_by(36)
            elif event.key == pygame.K_UP:
                self._scroll_by(-36)
            elif event.key in (pygame.K_END, pygame.K_PAGEDOWN):
                self.scroll = self.max_scroll
            elif event.key in (pygame.K_HOME, pygame.K_PAGEUP):
                self.scroll = 0
        elif event.type == pygame.MOUSEWHEEL:
            self._scroll_by(-event.y * 36)
        elif event.type == pygame.MOUSEBUTTONDOWN and app.focus.focus_at_point(*event.pos):
            app.pop()

    def draw(self, app, surf) -> None:
        ui.draw_background(surf)
        data = loader.load_howto()
        cfg = loader.load_season_config()
        diff = loader.load_difficulty()["Varsity"]

        div = ui.draw_screen_header(
            surf,
            title="How to Play",
            stats_line="Complete tutorial for judges and first-time players",
            objective="Read this once, then start New Season on Varsity",
            font_title=app.font_heading,
            font_body=app.font_body,
            font_small=app.font_small,
            font_bold=app.font_bold,
        )

        clip = pygame.Rect(
            theme.MARGIN_X,
            div + 20,
            theme.CONTENT_W,
            theme.WINDOW_HEIGHT - theme.HINT_H - div - 36,
        )
        self._clip_rect = clip
        self._viewport_height = clip.height
        pygame.draw.rect(surf, theme.PANEL_BG, clip)
        pygame.draw.rect(surf, theme.BORDER_BLUE, clip, width=4)

        previous_clip = surf.get_clip()
        surf.set_clip(clip.inflate(-4, -4))
        y = clip.y + 16 - self.scroll
        intro = data.get("intro", "")
        if intro:
            for line in self._wrap(app.font_body, intro, clip.width - 32):
                surf.blit(line, (clip.x + 16, y))
                y += line.get_height() + 8
            y += 12

        for pt in data["points"]:
            text = pt["text"].format(
                weekly_tokens=diff["weekly_tokens"],
                max_reserve=cfg["max_reserve"],
                moves_per_week=cfg["moves_per_week"],
            )
            head = app.font_bold.render(pt["heading"].upper(), True, theme.SECTION_YELLOW)
            surf.blit(head, (clip.x + 16, y))
            y += head.get_height() + 8
            for line in self._wrap(app.font_body, text, clip.width - 32):
                surf.blit(line, (clip.x + 16, y))
                y += line.get_height() + 6
            y += 16

        ctrl = data["controls"].format(
            weekly_tokens=diff["weekly_tokens"],
            max_reserve=cfg["max_reserve"],
            moves_per_week=cfg["moves_per_week"],
        )
        y += 8
        self._controls_content_top = y + self.scroll - clip.y
        controls_heading = app.font_bold.render("CONTROLS", True, theme.SECTION_YELLOW)
        surf.blit(controls_heading, (clip.x + 16, y))
        y += controls_heading.get_height() + 8
        for line in self._wrap(app.font_body, ctrl, clip.width - 32):
            surf.blit(line, (clip.x + 16, y))
            y += line.get_height() + 6

        self._content_height = y + self.scroll - clip.y + 16
        self.scroll = min(self.scroll, self.max_scroll)
        surf.set_clip(previous_clip)

        if self.max_scroll:
            cue = app.font_tiny.render(
                "END" if self.scroll >= self.max_scroll else f"{round(self.scroll / self.max_scroll * 100)}%  ↓",
                True,
                theme.SECTION_YELLOW,
            )
            cue_rect = cue.get_rect(bottomright=(clip.right - 12, clip.bottom - 8))
            pygame.draw.rect(surf, theme.PANEL_BG, cue_rect.inflate(12, 8))
            surf.blit(cue, cue_rect)

        done = app.focus.widgets[0]
        ui.draw_quest_button(
            surf, done["rect"], done["label"], app.font_button,
            focused=app.focus.current is done,
        )
        ui.draw_hint_bar(surf, self.hint, app.font_small)

    def _wrap(self, font, text, width):
        words = text.split()
        lines = []
        cur = ""
        for w in words:
            test = (cur + " " + w).strip()
            if font.size(test)[0] <= width:
                cur = test
            else:
                if cur:
                    lines.append(font.render(cur, True, theme.TEXT_WHITE))
                cur = w
        if cur:
            lines.append(font.render(cur, True, theme.TEXT_WHITE))
        return lines
