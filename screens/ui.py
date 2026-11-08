"""Shared pygame drawing — readable layout, no overlapping regions."""
from __future__ import annotations

import pygame

import theme


def draw_background(surf: pygame.Surface) -> None:
    """Flat main canvas. Decorative glows and shadows are intentionally absent."""
    surf.fill(theme.BG_DEEP)


def draw_gradient_rect(surf: pygame.Surface, rect: pygame.Rect) -> None:
    """Blue → magenta-purple → violet, drawn as one-pixel vertical lines."""
    stops = (theme.ACCENT_BLUE, theme.ACCENT_PINK, theme.ACCENT_PURPLE)
    for x in range(rect.width):
        t = x / max(1, rect.width - 1) * 2
        left = stops[min(1, int(t))]
        right = stops[min(2, int(t) + 1)]
        local = t - int(t)
        color = tuple(int(a * (1 - local) + b * local) for a, b in zip(left, right))
        pygame.draw.line(surf, color, (rect.x + x, rect.y), (rect.x + x, rect.bottom - 1))


_gradient_rect = draw_gradient_rect


def draw_text_centered(
    surf: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    center: tuple[int, int],
    color: tuple[int, int, int] = theme.TEXT_WHITE,
    *,
    uppercase: bool = False,
) -> pygame.Rect:
    rendered = font.render(text.upper() if uppercase else text, True, color)
    rect = rendered.get_rect(center=center)
    surf.blit(rendered, rect)
    return rect


def _fit_label(font: pygame.font.Font, text: str, max_w: int) -> str:
    if font.size(text)[0] <= max_w:
        return text
    while len(text) > 3 and font.size(text + "…")[0] > max_w:
        text = text[:-1]
    return text + "…"


