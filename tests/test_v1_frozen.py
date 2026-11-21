"""Guard rails: the released core-v1 benchmark must not change.

The suite files, the prompt, the engine's scoring and the published report are pinned here. Any
change to them changes every published number, so these tests fail before such a change can
land unnoticed. New suite formats and agents are added beside core-v1, never through it.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest

from mmarena.agents.base import Observation
from mmarena.agents.baselines import BASELINES
from mmarena.agents.llm import LLMAgent, prompt_hash
from mmarena.agents.prompt import render_prompt_parts
from mmarena.cache import CachedProvider, ResponseCache
from mmarena.engine import run_episode
from mmarena.games import make_game
from mmarena.providers.scripted import ScriptedProvider
from mmarena.report import build_report
from mmarena.runner import read_traces
from mmarena.suite import SUITE_DIR, load_suite

RESULTS = Path(__file__).resolve().parents[1] / "results" / "core-v1"

SUITE_SHA256 = {
    "core-v1": "52f1b1ab23bd9c53b7f2d2c07263591d4112b3ea4bb7d68699b05b473581c558",
    "full-v1": "d90d2c65effa987c503e6262812afab2d8a82ab24ea2c36884d67ed3c4979875",
    "smoke": "ea6ebe6688f90f366e65f16cb78a4d39cb8133451f329e74d40f2960c5d43a39",
}

# Step-0 prompt (system prompt and both user segments) of three core-v1 games, by suite index.
PROMPT_SHA256 = {
    0: ("dice-fb2da41f", "03967e0dc7dbeafb88f93774847e4073e1f77ad274417f599df671dc438d7bdc"),
    17: ("cards-078b9def", "69e6c2940147e4b14d5c7660f93653739116a8e02858ded22403af9a2e0867e8"),
    45: ("coin-2778e188", "a07f13407c6c388f330d6b2eb80f2afc4e7fde316410a54734a4d4cbf22680d3"),
}


def _step0(game) -> Observation:
    return Observation(
        game=game,
        step=0,
        stage=0,
        revealed=(),
        history=(),
        position=0,
        cash=0.0,
        bid_allowed=True,
        ask_allowed=True,
    )


@pytest.mark.parametrize("name", sorted(SUITE_SHA256))
def test_released_suite_files_unchanged(name: str) -> None:
    data = (SUITE_DIR / f"{name}.toml").read_bytes()
    assert hashlib.sha256(data).hexdigest() == SUITE_SHA256[name]


def test_core_v1_step0_prompts_unchanged() -> None:
    games = list(load_suite("core-v1").games())
    for index, (game_id, digest) in PROMPT_SHA256.items():
        game = games[index]
        assert game.id == game_id
        system, parts = render_prompt_parts(_step0(game))
        assert prompt_hash(system, parts) == digest


def _committed(name: str, n: int) -> list[dict]:
    traces = [t for t in read_traces(RESULTS / f"{name}.jsonl") if t["status"] == "ok"]
    traces.sort(key=lambda t: (t["game"]["id"], t["seed"]))
    # Every sixth episode: all five families, both variants.
    return traces[::6][:n]


@pytest.mark.parametrize("name", ["bayes", "static"])
def test_core_v1_replay_matches_committed_traces(name: str) -> None:
    for old in _committed(name, 10):
        g = old["game"]
        game = make_game(g["family"], g["seed"], g["variant"])
        assert game.id == g["id"]
        new = run_episode(game, BASELINES[name](), old["seed"])
        assert len(new["steps"]) == len(old["steps"])
        for a, b in zip(new["steps"], old["steps"], strict=True):
            assert (a["bid"], a["ask"], a["action"]) == (b["bid"], b["ask"], b["action"])
            assert math.isclose(a["ev"], b["ev"], rel_tol=1e-12, abs_tol=1e-12)
            assert math.isclose(a["bayes_ev"], b["bayes_ev"], rel_tol=1e-12, abs_tol=1e-12)


def test_scripted_llm_run_on_core_v1_keeps_prompt_and_cache_keys(tmp_path: Path) -> None:
    game = next(load_suite("core-v1").games())
    provider = CachedProvider(ScriptedProvider('{"bid": 1, "ask": 2}'), ResponseCache(tmp_path))
    trace = run_episode(game, LLMAgent(provider, name="scripted"), 0)
    assert trace["provenance"]["prompt_sha256"] == PROMPT_SHA256[0][1]
    assert trace["steps"][-1]["info"]["prompt_sha256"] == (
        "c6cab0d39ecc019127e52c31a9af1de875d2a487d4ef081acee5d73510af95a6"
    )
    keys = sorted(p.stem for p in tmp_path.rglob("*.json"))
    assert len(keys) == len(trace["steps"]) == 6
    assert hashlib.sha256("\n".join(keys).encode()).hexdigest() == (
        "917a8bb0db8575924e3f961aa7cb520bc3ee6d0946df2d39f65af74fa053e1a4"
    )


@pytest.mark.slow
def test_core_v1_report_rebuilds_byte_for_byte(tmp_path: Path) -> None:
    build_report(RESULTS, out_dir=tmp_path)
    for name in ("REPORT.md", "leaderboard.csv"):
        assert (tmp_path / name).read_bytes() == (RESULTS / name).read_bytes(), name
    new = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    old = json.loads((RESULTS / "summary.json").read_text(encoding="utf-8"))
    new.pop("run_dir"), old.pop("run_dir")
    assert _close(new, old)


def _close(a: object, b: object) -> bool:
    """Equal JSON values, floats to a relative 1e-9 (last-digit rounding differs by platform)."""
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_close(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_close(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, float) or isinstance(b, float):
        return (
            isinstance(a, (int, float))
            and isinstance(b, (int, float))
            and (math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12))
        )
    return a == b
