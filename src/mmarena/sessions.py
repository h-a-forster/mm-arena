"""Sessions: one game played for several rounds against a crowd whose informed share is hidden.

A session takes one perturbed core-v1 game, keeps its first reveal group, sets the disclosed
noise scale to ``noise_ratio`` times the game's prior standard deviation (rounded to two
significant figures) and plays it for ``rounds`` rounds. Each round draws a fresh hidden
outcome; the market maker quotes, part of the outcome is revealed, it quotes again, and the
contract settles with the settlement value made public. The informed share ``alpha`` is one of
the disclosed ``Regimes``; the suite fixes which one per session (balanced within each tier and
family) and it never changes within a session.

``SessionSpec`` is everything the market maker is told. It has no field for the true regime or
any outcome, so nothing rendered from it can leak them. ``Session`` adds the truth and the
suite bookkeeping.

Suite format 2 is a TOML file::

    format = 2
    name = "core-v2"
    description = "..."
    prompt = "v2.0"
    rounds = 6
    quotes_per_stage = 2
    reveal_groups = 1
    alpha = [0.05, 0.5, 0.9]
    alpha_prior = [1, 1, 1]
    salt = ""                 # optional; a held-out suite sets a secret one

    [tiers]
    open = 1.0                # noise ratio: noise scale / prior sd of the value

    [[block]]
    family = "dice"
    tier = "open"
    seed = 30000              # games use consecutive seeds from here
    regimes = [2, 0, 1]       # true regime index of each game, in order

``episodes`` (default 1) is the number of sessions per game (session seeds 0, 1, ...).
"""

from __future__ import annotations

import hashlib
import json
import zlib
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import numpy as np

from mmarena.games import FAMILIES, Game, Market, make_game
from mmarena.games.families import _nice
from mmarena.joint import Regimes

SUITE_FORMAT = 2
PROMPT_VERSIONS = ("v2.0",)
TIER_ORDER = ("open", "mixed", "tight")


@dataclass(frozen=True, eq=False)
class SessionSpec:
    """The public description of a session: game, disclosed regime grid, number of rounds."""

    game: Game
    regimes: Regimes
    rounds: int

    def __post_init__(self) -> None:
        if self.rounds < 1:
            raise ValueError("rounds must be >= 1")
        if self.game.market.informed_noise != 0:
            raise ValueError("sessions need informed_noise = 0")

    @property
    def steps_per_round(self) -> int:
        return self.game.n_steps

    @property
    def n_quotes(self) -> int:
        return self.rounds * self.steps_per_round

    def to_dict(self) -> dict[str, Any]:
        return {
            "game": self.game.to_dict(),
            "regimes": self.regimes.to_dict(),
            "rounds": self.rounds,
        }


@dataclass(frozen=True, eq=False)
class Session:
    """A session with its hidden truth (the regime) and suite bookkeeping."""

    spec: SessionSpec
    regime: int
    tier: str
    noise_ratio: float
    game_seed: int
    salt: str = ""

    def __post_init__(self) -> None:
        if not 0 <= self.regime < self.spec.regimes.k:
            raise ValueError(f"regime index {self.regime} out of range")

    @property
    def game(self) -> Game:
        return self.spec.game

    @property
    def alpha(self) -> float:
        return float(self.spec.regimes.alpha[self.regime])

    @property
    def id(self) -> str:
        """Stable id from the public spec and the salt; it does not depend on the regime."""
        payload = json.dumps(
            {
                "game": self.game.id,
                "regimes": self.spec.regimes.to_dict(),
                "rounds": self.spec.rounds,
                "salt": self.salt,
            },
            sort_keys=True,
        )
        return f"{self.game.family}-s{hashlib.sha256(payload.encode()).hexdigest()[:8]}"

    def to_dict(self) -> dict[str, Any]:
        """Everything needed to rebuild the session (``session_from_dict``), truth included."""
        return {
            "id": self.id,
            "family": self.game.family,
            "game_seed": self.game_seed,
            "tier": self.tier,
            "noise_ratio": self.noise_ratio,
            "quotes_per_stage": self.game.market.quotes_per_stage,
            "reveal_groups": len(self.game.reveals),
            "salt": self.salt,
            "regime": self.regime,
            "alpha": self.alpha,
            **self.spec.to_dict(),
        }


