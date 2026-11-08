"""Program dashboard — main menu after preseason briefing."""
from __future__ import annotations

import pygame

import theme
from engine import loader, match
from screens.manager import Screen
from screens import ui

MENU_W = theme.sx(1200)


def _hub_copy() -> dict:
    return loader.load_hub()


class HubScreen(Screen):
    def __init__(self) -> None:
        self.copy = _hub_copy()
        self.hint = self.copy["hints"]

    def build_focus(self, app) -> None:
        gx = (theme.WINDOW_WIDTH - MENU_W) // 2
        y = self._header_bottom(app) + app.font_bold.get_linesize() + 22
        b = self.copy["buttons"]
        widgets = [
            {"id": "help", "rect": pygame.Rect(theme.MARGIN_X, 16, 42, 42), "center": (theme.MARGIN_X + 21, 37), "label": "?"},
            {"id": "settings", "rect": pygame.Rect(theme.MARGIN_X + 47, 16, 42, 42), "center": (theme.MARGIN_X + 68, 37), "label": "S"},
            {
                "id": "exit",
                "rect": pygame.Rect(theme.WINDOW_WIDTH - theme.MARGIN_X - 292, 16, 136, 42),
                "center": (theme.WINDOW_WIDTH - theme.MARGIN_X - 224, 37),
                "label": b["exit"],
                "variant": "danger",
            },
            {
                "id": "new",
                "rect": pygame.Rect(gx, y, MENU_W, theme.BUTTON_H_FEATURED),
                "center": (gx + MENU_W // 2, y + theme.BUTTON_H_FEATURED // 2),
                "label": b["new_season"],
                "variant": "gradient",
            },
        ]
        y += theme.BUTTON_H_FEATURED + theme.BUTTON_GAP
        third = (MENU_W - 2 * theme.BUTTON_GAP) // 3
        widgets.append({"id": "howto", "rect": pygame.Rect(gx, y, third, theme.BUTTON_H), "center": (gx + third // 2, y + theme.BUTTON_H // 2), "label": b["how_to_play"]})
        widgets.append({"id": "about", "rect": pygame.Rect(gx + third + theme.BUTTON_GAP, y, third, theme.BUTTON_H), "center": (gx + third + theme.BUTTON_GAP + third // 2, y + theme.BUTTON_H // 2), "label": b["about"]})
        widgets.append(
            {
                "id": "briefing",
                "rect": pygame.Rect(gx + (third + theme.BUTTON_GAP) * 2, y, third, theme.BUTTON_H),
                "center": (gx + (third + theme.BUTTON_GAP) * 2 + third // 2, y + theme.BUTTON_H // 2),
                "label": b["briefing"],
            }
        )
        app.focus.set_widgets(widgets)

    def _header_bottom(self, app) -> int:
        objective = (
            app.hub_summary.get("objective", self.copy["default_objective"])
            if app.hub_summary
            else self.copy["default_objective"]
        )
        return ui.measure_screen_header(
            height=theme.WINDOW_HEIGHT,
            font_title=app.font_heading,
            font_body=app.font_tiny,
            font_bold=app.font_bold,
            objective=objective,
            detail_heading=self.copy["lineup_heading"],
            detail_lines=tuple(self._projected_starters()),
        ) - 4

    def handle_event(self, app, event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._confirm_exit(app)
            return
        if event.type == pygame.MOUSEBUTTONDOWN:
            if app.focus.focus_at_point(*event.pos):
                self._activate(app)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_s:
                from screens.settings import SettingsScreen

                app.push(SettingsScreen())
            elif event.key == pygame.K_SLASH and event.mod & pygame.KMOD_SHIFT:
                from screens.howto import HowToScreen

                app.push(HowToScreen())
            elif event.key in (pygame.K_TAB,):
                app.focus.move_tab(event.mod & pygame.KMOD_SHIFT)
            elif event.key in (pygame.K_UP, pygame.K_LEFT):
                app.focus.move_tab(True)
            elif event.key in (pygame.K_DOWN, pygame.K_RIGHT):
                app.focus.move_tab(False)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._activate(app)

    def _confirm_exit(self, app) -> None:
        from screens.modal import ConfirmModal

        app.push(
            ConfirmModal(
                "Leave the program dashboard?",
                on_yes=lambda a: setattr(a, "running", False),
                on_no=lambda a: None,
                yes_label="Exit",
                no_label="Stay",
            )
        )

    def _activate(self, app) -> None:
        cur = app.focus.current
        if not cur:
            return
        app.play_sound("click")
        key = cur["id"]
        if key == "exit":
            self._confirm_exit(app)
        elif key == "help":
            from screens.howto import HowToScreen

            app.push(HowToScreen())
        elif key == "howto":
            from screens.howto import HowToScreen

            app.push(HowToScreen())
        elif key == "settings":
            from screens.settings import SettingsScreen

            app.push(SettingsScreen())
        elif key == "about":
            from screens.about import AboutScreen

            app.push(AboutScreen())
        elif key == "briefing":
            from screens.intro import IntroScreen

            app.push(IntroScreen(return_to_hub=True))
        elif key == "new":
            from screens.difficulty import DifficultyScreen

            app.push(DifficultyScreen())

    def _projected_starters(self) -> list[str]:
        athletes = loader.load_athletes()
        ranked = sorted(athletes, key=lambda a: (-match.starter_score(a), -a.overall))
        lines = []
        for i, a in enumerate(ranked[:5], start=1):
            score = match.starter_score(a)
            lines.append(f"{i}. {a.name} ({a.pos}) — {score:.1f}")
        return lines

    def _blit_center(self, surf: pygame.Surface, font: pygame.font.Font, text: str, y: int, color: tuple[int, int, int]) -> int:
        rendered = font.render(text, True, color)
        surf.blit(rendered, rendered.get_rect(midtop=(theme.WINDOW_WIDTH // 2, y)))
        return y + rendered.get_height()

    def draw(self, app, surf) -> None:
        ui.draw_background(surf)
        cfg = loader.load_season_config()
        c = self.copy
        summary = app.hub_summary

        if summary:
            record = summary["record"]
            status = summary["ending"]
            objective = summary.get("objective", c["default_objective"])
        else:
            record = "0–0"
            status = "PRESEASON"
            objective = c["default_objective"]

        lineup = self._projected_starters()
        divider = ui.draw_screen_header(
            surf,
            title=cfg["school_name"],
            stats_line=f"{c['dashboard_title']}  |  RECORD {record}  |  {status}",
            objective=objective,
            font_title=app.font_heading,
            font_body=app.font_tiny,
            font_small=app.font_small,
            font_bold=app.font_bold,
            detail_heading=c["lineup_heading"],
            detail_lines=tuple(lineup),
        )

        heading = app.font_bold.render(c["actions_heading"].upper(), True, theme.SECTION_YELLOW)
        surf.blit(heading, heading.get_rect(midtop=(theme.WINDOW_WIDTH // 2, divider + 10)))

        for w in app.focus.widgets:
            if w["id"] in ("help", "settings"):
                ui.draw_icon_button(surf, w["rect"], w["label"], app.font_bold, app.focus.current is w)
            else:
                ui.draw_tile(
                    surf,
                    w["rect"],
                    w["label"],
                    app.font_button,
                    focused=app.focus.current is w,
                    featured=w.get("variant") == "gradient",
                )
        ui.draw_hint_bar(surf, self.hint, app.font_small)
