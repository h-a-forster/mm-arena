"""The ceiling script: the exactly solved miniature and the bracket from a ladder file."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ceiling_v2.py"


def _module():
    spec = importlib.util.spec_from_file_location("ceiling_v2", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_miniature_optimum_dominates_every_policy() -> None:
    res = _module().miniature(rho=0.5, rounds=3, quotes=1, grid=7)
    policies = [k for k in res if k not in ("optimum", "oracle_value_sd")]
    for k in policies:
        assert res["optimum"] >= res[k] - 1e-9, k
    assert res["optimum"] < 100
    assert res["lookahead-w4"] >= res["myopic"] - 1e-9


def test_bracket_reads_a_ladder_file(tmp_path: Path) -> None:
    rows = []
    for s, (o, b, l1) in {
        "a": ((2, 1, 1), (1, 0, 1), (1.5, 0, 1)),
        "b": ((1, 1, 1), (1, 1, 0), (1, 1, 1)),
    }.items():
        for agent, rounds in (("oracle", o), ("bayes", b), ("bayes-lookahead", l1)):
            rows.append({"session": s, "agent": agent, "tier": "mixed", "rounds": list(rounds),
                         "xpnl_alpha": float(sum(rounds))})  # fmt: skip
    path = tmp_path / "h.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    out = _module().bracket(str(path))["mixed"]
    assert out["best_public"] == pytest.approx(100 * 5.5 / 7)
    assert out["best_public_agent"] == "bayes-lookahead"
    assert out["relaxation"] == pytest.approx(100 * (2.5 + 4) / 7)
