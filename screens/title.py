from __future__ import annotations

import pygame

import theme
from engine import loader
from screens.manager import Screen
from screens import ui

MENU_TOP = 228
MENU_W = 760


class TitleScreen(Screen):
    hint = "Tab / Arrow keys · Enter to select · ? opens full tutorial · M: mute"

    def build_focus(self, app) -> None:
        gx = (theme.WINDOW_WIDTH - MENU_W) // 2
        y = MENU_TOP
        widgets = [
            {"id": "help", "rect": pygame.Rect(theme.MARGIN_X, 16, 48, 48), "center": (theme.MARGIN_X + 24, 40), "label": "?"},
            {"id": "about_icon", "rect": pygame.Rect(theme.MARGIN_X + 56, 16, 48, 48), "center": (theme.MARGIN_X + 80, 40), "label": "i"},
            {
                "id": "new",
                "rect": pygame.Rect(gx, y, MENU_W, theme.BUTTON_H_FEATURED),
                "center": (gx + MENU_W // 2, y + 36),
                "label": "New Season",
                "variant": "gradient",
            },
        ]
        y += theme.BUTTON_H_FEATURED + theme.BUTTON_GAP
        half = (MENU_W - theme.BUTTON_GAP) // 2
        widgets.append({"id": "howto", "rect": pygame.Rect(gx, y, half, theme.BUTTON_H), "center": (gx + half // 2, y + 30), "label": "How to Play"})
        widgets.append(
            {
                "id": "about",
                "rect": pygame.Rect(gx + half + theme.BUTTON_GAP, y, half, theme.BUTTON_H),
                "center": (gx + half + theme.BUTTON_GAP + half // 2, y + 30),
                "label": "About",
            }
        )
        quit_w = 240
        widgets.append(
            {
                "id": "quit",
                "rect": pygame.Rect(
                    (theme.WINDOW_WIDTH - quit_w) // 2,
                    theme.WINDOW_HEIGHT - theme.HINT_H - theme.BUTTON_H - 10,
                    quit_w,
                    theme.BUTTON_H,
                ),
                "center": (
                    theme.WINDOW_WIDTH // 2,
                    theme.WINDOW_HEIGHT - theme.HINT_H - theme.BUTTON_H // 2 - 10,
                ),
                "label": "Exit Game",
                "variant": "danger",
            }
        )
        app.focus.set_widgets(widgets)

    def handle_event(self, app, event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN:
            if app.focus.focus_at_point(*event.pos):
                self._activate(app)
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_TAB,):
                app.focus.move_tab(event.mod & pygame.KMOD_SHIFT)
            elif event.key in (pygame.K_UP, pygame.K_LEFT):
                app.focus.move_tab(True)
            elif event.key in (pygame.K_DOWN, pygame.K_RIGHT):
                app.focus.move_tab(False)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._activate(app)

    def _activate(self, app) -> None:
        cur = app.focus.current
        if not cur:
            return
        app.play_sound("click")
        key = cur["id"]
        if key == "quit":
            app.running = False
        elif key in ("howto", "help"):
            from screens.howto import HowToScreen

            app.push(HowToScreen())
        elif key in ("about", "about_icon"):
            from screens.about import AboutScreen

            app.push(AboutScreen())
        elif key == "new":
            from screens.difficulty import DifficultyScreen

            app.push(DifficultyScreen())

    def draw(self, app, surf) -> None:
        ui.draw_background(surf)
        cfg = loader.load_season_config()
        div = ui.draw_screen_header(
            surf,
            title="Hoops Manager",
            stats_line=f"{cfg['school_name']}  ·  7-game season  ·  Win 4 for playoffs",
            objective="Lead your school to the state championship",
            font_title=app.font_title,
            font_body=app.font_body,
            font_small=app.font_small,
            font_bold=app.font_bold,
        )
        prompt = app.font_bold.render("CHOOSE AN OPTION BELOW", True, theme.SECTION_YELLOW)
        surf.blit(prompt, prompt.get_rect(midtop=(theme.WINDOW_WIDTH // 2, div + 16)))
        tip = app.font_body.render("New here? Open How to Play for the full tutorial.", True, theme.TEXT_DIM)
        surf.blit(tip, tip.get_rect(midtop=(theme.WINDOW_WIDTH // 2, div + 48)))
        for w in app.focus.widgets:
            if w["id"] in ("help", "about_icon"):
                ui.draw_icon_button(surf, w["rect"], w["label"], app.font_bold, app.focus.current is w)
            else:
                ui.draw_quest_button(
                    surf,
                    w["rect"],
                    w["label"],
                    app.font_button,
                    focused=app.focus.current is w,
                    variant=w.get("variant", "default"),
                )
        ui.draw_hint_bar(surf, self.hint, app.font_small)
