"""Terminal practice mode: a human quotes, then gets an exact debrief against the Bayes quoter.

``play()`` runs one episode with :class:`HumanAgent` and prints :func:`review` of the trace.
``review()`` works on any agent's trace, so it also serves as a plain-text replay viewer.
Output is plain ASCII so it renders in any terminal.
"""

from __future__ import annotations

import json
import math
import random
import re
import textwrap
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from mmarena.agents.base import Observation, Quote
from mmarena.engine import run_episode
from mmarena.games.base import Game
from mmarena.games.families import FAMILIES, make_game

RULE = "-" * 78
HELP = """\
How to quote (one line per step):
  9.5 11.5    bid 9.5, ask 11.5 (bid must not be above ask)
  - 12        no bid, ask 12
  9 -         bid 9, no ask
  - -         no quote this step
  h or ?      this help
  r           reprint the rules
  q           quit the game
Prices are rounded to the tick. A counterparty who buys pays your ask (you go short 1);
one who sells receives your bid (you go long 1)."""


class QuitGame(BaseException):
    """Raised by :class:`HumanAgent` when the player quits.

    Derives from ``BaseException`` so the engine does not score it as an agent crash.
    """


def _ascii(text: str) -> str:
    return text.encode("ascii", "replace").decode("ascii")


def _g(x: float | None) -> str:
    return "-" if x is None else f"{x:g}"


def _decimals(tick: float) -> int:
    s = f"{tick:g}"
    return len(s.split(".")[1]) if "." in s else 0


def _px(x: float | None, d: int) -> str:
    return "-" if x is None else f"{x:.{d}f}"


def _pct(p: float) -> str:
    return f"{100 * p:g}%"


def _stage_reveals(game: dict[str, Any] | Game) -> list[str]:
    """Plain-words reveal schedule, one line per stage boundary."""
    if isinstance(game, Game):
        comps, reveals, qps = game.components, game.reveals, game.market.quotes_per_stage
    else:
        comps, reveals, qps = (
            game["components"],
            game["reveals"],
            game["market"]["quotes_per_stage"],
        )
    lines = []
    for s, group in enumerate(reveals):
        names = ", ".join(comps[c] for c in group)
        lines.append(f"before step {(s + 1) * qps + 1} (stage {s + 2}): {names}")
    shown = {c for g in reveals for c in g}
    hidden = [comps[c] for c in range(len(comps)) if c not in shown]
    if hidden:
        lines.append(f"never revealed before settlement: {', '.join(hidden)}")
    return lines


def rules_text(game: Game) -> str:
    """Game rules and market parameters in plain words. Public information only."""
    m = game.market
    if m.informed_noise > 0:
        informed = (
            f"With probability {_pct(m.alpha)} the counterparty is INFORMED: it sees the "
            f"settlement value plus random noise (sd {_g(m.informed_noise)}), buys if that is "
            "above your ask and sells if it is below your bid."
        )
    else:
        informed = (
            f"With probability {_pct(m.alpha)} the counterparty is INFORMED: it knows the "
            "settlement value, buys if it is above your ask and sells if it is below your bid."
        )
    lines = [
        RULE,
        f"{game.title}  ({game.family} / {game.variant}, seed {game.seed})",
        RULE,
        game.description,
        game.contract,
        f"Possible settlement values range from {_g(game.v_min)} to {_g(game.v_max)}.",
        "",
        "Market:",
        "- You are the market maker. Each step you post a bid and/or an ask; then one "
        "counterparty arrives and may trade 1 unit with you.",
        f"- {informed}",
        f"- Otherwise it is a NOISE trader: it values the contract at the current public fair "
        f"value plus random noise (sd {_g(m.noise_scale)}), buys above your ask, sells below "
        "your bid.",
        f"- Inventory limit {m.inventory_limit}: at +{m.inventory_limit} (long) your bid is "
        f"pulled, at -{m.inventory_limit} (short) your ask is pulled.",
        f"- Prices are rounded to the tick, {_g(m.tick)}.",
        f"- {m.quotes_per_stage} steps per stage, {game.n_stages} stages, "
        f"{game.n_steps} steps in total.",
        "- Revealed to everyone:",
        *(f"    {line}" for line in _stage_reveals(game)),
        "- At the end your P&L is cash + position x settlement value.",
        RULE,
    ]
    out = []
    for line in lines:
        if line.startswith("- ") and len(line) > 78:
            out.append(textwrap.fill(line, 78, subsequent_indent="  "))
        else:
            out.append(line)
    return "\n".join(out)


def _trade_words(h: dict[str, Any]) -> str:
    if h["action"] == "buy":
        return f"they bought 1 at {_g(h['price'])} (you sold)"
    if h["action"] == "sell":
        return f"they sold 1 at {_g(h['price'])} (you bought)"
    return "no trade"


