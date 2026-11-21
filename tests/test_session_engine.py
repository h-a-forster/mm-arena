"""Session engine: common random numbers, the two expectations, rounds, resume."""

from __future__ import annotations

import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from mmarena import joint
from mmarena.agents.base import InfraError, Quote
from mmarena.runner import read_traces, run_suite
from mmarena.session_engine import TRACE_VERSION, run_session
from mmarena.sessions import SessionObservation, SessionSpec, make_session
from mmarena.suite import load_suite

REGIMES = joint.Regimes.of([0.05, 0.5, 0.9])


class FnAgent:
    """Quotes ``fn(obs)``; records every observation."""

    def __init__(self, fn: Callable[[SessionObservation], Any], name: str = "fn") -> None:
        self.fn, self.name = fn, name
        self.seen: list[SessionObservation] = []

    def reset(self, spec: SessionSpec) -> None:
        self.seen = []

    def act(self, obs: SessionObservation) -> Quote:
        self.seen.append(obs)
        out = self.fn(obs)
        if isinstance(out, BaseException):
            raise out
        return Quote(*out)


def static(k: float) -> FnAgent:
    def fn(obs: SessionObservation) -> tuple[float, float]:
        g = obs.game
        return g.prior_mean - k * g.prior_std, g.prior_mean + k * g.prior_std

    return FnAgent(fn, f"static{k}")


SESSION = make_session("dice", 4242, 0.7, REGIMES, 1, 3, "mixed")


def test_draws_are_identical_across_agents() -> None:
    a = run_session(SESSION, static(0.3), 5)
    b = run_session(SESSION, static(1.5), 5)
    assert a["trace_version"] == TRACE_VERSION == 3
    assert [r["hidden"] for r in a["rounds"]] == [r["hidden"] for r in b["rounds"]]
    assert [s["taker"] for s in a["steps"]] == [s["taker"] for s in b["steps"]]
    c = run_session(SESSION, static(0.3), 6)
    assert [r["hidden"] for r in a["rounds"]] != [r["hidden"] for r in c["rounds"]]
    # same regime-free spec, different regime: same outcomes, different informed draws apply
    other = make_session("dice", 4242, 0.7, REGIMES, 2, 3, "mixed")
    d = run_session(other, static(0.3), 5)
    assert [r["hidden"] for r in a["rounds"]] == [r["hidden"] for r in d["rounds"]]


def test_steps_record_both_expectations_and_the_tower_identity() -> None:
    tr = run_session(SESSION, static(0.8), 1)
    assert len(tr["steps"]) == SESSION.spec.n_quotes == 12
    for s in tr["steps"]:
        for key in ("ev", "ev_alpha", "bayes_ev", "bayes_ev_alpha", "oracle_ev_alpha"):
            assert math.isfinite(s[key])
        assert s["oracle_ev_alpha"] >= s["ev_alpha"] - 1e-12  # nothing beats the oracle
        assert s["bayes_ev"] >= s["ev"] - 1e-12  # nor the learner on public information
        assert math.isclose(sum(s["alpha_w"]), 1.0)
    assert math.isclose(tr["xpnl"], sum(s["ev"] for s in tr["steps"]))
    assert math.isclose(tr["xpnl_alpha"], sum(r["xpnl_alpha"] for r in tr["rounds"]))
    assert math.isclose(tr["pnl"], sum(r["pnl"] for r in tr["rounds"]))


def test_public_ev_is_the_regime_average_of_conditional_evs() -> None:
    game = SESSION.game
    post = joint.JointPosterior(game, REGIMES)
    post.observe_trade("buy", game.prior_mean - 1, game.prior_mean + 0.5)
    post.settle(float(game.value[3]))
    post.observe_trade(None, game.prior_mean - 2, game.prior_mean + 2)
    wl, mu, s = post.level_weights(), post.mean(), game.market.noise_scale
    for bid, ask in ((mu - 1, mu + 1), (None, mu + 0.3), (mu - 3, None)):
        public = joint.quote_value(game.levels, wl, mu, bid, ask, REGIMES.alpha, s).ev
        parts = []
        for k in range(3):
            wk, ak = post.conditional(k)
            ev_k = joint.quote_value(game.levels, wk, mu, bid, ask, ak, s).ev
            parts.append(post.regime_weights()[k] * ev_k)
        assert math.isclose(public, sum(parts), rel_tol=1e-12, abs_tol=1e-12)