@dataclass(frozen=True)
class SessionObservation:
    """Everything the market maker may know at one quote of a session.

    ``revealed`` holds this round's reveals; ``history`` every quote of the session so far
    (``round``, ``step``, ``stage``, ``bid``, ``ask``, ``action``, ``price``); ``settled`` each
    finished round's reveals and settlement value. ``position`` and ``cash`` are for the
    current round (both start at zero each round).
    """

    spec: SessionSpec
    session_id: str
    round: int
    step: int
    stage: int
    revealed: tuple[dict[str, Any], ...]
    history: tuple[dict[str, Any], ...]
    settled: tuple[dict[str, Any], ...]
    position: int
    cash: float
    bid_allowed: bool
    ask_allowed: bool
    episode_seed: int = 0

    @property
    def game(self) -> Game:
        return self.spec.game

    @property
    def quote(self) -> int:
        """Index of this quote in the session."""
        return self.round * self.spec.steps_per_round + self.step

    @property
    def quotes_left(self) -> int:
        """Quotes left in the session, this one included."""
        return self.spec.n_quotes - self.quote

    @property
    def steps_left(self) -> int:
        """Quotes left in this round, this one included."""
        return self.spec.steps_per_round - self.step


def session_game(
    family: str,
    seed: int,
    noise_ratio: float,
    regimes: Regimes,
    quotes_per_stage: int = 2,
    reveal_groups: int = 1,
) -> Game:
    """The session's game: a perturbed core-v1 game with the session's market rules.

    The noise scale is ``noise_ratio`` x prior sd, rounded to two significant figures as in
    core-v1. Inventory limit and tick are core-v1's draw for the game. ``market.alpha`` holds
    the prior mean of the informed share (the chance that the first counterparty is informed);
    scoring uses the regimes, never this field.
    """
    base = make_game(family, seed, "perturbed")
    market = Market(
        alpha=regimes.mean_alpha,
        noise_scale=_nice(noise_ratio * base.prior_std),
        informed_noise=0.0,
        quotes_per_stage=quotes_per_stage,
        inventory_limit=base.market.inventory_limit,
        tick=base.market.tick,
    )
    return replace(base, reveals=base.reveals[:reveal_groups], market=market)


def make_session(
    family: str,
    seed: int,
    noise_ratio: float,
    regimes: Regimes,
    regime: int,
    rounds: int,
    tier: str = "",
    quotes_per_stage: int = 2,
    reveal_groups: int = 1,
    salt: str = "",
) -> Session:
    game = session_game(family, seed, noise_ratio, regimes, quotes_per_stage, reveal_groups)
    return Session(SessionSpec(game, regimes, rounds), regime, tier, noise_ratio, seed, salt)


def session_from_dict(d: Mapping[str, Any]) -> Session:
    """Rebuild a session from ``Session.to_dict`` (as stored in a trace); checks the id."""
    regimes = Regimes.of(d["regimes"]["alpha"], d["regimes"]["prior"])
    s = make_session(
        d["family"],
        int(d["game_seed"]),
        float(d["noise_ratio"]),
        regimes,
        int(d["regime"]),
        int(d["rounds"]),
        str(d.get("tier", "")),
        int(d["quotes_per_stage"]),
        int(d["reveal_groups"]),
        str(d.get("salt", "")),
    )
    if "id" in d and s.id != d["id"]:
        raise ValueError(f"rebuilt session id {s.id} does not match {d['id']}")
    return s