def parse_quote(text: str) -> tuple[float | None, float | None] | str:
    """Parse ``"bid ask"`` with ``-`` for a missing side. Returns the pair or an error message."""
    parts = [p for p in re.split(r"[\s,/]+", text.strip()) if p]
    if len(parts) != 2:
        return "enter two values: bid then ask (use - for no side), or h for help"
    out: list[float | None] = []
    for p in parts:
        if p == "-":
            out.append(None)
            continue
        try:
            x = float(p)
        except ValueError:
            return f"not a number: {p!r}"
        if not math.isfinite(x):
            return f"not a finite number: {p!r}"
        out.append(x)
    bid, ask = out
    if bid is not None and ask is not None and bid > ask:
        return f"crossed quote: bid {_g(bid)} is above ask {_g(ask)}"
    return bid, ask


class HumanAgent:
    """Market maker driven by a person at the terminal."""

    name = "human"

    def __init__(
        self,
        input_fn: Callable[[str], str] = input,
        output_fn: Callable[[str], Any] = print,
        recent: int = 3,
    ) -> None:
        self.input_fn = input_fn
        self.output_fn = output_fn
        self.recent = recent
        self.game: Game | None = None

    def _out(self, text: str) -> None:
        self.output_fn(_ascii(text))

    def reset(self, game: Game) -> None:
        self.game = game
        self._out(rules_text(game))
        self._out(HELP)

    def screen(self, obs: Observation) -> str:
        g = obs.game
        lines = [
            "",
            f"== {g.title} | stage {obs.stage + 1}/{g.n_stages} | "
            f"step {obs.step + 1}/{g.n_steps} ==",
        ]
        if obs.revealed:
            lines.append(
                "Revealed: " + ", ".join(f"{r['name']} = {_g(r['value'])}" for r in obs.revealed)
            )
        else:
            lines.append("Revealed: nothing yet")
        shown = {r["component"] for r in obs.revealed}
        hidden = [n for i, n in enumerate(g.components) if i not in shown]
        lines.append("Hidden:   " + ", ".join(hidden))
        hist = obs.history[-self.recent :]
        if hist:
            lines.append("Recent steps:")
            for h in hist:
                lines.append(
                    f"  step {h['step'] + 1}: you quoted {_g(h['bid'])} / {_g(h['ask'])}"
                    f" -> {_trade_words(h)}"
                )
        side = "long" if obs.position > 0 else "short" if obs.position < 0 else "flat"
        pos = f"{obs.position:+d}" if obs.position else "0"
        lines.append(f"Position: {pos} ({side})   Cash: {obs.cash:+.2f}")
        lim = g.market.inventory_limit
        if obs.bid_allowed and obs.ask_allowed:
            lines.append("You may quote both sides.")
        elif not obs.bid_allowed:
            lines.append(f"Long limit +{lim} reached: ask only (a bid would be pulled).")
        else:
            lines.append(f"Short limit -{lim} reached: bid only (an ask would be pulled).")
        return "\n".join(lines)

    def _ask(self) -> str:
        try:
            return self.input_fn("Quote (bid ask) > ")
        except EOFError:
            raise QuitGame("input closed") from None

    def act(self, obs: Observation) -> Quote:
        self._out(self.screen(obs))
        while True:
            raw = self._ask().strip()
            cmd = raw.lower()
            if cmd in ("q", "quit", "exit"):
                raise QuitGame("player quit")
            if cmd in ("h", "?", "help"):
                self._out(HELP)
                continue
            if cmd in ("r", "rules"):
                self._out(rules_text(obs.game))
                self._out(self.screen(obs))
                continue
            parsed = parse_quote(raw)
            if isinstance(parsed, str):
                self._out(f"  ! {parsed}")
                continue
            bid, ask = parsed
            tick = obs.game.market.tick
            rb = None if bid is None else round(bid / tick) * tick
            ra = None if ask is None else round(ask / tick) * tick
            if rb is not None and ra is not None and rb > ra + 1e-9:
                self._out("  ! crossed after rounding to the tick; widen the quote")
                continue
            if bid is not None and not obs.bid_allowed:
                self._out("  (bid will be pulled: long inventory limit)")
            if ask is not None and not obs.ask_allowed:
                self._out("  (ask will be pulled: short inventory limit)")
            return Quote(bid, ask, {"raw": raw})


# --------------------------------------------------------------------------- review


def _mid(bid: float | None, ask: float | None) -> float | None:
    return None if bid is None or ask is None else (bid + ask) / 2


def _mean(xs: Iterable[float]) -> float | None:
    xs = list(xs)
    return sum(xs) / len(xs) if xs else None


def _coaching(trace: dict[str, Any]) -> list[str]:
    steps = trace["steps"]
    notes: list[str] = []
    eps = 1e-9

    bad = [
        s
        for s in steps
        if (s["bid"] is not None and s["bid"] > s["hi"] + eps)
        or (s["ask"] is not None and s["ask"] < s["lo"] - eps)
    ]
    if bad:
        ex = bad[0]
        notes.append(
            f"{len(bad)} step(s) had a quote that could only lose: e.g. step {ex['t'] + 1} "
            f"quoted {_g(ex['bid'])} / {_g(ex['ask'])} while the value was known to lie in "
            f"[{_g(ex['lo'])}, {_g(ex['hi'])}]. Never bid above the max or offer below the min."
        )

    two = [s for s in steps if s["bid"] is not None and s["ask"] is not None and s["sd"] > eps]
    if two:
        z = _mean((_mid(s["bid"], s["ask"]) - s["mu"]) / s["sd"] for s in two)
        bz = _mean(
            (_mid(s["bayes_bid"], s["bayes_ask"]) - s["mu"]) / s["sd"]
            for s in two
            if s["bayes_bid"] is not None and s["bayes_ask"] is not None
        )
        where = "above" if z > 0 else "below"
        verdict = "a systematic bias" if abs(z) >= 0.25 else "close to centred"
        ref = f"; Bayes mid {bz:+.2f} sd" if bz is not None else ""
        notes.append(
            f"Mid vs fair value: your mid sat {abs(z):.2f} sd {where} the posterior mean on "
            f"average over {len(two)} two-sided steps ({verdict}{ref})."
        )

    both = [s for s in two if s["bayes_bid"] is not None and s["bayes_ask"] is not None]
    if both:
        ys = _mean(s["ask"] - s["bid"] for s in both)
        bs = _mean(s["bayes_ask"] - s["bayes_bid"] for s in both)
        cap = sum(s["capture"] for s in steps)
        adv = sum(s["adverse"] for s in steps)
        if bs and bs > eps:
            r = ys / bs
            word = "too tight" if r < 0.8 else "too wide" if r > 1.25 else "about right"
            notes.append(
                f"Spread: yours averaged {ys:.2f} vs Bayes {bs:.2f} ({r:.2f}x, {word}). "
                f"Expected spread capture {cap:+.2f}, expected adverse-selection cost {adv:.2f}."
            )

    moves = []
    for s, nxt in zip(steps, steps[1:], strict=False):
        if s["action"] is None or nxt["stage"] != s["stage"]:
            continue
        m0, m1 = _mid(s["bid"], s["ask"]), _mid(nxt["bid"], nxt["ask"])
        if m0 is None or m1 is None:
            continue
        sign = 1.0 if s["action"] == "buy" else -1.0
        moves.append((sign * (s["mu_after"] - s["mu"]), sign * (m1 - m0)))
    if moves:
        dmu = _mean(a for a, _ in moves)
        dmid = _mean(b for _, b in moves)
        ratio = f" ({dmid / dmu:.0%} of it)" if dmu and abs(dmu) > eps else ""
        notes.append(
            f"Reaction to fills ({len(moves)} fills followed by a same-stage quote): fair value "
            f"moved {dmu:+.2f} in the trade's direction on average; your mid moved {dmid:+.2f}"
            f"{ratio}. A buy is evidence the value is higher, a sell that it is lower."
        )

    blocked = [s for s in steps if not s["bid_allowed"] or not s["ask_allowed"]]
    if blocked:
        lim = trace["game"]["market"]["inventory_limit"]
        notes.append(
            f"Inventory limit +/-{lim} blocked one side on {len(blocked)} step(s) "
            f"(first at step {blocked[0]['t'] + 1}); skew quotes earlier to stay inside it."
        )

    invalid = [s for s in steps if s["invalid"]]
    empty = [s for s in steps if s["bid"] is None and s["ask"] is None and not s["invalid"]]
    if invalid or empty:
        notes.append(
            f"{len(invalid)} invalid quote(s) and {len(empty)} step(s) with no quote at all; "
            "an empty step earns nothing."
        )

    if steps:
        worst = max(steps, key=lambda s: s["bayes_ev"] - s["ev"])
        gap = worst["bayes_ev"] - worst["ev"]
        if gap > eps:
            notes.append(
                f"Largest single-step gap: step {worst['t'] + 1}, ev {worst['ev']:+.2f} vs Bayes "
                f"{worst['bayes_ev']:+.2f} (you {_g(worst['bid'])} / {_g(worst['ask'])}, Bayes "
                f"{_g(worst['bayes_bid'])} / {_g(worst['bayes_ask'])}, fair value "
                f"{worst['mu']:.2f})."
            )
    return notes[:5]


