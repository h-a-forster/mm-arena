"""Prompt version v2.0, for session suites (suite format 2).

Same structure as core-v1's prompt (``prompt.py``, unchanged): a system prompt with the rules,
a static game segment and a dynamic state segment; every call carries the full state and
nothing depends on earlier turns; the same reply format and parser. The text states the rules
and the objective and nothing else: no strategy hints, no summaries of the history (the
history is shown as raw rows), no mention of the suite's tiers.

Everything is rendered from a ``SessionObservation``, which has no field for the true informed
share or any hidden outcome.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from mmarena.agents.prompt import REPLY_FORMAT, _join, _num, _trade, render_game
from mmarena.sessions import SessionObservation, SessionSpec

PROMPT_VERSION = "v2.0"


def _frac(p: float) -> str:
    return str(Fraction(p).limit_denominator(1000))


def _prior(spec: SessionSpec) -> str:
    alphas = [_num(a) for a in spec.regimes.alpha]
    probs = {_frac(p) for p in spec.regimes.prior}
    if len(probs) == 1:
        return f"{{{', '.join(alphas)}}}, each with probability {probs.pop()}"
    prior = spec.regimes.prior
    pairs = [f"{a} with probability {_frac(p)}" for a, p in zip(alphas, prior, strict=True)]
    return _join(pairs)


def render_system(spec: SessionSpec) -> str:
    game, m = spec.game, spec.game.market
    n_rounds, n_stages, q = spec.rounds, game.n_stages, m.quotes_per_stage
    per_round, total, lim = spec.steps_per_round, spec.n_quotes, m.inventory_limit
    s_stages = "s" if n_stages != 1 else ""
    return f"""You are the market maker in a trading game. You quote a bid and an ask on a \
contract, counterparties trade with you at your prices, and the contract settles at its value. \
The game is played as a session of {n_rounds} rounds against the same population of \
counterparties. Your objective is to maximise your expected total profit over the session.

Rules
- Each round, a new hidden state is drawn as the game description says, independently of \
earlier rounds. A round has {n_stages} stage{s_stages} with {q} quotes per stage, \
{per_round} quotes per round and {total} quotes in the session. Before some stages, part of \
the round's hidden state is revealed to everyone (see the reveal schedule).
- After the last quote of a round, the contract settles. Only its settlement value is shown; \
parts of the hidden state that were not revealed stay hidden. Your position is closed at the \
settlement value and the next round starts with position 0 and cash 0.
- At each quote you post a bid (the price at which you buy) and an ask (the price at which you \
sell). Then exactly one counterparty arrives.
- With probability alpha the counterparty is informed: it knows the settlement value exactly \
and uses it as its valuation. The value of alpha is not disclosed. Before the session it was \
drawn from {_prior(spec)}, independently of the game and of the hidden states, and it is the \
same for every quote of the session.
- Otherwise (probability 1 - alpha) the counterparty is a noise trader. Its valuation is the \
public fair value plus Normal noise with standard deviation {_num(m.noise_scale)}, the same in \
every round. The public fair value is the expected settlement value given all public \
information so far: the game description, this round's revealed values, and every quote, \
trade and settlement of the session.
- The counterparty buys one unit from you at your ask if its valuation is above your ask, sells \
one unit to you at your bid if its valuation is below your bid, and otherwise does not trade. \
Every trade is one unit.
- Prices move to a multiple of {_num(m.tick)}: bids round down, asks round up. A bid above \
the ask is invalid.
- Within a round your position must stay between -{lim} and +{lim}. At +{lim} your bid is \
pulled (you cannot buy); at -{lim} your ask is pulled (you cannot sell). A quote on a pulled \
side is ignored.
- Buying at your bid costs you the bid in cash; selling at your ask pays you the ask. Your \
profit in a round is cash + position x settlement value; your session profit is the sum over \
rounds.
- A reply that cannot be read counts as no quote on either side for that quote.

Reply format
You may reason briefly first. End your reply with exactly one JSON object:
{REPLY_FORMAT}
Use null for a side you do not want to quote."""


def _reveal_line(revealed: list[dict[str, Any]] | tuple[dict[str, Any], ...], stage: int) -> str:
    vals = "; ".join(f"{r['name']} = {_num(r['value'])}" for r in revealed if r["stage"] == stage)
    return f"Revealed before stage {stage + 1}: {vals}"


def _round_rows(
    rows: list[dict[str, Any]], revealed: list[dict[str, Any]] | tuple[dict[str, Any], ...]
) -> list[str]:
    """Raw quote rows of one round, with each reveal placed where it happened."""
    out = ["quote | stage | your bid | your ask | trade"]
    shown: set[int] = set()
    for h in rows:
        stage = h["stage"]
        for s in sorted({r["stage"] for r in revealed if r["stage"] <= stage} - shown):
            out.append(_reveal_line(revealed, s))
            shown.add(s)
        bid = "-" if h["bid"] is None else _num(h["bid"])
        ask = "-" if h["ask"] is None else _num(h["ask"])
        out.append(f"{h['step'] + 1} | {stage + 1} | {bid} | {ask} | {_trade(h)}")
    for s in sorted({r["stage"] for r in revealed} - shown):
        out.append(_reveal_line(revealed, s))
    return out


def render_state(obs: SessionObservation) -> str:
    spec, game, m = obs.spec, obs.game, obs.game.market
    left = obs.quotes_left
    lines = ["Current state"]
    lines.append(
        f"- Round {obs.round + 1} of {spec.rounds}, stage {obs.stage + 1} of {game.n_stages}, "
        f"quote {obs.step + 1} of {spec.steps_per_round} in this round (quote {obs.quote + 1} "
        f"of {spec.n_quotes} in the session; {left} quote{'s' if left != 1 else ''} left "
        f"including this one)."
    )
    if obs.revealed:
        rev = "; ".join(f"{r['name']} = {_num(r['value'])}" for r in obs.revealed)
        lines.append(f"- Revealed this round: {rev}.")
    else:
        lines.append("- Revealed this round: nothing.")
    pos = obs.position
    side = " (long)" if pos > 0 else " (short)" if pos < 0 else ""
    pos_s = f"{pos:+d}" if pos else "0"
    lines.append(
        f"- Your position this round: {pos_s}{side}. Your cash this round: {_num(obs.cash)}."
    )
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
    if not obs.history:
        lines.append("History: no quotes yet.")
    else:
        lines.append("History")
        by_round: dict[int, list[dict[str, Any]]] = {}
        for h in obs.history:
            by_round.setdefault(h["round"], []).append(h)
        for done in obs.settled:
            r = done["round"]
            lines.append("")
            lines.append(f"Round {r + 1}")
            lines += _round_rows(by_round.get(r, []), done["revealed"])
            lines.append(f"Settlement value: {_num(done['value'])}")
        if obs.step > 0 or obs.revealed:
            lines.append("")
            lines.append(f"Round {obs.round + 1} (this round)")
            lines += _round_rows(by_round.get(obs.round, []), obs.revealed)
    lines.append("")
    lines.append(
        f"Post your quote for quote {obs.step + 1} of round {obs.round + 1}. "
        f"End with {REPLY_FORMAT}."
    )
    return "\n".join(lines)


def render_prompt_parts(obs: SessionObservation) -> tuple[str, list[str]]:
    """(system, [static user segment, dynamic user segment])."""
    return render_system(obs.spec), [render_game(obs.game), render_state(obs)]


def render_prompt(obs: SessionObservation) -> tuple[str, str]:
    system, parts = render_prompt_parts(obs)
    return system, "\n\n".join(parts)
