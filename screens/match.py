from __future__ import annotations

import math
import random

import pygame

import theme
from engine import loader
from engine.timeline import (
    FINAL_HOLD,
    SHOT_REAL,
    clock_at,
    event_real_time,
    game_end_real,
    timeline_for_result,
)
from screens.manager import Screen
from screens import ui

SPEEDS = (1, 2, 0)
SPEED_LABELS = {1: "1x", 2: "2x", 0: "INSTANT"}
RADIUS = 15
MIN_GAP = RADIUS * 2 + 3
MAX_SPEED = 520.0
ARRIVE_GAIN = 5.0
STEER_GAIN = 10.0
MAX_STEP = 1 / 30
PASS_REAL = 0.22
PASS_EVERY = 0.35
FLASH_REAL = 0.25
OFFENSE_SLOTS = ((300, 0), (230, -150), (230, 150), (70, -195), (95, 80))
SPEED_RECT = pygame.Rect(theme.MARGIN_X, 632, 210, 40)
QUICK_RECT = pygame.Rect(theme.WINDOW_WIDTH - theme.MARGIN_X - 250, 632, 250, 40)
HOME_COLOR = theme.TITLE_CYAN
AWAY_COLOR = theme.SECTION_YELLOW
BALL_COLOR = (224, 105, 49)


