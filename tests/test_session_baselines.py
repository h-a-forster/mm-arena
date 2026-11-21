"""Session baselines: agreement with the engine's references, privileged access, validity."""

from __future__ import annotations

import math

import numpy as np
import pytest

from mmarena.agents.base import Quote
from mmarena.agents.registry import make_agent_factory
from mmarena.agents.session_baselines import SESSION_BASELINES, OracleAgent, replay
from mmarena.joint import JointPosterior, Regimes
from mmarena.session_engine import run_session
from mmarena.sessions import Session, SessionObservation, make_session

REGIMES = Regimes.of([0.05, 0.5, 0.9])
FAMILIES = ("dice", "cards", "transform", "coin", "urn")
TIERS = {"open": 0.85, "mixed": 0.7, "tight": 0.5}  # the released noise ratios


def sessions(tier: str, n_per_family: int, base: int, rounds: int = 6) -> list[Session]:
    """Tuning-range sessions (seeds far from every released suite), regimes cycled."""
    out = []
    for fi, fam in enumerate(FAMILIES):
        for i in range(n_per_family):
            seed = base + 1000 * fi + i
            out.append(make_session(fam, seed, TIERS[tier], REGIMES, (fi + i) % 3, rounds, tier))
    return out


SMALL = sessions("mixed", 1, 140000, rounds=3)


def test_bayes_and_oracle_quote_exactly_the_engine_references() -> None:
    for s in SMALL:
        for name, prefix in (("bayes", "bayes"), ("oracle", "oracle")):
            tr = run_session(s, SESSION_BASELINES[name](), 0)
            for step in tr["steps"]:
                assert (step["bid"], step["ask"]) == (
                    step[f"{prefix}_bid"],
                    step[f"{prefix}_ask"],
                )
            if name == "bayes":
                assert math.isclose(tr["xpnl"], tr["bayes_xpnl_local"], rel_tol=1e-12)
            else:
                assert math.isclose(tr["xpnl_alpha"], tr["oracle_xpnl_alpha_local"], rel_tol=1e-12)


def test_replay_rebuilds_the_engine_posterior() -> None:
    s = SMALL[2]
    seen: list[tuple[SessionObservation, float, list[float]]] = []

    class Probe:
        name = "probe"

        def reset(self, spec) -> None:
            pass

        def act(self, obs: SessionObservation) -> Quote:
            post = replay(obs, JointPosterior(obs.game, obs.spec.regimes))
            seen.append((obs, post.mean(), post.regime_weights().tolist()))
            g = obs.game
            return Quote(g.prior_mean - 0.4 * g.prior_std, g.prior_mean + 0.6 * g.prior_std)

    tr = run_session(s, Probe(), 3)
    for (_obs, mu, rw), step in zip(seen, tr["steps"], strict=True):
        assert math.isclose(mu, step["mu"], rel_tol=1e-12, abs_tol=1e-12)
        np.testing.assert_allclose(rw, step["alpha_w"], rtol=1e-10, atol=1e-14)


def test_oracle_needs_the_privileged_hook() -> None:
    assert getattr(SESSION_BASELINES["oracle"](), "privileged", False)
    for name, make in SESSION_BASELINES.items():
        if name != "oracle":
            assert not getattr(make(), "privileged", False), name
    agent = OracleAgent()
    agent.reset(SMALL[0].spec)
    with pytest.raises(RuntimeError):
        agent.act(_first_obs(SMALL[0]))


def _first_obs(s: Session) -> SessionObservation:
    return SessionObservation(s.spec, s.id, 0, 0, 0, (), (), (), 0, 0.0, True, True)


def test_every_baseline_plays_a_session_without_invalid_quotes() -> None:
    s = SMALL[0]
    for name, make in SESSION_BASELINES.items():
        if name.startswith("bayes-lookahead-"):
            continue
        tr = run_session(s, make(), 0)
        assert tr["status"] == "ok", name
        assert not any(step["invalid"] for step in tr["steps"]), name