def _wrap_label(font: pygame.font.Font, text: str, max_w: int, max_lines: int = 2) -> list[str]:
    """Wrap a control label without silently truncating its action name."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if not current or font.size(candidate)[0] <= max_w:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:max_lines]


def measure_screen_header(
    *,
    height: int,
    font_title: pygame.font.Font,
    font_body: pygame.font.Font,
    font_bold: pygame.font.Font,
    objective: str,
    detail_heading: str = "",
    detail_lines: tuple[str, ...] = (),
) -> int:
    y = theme.HEADER_TOP + font_title.get_linesize() + 10
    y += font_bold.get_linesize() + 8
    if objective:
        y += font_body.get_linesize() + 8
    if detail_heading:
        y += font_body.get_linesize() + 4
    y += len(detail_lines) * (font_body.get_linesize() + 1)
    return max(round(height * .29), y + 10)


def draw_icon_button(surf: pygame.Surface, rect: pygame.Rect, glyph: str, font: pygame.font.Font, focused: bool) -> None:
    pygame.draw.rect(surf, theme.PANEL_BG, rect)
    pygame.draw.rect(surf, theme.TEXT_WHITE, rect, width=2)
    if focused:
        pygame.draw.rect(surf, theme.TITLE_CYAN, rect.inflate(6, 6), width=2)
    draw_text_centered(surf, glyph, font, rect.center)


def draw_screen_header(
    surf: pygame.Surface,
    *,
    title: str,
    stats_line: str,
    objective: str,
    font_title: pygame.font.Font,
    font_body: pygame.font.Font,
    font_small: pygame.font.Font,
    font_bold: pygame.font.Font | None = None,
    detail_heading: str = "",
    detail_lines: tuple[str, ...] = (),
) -> int:
    """Draw the normalized header band; return the content divider position."""
    bold = font_bold or font_body
    width, height = surf.get_size()
    cx = width // 2
    header_h = measure_screen_header(
        height=height,
        font_title=font_title,
        font_body=font_body,
        font_bold=bold,
        objective=objective,
        detail_heading=detail_heading,
        detail_lines=detail_lines,
    )
    pygame.draw.rect(surf, theme.HEADER_BG, (0, 0, width, header_h))
    pygame.draw.rect(surf, theme.ACCENT_BLUE, (0, header_h - 4, width, 4))
    y = theme.HEADER_TOP
    title_s = font_title.render(_fit_label(font_title, title.upper(), width - 360), True, theme.TITLE_CYAN)
    surf.blit(title_s, title_s.get_rect(midtop=(cx, y)))
    y += title_s.get_height() + 14
    stats_s = bold.render(_fit_label(bold, stats_line, width - 250), True, theme.TEXT_DIM)
    surf.blit(stats_s, stats_s.get_rect(midtop=(cx, y)))
    y += stats_s.get_height() + 10
    if objective:
        obj_s = font_body.render(objective, True, theme.OBJECTIVE_GREEN)
        surf.blit(obj_s, obj_s.get_rect(midtop=(cx, y)))
        y += obj_s.get_height() + 8
    if detail_heading:
        detail_s = font_body.render(detail_heading.upper(), True, theme.SECTION_YELLOW)
        surf.blit(detail_s, detail_s.get_rect(midtop=(cx, y)))
        y += detail_s.get_height() + 4
    for line in detail_lines:
        line_s = font_body.render(line, True, theme.TEXT_DIM)
        surf.blit(line_s, line_s.get_rect(midtop=(cx, y)))
        y += line_s.get_height() + 1
    return header_h - 4


def grid_button_rects(
    count: int,
    *,
    x: int,
    y: int,
    width: int,
    cols: int = theme.COLS,
    btn_h: int = theme.BUTTON_H,
    gap: int = theme.BUTTON_GAP,
    featured_full_width_index: int | None = None,
) -> list[pygame.Rect]:
    rects: list[pygame.Rect] = []
    col_w = (width - gap * (cols - 1)) // cols
    row = 0
    col = 0
    for i in range(count):
        if featured_full_width_index is not None and i == featured_full_width_index:
            fy = y + row * (btn_h + gap)
            rects.append(pygame.Rect(x, fy, width, theme.BUTTON_H_FEATURED))
            row += 1
            continue
        bx = x + col * (col_w + gap)
        by = y + row * (btn_h + gap)
        rects.append(pygame.Rect(bx, by, col_w, btn_h))
        col += 1
        if col >= cols:
            col = 0
            row += 1
    return rects


def draw_quest_button(
    surf: pygame.Surface,
    rect: pygame.Rect,
    text: str,
    font: pygame.font.Font,
    *,
    focused: bool = False,
    enabled: bool = True,
    variant: str = "default",
) -> None:
    labels = _wrap_label(font, text.upper(), rect.width - 20)
    if variant == "gradient" and enabled:
        draw_gradient_rect(surf, rect)
        pygame.draw.rect(surf, theme.ACCENT_BLUE, rect, width=4)
        color = theme.TEXT_WHITE
    elif variant in ("green", "confirm") and enabled:
        pygame.draw.rect(surf, theme.BUTTON_GREEN_EDGE, rect)
        face = rect.copy()
        face.height = max(1, face.height - 4)
        pygame.draw.rect(surf, theme.BUTTON_GREEN, face)
        color = theme.BG_DEEP
    elif variant == "danger":
        fill = theme.BTN_DANGER if enabled else theme.PANEL_BG
        pygame.draw.rect(surf, fill, rect)
        pygame.draw.rect(surf, theme.BTN_DANGER, rect, width=4)
        color = theme.TEXT_WHITE if enabled else theme.TEXT_DIM
    else:
        fill = theme.PANEL_BG if enabled else theme.HEADER_BG
        pygame.draw.rect(surf, fill, rect)
        border = theme.TITLE_CYAN if focused and enabled else theme.BORDER_BLUE
        pygame.draw.rect(surf, border, rect, width=4)
        color = theme.TEXT_WHITE if enabled else theme.TEXT_DIM
    line_h = font.get_linesize()
    first_y = rect.centery - ((len(labels) - 1) * line_h) // 2
    for index, label in enumerate(labels):
        draw_text_centered(surf, label, font, (rect.centerx, first_y + index * line_h), color)
    if focused and enabled:
        pygame.draw.rect(surf, theme.TEXT_WHITE, rect.inflate(8, 8), width=2)


def draw_tile(
    surf: pygame.Surface,
    rect: pygame.Rect,
    text: str,
    font: pygame.font.Font,
    *,
    focused: bool = False,
    enabled: bool = True,
    featured: bool = False,
) -> None:
    draw_quest_button(
        surf, rect, text, font, focused=focused, enabled=enabled,
        variant="gradient" if featured else "default",
    )


def draw_button(
    surf: pygame.Surface,
    rect: pygame.Rect,
    text: str,
    font: pygame.font.Font,
    *,
    focused: bool = False,
    enabled: bool = True,
    disabled_reason: str | None = None,
    variant: str = "default",
) -> None:
    draw_quest_button(surf, rect, text, font, focused=focused, enabled=enabled, variant=variant)
    del disabled_reason


def draw_panel(
    surf: pygame.Surface,
    rect: pygame.Rect,
    *,
    dark: bool = True,
    font: pygame.font.Font,
    title: str | None = None,
    font_bold: pygame.font.Font | None = None,
) -> None:
    pygame.draw.rect(surf, theme.PANEL_BG, rect)
    pygame.draw.rect(surf, theme.BORDER_BLUE, rect, width=4)
    if title:
        bf = font_bold or font
        label = bf.render(title.upper(), True, theme.SECTION_YELLOW)
        surf.blit(label, (rect.x + 16, rect.y + 12))


def draw_stat_badge(
    surf: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    value: str,
    font_label: pygame.font.Font,
    font_value: pygame.font.Font,
    *,
    accent: tuple[int, int, int] = theme.TITLE_CYAN,
) -> None:
    """Compact shared HUD badge used by the hub and match screens."""
    pygame.draw.rect(surf, theme.BG_DEEP, rect)
    pygame.draw.rect(surf, accent, rect, width=4)
    surf.blit(font_label.render(label.upper(), True, theme.TEXT_DIM), (rect.x + 12, rect.y + 8))
    value_s = font_value.render(value, True, accent)
    surf.blit(value_s, (rect.x + 12, rect.bottom - value_s.get_height() - 8))


def draw_objective_banner(
    surf: pygame.Surface,
    rect: pygame.Rect,
    text: str,
    font: pygame.font.Font,
) -> None:
    pygame.draw.rect(surf, theme.BG_DEEP, rect)
    pygame.draw.rect(surf, theme.OBJECTIVE_GREEN, rect, width=4)
    tag = font.render("OBJECTIVE", True, theme.OBJECTIVE_GREEN)
    surf.blit(tag, (rect.x + 12, rect.y + 8))
    lines = wrap_text(font, text, rect.width - tag.get_width() - 42)
    if lines:
        surf.blit(lines[0], (rect.x + tag.get_width() + 26, rect.y + 8))


def draw_status_strip(surf: pygame.Surface, text: str, font: pygame.font.Font) -> None:
    if not text:
        return
    rect = pygame.Rect(theme.MARGIN_X, theme.FOOTER_Y - 40, theme.CONTENT_W, 32)
    msg = font.render(text, True, theme.TEXT_WHITE)
    surf.blit(msg, msg.get_rect(midleft=(rect.x + 8, rect.centery)))


def draw_bar(
    surf: pygame.Surface,
    rect: pygame.Rect,
    value: int,
    maximum: int,
    label: str,
    font: pygame.font.Font,
    *,
    fill_color: tuple[int, int, int] = theme.ACCENT_BLUE,
) -> None:
    pygame.draw.rect(surf, theme.HEADER_BG, rect)
    inner = rect.copy()
    inner.width = max(4, int(rect.width * (value / max(1, maximum))))
    pygame.draw.rect(surf, fill_color, inner)
    text = font.render(f"{label} {value}", True, theme.TEXT_WHITE)
    surf.blit(text, (rect.right + 8, rect.centery - text.get_height() // 2))


def draw_change_indicator(
    surf: pygame.Surface,
    pos: tuple[int, int],
    delta: int,
    font: pygame.font.Font,
) -> None:
    positive = delta >= 0
    color = theme.GOOD_GREEN if positive else theme.BAD_RED
    points = (
        [(pos[0], pos[1] - 8), (pos[0] - 8, pos[1] + 6), (pos[0] + 8, pos[1] + 6)]
        if positive
        else [(pos[0], pos[1] + 8), (pos[0] - 8, pos[1] - 6), (pos[0] + 8, pos[1] - 6)]
    )
    pygame.draw.polygon(surf, color, points)
    sign = "+" if positive else "−"
    surf.blit(font.render(f"{sign}{abs(delta)}", True, color), (pos[0] + 12, pos[1] - 10))


def draw_court(surf: pygame.Surface, alpha: int = 40) -> None:
    """Draw an original, scalable top-down basketball court."""
    draw_background(surf)
    layer = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    court = pygame.Rect(78, 112, theme.WINDOW_WIDTH - 156, 480)
    wood = (191, 126, 62, max(80, min(255, alpha + 95)))
    line = (255, 241, 210, max(120, min(255, alpha + 150)))
    pygame.draw.rect(layer, wood, court)
    for x in range(court.x, court.right, 56):
        pygame.draw.line(layer, (134, 82, 42, 80), (x, court.y), (x, court.bottom), 2)
    pygame.draw.rect(layer, line, court, width=4)
    pygame.draw.line(layer, line, (court.centerx, court.y), (court.centerx, court.bottom), 4)
    pygame.draw.circle(layer, line, court.center, 68, 4)
    lane_w, lane_h = 190, 220
    left_lane = pygame.Rect(court.x, court.centery - lane_h // 2, lane_w, lane_h)
    right_lane = pygame.Rect(court.right - lane_w, court.centery - lane_h // 2, lane_w, lane_h)
    pygame.draw.rect(layer, line, left_lane, width=4)
    pygame.draw.rect(layer, line, right_lane, width=4)
    pygame.draw.arc(layer, line, pygame.Rect(court.x + 82, court.centery - 150, 210, 300), -1.15, 1.15, 4)
    pygame.draw.arc(layer, line, pygame.Rect(court.right - 292, court.centery - 150, 210, 300), 2.0, 4.28, 4)
    for x, direction in ((court.x + 48, 1), (court.right - 48, -1)):
        pygame.draw.line(layer, line, (x, court.centery - 46), (x, court.centery + 46), 5)
        pygame.draw.circle(layer, (230, 84, 45, 255), (x + 16 * direction, court.centery), 9, 3)
    surf.blit(layer, (0, 0))


def wrap_text(font: pygame.font.Font, text: str, width: int) -> list[pygame.Surface]:
    words = text.split()
    lines: list[pygame.Surface] = []
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


def draw_hint_bar(surf: pygame.Surface, text: str, font: pygame.font.Font) -> None:
    rect = pygame.Rect(0, theme.WINDOW_HEIGHT - theme.HINT_H, theme.WINDOW_WIDTH, theme.HINT_H)
    pygame.draw.rect(surf, theme.PANEL_BG, rect)
    pygame.draw.rect(surf, theme.ACCENT_BLUE, (0, rect.y, theme.WINDOW_WIDTH, 4))
    label = font.render("DIRECTIONS", True, theme.SECTION_YELLOW)
    label_y = rect.centery - label.get_height() // 2
    surf.blit(label, (theme.MARGIN_X, label_y))
    divider_x = theme.MARGIN_X + label.get_width() + 14
    pygame.draw.line(surf, theme.BORDER_BLUE, (divider_x, rect.y + 9), (divider_x, rect.bottom - 9), 2)
    directions = font.render(text, True, theme.TEXT_WHITE)
    surf.blit(directions, (divider_x + 14, rect.centery - directions.get_height() // 2))


def draw_scoreboard(
    surf: pygame.Surface,
    home: str,
    away: str,
    home_score: int,
    away_score: int,
    font_big: pygame.font.Font,
    font_small: pygame.font.Font,
) -> None:
    panel = pygame.Rect(300, 28, 680, 118)
    draw_panel(surf, panel, font=font_small)
    home_name = font_small.render(_fit_label(font_small, home.upper(), 215), True, theme.TEXT_WHITE)
    away_name = font_small.render(_fit_label(font_small, away.upper(), 215), True, theme.TEXT_WHITE)
    hs = font_big.render(str(home_score), True, theme.TITLE_CYAN)
    as_ = font_big.render(str(away_score), True, theme.SECTION_YELLOW)
    surf.blit(home_name, home_name.get_rect(midtop=(panel.x + 150, panel.y + 10)))
    surf.blit(away_name, away_name.get_rect(midtop=(panel.right - 150, panel.y + 10)))
    surf.blit(hs, hs.get_rect(center=(panel.x + 150, panel.y + 75)))
    surf.blit(as_, as_.get_rect(center=(panel.right - 150, panel.y + 75)))
    center = font_small.render("GAME DAY", True, theme.TEXT_DIM)
    surf.blit(center, center.get_rect(center=(panel.centerx, panel.y + 52)))
    pygame.draw.circle(surf, (221, 104, 48), (panel.centerx, panel.y + 84), 14)
    pygame.draw.arc(surf, theme.BG_DEEP, (panel.centerx - 14, panel.y + 70, 28, 28), 0, 3.14, 2)