class MatchScreen(Screen):
    hint = "Enter/Space: skip to final · F: speed · Q: quick sim · M: mute"

    def __init__(self) -> None:
        self.done = False

    def on_enter(self, app) -> None:
        self.build_focus(app)
        self.done = False
        self.result = app.state.last_result
        self.home_name = loader.load_season_config()["school_name"]
        self.away_name = self.result.opponent_name
        self.timeline = timeline_for_result(self.result, self.home_name)
        events = self.timeline.events
        self.times = [event_real_time(self.timeline, e) for e in events]
        self.highlights = [i for i, e in enumerate(events) if e.highlight]
        self.game_end = game_end_real(self.timeline)
        self.end_t = self.game_end + FINAL_HOLD
        self.play_t = 0.0
        self.real_t = 0.0
        self.next_i = 0
        self.home_score = 0
        self.away_score = 0
        self.flash = {"home": 0.0, "away": 0.0}
        self.pbp = f"Tip-off: {self.home_name} vs {self.away_name}"
        self.rng = random.Random(self.result.week * 3571 + self.result.team_score)
        self.quick = app.quick_sim_state is not None and app.quick_sim_state is app.state

        self.court = pygame.Surface((theme.WINDOW_WIDTH, theme.WINDOW_HEIGHT))
        ui.draw_court(self.court, alpha=70)
        self.bounds = ui.court_rect().inflate(-2 * RADIUS - 6, -2 * RADIUS - 6)
        left_hoop, right_hoop = ui.hoop_positions()
        self.hoop = {"home": pygame.Vector2(right_hoop), "away": pygame.Vector2(left_hoop)}
        self.direction = {"home": 1, "away": -1}
        self._text_cache: dict[tuple[str, int], pygame.Surface] = {}

        self.players = {"home": len(self.timeline.home_players), "away": len(self.timeline.away_players)}
        center = pygame.Vector2(ui.court_rect().center)
        self.pos: dict[str, list[pygame.Vector2]] = {}
        self.vel: dict[str, list[pygame.Vector2]] = {}
        self.phase = {}
        for team, side in (("home", -1), ("away", 1)):
            count = self.players[team]
            self.pos[team] = [
                center + pygame.Vector2(side * (60 + 70 * (i % 3)), -110 + 55 * i) for i in range(count)
            ]
            self.vel[team] = [pygame.Vector2() for _ in range(count)]
            self.phase[team] = [self.rng.uniform(0, math.tau) for _ in range(count)]
        self.labels = {
            team: [app.font_small.render(str(i + 1), True, theme.PANEL_BG) for i in range(self.players[team])]
            for team in ("home", "away")
        }

        self.owner = ("home", 0)
        self.ball = pygame.Vector2(center)
        self.anim: dict | None = None
        self.last_pass_t = -1.0
        self.resolved_highlights: set[int] = set()
        if app.match_speed == 0:
            self._skip_to_end()

    # ---- input -------------------------------------------------------------

    def handle_event(self, app, event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._skip_or_finish(app)
            elif event.key == pygame.K_f:
                self._cycle_speed(app)
            elif event.key == pygame.K_q:
                self._toggle_quick(app)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if SPEED_RECT.collidepoint(event.pos):
                self._cycle_speed(app)
            elif QUICK_RECT.collidepoint(event.pos):
                self._toggle_quick(app)
            else:
                self._skip_or_finish(app)

    def _skip_or_finish(self, app) -> None:
        if self.play_t < self.game_end:
            self._skip_to_end()
        else:
            self._finish(app)

    def _cycle_speed(self, app) -> None:
        app.match_speed = SPEEDS[(SPEEDS.index(app.match_speed) + 1) % len(SPEEDS)]
        if app.match_speed == 0:
            self._skip_to_end()

    def _toggle_quick(self, app) -> None:
        if app.quick_sim_state is app.state:
            app.quick_sim_state = None
            self.quick = False
        else:
            app.quick_sim_state = app.state
            self.quick = True
            self._skip_to_end()

    def _skip_to_end(self) -> None:
        self.play_t = max(self.play_t, self.game_end)
        self._apply_events()
        self.anim = None

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

    # ---- timeline playback ---------------------------------------------------

    def _apply_events(self) -> None:
        events = self.timeline.events
        while self.next_i < len(events) and self.times[self.next_i] <= self.play_t:
            event = events[self.next_i]
            if event.kind == "make":
                self.flash[event.team] = FLASH_REAL
            self.home_score, self.away_score = event.home_score, event.away_score
            if event.highlight:
                self.pbp = event.text
            self.next_i += 1
        if self.play_t >= self.game_end:
            self.home_score, self.away_score = self.timeline.home_final, self.timeline.away_final
            ot = " in overtime" if self.timeline.overtime else ""
            self.pbp = f"Final{ot}: {self.home_name} {self.home_score}, {self.away_name} {self.away_score}"

    def update(self, app, dt: float) -> None:
        if self.done:
            return
        if self.quick:
            self._finish(app)
            return
        speed = app.match_speed
        if speed == 0:
            self._skip_to_end()
            speed = 1
        self.play_t += dt * speed
        self.real_t += dt
        for team in self.flash:
            self.flash[team] = max(0.0, self.flash[team] - dt)
        self._apply_events()
        if self.play_t < self.game_end:
            self._update_ball()
        remaining = min(dt, 0.5)
        while remaining > 0:
            step = min(MAX_STEP, remaining)
            self._move_players(step, speed)
            remaining -= step
        if self.play_t >= self.end_t:
            self._finish(app)

    def _next_highlight(self) -> int | None:
        for i in self.highlights:
            if i not in self.resolved_highlights:
                return i
        return None

    def _player_pos(self, team: str, index: int) -> pygame.Vector2:
        return self.pos[team][index % self.players[team]]

    def _held_ball(self) -> pygame.Vector2:
        team, index = self.owner
        return self._player_pos(team, index) + pygame.Vector2(9 * self.direction[team], -9)

    def _start_pass(self, team: str, index: int) -> None:
        self.anim = {
            "kind": "pass",
            "start": self.play_t,
            "dur": PASS_REAL,
            "from": pygame.Vector2(self.ball),
            "to": (team, index % self.players[team]),
        }
        self.last_pass_t = self.play_t

    def _nearest(self, team: str, point: pygame.Vector2) -> int:
        return min(range(self.players[team]), key=lambda i: self.pos[team][i].distance_to(point))

    def _update_ball(self) -> None:
        h = self._next_highlight()
        events = self.timeline.events

        if self.anim:
            u = (self.play_t - self.anim["start"]) / self.anim["dur"]
            if u < 1.0:
                frm = self.anim["from"]
                if self.anim["kind"] == "pass":
                    to = self._player_pos(*self.anim["to"])
                    lift = 12
                else:
                    to = self.anim["target"]
                    lift = 46
                self.ball = frm.lerp(to, max(0.0, u)) + pygame.Vector2(0, -lift * math.sin(math.pi * max(0.0, u)))
                return
            if self.anim["kind"] == "pass":
                self.owner = self.anim["to"]
            else:
                shooter_team = self.anim["team"]
                other = "away" if shooter_team == "home" else "home"
                self.owner = (other, self._nearest(other, self.hoop[shooter_team]))
                self.resolved_highlights.add(self.anim["event"])
            self.anim = None

        self.ball = self._held_ball()
        if h is None:
            return
        event = events[h]
        due = self.times[h]
        team, _ = self.owner

        if event.kind == "turnover":
            if self.play_t >= due:
                thief = "away" if event.team == "home" else "home"
                self._start_pass(thief, self._nearest(thief, self.ball))
                self.resolved_highlights.add(h)
                return
        elif self.play_t >= due - SHOT_REAL:
            self.owner = (event.team, event.player)
            target = pygame.Vector2(self.hoop[event.team])
            if event.kind == "miss":
                target += pygame.Vector2(-26 * self.direction[event.team], self.rng.choice((-24, 24)))
            self.anim = {
                "kind": "shot",
                "start": self.play_t,
                "dur": max(0.05, due - self.play_t),
                "from": pygame.Vector2(self.ball),
                "target": target,
                "team": event.team,
                "event": h,
            }
            return

        if team != event.team:
            self._start_pass(event.team, self._nearest(event.team, self.ball))
            return
        if self.play_t - self.last_pass_t < PASS_EVERY or due - self.play_t < PASS_REAL + SHOT_REAL:
            return
        owner_index = self.owner[1]
        if due - self.play_t < 0.75 and owner_index != event.player % self.players[event.team]:
            receiver = event.player
        else:
            options = [i for i in range(self.players[team]) if i != owner_index] or [owner_index]
            receiver = self.rng.choice(options)
        self._start_pass(team, receiver)

    # ---- movement ------------------------------------------------------------

    def _attacking_team(self) -> str:
        h = self._next_highlight()
        if h is not None:
            return self.timeline.events[h].team
        return self.owner[0]

    def _targets(self) -> dict[str, list[pygame.Vector2]]:
        attack = self._attacking_team()
        defend = "away" if attack == "home" else "home"
        hoop = self.hoop[attack]
        d = self.direction[attack]
        h = self._next_highlight()
        shooter = None
        if h is not None:
            event = self.timeline.events[h]
            if event.kind != "turnover" and self.times[h] - self.play_t < SHOT_REAL + 0.4:
                shooter = (event.player % self.players[attack], event.points)

        offense: list[pygame.Vector2] = []
        for i in range(self.players[attack]):
            dx, dy = OFFENSE_SLOTS[i % len(OFFENSE_SLOTS)]
            wiggle = pygame.Vector2(
                math.sin(self.real_t * 1.7 + self.phase[attack][i]) * 22,
                math.cos(self.real_t * 1.3 + self.phase[attack][i]) * 18,
            )
            spot = pygame.Vector2(hoop.x - d * dx, hoop.y + dy) + wiggle
            if shooter and shooter[0] == i:
                reach = {3: 245, 2: 85, 1: 170}.get(shooter[1], 85)
                spot = pygame.Vector2(hoop.x - d * reach, hoop.y + (dy * 0.3 if shooter[1] != 1 else 0))
            offense.append(spot)

        defense: list[pygame.Vector2] = []
        for i in range(self.players[defend]):
            mark = offense[i % len(offense)]
            toward = hoop - mark
            if toward.length_squared() > 0:
                toward.scale_to_length(36)
            defense.append(mark + toward + pygame.Vector2(0, 6 if i % 2 else -6))
        return {attack: offense, defend: defense}

    def _move_players(self, dt: float, speed: float) -> None:
        targets = self._targets()
        limit = MAX_SPEED * max(1.0, speed)
        bodies: list[pygame.Vector2] = []
        for team in ("home", "away"):
            for i, pos in enumerate(self.pos[team]):
                gap = targets[team][i] - pos
                distance = gap.length()
                desired = pygame.Vector2()
                if distance > 0.5:
                    desired = gap / distance * min(limit, distance * ARRIVE_GAIN)
                vel = self.vel[team][i]
                vel += (desired - vel) * min(1.0, STEER_GAIN * dt)
                if vel.length() > limit:
                    vel.scale_to_length(limit)
                pos += vel * dt
                bodies.append(pos)
        for _ in range(2):
            for a in range(len(bodies)):
                for b in range(a + 1, len(bodies)):
                    offset = bodies[b] - bodies[a]
                    dist = offset.length()
                    if dist < MIN_GAP:
                        push = offset / dist if dist > 0.01 else pygame.Vector2(1, 0)
                        shift = push * (MIN_GAP - dist) / 2
                        bodies[a] -= shift
                        bodies[b] += shift
        for pos in bodies:
            pos.x = max(self.bounds.left, min(self.bounds.right, pos.x))
            pos.y = max(self.bounds.top, min(self.bounds.bottom, pos.y))

    # ---- drawing -------------------------------------------------------------

    def _text(self, app, text: str, font_key: str, color) -> pygame.Surface:
        key = (text, id(color), font_key)
        cached = self._text_cache.get(key)
        if cached is None:
            if len(self._text_cache) > 64:
                self._text_cache.clear()
            cached = getattr(app, font_key).render(text, True, color)
            self._text_cache[key] = cached
        return cached

    def _clock_label(self) -> str:
        if self.play_t >= self.game_end:
            return "FINAL/OT" if self.timeline.overtime else "FINAL"
        period, seconds, in_break = clock_at(self.timeline, self.play_t)
        name = f"Q{period}" if period <= 4 else "OT"
        if in_break:
            return "HALFTIME" if period == 2 else f"END {name}"
        whole = max(0, math.ceil(seconds - 1e-6))
        return f"{name}  {whole // 60}:{whole % 60:02d}"

    def draw(self, app, surf) -> None:
        surf.blit(self.court, (0, 0))
        ui.draw_scoreboard(
            surf,
            self.home_name,
            self.away_name,
            self.home_score,
            self.away_score,
            app.font_title,
            app.font_body,
            flash_home=self.flash["home"] > 0,
            flash_away=self.flash["away"] > 0,
        )
        clock_panel = pygame.Rect(535, 154, 210, 44)
        pygame.draw.rect(surf, theme.PANEL_BG, clock_panel)
        pygame.draw.rect(surf, theme.SECTION_YELLOW, clock_panel, width=2)
        clock_s = self._text(app, self._clock_label(), "font_bold", theme.TEXT_WHITE)
        surf.blit(clock_s, clock_s.get_rect(center=clock_panel.center))

        for team, color in (("home", HOME_COLOR), ("away", AWAY_COLOR)):
            for i, pos in enumerate(self.pos[team]):
                center = (int(pos.x), int(pos.y))
                pygame.draw.circle(surf, color, center, RADIUS)
                pygame.draw.circle(surf, theme.PANEL_BG, center, RADIUS, 3)
                label = self.labels[team][i]
                surf.blit(label, label.get_rect(center=center))

        ball = (int(self.ball.x), int(self.ball.y))
        pygame.draw.circle(surf, BALL_COLOR, ball, 9)
        pygame.draw.circle(surf, theme.BG_DEEP, ball, 9, 2)

        status = self._text(app, self.pbp, "font_small", theme.TEXT_WHITE)
        surf.blit(status, status.get_rect(midtop=(theme.WINDOW_WIDTH // 2, 600)))

        speed_label = f"Speed {SPEED_LABELS[app.match_speed]} [F]"
        quick_on = app.quick_sim_state is not None and app.quick_sim_state is app.state
        ui.draw_quest_button(surf, SPEED_RECT, speed_label, app.font_tiny)
        ui.draw_quest_button(surf, QUICK_RECT, f"Quick sim {'on' if quick_on else 'off'} [Q]", app.font_tiny)
        ui.draw_hint_bar(surf, self.hint, app.font_small)