def review(trace: dict[str, Any]) -> str:
    """Plain-text debrief of one episode trace (any agent)."""
    g = trace["game"]
    d = _decimals(g["market"]["tick"])
    steps = trace.get("steps") or []
    out = [
        RULE,
        f"REVIEW  {g['title']}  ({g['family']} / {g['variant']}, game seed {g['seed']}, "
        f"episode seed {trace['seed']})  agent: {trace['agent']}",
        RULE,
    ]
    if trace.get("status") != "ok":
        out.append(f"Episode did not finish: {trace.get('error')}")
    hidden = ", ".join(f"{k} = {_g(v)}" for k, v in trace["hidden"].items())
    out.append(f"Settlement value: {_g(trace['value'])}   ({hidden})")
    out.append(f"Final position: {trace['position']:+d}")
    if trace.get("status") == "ok":
        bayes = trace["bayes_xpnl_local"]
        out += [
            f"Realized P&L:          {trace['pnl']:+.2f}   (includes luck of the draw)",
            f"Expected P&L (xpnl):   {trace['xpnl']:+.2f}   (exact expectation of your quotes)",
            f"Bayes on same path:    {bayes:+.2f}   (sum of Bayes-optimal step ev)",
        ]
        if bayes > 1e-9:
            out.append(f"Efficiency:            {trace['xpnl'] / bayes:.0%} of Bayes")
    out.append("")
    hdr = (
        f"{'stp':>3} {'st':>2} | {'your bid':>8} {'ask':>6} | {'bayes bid':>9} {'ask':>6} | "
        f"{'fair +/- sd':>14} | {'trade':<14} {'taker':<8} | {'ev':>6} {'bayes':>6}"
    )
    out += [hdr, "-" * len(hdr)]
    reveals = {}
    for r in trace.get("revealed", []):
        reveals.setdefault(r["stage"], []).append(f"{r['name']} = {_g(r['value'])}")
    seen_stage = -1
    for s in steps:
        if s["stage"] != seen_stage:
            seen_stage = s["stage"]
            if seen_stage in reveals:
                out.append(f"    -- revealed: {', '.join(reveals[seen_stage])}")
        if s["invalid"]:
            yours = f"{'invalid:' + s['invalid']:>15}"
        else:
            yb = _px(s["bid"], d) + ("*" if "bid" in s["pulled"] else "")
            ya = _px(s["ask"], d) + ("*" if "ask" in s["pulled"] else "")
            yours = f"{yb:>8} {ya:>6}"
        if s["action"] == "buy":
            trade = f"buy @ {_g(s['price'])}"
        elif s["action"] == "sell":
            trade = f"sell @ {_g(s['price'])}"
        else:
            trade = "none"
        fair = f"{s['mu']:.2f} +/- {s['sd']:.2f}"
        out.append(
            f"{s['t'] + 1:>3} {s['stage'] + 1:>2} | {yours} | {_px(s['bayes_bid'], d):>9} "
            f"{_px(s['bayes_ask'], d):>6} | {fair:>14} | {trade:<14} {s['taker']:<8} | "
            f"{s['ev']:>+6.2f} {s['bayes_ev']:>+6.2f}"
        )
    out.append(
        "buy = they bought at your ask (you sold), sell = they sold at your bid (you bought); "
        "* = pulled by limit."
    )
    if steps:
        out += ["", "Coaching notes:"]
        for i, n in enumerate(_coaching(trace), 1):
            out.append(textwrap.fill(n, 96, initial_indent=f"  {i}. ", subsequent_indent="     "))
    out.append(RULE)
    return _ascii("\n".join(out))


# --------------------------------------------------------------------------- entry point


def play(
    family: str | None = None,
    variant: str = "perturbed",
    seed: int | None = None,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], Any] = print,
    save_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """Play one game in the terminal and print the debrief.

    Picks a random family and seed when not given. Returns the trace, or ``None`` if the player
    quits. With ``save_path`` the trace is appended to that file as one JSON line.
    """
    rng = random.Random()
    family = family or rng.choice(sorted(FAMILIES))
    seed = rng.randrange(10_000) if seed is None else int(seed)
    game = make_game(family, seed, variant)
    output_fn(f"Game: family={family} variant={variant} seed={seed} (use these to replay)")
    agent = HumanAgent(input_fn=input_fn, output_fn=output_fn)
    try:
        trace = run_episode(game, agent, seed)
    except QuitGame:
        output_fn("Game abandoned; nothing scored.")
        return None
    output_fn("")
    output_fn("Game over.")
    output_fn(review(trace))
    if save_path is not None:
        path = Path(save_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(trace) + "\n")
        output_fn(f"Trace appended to {path.as_posix()}")
    return trace
