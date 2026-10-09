"""Regressions for issues found in review: parsing, error classification, edge values."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from mmarena.agents.base import InfraError, Quote
from mmarena.agents.llm import LLMAgent
from mmarena.agents.prompt import parse_quote
from mmarena.cli import main
from mmarena.engine import run_episode
from mmarena.games import make_game
from mmarena.metrics import load_episodes
from mmarena.providers.base import TransientError


def test_parser_takes_the_last_answer() -> None:
    assert parse_quote('Format is {"bid": 1, "ask": 2}. My answer: {bid: 10, ask: 12}') == (10, 12)
    assert parse_quote('{"bid": 10, "ask": 12, "note": {"bid": 1, "ask": 2}}') == (10, 12)
    assert parse_quote('{bid: 1, ask: 2} then {"bid": 3, "ask": null}') == (3, None)


class _Boom:
    name, model, options = "boom", "m", {}

    def complete(self, system, user, *, max_tokens):
        raise OSError(28, "No space left on device")


def test_unexpected_provider_error_is_infra() -> None:
    g = make_game("dice", 1, "classic")
    tr = run_episode(g, LLMAgent(_Boom()), 0)
    assert tr["status"] == "error" and "No space left" in tr["error"]


def test_openrouter_finish_reason_error_is_transient() -> None:
    from mmarena.providers.openai import OpenAIProvider

    calls = []

    def create(**kw):
        calls.append(kw)
        return SimpleNamespace(
            choices=[SimpleNamespace(finish_reason="error", message=SimpleNamespace(content=""))],
            usage=None,
            model="m",
        )

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    prov = OpenAIProvider("m", base_url="http://x/v1", retries=2, client=client)
    with pytest.raises((TransientError, InfraError)):
        prov.complete("s", "u", max_tokens=10)
    assert len(calls) == 2  # retried, not returned as the model's answer


class _Huge:
    name = "huge"

    def reset(self, game):
        pass

    def act(self, obs):
        return Quote(1.0, 1e308)


def test_huge_quote_is_nonfinite_not_a_crash() -> None:
    tr = run_episode(make_game("dice", 1, "classic"), _Huge(), 0)
    assert tr["status"] == "ok"
    assert tr["steps"][0]["invalid"] == "nonfinite"
    assert tr["steps"][0]["bid"] is None and tr["steps"][0]["ask"] is None


def test_mid_z_skips_collapsed_posterior() -> None:
    tr = run_episode(make_game("dice", 1, "classic"), _Huge(), 0)
    for s in tr["steps"]:
        s.update(bid=s["mu"] - 1, ask=s["mu"] + 1, invalid=None, sd=1e-15, hi=5.0, lo=5.0)
    m = load_episodes({"x": [tr]})["x"].episodes[0]
    assert m.z_n == 0


def test_cli_name_needs_single_agent(tmp_path) -> None:
    with pytest.raises(SystemExit, match="single"):
        main(
            [
                "run",
                "--agent",
                "bayes",
                "--agent",
                "static",
                "--name",
                "x",
                "--suite",
                "smoke",
                "--out",
                str(tmp_path),
            ]
        )
