"""Agent interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from mmarena.games.base import Game


class AgentError(Exception):
    """The agent produced an unusable quote (bad format, refusal). Scored as an invalid quote."""


class InfraError(Exception):
    """Provider or account failure (auth, rate limit, outage). Excludes the episode from scoring."""


@dataclass(frozen=True)
class Observation:
    """Everything a market maker is allowed to know at one quoting step."""

    game: Game
    step: int
    stage: int
    revealed: tuple[dict[str, Any], ...]
    history: tuple[dict[str, Any], ...]
    position: int
    cash: float
    bid_allowed: bool
    ask_allowed: bool
    episode_seed: int = 0

    @property
    def steps_left(self) -> int:
        return self.game.n_steps - self.step


@dataclass
class Quote:
    """A two-sided quote. ``None`` on a side means no quote on that side."""

    bid: float | None
    ask: float | None
    info: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Agent(Protocol):
    name: str

    def reset(self, game: Game) -> None: ...

    def act(self, obs: Observation) -> Quote: ...