def test_rounds_start_flat_and_reveal_afresh() -> None:
    agent = static(0.5)
    tr = run_session(SESSION, agent, 2)
    per_round = SESSION.spec.steps_per_round
    for obs in agent.seen:
        if obs.step == 0:
            assert obs.position == 0 and obs.cash == 0.0 and obs.revealed == ()
            assert len(obs.settled) == obs.round
            assert len(obs.history) == obs.round * per_round
        assert obs.quotes_left == SESSION.spec.n_quotes - obs.quote
    last = agent.seen[-1]
    assert [x["value"] for x in last.settled] == [r["value"] for r in tr["rounds"][:-1]]
    for r in tr["rounds"]:
        steps = [s for s in tr["steps"] if s["round"] == r["round"]]
        assert math.isclose(r["pnl"], steps[-1]["cash"] + steps[-1]["position"] * r["value"])


def test_observation_never_carries_the_regime() -> None:
    agent = static(0.5)
    run_session(SESSION, agent, 0)
    names = set(SessionObservation.__dataclass_fields__)
    assert not {"regime", "alpha", "omega", "hidden"} & names
    assert all(obs.spec is SESSION.spec for obs in agent.seen)


def test_privileged_agents_get_the_regime_through_the_hook_only() -> None:
    class Peek(FnAgent):
        privileged = True

        def set_regime(self, k: int) -> None:
            self.k = k

    agent = Peek(lambda obs: (None, None))
    run_session(SESSION, agent, 0)
    assert agent.k == SESSION.regime
    plain = static(1.0)
    run_session(SESSION, plain, 0)
    assert not hasattr(plain, "k")


def test_infra_error_stops_the_session_unscored() -> None:
    def fn(obs: SessionObservation):
        return InfraError("down") if obs.quote == 5 else (1.0, 2.0)

    tr = run_session(SESSION, FnAgent(fn), 0)
    assert tr["status"] == "error" and tr["pnl"] is None and tr["xpnl_alpha"] is None
    assert len(tr["steps"]) == 5


def test_invalid_and_crossed_quotes_score_zero() -> None:
    def fn(obs: SessionObservation):
        return [(5.0, 4.0), (math.nan, 3.0), ValueError("boom"), (None, None)][obs.quote % 4]

    tr = run_session(SESSION, FnAgent(fn), 0)
    kinds = [s["invalid"] for s in tr["steps"][:4]]
    assert kinds == ["crossed", "nonfinite", "exception", None]
    assert all(s["ev"] == 0 and s["ev_alpha"] == 0 for s in tr["steps"])


def test_suite_run_resumes_and_skips_finished_sessions(tmp_path: Path) -> None:
    suite = load_suite("smoke-v2")
    out = tmp_path / "x.jsonl"
    first = run_suite(suite, lambda: static(1.0), out)
    assert len(first) == 3 and all(t["suite"] == "smoke-v2" for t in first)
    assert all(t["prompt_version"] == "v2.0" for t in first)
    assert run_suite(suite, lambda: static(1.0), out) == []
    lines = out.read_text(encoding="utf-8").splitlines()
    out.write_text("\n".join(lines[:2]) + "\n" + lines[2][:50], encoding="utf-8")
    again = run_suite(suite, lambda: static(1.0), out)
    assert [t["session"]["id"] for t in again] == [first[2]["session"]["id"]]
    assert len(read_traces(out)) == 3


@pytest.mark.slow
def test_realised_pnl_matches_both_expectations_for_a_public_quoter() -> None:
    """Mean realised P&L minus mean ev and minus mean ev_alpha: zero within Monte Carlo error."""
    sessions = [make_session(f, 900 + i, 0.7, REGIMES, i % 3, 4) for i, f in
                enumerate(["dice", "cards", "coin", "urn", "transform", "dice"])]  # fmt: skip
    d_ev, d_alpha = [], []
    for s in sessions:
        for seed in range(60):
            tr = run_session(s, static(0.6), seed)
            sd = s.game.prior_std
            d_ev.append((tr["pnl"] - tr["xpnl"]) / sd)
            d_alpha.append((tr["pnl"] - tr["xpnl_alpha"]) / sd)
    for d in (np.array(d_ev), np.array(d_alpha)):
        assert abs(d.mean()) < 4 * d.std(ddof=1) / math.sqrt(len(d))
