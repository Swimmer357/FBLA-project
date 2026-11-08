from __future__ import annotations

import sys

import pygame

import theme
from engine import loader
from screens.manager import Screen
from screens import ui


class AboutScreen(Screen):
    hint = "Up/Down or wheel: scroll · Enter/Esc: back · M: mute"

    def __init__(self) -> None:
        self.scroll = 0
        self._content_height = 0
        self._viewport_height = 0
        self._clip_rect = pygame.Rect(0, 0, 0, 0)

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
        data = loader.load_about()
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        pg_ver = pygame.version.ver
        lines = [
            ("What this game is", data["what"]),
            ("Design rationale", data["rationale"]),
            (
                "How it was built",
                data["built"] + f" Running Python {py_ver} and pygame {pg_ver}.",
            ),
            ("How the art is made", data["art"]),
            ("Accessibility", data["accessibility"]),
            ("Credits", f"{data['credits_font']} · {data['credits_sound']}"),
            ("How we tested", data["testing"]),
            ("User journey", " → ".join(data["journey_steps"])),
            ("Evaluation & improvements", data["improvements"]),
        ]
        ui.draw_background(surf)
        done = app.focus.widgets[0]
        ui.draw_quest_button(
            surf, done["rect"], done["label"], app.font_button,
            focused=app.focus.current is done,
        )
        clip = pygame.Rect(
            theme.MARGIN_X,
            82,
            theme.CONTENT_W,
            theme.WINDOW_HEIGHT - theme.HINT_H - 98,
        )
        self._clip_rect = clip
        self._viewport_height = clip.height
        pygame.draw.rect(surf, theme.PANEL_BG, clip)
        pygame.draw.rect(surf, theme.BORDER_BLUE, clip, width=4)
        previous_clip = surf.get_clip()
        surf.set_clip(clip.inflate(-4, -4))
        y = clip.y + 14 - self.scroll
        surf.blit(app.font_heading.render("About", True, theme.TITLE_CYAN), (clip.x + 16, y))
        y += app.font_heading.get_linesize() + 10
        for heading, body in lines:
            heading_s = app.font_body.render(heading, True, theme.ORANGE)
            surf.blit(heading_s, (clip.x + 16, y))
            y += heading_s.get_height() + 6
            for chunk in self._wrap(app.font_small, body, clip.width - 32):
                surf.blit(chunk, (clip.x + 16, y))
                y += chunk.get_height() + 4
            y += 12
        self._content_height = y + self.scroll - clip.y + 14
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
                    lines.append(font.render(cur, True, theme.WHITE))
                cur = w
        if cur:
            lines.append(font.render(cur, True, theme.WHITE))
        return lines
