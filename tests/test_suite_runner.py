"""Suites and the resumable runner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mmarena.agents.base import InfraError, Quote
from mmarena.agents.baselines import StaticAgent
from mmarena.runner import read_traces, run_suite
from mmarena.suite import Block, Suite, builtin_suites, load_suite

EXPECTED = {"smoke": 5, "core-v1": 120, "full-v1": 480}


def test_builtin_suites_load() -> None:
    assert set(EXPECTED) <= set(builtin_suites())
    for name, n in EXPECTED.items():
        s = load_suite(name)
        assert s.name == name
        eps = s.episodes_list()
        assert len(eps) == n == sum(b.games for b in s.blocks) * s.episodes
        if name != "smoke":
            assert f"({n} episodes)" in s.description


@pytest.mark.parametrize("name", ["core-v1", "full-v1"])
def test_builtin_suites_have_unique_episodes(name: str) -> None:
    eps = load_suite(name).episodes_list()
    keys = [(g.id, s) for g, s in eps]
    assert len(set(keys)) == len(keys)


def test_load_suite_by_path_and_errors(tmp_path: Path) -> None:
    p = tmp_path / "mine.toml"
    p.write_text(
        'name = "mine"\nepisodes = 2\n[[block]]\nfamily = "coin"\nvariant = "classic"\n'
        'games = 1\nseed = 3\n[[block]]\nfamily = "urn"\ngames = 2\nseed = 10\n',
        encoding="utf-8",
    )
    s = load_suite(p)
    assert s.name == "mine" and s.episodes == 2
    assert s.blocks[1] == Block("urn", "perturbed", 2, 10)
    eps = s.episodes_list()
    assert [(g.family, g.seed, e) for g, e in eps] == [
        ("coin", 3, 0),
        ("coin", 3, 1),
        ("urn", 10, 0),
        ("urn", 10, 1),
        ("urn", 11, 0),
        ("urn", 11, 1),
    ]
    with pytest.raises(FileNotFoundError):
        load_suite("no-such-suite")
    bad = tmp_path / "bad.toml"
    bad.write_text('[[block]]\nfamily = "poker"\n', encoding="utf-8")
    with pytest.raises(ValueError):
        load_suite(bad)
    bad.write_text('[[block]]\nfamily = "dice"\nvariant = "odd"\n', encoding="utf-8")
    with pytest.raises(ValueError):
        load_suite(bad)
    bad.write_text('name = "empty"\n', encoding="utf-8")
    with pytest.raises(ValueError):
        load_suite(bad)


def _suite() -> Suite:
    return Suite(
        name="t",
        description="",
        episodes=2,
        blocks=(Block("coin", "perturbed", 1, 8000), Block("urn", "perturbed", 1, 9000)),
    )


class Flaky:
    """Raises InfraError on urn games, otherwise quotes like the static agent."""

    name = "flaky"

    def reset(self, game) -> None:
        self.game = game
        self.inner = StaticAgent()

    def act(self, obs) -> Quote:
        if self.game.family == "urn":
            raise InfraError("outage")
        return self.inner.act(obs)


def test_run_suite_writes_jsonl(tmp_path: Path) -> None:
    out = tmp_path / "sub" / "run.jsonl"
    seen = []
    res = run_suite(_suite(), StaticAgent, out, on_episode=lambda t, i, n: seen.append((i, n)))
    assert len(res) == 4 and seen[-1] == (4, 4)
    traces = read_traces(out)
    assert len(traces) == 4
    assert all(t["suite"] == "t" and t["status"] == "ok" for t in traces)
    assert {(t["game"]["family"], t["seed"]) for t in traces} == {
        ("coin", 0),
        ("coin", 1),
        ("urn", 0),
        ("urn", 1),
    }
    # resume: nothing left to do
    assert run_suite(_suite(), StaticAgent, out) == []
    assert len(read_traces(out)) == 4
    # no resume: file replaced
    assert len(run_suite(_suite(), StaticAgent, out, resume=False)) == 4
    assert len(read_traces(out)) == 4


def test_resume_retries_errors(tmp_path: Path) -> None:
    out = tmp_path / "run.jsonl"
    res = run_suite(_suite(), Flaky, out)
    assert sorted(t["status"] for t in res) == ["error", "error", "ok", "ok"]
    res2 = run_suite(_suite(), StaticAgent, out)
    assert len(res2) == 2
    assert all(t["game"]["family"] == "urn" and t["status"] == "ok" for t in res2)
    lines = read_traces(out)
    assert len(lines) == 6
    last_ok = {(t["game"]["id"], t["seed"]): t for t in lines if t["status"] == "ok"}
    assert len(last_ok) == 4


def test_parallel_workers_match_serial(tmp_path: Path) -> None:
    a = run_suite(_suite(), StaticAgent, tmp_path / "a.jsonl", workers=1)
    b = run_suite(_suite(), StaticAgent, tmp_path / "b.jsonl", workers=3)

    def key(t):
        return (t["game"]["id"], t["seed"])

    strip = [
        {k: v for k, v in t.items() if k != "steps"} | {"pnls": [s["cash"] for s in t["steps"]]}
        for t in sorted(a, key=key)
    ]
    strip_b = [
        {k: v for k, v in t.items() if k != "steps"} | {"pnls": [s["cash"] for s in t["steps"]]}
        for t in sorted(b, key=key)
    ]
    assert strip == strip_b


def _truncate_last_line(out: Path) -> None:
    raw = out.read_bytes()
    lines = raw.splitlines(keepends=True)
    out.write_bytes(b"".join(lines[:-1]) + lines[-1][: len(lines[-1]) // 2])


def test_read_traces_tolerates_truncated_last_line(tmp_path: Path) -> None:
    out = tmp_path / "run.jsonl"
    run_suite(_suite(), StaticAgent, out)
    _truncate_last_line(out)
    assert len(read_traces(out)) == 3
    assert read_traces(tmp_path / "missing.jsonl") == []


def test_resume_reruns_truncated_episode(tmp_path: Path) -> None:
    out = tmp_path / "run.jsonl"
    run_suite(_suite(), StaticAgent, out)
    _truncate_last_line(out)
    res = run_suite(_suite(), StaticAgent, out)
    assert len(res) == 1 and res[0]["status"] == "ok"


def test_resume_after_truncation_keeps_every_episode(tmp_path: Path) -> None:
    out = tmp_path / "run.jsonl"
    run_suite(_suite(), StaticAgent, out)
    _truncate_last_line(out)
    run_suite(_suite(), StaticAgent, out)
    keys = {(t["game"]["id"], t["seed"]) for t in read_traces(out) if t["status"] == "ok"}
    assert len(keys) == 4


def test_traces_round_trip_json(tmp_path: Path) -> None:
    out = tmp_path / "run.jsonl"
    run_suite(_suite(), StaticAgent, out)
    for line in out.read_text(encoding="utf-8").splitlines():
        t = json.loads(line)
        assert json.loads(json.dumps(t, allow_nan=False)) == t
