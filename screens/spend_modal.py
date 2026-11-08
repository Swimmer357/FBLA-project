"""Reusable confirmation sheet for token spending and upgrade projections."""
from __future__ import annotations

import pygame

import theme
from engine.projections import SpendPreview
from screens import ui
from screens.manager import Screen


class SpendPreviewModal(Screen):
    draw_under_modal = True
    hint = "Review cost and effects · Enter: select · Esc: cancel · M: mute"

    def __init__(self, preview: SpendPreview, on_confirm) -> None:
        self.preview = preview
        self.on_confirm = on_confirm

    def build_focus(self, app) -> None:
        app.focus.set_widgets(
            [
                {"id": "cancel", "rect": pygame.Rect(330, 554, 260, 58), "center": (460, 583), "label": "Cancel"},
                {"id": "confirm", "rect": pygame.Rect(620, 554, 330, 58), "center": (785, 583), "label": self.preview.confirm_label},
            ]
        )

    def handle_event(self, app, event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                app.pop()
            elif event.key == pygame.K_TAB:
                app.focus.move_tab(bool(event.mod & pygame.KMOD_SHIFT))
            elif event.key in (pygame.K_LEFT, pygame.K_UP):
                app.focus.move_tab(True)
            elif event.key in (pygame.K_RIGHT, pygame.K_DOWN):
                app.focus.move_tab(False)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._activate(app)
        elif event.type == pygame.MOUSEBUTTONDOWN and app.focus.focus_at_point(*event.pos):
            self._activate(app)

    def _activate(self, app) -> None:
        current = app.focus.current
        if not current:
            return
        app.play_sound("click")
        confirm = current["id"] == "confirm"
        app.pop()
        if confirm:
            self.on_confirm(app)

    @staticmethod
    def _draw_column(app, surf, rect: pygame.Rect, heading: str, items: tuple[str, ...], color) -> None:
        pygame.draw.rect(surf, theme.BG_DEEP, rect)
        pygame.draw.rect(surf, color, rect, width=2)
        surf.blit(app.font_bold.render(heading, True, color), (rect.x + 12, rect.y + 10))
        y = rect.y + 46
        for item in items:
            for line in ui.wrap_text(app.font_small, f"• {item}", rect.width - 24):
                if y + line.get_height() <= rect.bottom - 8:
                    surf.blit(line, (rect.x + 12, y))
                y += line.get_height() + 4
            y += 5

    def draw(self, app, surf) -> None:
        overlay = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 218))
        surf.blit(overlay, (0, 0))
        panel = pygame.Rect(100, 58, 1080, 580)
        ui.draw_panel(surf, panel, font=app.font_small)

        warning = app.font_small.render("REVIEW BEFORE COMMITTING TOKENS", True, theme.SECTION_YELLOW)
        surf.blit(warning, (panel.x + 24, panel.y + 16))
        title = app.font_heading.render(self.preview.title.upper(), True, theme.TITLE_CYAN)
        surf.blit(title, (panel.x + 24, panel.y + 44))

        summary = pygame.Rect(panel.x + 24, panel.y + 92, panel.width - 48, 94)
        pygame.draw.rect(surf, theme.BG_DEEP, summary)
        pygame.draw.rect(surf, theme.BORDER_BLUE, summary, width=2)
        y = summary.y + 12
        for line in ui.wrap_text(app.font_small, self.preview.summary, summary.width - 24)[:3]:
            surf.blit(line, (summary.x + 12, y))
            y += line.get_height() + 5

        col_gap = 14
        col_w = (summary.width - col_gap * 2) // 3
        col_y = summary.bottom + 16
        col_h = 172
        self._draw_column(app, surf, pygame.Rect(summary.x, col_y, col_w, col_h), "COST", self.preview.cost, theme.SECTION_YELLOW)
        self._draw_column(app, surf, pygame.Rect(summary.x + col_w + col_gap, col_y, col_w, col_h), "BENEFITS", self.preview.benefits, theme.GOOD_GREEN)
        self._draw_column(app, surf, pygame.Rect(summary.x + (col_w + col_gap) * 2, col_y, col_w, col_h), "DRAWBACKS", self.preview.drawbacks, theme.BAD_RED)

        if self.preview.projection:
            projection = pygame.Rect(summary.x, col_y + col_h + 14, summary.width, 64)
            pygame.draw.rect(surf, theme.BG_DEEP, projection)
            pygame.draw.rect(surf, theme.ACCENT_PURPLE, projection, width=2)
            label = app.font_small.render("FUTURE UPGRADE PROJECTION", True, theme.ACCENT_PINK)
            surf.blit(label, (projection.x + 12, projection.y + 8))
            detail = "  ·  ".join(self.preview.projection)
            rendered = app.font_small.render(ui._fit_label(app.font_small, detail, projection.width - 24), True, theme.TEXT_WHITE)
            surf.blit(rendered, (projection.x + 12, projection.y + 34))

        for widget in app.focus.widgets:
            ui.draw_quest_button(
                surf,
                widget["rect"],
                widget["label"],
                app.font_button,
                focused=app.focus.current is widget,
                variant="gradient" if widget["id"] == "confirm" else "default",
            )
        ui.draw_hint_bar(surf, self.hint, app.font_small)
