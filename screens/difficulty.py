from __future__ import annotations

import pygame

import theme
from engine import loader
from screens.manager import Screen
from screens import ui


class DifficultyScreen(Screen):
    hint = "Pick difficulty · Esc: back · M: mute"

    def build_focus(self, app) -> None:
        widgets = []
        gx = (theme.WINDOW_WIDTH - 960) // 2
        y = theme.MAIN_TOP
        w = (960 - 2 * theme.BUTTON_GAP) // 3
        for i, (name, cfg) in enumerate(loader.load_difficulty().items()):
            rect = pygame.Rect(gx + i * (w + theme.BUTTON_GAP), y, w, 160)
            widgets.append({"id": name, "rect": rect, "center": rect.center, "cfg": cfg})
        app.focus.set_widgets(widgets)

    def handle_event(self, app, event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                app.pop()
            elif event.key == pygame.K_LEFT:
                app.focus.move_tab(True)
            elif event.key in (pygame.K_RIGHT, pygame.K_DOWN):
                app.focus.move_tab(False)
            elif event.key == pygame.K_TAB:
                app.focus.move_tab(bool(event.mod & pygame.KMOD_SHIFT))
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._pick(app)
        if event.type == pygame.MOUSEBUTTONDOWN and app.focus.focus_at_point(*event.pos):
            self._pick(app)

    def _pick(self, app) -> None:
        cur = app.focus.current
        if not cur:
            return
        app.play_sound("click")
        from screens.captain import CaptainScreen

        app.push(CaptainScreen(cur["id"]))

    def draw(self, app, surf) -> None:
        ui.draw_background(surf)
        ui.draw_screen_header(
            surf,
            title="Choose Difficulty",
            stats_line="Same rules on every level — only numbers change",
            objective="Varsity is recommended for your first season",
            font_title=app.font_title,
            font_body=app.font_body,
            font_small=app.font_small,
        )
        for w in app.focus.widgets:
            cfg = w["cfg"]
            focused = app.focus.current is w
            ui.draw_panel(surf, w["rect"], font=app.font_small)
            if focused:
                pygame.draw.rect(surf, theme.TITLE_CYAN, w["rect"].inflate(6, 6), width=2)
            if cfg.get("recommended"):
                tag = app.font_small.render("RECOMMENDED", True, theme.OBJECTIVE_GREEN)
                surf.blit(tag, (w["rect"].x + 12, w["rect"].y + 12))
            title = app.font_body.render(cfg["label"].upper(), True, theme.TITLE_CYAN)
            surf.blit(title, (w["rect"].x + 12, w["rect"].y + 36))
            lines = [
                f"{cfg['weekly_tokens']} tokens / week",
                f"Opponent rating {cfg['rating_offset']:+d}",
                f"Event chance {int(cfg['event_chance'] * 100)}%",
            ]
            y = w["rect"].y + 72
            for line in lines:
                surf.blit(app.font_small.render(line, True, theme.TEXT_WHITE), (w["rect"].x + 12, y))
                y += 24
        ui.draw_hint_bar(surf, self.hint, app.font_small)
