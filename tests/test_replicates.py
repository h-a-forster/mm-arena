"""Replicate runs (`#rN`) in a report directory."""

from __future__ import annotations

import importlib.util
import json
import math
import statistics
from pathlib import Path
from types import SimpleNamespace

import pytest

from mmarena.agents.baselines import BASELINES
from mmarena.report import build_report, render_markdown, split_replicate
from mmarena.runner import run_suite
from mmarena.suite import Block, Suite

SUITE = Suite(
    name="tiny",
    description="",
    episodes=2,
    blocks=(
        Block("dice", "classic", 2, 1000),
        Block("dice", "perturbed", 3, 5000),
        Block("coin", "perturbed", 2, 8000),
    ),
)
# fake LLM setup -> baseline behind each of its runs
SETUPS = {
    "fake:alpha": ["static", "bayes-noflow"],
    "fake:beta": ["random", "static", "bayes-noflow"],
    "fake:solo": ["static"],
}


@pytest.fixture(scope="module")
def base_traces(tmp_path_factory) -> dict[str, list[dict]]:
    d = tmp_path_factory.mktemp("base")
    out = {}
    for name in ("bayes", "static", "bayes-noflow", "random"):
        run_suite(SUITE, BASELINES[name], d / f"{name}.jsonl", resume=False)
        out[name] = [json.loads(x) for x in (d / f"{name}.jsonl").read_text().splitlines()]
    return out


def write_run(path, traces, agent):
    with path.open("w", encoding="utf-8") as fh:
        for t in traces:
            fh.write(json.dumps({**t, "agent": agent}) + "\n")


@pytest.fixture(scope="module")
def run_dir(tmp_path_factory, base_traces):
    d = tmp_path_factory.mktemp("reps")
    write_run(d / "bayes.jsonl", base_traces["bayes"], "bayes")
    for setup, runs in SETUPS.items():
        for k, src in enumerate(runs, 1):
            name = setup if k == 1 else f"{setup}#r{k}"
            write_run(
                d / f"{name.replace(':', '_').replace('#', '_')}.jsonl", base_traces[src], name
            )
    return d


def test_split_replicate():
    assert split_replicate("claude-cli:m@high") == ("claude-cli:m@high", 1)
    assert split_replicate("claude-cli:m@high#r2") == ("claude-cli:m@high", 2)
    assert split_replicate("a#r12") == ("a", 12)
    assert split_replicate("a#r1") == ("a", 1)
    assert split_replicate("a#rx") == ("a#rx", 1)


def test_primary_runs_only_outside_replicate_section(run_dir):
    r = build_report(run_dir, n_boot=100)
    names = {row["agent"] for row in r.leaderboard}
    assert names == {"bayes", *SETUPS}
    assert {v["agent"] for v in r.variants} == names
    assert set(r.decomposition) == names
    assert all("#r" not in x for p in r.pairwise for x in (p["a"], p["b"]))
    assert set(r.variance["per_agent"]) == names
    md = (run_dir / "REPORT.md").read_text(encoding="utf-8")
    assert "primary runs only" in md
    assert "## Run-to-run variability" in md
    assert "P(best)" not in md


def test_replicate_tables(run_dir):
    r = build_report(run_dir, n_boot=100, write=False)
    rep = r.replicates
    assert [s["setup"] for s in rep["setups"]] == ["fake:alpha", "fake:beta"]
    alpha = rep["setups"][0]
    assert [x["run"] for x in alpha["runs"]] == [1, 2]
    assert alpha["runs"][0]["vs_first"] is None
    assert alpha["runs"][1]["vs_first"]["diff_value"] > 0  # noflow beats static here
    edges = [x["edge_captured"] for x in alpha["runs"]]
    # all runs cover the same episodes, so the pooled edge is the mean of the run edges
    assert alpha["pooled"]["edge_captured"] == pytest.approx(sum(edges) / 2)
    assert len(rep["pairs"]) == 1
    pair = rep["pairs"][0]
    assert (pair["runs_a"], pair["runs_b"]) == (2, 3)
    assert len(pair["combinations"]) == 6
    assert pair["p_holm"] >= pair["p_value"]
    # pooled pair difference: mean of 2 runs vs mean of 3 runs
    eb = [x["edge_captured"] for x in rep["setups"][1]["runs"]]
    assert pair["diff_value"] == pytest.approx(sum(edges) / 2 - sum(eb) / 3)
    first = pair["combinations"][0]
    assert (first["run_a"], first["run_b"]) == (1, 1)
    assert first["diff_value"] == pytest.approx(edges[0] - eb[0])
    # run-to-run SD over all runs of a setup, 2 or 3 of them
    assert alpha["pooled"]["run_sd"] == pytest.approx(statistics.stdev(edges))
    sd_beta = rep["setups"][1]["pooled"]["run_sd"]
    assert sd_beta == pytest.approx(statistics.stdev(eb))
    pooled_rows = [x for x in render_markdown(r).splitlines() if "| pooled |" in x]
    assert pooled_rows[1].endswith(f"| {sd_beta:.1f} |")


def test_summary_json_has_replicates_and_decomposition(run_dir):
    build_report(run_dir, n_boot=50)
    s = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert s["replicates"]["pairs"][0]["combinations"]
    for row in s["leaderboard"]:
        assert row["agent"] in s["decomposition"]
        assert s["decomposition"][row["agent"]]["mismatches"] == 0


def test_no_replicates_no_section(tmp_path, base_traces):
    write_run(tmp_path / "bayes.jsonl", base_traces["bayes"], "bayes")
    write_run(tmp_path / "static.jsonl", base_traces["static"], "static")
    r = build_report(tmp_path, n_boot=50)
    assert r.replicates == {}
    md = (tmp_path / "REPORT.md").read_text(encoding="utf-8")
    assert "Run-to-run" not in md and "primary runs only" not in md


def test_gap_uses_structure_clusters_and_holm_over_llms(run_dir):
    r = build_report(run_dir, n_boot=100, write=False)
    v = {x["agent"]: x for x in r.variants}
    # two classic dice games share one hidden structure
    assert v["fake:alpha"]["clusters_classic"] == 1
    assert v["fake:alpha"]["clusters_perturbed"] >= 4
    assert math.isnan(v["bayes"]["gap_p_holm"])
    llm = [x for a, x in v.items() if ":" in a]
    assert all(x["gap_p_holm"] >= x["gap_p"] for x in llm if math.isfinite(x["gap_p"]))


def test_top_llm_pair_variance(run_dir):
    r = build_report(run_dir, n_boot=100, write=False)
    llms = [row["agent"] for row in r.leaderboard if ":" in row["agent"]]
    top = r.variance["top_llm_pair"]
    assert (top["a"], top["b"]) == tuple(llms[:2])
    assert "#r" not in top["a"] + top["b"]
    assert top["n"] == r.variance["per_agent"][top["a"]]["n"]
    md = (run_dir / "REPORT.md").read_text(encoding="utf-8")
    assert f"`{top['a']}` - `{top['b']}` (top two LLM setups)" in md


def test_effort_figure_names_every_replicate_run(tmp_path, monkeypatch):
    pytest.importorskip("matplotlib")
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    path = Path(__file__).parents[1] / "scripts" / "figures.py"
    if not path.exists():
        pytest.skip("scripts/ is not in the sdist")
    spec = importlib.util.spec_from_file_location("figures", path)
    figures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(figures)
    runs = [{"run": n} for n in (1, 2, 3)]
    setups = [
        {"setup": "claude-cli:claude-opus-5-5@high", "runs": runs},
        {"setup": "claude-cli:claude-haiku-5-5@high", "runs": runs[:2]},
    ]
    note = figures.replicate_note(SimpleNamespace(replicates={"setups": setups}))
    assert "opus high r2/r3" in note and "haiku high r2)" in note
    assert figures.replicate_note(SimpleNamespace(replicates={})) == ""

    # Four replicated setups (the committed core-v1): the subtitle must stay inside the figure.
    names = [f"claude-cli:claude-{m}@high" for m in ("haiku-5-5", "sonnet-5-5", "opus-5-5")]
    names.append("claude-cli:claude-fable-5-1@high")
    row = {"edge_captured": 80.0, "edge_lo": 75.0, "edge_hi": 85.0}
    reps = [{"run": n, "edge_captured": 80.0} for n in (1, 2, 3)]
    report = SimpleNamespace(
        leaderboard=[{"agent": n, **row} for n in names],
        replicates={"setups": [{"setup": n, "runs": reps} for n in names]},
    )
    figs = []
    monkeypatch.setattr(figures, "save", lambda fig, path: figs.append(fig))
    figures.plot_effort(report, tmp_path / "effort")
    fig = figs[0]
    FigureCanvasAgg(fig).draw()
    sub = fig.axes[0]._left_title  # _title() sets the subtitle with loc="left"
    assert "sonnet high r2/r3" in sub.get_text()
    assert sub.get_window_extent().x1 <= fig.bbox.x1
