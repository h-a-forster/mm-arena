"""Prompt rendering and reply parsing for LLM market makers.

Every call carries the full state; nothing depends on earlier turns. The system prompt and the
first user segment (game, contract, reveal schedule) are fixed for a game, so providers with
prompt caching reuse them across steps. The second user segment holds the current state.
The wording states the rules and the objective and nothing else: no strategy hints.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any

from mmarena.agents.base import AgentError, Observation
from mmarena.games.base import Game

REPLY_FORMAT = '{"bid": <number or null>, "ask": <number or null>}'


def _num(x: float) -> str:
    """Compact number: no float noise, no trailing zeros."""
    x = round(float(x), 6)
    if x == 0:
        x = 0.0  # no "-0"
    return f"{x:.10g}"


def _join(names: list[str]) -> str:
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def render_system(game: Game) -> str:
    m = game.market
    n_stages, q, n = game.n_stages, m.quotes_per_stage, game.n_steps
    lim = m.inventory_limit
    s_stages = "s" if n_stages != 1 else ""
    s_quotes = "s" if q != 1 else ""
    if m.informed_noise > 0:
        informed = (
            f"it observes the settlement value plus Normal noise with standard deviation "
            f"{_num(m.informed_noise)}, and uses that signal as its valuation"
        )
    else:
        informed = "it knows the settlement value exactly and uses it as its valuation"
    return f"""You are the market maker in a trading game. You quote a bid and an ask on one \
contract, counterparties trade with you at your prices, and at the end the contract settles at \
its value. Your objective is to maximise your expected profit at settlement.

Rules
- The game has {n_stages} stage{s_stages} with {q} quote{s_quotes} per stage, {n} quotes \
in total. Before some stages, part of the hidden state is revealed to everyone \
(see the reveal schedule).
- At each quote you post a bid (the price at which you buy) and an ask (the price at which you \
sell). Then exactly one counterparty arrives.
- With probability {_num(m.alpha)} the counterparty is informed: {informed}.
- Otherwise (probability {_num(1 - m.alpha)}) it is a noise trader. Its valuation is the public \
fair value plus Normal noise with standard deviation {_num(m.noise_scale)}. The public fair value \
is the expected settlement value given all public information so far: the game description, the \
revealed values and the trading history.
- The counterparty buys one unit from you at your ask if its valuation is above your ask, sells \
one unit to you at your bid if its valuation is below your bid, and otherwise does not trade. \
Every trade is one unit.
- Prices move to a multiple of {_num(m.tick)}: bids round down, asks round up. A bid above \
the ask is invalid.
- Your position must stay between -{lim} and +{lim}. At +{lim} your bid is pulled (you cannot \
buy); at -{lim} your ask is pulled (you cannot sell). A quote on a pulled side is ignored.
- Buying at your bid costs you the bid in cash; selling at your ask pays you the ask. At \
settlement your profit is cash + position x settlement value.
- A reply that cannot be read counts as no quote on either side for that step.

