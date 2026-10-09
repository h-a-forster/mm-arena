"""Run an agent over a suite, writing one JSON line per episode. Resumable."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from mmarena.agents.base import Agent
from mmarena.engine import run_episode
from mmarena.games import Game
from mmarena.suite import Suite


def read_traces(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    out = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # a line cut off by an interrupted run
    return out


def run_suite(
    suite: Suite,
    make_agent: Callable[[], Agent],
    out: str | Path,
    workers: int = 1,
    resume: bool = True,
    on_episode: Callable[[dict[str, Any], int, int], None] | None = None,
) -> list[dict[str, Any]]:
    """Play every (game, seed) in ``suite`` with a fresh agent per episode.

    Completed episodes already in ``out`` are skipped when ``resume`` is set; errored ones are
    retried. Returns the traces of the episodes run in this call.
    """
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done: set[tuple[str, int]] = set()
    if resume:
        done = {(t["game"]["id"], t["seed"]) for t in read_traces(out) if t.get("status") == "ok"}
    elif out.exists():
        out.unlink()
    todo: list[tuple[Game, int]] = [
        (g, s) for g, s in suite.episodes_list() if (g.id, s) not in done
    ]
    lock = threading.Lock()
    results: list[dict[str, Any]] = []

    def play(game: Game, seed: int) -> dict[str, Any]:
        trace = run_episode(game, make_agent(), seed)
        trace["suite"] = suite.name
        return trace

    def record(trace: dict[str, Any]) -> None:
        with lock:
            with out.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(trace, separators=(",", ":")) + "\n")
            results.append(trace)
            if on_episode:
                on_episode(trace, len(results), len(todo))

    if workers <= 1:
        for g, s in todo:
            record(play(g, s))
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(play, g, s) for g, s in todo]
            for f in as_completed(futures):
                record(f.result())
    return results
