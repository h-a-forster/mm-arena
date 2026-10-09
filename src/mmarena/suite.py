"""Benchmark suites: versioned, deterministic lists of (game, episode seed) pairs."""

from __future__ import annotations

import tomllib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from mmarena.games import FAMILIES, VARIANTS, Game, make_game

SUITE_DIR = Path(__file__).parent / "suites"


@dataclass(frozen=True)
class Block:
    family: str
    variant: str
    games: int
    seed: int


@dataclass(frozen=True)
class Suite:
    name: str
    description: str
    episodes: int
    blocks: tuple[Block, ...]

    def games(self) -> Iterator[Game]:
        for b in self.blocks:
            for i in range(b.games):
                yield make_game(b.family, b.seed + i, b.variant)

    def episodes_list(self) -> list[tuple[Game, int]]:
        return [(g, e) for g in self.games() for e in range(self.episodes)]


def load_suite(name_or_path: str | Path) -> Suite:
    """Load a built-in suite by name (``core-v1``) or a TOML file by path."""
    path = Path(name_or_path)
    if not path.suffix:
        path = SUITE_DIR / f"{name_or_path}.toml"
    if not path.exists():
        builtin = sorted(p.stem for p in SUITE_DIR.glob("*.toml"))
        raise FileNotFoundError(f"suite {name_or_path!r} not found; built-in suites: {builtin}")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    blocks = []
    for raw in data.get("block", []):
        fam, var = raw["family"], raw.get("variant", "perturbed")
        if fam not in FAMILIES:
            raise ValueError(f"{path}: unknown family {fam!r}")
        if var not in VARIANTS:
            raise ValueError(f"{path}: unknown variant {var!r}")
        blocks.append(Block(fam, var, int(raw.get("games", 1)), int(raw.get("seed", 0))))
    if not blocks:
        raise ValueError(f"{path}: no [[block]] entries")
    return Suite(
        name=str(data.get("name", path.stem)),
        description=str(data.get("description", "")),
        episodes=int(data.get("episodes", 1)),
        blocks=tuple(blocks),
    )


def builtin_suites() -> list[str]:
    return sorted(p.stem for p in SUITE_DIR.glob("*.toml"))
