"""Centring-vs-width decomposition."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from mmarena.agents.baselines import BASELINES
from mmarena.decompose import build_game, decompose_runs, decompose_trace
from mmarena.engine import run_episode
from mmarena.games import make_game
from mmarena.report import load_run

CORE = Path(__file__).resolve().parents[1] / "results" / "core-v1"
GAMES = [("dice", 5000), ("coin", 8000), ("urn", 9000), ("cards", 6000)]


@pytest.fixture(scope="module")
def runs() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for name in ("bayes", "bayes-noflow", "static", "random"):
        out[name] = [
            run_episode(make_game(fam, gseed, "perturbed"), BASELINES[name](), s)
            for fam, gseed in GAMES
            for s in (0, 1)
        ]
    return out


def test_bayes_is_100_in_every_quote_column(runs):
    d = decompose_runs(runs)["bayes"]
    for col in ("as_played", "agent_mid_bayes_width", "bayes_mid_agent_width"):
        assert d[col] == pytest.approx(100.0)
    # The mean-centred quote with the Bayes width is no better than the Bayes quote.
    assert d["mu_agent_width"] <= 100.0 + 1e-9
    assert d["mismatches"] == 0


def test_replay_reproduces_step_ev(runs):
    res = decompose_runs(runs)
    assert all(d["mismatches"] == 0 for d in res.values())
    assert all(d["unreplayed_episodes"] == 0 for d in res.values())


def test_as_played_is_local_efficiency(runs):
    res = decompose_runs(runs)
    for name, traces in runs.items():
        num = sum(t["xpnl"] / t["game"]["prior_std"] for t in traces)
        den = sum(t["bayes_xpnl_local"] / t["game"]["prior_std"] for t in traces)
        assert res[name]["as_played"] == pytest.approx(100 * num / den)


def test_static_quoter_loses_on_centring_not_width(runs):
    d = decompose_runs(runs)["static"]
    assert d["bayes_mid_agent_width"] > d["as_played"]
    assert d["covered_share"] <= 100.0


def test_tampered_ev_is_counted_as_mismatch(runs):
    t = json.loads(json.dumps(runs["static"][0]))
    t["steps"][1]["ev"] += 0.5
    game = build_game(t["game"])
    assert decompose_trace(game, t).mismatches == 1


def test_uncovered_steps_keep_their_value(runs):
    t = json.loads(json.dumps(runs["static"][0]))
    for s in t["steps"]:
        s["ask"] = None  # one-sided everywhere: nothing is covered
    game = build_game(t["game"])
    d = decompose_trace(game, t)
    assert d.covered == 0
    assert d.agent_mid_bayes_width == pytest.approx(d.as_played)
    assert d.mu_agent_width == pytest.approx(d.as_played)


def test_unrebuildable_game_is_skipped(runs):
    t = json.loads(json.dumps(runs["static"][0]))
    t["game"]["id"] = "dice-ffffffff"
    d = decompose_runs({"static": [t]})["static"]
    assert d["unreplayed_episodes"] == 1
    assert math.isnan(d["as_played"])


@pytest.mark.skipif(not CORE.exists(), reason="results/core-v1 not present")
def test_real_traces_replay_exactly():
    traces = load_run(CORE)
    res = decompose_runs(traces)
    assert res and all(d["mismatches"] == 0 for d in res.values())
    assert res["bayes"]["agent_mid_bayes_width"] == pytest.approx(100.0)
    assert res["bayes"]["bayes_mid_agent_width"] == pytest.approx(100.0)