def balanced_regimes(n: int, k: int, seed: Sequence[int] | int) -> list[int]:
    """``n`` regime indices, each of the ``k`` regimes equally often, in a seeded random order."""
    if n % k:
        raise ValueError(f"{n} sessions cannot hold {k} regimes equally often")
    rng = np.random.default_rng(seed)
    return [int(x) for x in rng.permutation(np.repeat(np.arange(k), n // k))]


@dataclass(frozen=True)
class SessionBlock:
    family: str
    tier: str
    seed: int
    regimes: tuple[int, ...]

    @property
    def games(self) -> int:
        return len(self.regimes)


@dataclass(frozen=True)
class SessionSuite:
    """A format-2 suite: blocks of sessions, each block one family in one tier."""

    name: str
    description: str
    prompt: str
    rounds: int
    quotes_per_stage: int
    reveal_groups: int
    regimes: Regimes
    tiers: Mapping[str, float]
    blocks: tuple[SessionBlock, ...]
    episodes: int = 1
    salt: str = ""
    format: int = field(default=SUITE_FORMAT)

    def sessions(self) -> Iterator[Session]:
        """Each block's games from consecutive seeds; seeds that repeat a game are skipped."""
        seen: set[str] = set()
        for b in self.blocks:
            seed, made = b.seed, 0
            while made < b.games:
                if seed - b.seed > 100 * b.games:
                    raise ValueError(f"cannot find {b.games} distinct {b.family} games")
                s = make_session(
                    b.family,
                    seed,
                    self.tiers[b.tier],
                    self.regimes,
                    b.regimes[made],
                    self.rounds,
                    b.tier,
                    self.quotes_per_stage,
                    self.reveal_groups,
                    self.salt,
                )
                seed += 1
                if s.game.id in seen:
                    continue
                seen.add(s.game.id)
                made += 1
                yield s

    def episodes_list(self) -> list[tuple[Session, int]]:
        return [(s, e) for s in self.sessions() for e in range(self.episodes)]

    def games(self) -> Iterator[Game]:
        for s in self.sessions():
            yield s.game


def suite_from_data(data: Mapping[str, Any], path: Path) -> SessionSuite:
    """Build a format-2 suite from parsed TOML; every field is validated first."""
    if int(data.get("format", 0)) != SUITE_FORMAT:
        raise ValueError(f"{path}: not a format-{SUITE_FORMAT} suite")
    prompt = str(data.get("prompt", ""))
    if prompt not in PROMPT_VERSIONS:
        raise ValueError(f"{path}: unknown prompt version {prompt!r}; known: {PROMPT_VERSIONS}")
    regimes = Regimes.of(data["alpha"], data.get("alpha_prior"))
    tiers = {str(k): float(v) for k, v in dict(data.get("tiers", {})).items()}
    if not tiers or any(not v > 0 for v in tiers.values()):
        raise ValueError(f"{path}: [tiers] must map tier names to positive noise ratios")
    blocks = []
    for raw in data.get("block", []):
        if extra := set(raw) - {"family", "tier", "seed", "regimes"}:
            raise ValueError(f"{path}: unknown block key(s) {sorted(extra)}")
        fam, tier = raw["family"], raw["tier"]
        if fam not in FAMILIES:
            raise ValueError(f"{path}: unknown family {fam!r}")
        if tier not in tiers:
            raise ValueError(f"{path}: block tier {tier!r} is not in [tiers]")
        regs = tuple(int(r) for r in raw["regimes"])
        if not regs or any(not 0 <= r < regimes.k for r in regs):
            raise ValueError(f"{path}: block regimes must be indices 0..{regimes.k - 1}")
        blocks.append(SessionBlock(fam, tier, int(raw["seed"]), regs))
    if not blocks:
        raise ValueError(f"{path}: no [[block]] entries")
    known = {
        "format",
        "name",
        "description",
        "prompt",
        "rounds",
        "quotes_per_stage",
        "reveal_groups",
        "alpha",
        "alpha_prior",
        "tiers",
        "block",
        "episodes",
        "salt",
    }
    if unknown := set(data) - known:
        raise ValueError(f"{path}: unknown key(s) {sorted(unknown)}")
    return SessionSuite(
        name=str(data.get("name", path.stem)),
        description=str(data.get("description", "")),
        prompt=prompt,
        rounds=int(data["rounds"]),
        quotes_per_stage=int(data.get("quotes_per_stage", 2)),
        reveal_groups=int(data.get("reveal_groups", 1)),
        regimes=regimes,
        tiers=tiers,
        blocks=tuple(blocks),
        episodes=int(data.get("episodes", 1)),
        salt=str(data.get("salt", "")),
    )


def suite_hash(path: str | Path) -> str:
    """SHA-256 of a suite file's parsed content (canonical JSON).

    Independent of formatting, comments and line endings; any change to a value, the salt
    included, changes it.
    """
    import tomllib

    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    canon = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def render_suite_toml(
    name: str,
    description: str,
    tiers: Mapping[str, float],
    blocks: Sequence[SessionBlock],
    rounds: int = 6,
    alpha: Sequence[float] = (0.05, 0.5, 0.9),
    salt: str = "",
    prompt: str = "v2.0",
) -> str:
    """TOML text of a format-2 suite (two quotes per stage, first reveal group, flat prior)."""
    lines = [
        f"format = {SUITE_FORMAT}",
        f"name = {json.dumps(name)}",
        f"description = {json.dumps(description)}",
        f"prompt = {json.dumps(prompt)}",
        f"rounds = {rounds}",
        "quotes_per_stage = 2",
        "reveal_groups = 1",
        f"alpha = [{', '.join(f'{a:g}' for a in alpha)}]",
        f"alpha_prior = [{', '.join('1' for _ in alpha)}]",
    ]
    if salt:
        lines.append(f"salt = {json.dumps(salt)}")
    lines += ["", "[tiers]", *(f"{t} = {r:g}" for t, r in tiers.items())]
    for b in blocks:
        lines += [
            "",
            "[[block]]",
            f"family = {json.dumps(b.family)}",
            f"tier = {json.dumps(b.tier)}",
            f"seed = {b.seed}",
            f"regimes = [{', '.join(str(r) for r in b.regimes)}]",
        ]
    return "\n".join(lines) + "\n"


def session_rng(session: Session, seed: int) -> np.random.Generator:
    """The session's random stream: a function of (session id, seed) only."""
    return np.random.default_rng([zlib.crc32(session.id.encode()), int(seed)])
