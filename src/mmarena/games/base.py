"""Game definition: a finite hidden state, a contract on it, a reveal schedule and a market."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np

# Exact enumeration keeps every posterior exact. Families stay well under this.
MAX_OUTCOMES = 250_000


@dataclass(frozen=True)
class Market:
    """Counterparty model and trading rules. Disclosed in full to every agent.

    Each quoting step one counterparty arrives. With probability ``alpha`` it is informed: it
    sees the settlement value (plus ``informed_noise`` Gaussian noise), buys if that signal is
    above the ask and sells if it is below the bid. Otherwise it is a noise trader whose
    valuation is the public fair value plus Normal(0, ``noise_scale``) noise; it buys if the
    valuation is above the ask and sells if it is below the bid. Every fill is one unit.
    """

    alpha: float
    noise_scale: float
    informed_noise: float = 0.0
    quotes_per_stage: int = 3
    inventory_limit: int = 5
    tick: float = 0.1

    def __post_init__(self) -> None:
        if not 0.0 <= self.alpha <= 1.0:
            raise ValueError(f"alpha must be in [0, 1], got {self.alpha}")
        if self.noise_scale <= 0:
            raise ValueError(f"noise_scale must be > 0, got {self.noise_scale}")
        if self.informed_noise < 0:
            raise ValueError(f"informed_noise must be >= 0, got {self.informed_noise}")
        if self.quotes_per_stage < 1:
            raise ValueError("quotes_per_stage must be >= 1")
        if self.inventory_limit < 1:
            raise ValueError("inventory_limit must be >= 1")
        if self.tick <= 0:
            raise ValueError("tick must be > 0")

    def to_dict(self) -> dict[str, Any]:
        return {
            "alpha": self.alpha,
            "noise_scale": self.noise_scale,
            "informed_noise": self.informed_noise,
            "quotes_per_stage": self.quotes_per_stage,
            "inventory_limit": self.inventory_limit,
            "tick": self.tick,
        }


@dataclass(frozen=True, eq=False)
class Game:
    """One game instance.

    ``outcomes[i]`` are the component values of hidden state ``i`` (dice, cards, flips, a latent
    parameter), ``prob[i]`` its prior probability and ``value[i]`` the contract's settlement
    value. ``reveals[s]`` lists the components made public before stage ``s + 1``. Components
    never revealed stay hidden until settlement.
    """

    family: str
    variant: str
    title: str
    description: str
    contract: str
    components: tuple[str, ...]
    outcomes: np.ndarray
    prob: np.ndarray
    value: np.ndarray
    reveals: tuple[tuple[int, ...], ...]
    market: Market
    params: Mapping[str, Any] = field(default_factory=dict)
    seed: int | None = None

    def __post_init__(self) -> None:
        outcomes = np.asarray(self.outcomes, dtype=float)
        prob = np.asarray(self.prob, dtype=float)
        value = np.asarray(self.value, dtype=float)
        if outcomes.ndim != 2 or outcomes.shape[1] != len(self.components):
            raise ValueError("outcomes must be (n_outcomes, n_components)")
        if prob.shape != (outcomes.shape[0],) or value.shape != prob.shape:
            raise ValueError("prob and value must have one entry per outcome")
        if np.any(prob < 0) or not np.isclose(prob.sum(), 1.0, atol=1e-9):
            raise ValueError("prob must be non-negative and sum to 1")
        keep = prob > 0
        outcomes, prob, value = outcomes[keep], prob[keep] / prob[keep].sum(), value[keep]
        if len(prob) > MAX_OUTCOMES:
            raise ValueError(f"{len(prob)} outcomes exceeds MAX_OUTCOMES={MAX_OUTCOMES}")
        seen: set[int] = set()
        for group in self.reveals:
            if not group:
                raise ValueError("empty reveal group")
            for c in group:
                if not 0 <= c < len(self.components) or c in seen:
                    raise ValueError(f"bad or repeated reveal component {c}")
                seen.add(c)
        for name, arr in (("outcomes", outcomes), ("prob", prob), ("value", value)):
            arr.setflags(write=False)
            object.__setattr__(self, name, arr)
        levels, inverse = np.unique(value, return_inverse=True)
        levels.setflags(write=False)
        inverse.setflags(write=False)
        object.__setattr__(self, "levels", levels)
        object.__setattr__(self, "level_index", inverse)

    levels: np.ndarray = field(init=False, repr=False)
    level_index: np.ndarray = field(init=False, repr=False)

    @property
    def id(self) -> str:
        """Stable content id: family plus a hash of the spec, rules text, reveals and market.

        Identical games share an id (and therefore identical episode draws); suites skip them.
        """
        payload = json.dumps(
            {
                "params": _jsonable(self.params),
                "market": self.market.to_dict(),
                "reveals": [list(g) for g in self.reveals],
                "description": self.description,
                "contract": self.contract,
            },
            sort_keys=True,
        )
        return f"{self.family}-{hashlib.sha256(payload.encode()).hexdigest()[:8]}"

    @property
    def n_stages(self) -> int:
        return len(self.reveals) + 1

    @property
    def n_steps(self) -> int:
        return self.n_stages * self.market.quotes_per_stage

    @property
    def prior_mean(self) -> float:
        return float(self.prob @ self.value)

    @property
    def prior_std(self) -> float:
        return float(np.sqrt(max(self.prob @ (self.value - self.prior_mean) ** 2, 0.0)))

    @property
    def v_min(self) -> float:
        return float(self.levels[0])

    @property
    def v_max(self) -> float:
        return float(self.levels[-1])

    def stage_of(self, step: int) -> int:
        return step // self.market.quotes_per_stage

    def to_dict(self) -> dict[str, Any]:
        """Spec without the outcome table (which is regenerated from family, variant and seed)."""
        return {
            "id": self.id,
            "family": self.family,
            "variant": self.variant,
            "seed": self.seed,
            "title": self.title,
            "description": self.description,
            "contract": self.contract,
            "components": list(self.components),
            "reveals": [list(g) for g in self.reveals],
            "market": self.market.to_dict(),
            "params": _jsonable(self.params),
            "n_outcomes": int(len(self.prob)),
            "prior_mean": self.prior_mean,
            "prior_std": self.prior_std,
            "v_min": self.v_min,
            "v_max": self.v_max,
        }


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, Mapping):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj
