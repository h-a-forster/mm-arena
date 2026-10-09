"""Shared fixtures and helpers for the simulator tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pytest

from mmarena.agents.base import Observation, Quote
from mmarena.games import Game, Market, make_game

FAMILY_NAMES = ("dice", "cards", "transform", "coin", "urn")
SEEDS = tuple(range(30))


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--runslow", action="store_true", help="also run tests marked slow")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "slow: long-running statistical test (run with --runslow)")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--runslow"):
        return
    skip = pytest.mark.skip(reason="slow; use --runslow")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)


class ScriptedAgent:
    """Agent whose quote is a function of the observation. Records every observation."""

    def __init__(self, fn: Callable[[Observation], Any], name: str = "scripted") -> None:
        self.fn = fn
        self.name = name
        self.seen: list[Observation] = []

    def reset(self, game: Game) -> None:
        self.seen = []

    def act(self, obs: Observation) -> Quote:
        self.seen.append(obs)
        out = self.fn(obs)
        if isinstance(out, BaseException):
            raise out
        if isinstance(out, Quote):
            return out
        bid, ask = out
        return Quote(bid, ask)


def tiny_game(
    values: tuple[float, ...] = (0.0, 5.0, 10.0),
    prob: tuple[float, ...] = (0.2, 0.3, 0.5),
    market: Market | None = None,
) -> Game:
    """One-component game: the hidden state is the settlement value itself."""
    v = np.asarray(values, dtype=float)
    return Game(
        family="tiny",
        variant="test",
        title="Tiny",
        description="A test game.",
        contract="Settles at the hidden value.",
        components=("x",),
        outcomes=v[:, None],
        prob=np.asarray(prob, dtype=float),
        value=v,
        reveals=(),
        market=market or Market(alpha=0.4, noise_scale=3.0, quotes_per_stage=3),
        params={"values": list(values), "prob": list(prob)},
        seed=0,
    )


@pytest.fixture
def coin_game() -> Game:
    """Classic coin game (65 outcomes, 3 stages) with a fixed, fast market."""
    return make_game(
        "coin",
        0,
        "classic",
        market=Market(alpha=0.35, noise_scale=1.5, quotes_per_stage=2, inventory_limit=3, tick=0.1),
    )


@pytest.fixture
def scripted() -> type[ScriptedAgent]:
    return ScriptedAgent
