"""Session report: scores, the shortfall identity, learning response, tests, CLI dispatch."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from mmarena.agents.registry import make_agent_factory
from mmarena.cli import main
from mmarena.runner import run_suite
from mmarena.session_report import build_session_report, is_session_run, learning_response
from mmarena.suite import load_suite


def _run(tmp: Path, specs: dict[str, str]) -> Path:
    suite = load_suite("smoke-v2")
    for name, spec in specs.items():
        factory = make_agent_factory(spec, suite_format=2, name=name)
        run_suite(suite, factory, tmp / f"{name.replace(':', '_').replace('#', '_')}.jsonl")
    return tmp


@pytest.fixture(scope="module")
def baseline_report(tmp_path_factory: pytest.TempPathFactory) -> dict:
    d = tmp_path_factory.mktemp("ci2")
    names = ("oracle", "bayes", "bayes-nolearn", "bayes-noflow", "static", "bayes-optimist")
    _run(d, {n: n for n in names})
    return build_session_report(d)


def _agent(report: dict, name: str) -> dict:
    return next(a for a in report["agents"] if a["agent"] == name)


def test_scores_are_ratios_of_sums_with_intervals(baseline_report: dict) -> None:
    o = _agent(baseline_report, "oracle")
    assert o["pooled"]["value"] == pytest.approx(100.0)
    b = _agent(baseline_report, "bayes")
    sess = o["per_session"]
    want = 100 * sum(b["per_session"].values()) / sum(sess.values())
    assert b["pooled"]["value"] == pytest.approx(want)
    for e in [b["pooled"], *b["tiers"].values()]:
        assert e["lo"] <= e["value"] + 1e-9 and e["value"] <= e["hi"] + 1e-9
    assert set(b["tiers"]) == {"open", "mixed"}
    assert baseline_report["computed_references"] == []
    assert baseline_report["missing_baselines"] == []  # only named beside LLM runs


def test_shortfall_identity_is_exact(baseline_report: dict) -> None:
    for a in baseline_report["agents"]:
        for tier, d in a["shortfall"].items():
            parts = d["pricing"] + d["information"] + d["path"] + d["residual"]
            assert math.isclose(d["shortfall"], parts, abs_tol=1e-9), (a["agent"], tier)
        if a["agent"] == "bayes":
            assert a["shortfall"]["pooled"]["pricing"] == pytest.approx(0, abs=1e-12)
            assert a["shortfall"]["pooled"]["residual"] == pytest.approx(0, abs=1e-12)
        if a["agent"] == "oracle":
            assert a["shortfall"]["pooled"]["shortfall"] == pytest.approx(0, abs=1e-12)


def test_learning_response_is_one_for_bayes_and_near_zero_without_learning(
    baseline_report: dict,
) -> None:
    assert _agent(baseline_report, "bayes")["learning_response"]["value"] == pytest.approx(1.0)
    assert abs(_agent(baseline_report, "bayes-nolearn")["learning_response"]["value"]) < 0.2
    assert abs(_agent(baseline_report, "bayes-noflow")["learning_response"]["value"]) < 0.2
    # a width that follows neither reference quote reads 0, not the share of variance it
    # has in common with the prior-regime width
    assert abs(_agent(baseline_report, "static")["learning_response"]["value"]) < 0.05


def test_learning_response_is_the_coefficient_on_the_bayes_width() -> None:
    rng = np.random.default_rng(0)
    prior = rng.uniform(0.5, 1.5, 200)
    bayes = 0.6 * prior + rng.uniform(0.0, 1.0, 200)  # correlated with the prior-regime width
    noise = rng.normal(0, 0.01, 200)
    assert learning_response(bayes, bayes, prior) == pytest.approx(1.0)
    # exactly 0, not rounding noise of either sign, so p-values agree across machines
    assert learning_response(prior, bayes, prior) == 0.0
    assert learning_response(0.3 + 0.5 * prior, bayes, prior) == 0.0
    assert learning_response(np.full(200, 0.8) + noise, bayes, prior) == pytest.approx(0, abs=0.01)
    assert learning_response(0.3 * bayes + 0.7 * prior, bayes, prior) == pytest.approx(0.3)
    assert math.isnan(learning_response(prior, prior, prior))  # the widths never differ


def test_committed_reports_use_the_joint_regression() -> None:
    root = Path(__file__).resolve().parents[1] / "results"
    for suite in ("core-v2", "tight-v2"):
        summary = json.loads((root / suite / "summary.json").read_text(encoding="utf-8"))
        lr = {a["agent"]: a["learning_response"]["value"] for a in summary["agents"]}
        # the oracle is exact, so its p-values do not depend on how the machine rounds
        o = next(a for a in summary["agents"] if a["agent"] == "oracle")
        assert {o["tiers"][t]["value"] for t in o["tiers"]} == {100.0}
        if "gradient" in o:  # two tiers
            assert o["gradient"] == {"value": 0.0, "lo": 0.0, "hi": 0.0, "p_le0": 1.0}
        assert lr["bayes"] == pytest.approx(1.0)
        assert abs(lr["static"]) < 0.05 and abs(lr["random"]) < 0.05, suite


def test_ceiling_lines_are_printed_and_never_a_denominator(baseline_report: dict) -> None:
    c = baseline_report["ceiling"]
    assert c["open"]["value"] == 92.0 and c["mixed"]["value"] == 90.0
    assert c["open"]["value"] > c["pooled"]["value"] > c["mixed"]["value"]
    assert baseline_report["second_column"]["tiers"] == []  # no tier below 85 in smoke-v2


def test_missing_references_are_computed(tmp_path: Path) -> None:
    _run(tmp_path, {"bayes": "bayes"})
    r = build_session_report(tmp_path)
    assert set(r["computed_references"]) == {"oracle", "bayes-nolearn"}
    assert _agent(r, "oracle")["computed"] and not _agent(r, "bayes")["computed"]
    assert (tmp_path / "REPORT.md").read_text(encoding="utf-8").startswith("# mm-arena session")


def test_replicates_and_preregistered_families(tmp_path: Path) -> None:
    quote = 'scripted:{"bid": 1, "ask": 99}'
    tight = 'scripted:{"bid": 14, "ask": 21}'
    _run(
        tmp_path,
        {
            "lab:m1@high": tight,
            "lab:m1@high#r2": quote,
            "lab:m1@low": quote,
            "lab:m2@high": quote,
            "lab:m2@high#r2": tight,
        },
    )
    r = build_session_report(tmp_path)
    rep = r["replicates"]
    assert set(rep["setups"]) == {"lab:m1@high", "lab:m2@high"}
    assert rep["setups"]["lab:m1@high"]["runs"] == 2
    assert len(rep["pairs"]) == 1
    fams = r["tests"]
    assert {t["test"] for t in fams["A"]} == {
        "lab:m1@high vs lab:m1@low, pooled",
        "lab:m1@high vs lab:m2@high, pooled",
        "lab:m1@low vs lab:m2@high, pooled",
    }
    assert any(t["test"] == "lab:m1@high > lab:m1@low, pooled" for t in fams["C"])
    for fam in fams.values():
        for t in fam:
            assert not math.isfinite(t["p"]) or t["p_holm"] >= t["p"] - 1e-12
    md = (tmp_path / "REPORT.md").read_text(encoding="utf-8")
    assert "## Run-to-run variability" in md and "Family B" in md
    # an LLM run directory without the reference quoters says which rows are absent
    assert {"static", "random", "bayes-lookahead"} <= set(r["missing_baselines"])
    assert "bayes" not in r["missing_baselines"] and "--agent baselines" in md


def test_cli_report_dispatches_on_trace_version(tmp_path: Path, capsys) -> None:
    assert main(["run", "--agent", "bayes", "--suite", "smoke-v2", "--out", str(tmp_path)]) == 0
    assert is_session_run(tmp_path)
    assert main(["report", str(tmp_path), "--quiet"]) == 0
    s = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert s["trace_version"] == 3 and s["suite"] == "smoke-v2"
    assert not is_session_run(Path(__file__).resolve().parents[1] / "results" / "core-v1")


def test_summary_run_dir_uses_forward_slashes(tmp_path: Path) -> None:
    """``run_dir`` is written the same on every platform, in new and in committed reports."""
    d = tmp_path / "runs" / "ci2"
    _run(d, {"bayes": "bayes"})
    assert build_session_report(d)["run_dir"] == d.as_posix()
    root = Path(__file__).resolve().parents[1]
    for name in ("core-v2", "tight-v2"):
        text = (root / "results" / name / "summary.json").read_text(encoding="utf-8")
        assert json.loads(text)["run_dir"] == f"results/{name}"


def test_mid_error_is_finite_when_a_reveal_fixes_the_value() -> None:
    from mmarena.agents.session_baselines import SESSION_BASELINES
    from mmarena.session_engine import run_session
    from mmarena.session_metrics import session_metrics
    from mmarena.suite import load_suite

    session = next(s for s in load_suite("core-v2").sessions() if s.id == "transform-sde0e5385")
    trace = run_session(session, SESSION_BASELINES["static"](), 0)
    assert any(0 < x["sd"] < 1e-9 for x in trace["steps"])  # the value is known after the reveal
    m = session_metrics(trace)
    assert m.mid_err / m.n_mid < 10
