"""Tools written for core-v1 refuse session suites and traces instead of misreading them."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from mmarena.cli import main
from mmarena.sessions import suite_hash
from mmarena.suite import SUITE_DIR, load_suite

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def session_run(tmp_path_factory: pytest.TempPathFactory) -> Path:
    d = tmp_path_factory.mktemp("v2run")
    assert main(["run", "--agent", "static", "--suite", "smoke-v2", "--out", str(d)]) == 0
    return d


def test_show_refuses_session_traces(session_run: Path) -> None:
    with pytest.raises(SystemExit, match="session traces"):
        main(["show", str(session_run / "static.jsonl")])


def test_figures_refuse_session_runs(session_run: Path, tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    with pytest.raises(SystemExit, match="session traces"):
        _script("figures").main(str(session_run), str(tmp_path))


def test_open_weight_refuses_session_suites(monkeypatch: pytest.MonkeyPatch) -> None:
    args = ["open_weight.py", "--suite", "smoke-v2", "--base-url", "http://x", "--out", "x"]
    monkeypatch.setattr(sys, "argv", args)
    with pytest.raises(SystemExit, match="session suite"):
        _script("open_weight").main()


def test_headroom_v1_refuses_session_suites(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["headroom.py", "--suite", "smoke-v2"])
    with pytest.raises(SystemExit, match="session suite"):
        _script("headroom").main()


def test_ladder_and_tuning_scripts_default_to_the_released_tiers() -> None:
    core, tight = dict(load_suite("core-v2").tiers), dict(load_suite("tight-v2").tiers)
    ladder = _script("headroom_v2")
    assert ladder.parse_tiers(ladder.DEFAULT_TIERS) == {**core, **tight}
    tune = _script("tune_v2")
    assert tune.parse_tiers(tune.DEFAULT_TIERS) == core


def test_run_expands_baselines_to_every_reference_quoter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mmarena.agents.baselines import BASELINES
    from mmarena.agents.session_baselines import SESSION_BASELINES

    played: list[str] = []
    monkeypatch.setattr(
        "mmarena.runner.run_suite", lambda suite, make, out, **kw: played.append(make().name) or []
    )
    out = str(tmp_path)
    assert main(["run", "--agent", "baselines", "--suite", "smoke-v2", "--out", out]) == 0
    assert played == list(SESSION_BASELINES)
    played.clear()
    assert main(["run", "--agent", "baselines", "--suite", "smoke", "--out", out]) == 0
    assert played == list(BASELINES)
    with pytest.raises(SystemExit, match="single --agent"):
        main(["run", "--agent", "baselines", "--name", "x", "--suite", "smoke-v2", "--out", out])


def test_suite_hash_command(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["suite-hash", "smoke-v2"]) == 0
    out = capsys.readouterr().out
    assert out.split()[0] == suite_hash(SUITE_DIR / "smoke-v2.toml")
