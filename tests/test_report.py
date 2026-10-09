"""Report building and plots on a small run directory."""

from __future__ import annotations

import csv
import json

import pytest

from mmarena.agents.baselines import BASELINES
from mmarena.report import build_report
from mmarena.runner import run_suite
from mmarena.suite import Block, Suite

SUITE = Suite(
    name="tiny",
    description="",
    episodes=2,
    blocks=(
        Block("dice", "classic", 1, 1000),
        Block("dice", "perturbed", 2, 5000),
        Block("coin", "perturbed", 2, 8000),
        Block("urn", "classic", 1, 1400),
    ),
)
AGENTS = ("bayes", "bayes-noflow", "static", "random")


@pytest.fixture(scope="module")
def run_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("run")
    for name in AGENTS:
        run_suite(SUITE, BASELINES[name], d / f"{name}.jsonl", resume=False)
    return d


def test_build_report_writes_files(run_dir):
    r = build_report(run_dir, n_boot=200)
    for f in ("summary.json", "leaderboard.csv", "REPORT.md"):
        assert (run_dir / f).exists()
    by = {row["agent"]: row for row in r.leaderboard}
    assert set(by) == set(AGENTS)
    assert by["bayes"]["edge_captured"] == pytest.approx(100.0)
    assert by["bayes"]["rank"] == 1
    assert by["random"]["edge_captured"] < by["static"]["edge_captured"] < 100
    assert r.reference_generated == 0
    assert len(r.pairwise) == 6
    assert all(p["p_holm"] >= p["p_value"] for p in r.pairwise)

    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["leaderboard"][0]["agent"] == "bayes"
    rows = list(csv.DictReader((run_dir / "leaderboard.csv").open(encoding="utf-8")))
    assert [row["agent"] for row in rows] == [row["agent"] for row in r.leaderboard]
    md = (run_dir / "REPORT.md").read_text(encoding="utf-8")
    for heading in ("## Leaderboard", "## By family and variant", "## Pairwise vs `bayes`"):
        assert heading in md


def test_report_is_deterministic(run_dir, tmp_path):
    a = build_report(run_dir, out_dir=tmp_path / "a", n_boot=100, seed=7)
    b = build_report(run_dir, out_dir=tmp_path / "b", n_boot=100, seed=7)
    assert (tmp_path / "a" / "summary.json").read_text() == (
        tmp_path / "b" / "summary.json"
    ).read_text()
    assert a.leaderboard[0]["edge_lo"] == b.leaderboard[0]["edge_lo"]


def test_report_without_reference_file(run_dir, tmp_path):
    sub = tmp_path / "noref"
    sub.mkdir()
    for name in ("static", "random"):
        (sub / f"{name}.jsonl").write_bytes((run_dir / f"{name}.jsonl").read_bytes())
    full = {row["agent"]: row for row in build_report(run_dir, write=False, n_boot=50).leaderboard}
    r = build_report(sub, n_boot=50)
    assert r.reference_generated == SUITE.episodes * sum(b.games for b in SUITE.blocks)
    for row in r.leaderboard:
        assert row["edge_captured"] == pytest.approx(full[row["agent"]]["edge_captured"])


def test_error_episodes_are_excluded(run_dir, tmp_path):
    sub = tmp_path / "err"
    sub.mkdir()
    lines = (run_dir / "static.jsonl").read_text(encoding="utf-8").splitlines()
    bad = json.loads(lines[0])
    bad.update(status="error", error="infra: test", game={**bad["game"], "id": "dice-missing"})
    (sub / "static.jsonl").write_text("\n".join([*lines, json.dumps(bad)]) + "\n", encoding="utf-8")
    (sub / "bayes.jsonl").write_bytes((run_dir / "bayes.jsonl").read_bytes())
    r = build_report(sub, n_boot=50)
    row = next(x for x in r.leaderboard if x["agent"] == "static")
    assert row["n_error"] == 1
    assert row["episodes"] == len(lines)
    assert "Episodes excluded" in (sub / "REPORT.md").read_text(encoding="utf-8")


def test_plots_render(run_dir, tmp_path):
    pytest.importorskip("matplotlib")
    from mmarena.plots import plot_run

    paths = plot_run(run_dir, tmp_path / "plots", pair=("bayes", "static"))
    assert len(paths) == 4
    for p in paths:
        assert p.exists() and p.stat().st_size > 0
        assert p.with_suffix(".svg").exists()
