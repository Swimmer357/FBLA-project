from __future__ import annotations

import pygame

import theme
from engine import loader
from screens.manager import Screen
from screens import ui


class MatchScreen(Screen):
    hint = "Enter or click to skip scoreboard · M: mute"

    def __init__(self) -> None:
        self.t = 0.0
        self.done = False

    def on_enter(self, app) -> None:
        self.build_focus(app)
        self.result = app.state.last_result
        self.t = 0.0
        self.done = False

    def handle_event(self, app, event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._finish(app)
        if event.type == pygame.MOUSEBUTTONDOWN:
            self._finish(app)

    def _finish(self, app) -> None:
        if self.done:
            return
        self.done = True
        if self.result.won:
            app.play_sound("chime")
        else:
            app.play_sound("buzzer")
        from screens.results import ResultsScreen

        app.replace(ResultsScreen())

    def update(self, app, dt: float) -> None:
        self.t += dt
        if self.t >= 3.0:
            self._finish(app)

    def draw(self, app, surf) -> None:
        ui.draw_court(surf, alpha=70)
        cfg = loader.load_season_config()
        home = cfg["school_name"]
        away = self.result.opponent_name
        progress = min(1.0, self.t / 3.0) if not self.done else 1.0
        hs = int(self.result.team_score * progress)
        os_ = int(self.result.opponent_score * progress)
        ui.draw_scoreboard(surf, home, away, hs, os_, app.font_title, app.font_body)

        # A compact game-day presentation: four quarters advance while the
        # deterministic final score counts up. This never changes simulation logic.
        quarter = min(4, int(progress * 4) + 1)
        seconds = max(0, int((1.0 - ((progress * 4) % 1.0)) * 8 * 60))
        clock = f"Q{quarter}  {seconds // 60}:{seconds % 60:02d}" if progress < 1 else "FINAL"
        clock_s = app.font_bold.render(clock, True, theme.TEXT_WHITE)
        clock_panel = pygame.Rect(535, 154, 210, 44)
        pygame.draw.rect(surf, theme.PANEL_BG, clock_panel)
        pygame.draw.rect(surf, theme.SECTION_YELLOW, clock_panel, width=2)
        surf.blit(clock_s, clock_s.get_rect(center=clock_panel.center))

        home_positions = [(300, 270), (390, 430), (505, 320), (470, 515), (600, 405)]
        away_positions = [(980, 270), (890, 430), (775, 320), (810, 515), (680, 405)]
        bob = int(8 * abs((progress * 8) % 2 - 1))
        for i, (x, y) in enumerate(home_positions):
            pygame.draw.circle(surf, theme.TITLE_CYAN, (x + bob, y), 15)
            pygame.draw.circle(surf, theme.PANEL_BG, (x + bob, y), 15, 3)
            n = app.font_small.render(str(i + 1), True, theme.PANEL_BG)
            surf.blit(n, n.get_rect(center=(x + bob, y)))
        for i, (x, y) in enumerate(away_positions):
            pygame.draw.circle(surf, theme.SECTION_YELLOW, (x - bob, y), 15)
            pygame.draw.circle(surf, theme.PANEL_BG, (x - bob, y), 15, 3)
            n = app.font_small.render(str(i + 1), True, theme.PANEL_BG)
            surf.blit(n, n.get_rect(center=(x - bob, y)))

        ball_x = int(250 + 780 * progress)
        ball_y = int(390 - 85 * abs(((progress * 6) % 2) - 1))
        pygame.draw.circle(surf, (224, 105, 49), (ball_x, ball_y), 11)
        pygame.draw.circle(surf, theme.BG_DEEP, (ball_x, ball_y), 11, 2)

        status = "SIMULATING YOUR GAME PLAN" if progress < 1 else "FINAL SCORE"
        status_s = app.font_small.render(status, True, theme.TEXT_WHITE)
        surf.blit(status_s, status_s.get_rect(midtop=(theme.WINDOW_WIDTH // 2, 606)))
        ui.draw_hint_bar(surf, self.hint, app.font_small)
