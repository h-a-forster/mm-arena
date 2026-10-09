"""Deterministic fake provider for tests and offline demos."""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from typing import Any

from mmarena.providers.base import Completion, UserInput, join_user

Script = str | Sequence[str] | Callable[[str, str], str]


class ScriptedProvider:
    """Returns canned text.

    ``script`` is one string (returned every call), a sequence (returned in order, the last
    entry repeating), or a callable ``(system, user) -> text``.
    """

    name = "scripted"

    def __init__(self, script: Script, model: str = "scripted"):
        self.script = script
        self.model = model
        label = script if isinstance(script, str) else type(script).__name__
        self.options: dict[str, Any] = {"script": label}
        self.calls: list[tuple[str, str]] = []
        self._lock = threading.Lock()

    def complete(self, system: str, user: UserInput, *, max_tokens: int) -> Completion:
        text_in = join_user(user)
        with self._lock:
            i = len(self.calls)
            self.calls.append((system, text_in))
        if callable(self.script):
            text = self.script(system, text_in)
        elif isinstance(self.script, str):
            text = self.script
        else:
            text = self.script[min(i, len(self.script) - 1)]
        return Completion(
            text=text,
            usage={"input_tokens": len(system + text_in) // 4, "output_tokens": len(text) // 4},
            cost_usd=0.0,
            model=self.model,
        )
