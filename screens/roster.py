"""Global roster overlay, available from every screen with R."""
from __future__ import annotations

import pygame

import theme
from engine import loader, match
from screens import ui
from screens.manager import Screen


class RosterScreen(Screen):
    draw_under_modal = True
    hint = "Review player labels and roles · R / Esc / Enter: close · M: mute"

    def build_focus(self, app) -> None:
        rect = pygame.Rect(theme.WINDOW_WIDTH - theme.MARGIN_X - 170, 78, 170, 46)
        app.focus.set_widgets([{"id": "close", "rect": rect, "center": rect.center, "label": "Close Roster"}])

    def handle_event(self, app, event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_r, pygame.K_RETURN, pygame.K_SPACE):
                app.pop()
        elif event.type == pygame.MOUSEBUTTONDOWN and app.focus.focus_at_point(*event.pos):
            app.pop()

    def _athletes(self, app):
        return app.state.athletes if app.state is not None else loader.load_athletes()

    def draw(self, app, surf) -> None:
        overlay = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 225))
        surf.blit(overlay, (0, 0))

        athletes = self._athletes(app)
        starters = {a.name for a in match.pick_starters(athletes)}
        captain_index = app.state.captain_index if app.state is not None else None

        panel = pygame.Rect(36, 28, theme.WINDOW_WIDTH - 72, 620)
        ui.draw_panel(surf, panel, font=app.font_small)
        title = app.font_heading.render("TEAM ROSTER", True, theme.TITLE_CYAN)
        surf.blit(title, (panel.x + 22, panel.y + 16))
        mode = "CURRENT SEASON" if app.state is not None else "PRESEASON PROJECTION"
        summary = f"{mode}  ·  Players: {len(athletes)}  ·  Automatic starters: 5"
        surf.blit(app.font_small.render(summary, True, theme.TEXT_DIM), (panel.x + 22, panel.y + 58))

        close = app.focus.widgets[0]
        ui.draw_quest_button(
            surf, close["rect"], close["label"], app.font_small,
            focused=app.focus.current is close,
        )

        gap = 12
        card_w = (panel.width - 44 - gap) // 2
        card_h = 88
        start_y = panel.y + 104
        for i, athlete in enumerate(athletes[:10]):
            col = i % 2
            row = i // 2
            rect = pygame.Rect(panel.x + 22 + col * (card_w + gap), start_y + row * (card_h + 8), card_w, card_h)
            pygame.draw.rect(surf, theme.BG_DEEP, rect)
            border = theme.TITLE_CYAN if athlete.name in starters else theme.BORDER_BLUE
            pygame.draw.rect(surf, border, rect, width=4)

            is_captain = captain_index is not None and athlete.roster_index == captain_index
            role = "CAPTAIN / STARTER" if is_captain else ("STARTER" if athlete.name in starters else "BENCH")
            availability = "AVAILABLE" if athlete.available else f"OUT {athlete.games_out} GAME(S)"
            name = ui._fit_label(app.font_bold, athlete.name, card_w - 220)
            surf.blit(app.font_bold.render(name, True, theme.TEXT_WHITE), (rect.x + 12, rect.y + 8))
            role_s = app.font_tiny.render(f"{athlete.pos} · {role} · {availability}", True, border)
            surf.blit(role_s, role_s.get_rect(topright=(rect.right - 12, rect.y + 10)))

            primary = (
                f"Shooting {athlete.shooting}   Defense {athlete.defense}   "
                f"Stamina {athlete.stamina}   Overall {athlete.overall:.0f}"
            )
            secondary = (
                f"Potential {athlete.potential}   Leadership {athlete.leadership}   "
                f"Morale {athlete.morale}   Fatigue {athlete.fatigue}"
            )
            surf.blit(app.font_tiny.render(primary, True, theme.TEXT_WHITE), (rect.x + 12, rect.y + 38))
            fatigue_color = theme.BAD_RED if athlete.fatigue >= 70 else theme.TEXT_DIM
            surf.blit(app.font_tiny.render(secondary, True, fatigue_color), (rect.x + 12, rect.y + 62))

        ui.draw_hint_bar(surf, self.hint, app.font_small)
