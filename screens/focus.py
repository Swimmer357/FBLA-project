"""Keyboard focus management."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FocusManager:
    widgets: list[dict] = field(default_factory=list)
    index: int = 0

    def set_widgets(self, widgets: list[dict]) -> None:
        self.widgets = widgets
        self.index = 0

    @property
    def current(self) -> dict | None:
        if not self.widgets:
            return None
        return self.widgets[self.index % len(self.widgets)]

    def move_tab(self, backward: bool = False) -> None:
        if not self.widgets:
            return
        if backward:
            self.index = (self.index - 1) % len(self.widgets)
        else:
            self.index = (self.index + 1) % len(self.widgets)

    def move_dir(self, dx: int, dy: int) -> None:
        if not self.widgets:
            return
        cur = self.current
        if cur is None:
            return
        cx, cy = cur["center"]
        best = None
        best_dist = 1e9
        for i, w in enumerate(self.widgets):
            if i == self.index:
                continue
            wx, wy = w["center"]
            if dx > 0 and wx <= cx:
                continue
            if dx < 0 and wx >= cx:
                continue
            if dy > 0 and wy <= cy:
                continue
            if dy < 0 and wy >= cy:
                continue
            dist = (wx - cx) ** 2 + (wy - cy) ** 2
            if dist < best_dist:
                best_dist = dist
                best = i
        if best is not None:
            self.index = best

    def focus_at_point(self, x: int, y: int) -> bool:
        for i, w in enumerate(self.widgets):
            if w["rect"].collidepoint(x, y):
                self.index = i
                return True
        return False
