from __future__ import annotations

import itertools
import json

import pytest

from mmarena.agents.baselines import BASELINES
from mmarena.engine import run_episode
from mmarena.games.families import FAMILIES, make_game
from mmarena.play import HumanAgent, QuitGame, parse_quote, play, review


def scripted(lines, tail="9 12"):
    it = itertools.chain(lines, itertools.repeat(tail))
    prompts = []

    def input_fn(prompt=""):
        prompts.append(prompt)
        return next(it)

    input_fn.prompts = prompts
    return input_fn


def test_parse_quote():
    assert parse_quote("9.5 11.5") == (9.5, 11.5)
    assert parse_quote("- 12") == (None, 12.0)
    assert parse_quote("9 -") == (9.0, None)
    assert parse_quote("9.5, 11.5") == (9.5, 11.5)
    assert isinstance(parse_quote("12 9"), str)
    assert isinstance(parse_quote("abc 3"), str)
    assert isinstance(parse_quote("nan 3"), str)
    assert isinstance(parse_quote("9"), str)


def test_full_scripted_game(tmp_path):
    out: list[str] = []
    inp = scripted(["abc", "abc 3", "12 9", "h", "?", "r", "- 12", "9 -", "", "1 2 3"])
    save = tmp_path / "traces.jsonl"
    trace = play("dice", "classic", 7, input_fn=inp, output_fn=out.append, save_path=save)
    game = make_game("dice", 7, "classic")
    assert trace is not None and trace["status"] == "ok"
    assert trace["agent"] == "human"
    steps = trace["steps"]
    assert len(steps) == game.n_steps
    assert steps[0]["bid_quoted"] is None and steps[0]["ask_quoted"] == 12.0
    assert steps[1]["bid_quoted"] == 9.0 and steps[1]["ask_quoted"] is None
    assert all(s["invalid"] is None for s in steps)
    text = "\n".join(out)
    assert "seed=7" in text
    assert text.count("How to quote") >= 3  # shown at start, plus h and ?
    assert "crossed quote" in text and "not a number" in text
    game_part, review_part = text.split("Game over.")
    assert "Bayes" not in game_part and "fair +/-" not in game_part
    assert "REVIEW" in review_part and "Coaching notes:" in review_part
    assert text.isascii()
    saved = [json.loads(line) for line in save.read_text().splitlines()]
    assert len(saved) == 1 and saved[0]["xpnl"] == pytest.approx(trace["xpnl"])


def test_quit_and_eof():
    out: list[str] = []
    assert play("coin", "classic", 1, input_fn=scripted(["h", "q"]), output_fn=out.append) is None
    assert "abandoned" in out[-1]

    def eof(prompt=""):
        raise EOFError

    assert play("urn", "perturbed", 2, input_fn=eof, output_fn=out.append) is None
    agent = HumanAgent(input_fn=scripted(["quit"]), output_fn=lambda s: None)
    with pytest.raises(QuitGame):
        run_episode(make_game("dice", 1, "classic"), agent, 1)


def test_random_pick():
    trace = play(input_fn=scripted([]), output_fn=lambda s: None)
    assert trace is not None and trace["game"]["family"] in FAMILIES


@pytest.mark.parametrize("family", sorted(FAMILIES))
def test_review_baselines(family):
    for variant in ("classic", "perturbed"):
        game = make_game(family, 3, variant)
        for name, make in BASELINES.items():
            trace = run_episode(game, make(), 3)
            text = review(trace)
            assert text.isascii()
            assert "Settlement value" in text and name in text
            assert text.count("\n") > game.n_steps
            assert "Coaching notes:" in text


def test_review_error_trace():
    trace = run_episode(make_game("dice", 1, "classic"), BASELINES["static"](), 1)
    trace.update(status="error", error="infra: boom", pnl=None, xpnl=None, steps=[])
    text = review(trace)
    assert "did not finish" in text