Reply format
You may reason briefly first. End your reply with exactly one JSON object:
{REPLY_FORMAT}
Use null for a side you do not want to quote."""


def render_game(game: Game) -> str:
    lines = [f"Game: {game.title}", game.description.strip(), f"Contract: {game.contract}", ""]
    lines.append("Reveal schedule")
    shown: set[int] = set()
    for s, group in enumerate(game.reveals):
        names = [game.components[c] for c in group]
        shown.update(group)
        verb = "is" if len(names) == 1 else "are"
        lines.append(f"- Before stage {s + 2}: {_join(names)} {verb} revealed.")
    hidden = [c for i, c in enumerate(game.components) if i not in shown]
    if not game.reveals:
        lines.append("- Nothing is revealed before settlement.")
    elif hidden:
        lines.append(f"- Not revealed before settlement: {_join(hidden)}.")
    return "\n".join(lines)


def _trade(h: dict[str, Any]) -> str:
    if h["action"] == "buy":
        return f"they bought at your ask ({_num(h['price'])})"
    if h["action"] == "sell":
        return f"they sold at your bid ({_num(h['price'])})"
    return "none"


def render_state(obs: Observation) -> str:
    game = obs.game
    m = game.market
    lines = ["Current state"]
    lines.append(
        f"- Stage {obs.stage + 1} of {game.n_stages}, quote {obs.step + 1} of {game.n_steps} "
        f"({obs.steps_left} quote{'s' if obs.steps_left != 1 else ''} left including this one)."
    )
    if obs.revealed:
        rev = "; ".join(f"{r['name']} = {_num(r['value'])}" for r in obs.revealed)
        lines.append(f"- Revealed so far: {rev}.")
    else:
        lines.append("- Revealed so far: nothing.")
    pos = obs.position
    side = " (long)" if pos > 0 else " (short)" if pos < 0 else ""
    pos_s = f"{pos:+d}" if pos else "0"
    lines.append(f"- Your position: {pos_s}{side}. Your cash: {_num(obs.cash)}.")
    lim = m.inventory_limit
    if obs.bid_allowed and obs.ask_allowed:
        lines.append("- Allowed this quote: bid and ask.")
    elif obs.ask_allowed:
        lines.append(f"- Allowed this quote: ask only (your position is +{lim}; bid pulled).")
    elif obs.bid_allowed:
        lines.append(f"- Allowed this quote: bid only (your position is -{lim}; ask pulled).")
    else:
        lines.append("- Allowed this quote: none.")
    lines.append("")
    if obs.history:
        lines.append("History")
        lines.append("quote | stage | your bid | your ask | trade")
        for h in obs.history:
            bid = "-" if h["bid"] is None else _num(h["bid"])
            ask = "-" if h["ask"] is None else _num(h["ask"])
            lines.append(f"{h['step'] + 1} | {h['stage'] + 1} | {bid} | {ask} | {_trade(h)}")
    else:
        lines.append("History: no quotes yet.")
    lines.append("")
    lines.append(f"Post your quote for quote {obs.step + 1}. End with {REPLY_FORMAT}.")
    return "\n".join(lines)


def render_prompt_parts(obs: Observation) -> tuple[str, list[str]]:
    """(system, [static user segment, dynamic user segment])."""
    return render_system(obs.game), [render_game(obs.game), render_state(obs)]


def render_prompt(obs: Observation) -> tuple[str, str]:
    """(system, user) for one quoting step."""
    system, parts = render_prompt_parts(obs)
    return system, "\n\n".join(parts)


def render_repair(user: str, reply: str, problem: str, max_chars: int = 1500) -> str:
    """The original user message plus a note on why the previous reply was rejected."""
    shown = reply if len(reply) <= max_chars else "..." + reply[-max_chars:]
    return (
        f"{user}\n\nYour previous reply could not be used: {problem}\n"
        f"Previous reply:\n<<<\n{shown}\n>>>\n"
        f"Reply again. End with exactly one JSON object: {REPLY_FORMAT}"
    )


# --------------------------------------------------------------------------- parsing

_KEY_RE = re.compile(r"""["']?(bid|ask)["']?\s*:\s*("[^"]*"|'[^']*'|[^,}\s]+)""", re.IGNORECASE)


def _side(v: Any, side: str) -> float | None:
    if v is None:
        return None
    if isinstance(v, bool):
        raise AgentError(f"{side} must be a number or null, got {v!r}")
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip().strip("'\"").strip()
        if s.lower() in ("null", "none", ""):
            return None
        try:
            return float(s.replace(",", ""))
        except ValueError:
            pass
    raise AgentError(f"{side} must be a number or null, got {v!r}")


def _candidates(text: str) -> list[dict[str, Any]]:
    """Every JSON object in ``text`` (outermost first, in order of appearance)."""
    decoder = json.JSONDecoder()
    found: list[dict[str, Any]] = []
    i = text.find("{")
    while i >= 0:
        try:
            obj, end = decoder.raw_decode(text, i)
        except ValueError:
            obj, end = None, i + 1
        if isinstance(obj, dict):
            found.append(obj)
            # Nested objects inside this one are reported too, after it.
            found.extend(_candidates(text[i + 1 : end - 1]))
        i = text.find("{", end if isinstance(obj, dict) else i + 1)
    return found


def _loose(text: str) -> dict[str, Any] | None:
    """Last brace group with bid and ask keys, read leniently (unquoted keys, None, etc.)."""
    for chunk in reversed(re.findall(r"\{[^{}]*\}", text)):
        pairs = {k.lower(): v for k, v in _KEY_RE.findall(chunk)}
        if "bid" in pairs and "ask" in pairs:
            return pairs
    return None


def parse_quote(text: str) -> tuple[float | None, float | None]:
    """Read ``(bid, ask)`` from the last JSON object in ``text`` that has both keys.

    Numbers and numeric strings are accepted; null means no quote. Raises AgentError.
    """
    if not text or not text.strip():
        raise AgentError("empty reply")
    objs = [o for o in _candidates(text) if "bid" in o and "ask" in o]
    obj: dict[str, Any] | None = objs[-1] if objs else None
    if obj is None:
        obj = _loose(text)
    if obj is None:
        raise AgentError(f"no JSON object with 'bid' and 'ask' keys found; expected {REPLY_FORMAT}")
    bid, ask = _side(obj["bid"], "bid"), _side(obj["ask"], "ask")
    for side, v in (("bid", bid), ("ask", ask)):
        if v is not None and not math.isfinite(v):
            raise AgentError(f"{side} is not a finite number")
    return bid, ask