def test_registry_refuses_the_other_formats_baselines() -> None:
    assert make_agent_factory("bayes-nolearn", suite_format=2)().name == "bayes-nolearn"
    assert make_agent_factory("oracle", suite_format=2, name="o#x")().name == "o#x"
    with pytest.raises(ValueError):
        make_agent_factory("bayes-nolearn")  # session-only baseline on a format-1 suite
    with pytest.raises(ValueError):
        make_agent_factory("oracle", suite_format=1)
    with pytest.raises(ValueError):
        make_agent_factory("bayes", suite_format=3)
    v1 = make_agent_factory("bayes")()
    v2 = make_agent_factory("bayes", suite_format=2)()
    assert type(v1).__module__.endswith(".baselines")
    assert type(v2).__module__.endswith(".session_baselines")


@pytest.mark.slow
def test_oracle_realised_pnl_is_unbiased_for_ev_alpha_only() -> None:
    pool = sessions("mixed", 1, 150000, rounds=4)
    d_alpha, d_ev = [], []
    for s in pool:
        for seed in range(40):
            tr = run_session(s, SESSION_BASELINES["oracle"](), seed)
            d_alpha.append((tr["pnl"] - tr["xpnl_alpha"]) / s.game.prior_std)
            d_ev.append((tr["pnl"] - tr["xpnl"]) / s.game.prior_std)
    a, e = np.array(d_alpha), np.array(d_ev)
    se_a = a.std(ddof=1) / math.sqrt(len(a))
    assert abs(a.mean()) < 4 * se_a
    assert e.mean() > 2 * e.std(ddof=1) / math.sqrt(len(e))  # ev understates the oracle


@pytest.mark.slow
def test_filter_concentrates_on_the_true_regime_under_an_informative_quote() -> None:
    """Fixed quote at the public mean +/- 0.5 prior sd for 30 rounds: mass on the truth > 0.95."""

    class Fixed:
        name = "fixed-informative"

        def reset(self, spec) -> None:
            pass

        def act(self, obs: SessionObservation) -> Quote:
            mu = replay(obs, JointPosterior(obs.game, obs.spec.regimes)).mean()
            h = 0.5 * obs.game.prior_std
            return Quote(mu - h, mu + h)

    masses = []
    for s in sessions("mixed", 1, 160000, rounds=30):
        tr = run_session(s, Fixed(), 0)
        masses.append(tr["rounds"][-1]["alpha_w_start"][s.regime])
    assert np.mean(masses) > 0.95


@pytest.mark.slow
def test_learner_converges_on_the_open_tier() -> None:
    """30 rounds: the myopic learner earns at least 93% of the oracle in rounds 21 to 30.

    On the mixed tier convergence is not guaranteed: in some benign sessions the learner keeps
    quoting wide and stops learning (incomplete learning of a greedy policy), so no fixed
    threshold holds there across samples.
    """
    num = den = 0.0
    for s in sessions("open", 3, 170000, rounds=30):
        b = run_session(s, SESSION_BASELINES["bayes"](), 0)
        o = run_session(s, SESSION_BASELINES["oracle"](), 0)
        num += sum(r["xpnl_alpha"] for r in b["rounds"][20:])
        den += sum(r["xpnl_alpha"] for r in o["rounds"][20:])
    assert num / den >= 0.93


@pytest.mark.slow
def test_lookahead_beats_the_myopic_learner_on_the_tight_tier() -> None:
    """Greedy quoting learns too little at a low noise ratio; probing pays (paired sessions)."""
    pool = sessions("tight", 2, 180000)
    look = sum(
        run_session(s, SESSION_BASELINES["bayes-lookahead"](), 0)["xpnl_alpha"] for s in pool
    )
    bayes = sum(run_session(s, SESSION_BASELINES["bayes"](), 0)["xpnl_alpha"] for s in pool)
    assert look > bayes


@pytest.mark.slow
def test_baseline_ladder_on_tuning_sessions() -> None:
    """oracle > bayes > bayes-nolearn > bayes-noflow > glosten-milgrom pooled; static below
    bayes-noflow on every tier."""
    pools = {t: sessions(t, 3, 190000) for t in TIERS}
    names = ("oracle", "bayes", "bayes-nolearn", "bayes-noflow", "glosten-milgrom", "static")
    tot = {
        (n, t): sum(run_session(s, SESSION_BASELINES[n](), 0)["xpnl_alpha"] for s in pool)
        for n in names
        for t, pool in pools.items()
    }
    pooled = [sum(tot[(n, t)] for t in TIERS) for n in names[:-1]]
    assert pooled == sorted(pooled, reverse=True)
    for t in TIERS:
        assert tot[("static", t)] < tot[("bayes-noflow", t)]
