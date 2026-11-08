"""Focused coverage for the browser-compatible game loop."""
from __future__ import annotations

import asyncio
import inspect

import pygame

import screens.manager as manager
from screens.manager import GameApp


def test_run_is_coroutine_and_yields_once_after_each_render(monkeypatch):
    calls: list[object] = []
    app = GameApp.__new__(GameApp)
    app.running = True
    app.clock = type("Clock", (), {"tick": lambda self, fps: calls.append(("tick", fps)) or 16})()

    class OneFrameScreen:
        def update(self, current_app, dt):
            calls.append(("update", dt))
            current_app.running = False

    app.stack = [OneFrameScreen()]
    app.draw_frame = lambda: calls.append("draw")

    monkeypatch.setattr(pygame.event, "get", lambda: [])
    monkeypatch.setattr(pygame.display, "flip", lambda: calls.append("display"))
    monkeypatch.setattr(pygame, "quit", lambda: calls.append("quit"))

    async def fake_sleep(delay):
        calls.append(("sleep", delay))

    monkeypatch.setattr(manager.asyncio, "sleep", fake_sleep)

    assert inspect.iscoroutinefunction(GameApp.run)
    asyncio.run(app.run())

    assert calls == [
        ("tick", 60),
        ("update", 0.016),
        "draw",
        "display",
        ("sleep", 0),
        "quit",
    ]
