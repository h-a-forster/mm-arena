"""Estimated ceiling for a quoter that does not know the informed share.

    uv run python scripts/ceiling_v2.py bracket tmp/headroom_v2.jsonl
    uv run python scripts/ceiling_v2.py miniature --rho 0.5 [--rounds 6] [--quotes 2] [--grid 15]

``bracket`` reads a ``scripts/headroom_v2.py`` output and prints, per tier, the bracket of the
best score a public quoter (one that has to learn the informed share) can reach, as a share of
the known-regime oracle:

- from below, the best public quoter in the file;
- from above, a relaxation: tell every quoter the informed share for free after round 1. No
  public quoter can beat "best public profit in round 1, the oracle's afterwards". The best
  round-1 profit is taken over the quoters in the file, so the bound is an estimate.

``miniature`` solves a small version of the game exactly by dynamic programming and prints the
Bayes-optimal policy's share of the oracle next to the myopic learner, fixed guesses and
lookahead with weights 1, 4 and the number of quotes left. Game: two four-sided dice, contract
on the sum, the first die revealed half-way through each round, ``rounds`` rounds of
``2 x quotes`` quotes, the settlement shown after each round, informed shares {0.05, 0.5, 0.9}
with a flat prior, noise scale ``rho`` x prior sd: the suite's fill model and scoring. Quotes
are symmetric tick offsets from the public mean (or no quote); every policy, the oracle
included, uses that menu. Within a round the tree of fills, the reveal and the settlement is
expanded exactly; between rounds the value is interpolated on a grid of beliefs over the
informed share (``--grid`` points per axis, denser near 0 and 1). On one core the tight tier
(rho 0.5) takes about 15 minutes.

In the miniature the best lookahead variant is within 0 to 2 points of the optimum on every
tier; the ceiling estimate in ``mmarena.session_report.CEILING`` therefore sits just above the
suite's best lookahead variant, inside the bracket.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

AL = np.array([0.05, 0.5, 0.9])
K = 3


def Phi(x):  # noqa: N802 - the normal CDF
    """Normal CDF, vectorised (Abramowitz-Stegun 7.1.26, absolute error below 1.5e-7)."""
    x = np.asarray(x, dtype=float)
    z = np.abs(x) / np.sqrt(2.0)
    t = 1.0 / (1.0 + 0.3275911 * z)
    y = 1.0 - (
        ((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592
    ) * t * np.exp(-z * z)
    return 0.5 * (1.0 + np.sign(x) * y)


class Miniature:
    def __init__(self, rho, q, rounds, sym=False, faces=4, tick=0.5, grid=None, alphas=AL):
        self.q, self.R, self.tick = q, rounds, tick
        self.al = np.asarray(alphas, dtype=float)
        d1, d2 = np.meshgrid(np.arange(1, faces + 1), np.arange(1, faces + 1), indexing="ij")
        self.Vo = (d1 + d2).ravel().astype(float)
        self.grp = (d1 - 1).ravel()
        self.ng = faces
        self.O = len(self.Vo)
        self.p0 = np.full(self.O, 1.0 / self.O)
        self.levels = np.unique(self.Vo)
        self.sd = float(np.sqrt(self.p0 @ (self.Vo - self.p0 @ self.Vo) ** 2))
        self.s = rho * self.sd
        J = int(min(max(np.ceil(2.5 * self.s / tick), 3), 6))
        offs = list(range(J))
        if sym:
            acts = [(j, j) for j in offs] + [(-1, -1)]
        else:
            acts = [(b, a) for b in [-1, *offs] for a in [-1, *offs]]
        self.JB = np.array([a[0] for a in acts])
        self.JA = np.array([a[1] for a in acts])
        self.A = len(acts)
        self.GU = np.array(
            grid
            if grid is not None
            else [0, 0.02, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.98, 1.0]
        )

    # ---- primitives
    def root(self, w):
        """Round-start joint weights for alpha beliefs w [N, K]."""
        return w[:, :, None] * self.p0[None, None, :]

    def expand(self, P, jb, ja):
        Vo, al, tick = self.Vo, self.al, self.tick
        mass = P.sum(axis=(1, 2))
        live = mass > 1e-13
        P = P * live[:, None, None]  # branches of probability ~0 contribute nothing
        mu = np.where(live, (P.sum(axis=1) @ Vo) / np.where(live, mass, 1.0), float(self.p0 @ Vo))
        ha, hb = ja >= 0, jb >= 0
        ask = np.ceil(mu / tick - 1e-9) * tick + ja * tick
        bid = np.floor(mu / tick + 1e-9) * tick - jb * tick
        nb = Phi((mu - ask) / self.s) * ha
        ns = Phi((bid - mu) / self.s) * hb
        ib = (Vo[None, :] > ask[:, None]) & ha[:, None]
        isl = (Vo[None, :] < bid[:, None]) & hb[:, None]
        pb = al[None, :, None] * ib[:, None, :] + (1 - al)[None, :, None] * nb[:, None, None]
        ps = al[None, :, None] * isl[:, None, :] + (1 - al)[None, :, None] * ns[:, None, None]
        Pb, Ps = P * pb, P * ps
        Pn = P - Pb - Ps
        rk = (
            Pb * (ask[:, None, None] - Vo[None, None, :])
            + Ps * (Vo[None, None, :] - bid[:, None, None])
        ).sum(axis=2)
        return Pb, Ps, Pn, rk

    def tile(self, P):
        n = len(P)
        Pt = np.broadcast_to(P[None], (self.A, *P.shape)).reshape(self.A * n, K, self.O)
        return Pt, np.repeat(self.JB, n), np.repeat(self.JA, n)

    def interp(self, grid, w):
        """Bilinear in (u, v) = (w0, w1 / (1 - w0)); grid [..., G, G]; w [N, K] -> [..., N]."""
        GU = self.GU
        u = np.clip(w[:, 0], 0.0, 1.0)
        rest = 1.0 - u
        v = np.where(rest > 1e-12, w[:, 1] / np.where(rest > 1e-12, rest, 1.0), 0.0)
        v = np.clip(v, 0.0, 1.0)

        def loc(x):
            i = np.clip(np.searchsorted(GU, x, side="right") - 1, 0, len(GU) - 2)
            return i, (x - GU[i]) / (GU[i + 1] - GU[i])

        iu, fu = loc(u)
        iv, fv = loc(v)
        return (
            grid[..., iu, iv] * (1 - fu) * (1 - fv)
            + grid[..., iu + 1, iv] * fu * (1 - fv)
            + grid[..., iu, iv + 1] * (1 - fu) * fv
            + grid[..., iu + 1, iv + 1] * fu * fv
        )

    def settle(self, P):
        """Yield (mass [N], alpha belief [N, K]) per settlement value."""
        for v in self.levels:
            wk = P[:, :, self.Vo == v].sum(axis=2)
            m = wk.sum(axis=1)
            live = m > 1e-13
            yield m * live, np.where(live[:, None], wk / np.where(live, m, 1.0)[:, None], 1.0 / K)

    def grid_beliefs(self):
        U, Vv = np.meshgrid(self.GU, self.GU, indexing="ij")
        u, v = U.ravel(), Vv.ravel()
        return np.stack([u, (1 - u) * v, (1 - u) * (1 - v)], axis=1)

    # ---- optimum
    def opt_stage(self, P, t, Vn):
        if t == 2 * self.q:
            if Vn is None:
                return np.zeros(len(P))
            return sum(m * self.interp(Vn, w) for m, w in self.settle(P))
        if t == self.q:
            return sum(
                self.opt_quote(P * (self.grp == g)[None, None, :], t, Vn) for g in range(self.ng)
            )
        return self.opt_quote(P, t, Vn)

    def opt_quote(self, P, t, Vn, argmax=False):
        n = len(P)
        Pt, jb, ja = self.tile(P)
        Pb, Ps, Pn, rk = self.expand(Pt, jb, ja)
        v = rk.sum(axis=1)
        del Pt
        for ch in (Pb, Ps, Pn):
            v = v + self.opt_stage(ch, t + 1, Vn)
        v = v.reshape(self.A, n)
        return v.argmax(axis=0) if argmax else v.max(axis=0)

    # ---- policy evaluation (value by alpha row)
    def myopic_best(self, P):
        n = len(P)
        Pt, jb, ja = self.tile(P)
        rk = self.expand(Pt, jb, ja)[3]
        return rk.sum(axis=1).reshape(self.A, n).max(axis=0)

    def choose(self, pol, P, t, r, M0):
        n = len(P)
        Pt, jb, ja = self.tile(P)
        Pb, Ps, Pn, rk = self.expand(Pt, jb, ja)
        kind = pol[0]
        if kind == "oracle":
            score = rk[:, pol[1]]
        elif kind == "myopic":
            score = rk.sum(axis=1)
        elif kind == "fixed":  # one alpha assumed for pricing: weights collapsed on row pol[1]
            score = rk[:, pol[1]]
        else:  # lookahead with weight lam on the next quote's myopic value
            left = (self.R - 1 - r) * 2 * self.q + (2 * self.q - 1 - t)
            lam = float(left) if pol[1] == "R" else min(float(pol[1]), float(left))
            score = rk.sum(axis=1)
            if left > 0:
                nxt = np.zeros(len(Pt))
                for ch in (Pb, Ps, Pn):
                    if t + 1 == 2 * self.q:
                        nxt += sum(m * self.interp(M0, w) for m, w in self.settle(ch))
                    elif t + 1 == self.q:
                        nxt += sum(
                            self.myopic_best(ch * (self.grp == g)[None, None, :])
                            for g in range(self.ng)
                        )
                    else:
                        nxt += self.myopic_best(ch)
                score = score + lam * nxt
        a = score.reshape(self.A, n).argmax(axis=0)
        return self.JB[a], self.JA[a]

    def pol_stage(self, pol, P, t, r, Vn, M0):
        if t == 2 * self.q:
            if Vn is None:
                return np.zeros((len(P), K))
            out = np.zeros((len(P), K))
            for m, w in self.settle(P):
                out += m[:, None] * self.interp(Vn, w).T
            return out
        if t == self.q:
            return sum(
                self.pol_quote(pol, P * (self.grp == g)[None, None, :], t, r, Vn, M0)
                for g in range(self.ng)
            )
        return self.pol_quote(pol, P, t, r, Vn, M0)

    def pol_quote(self, pol, P, t, r, Vn, M0):
        out = np.zeros((len(P), K))
        for lo in range(0, len(P), 4000):
            Pc = P[lo : lo + 4000]
            jb, ja = self.choose(pol, Pc, t, r, M0)
            Pb, Ps, Pn, rk = self.expand(Pc, jb, ja)
            v = rk.copy()
            for ch in (Pb, Ps, Pn):
                v += self.pol_stage(pol, ch, t + 1, r, Vn, M0)
            out[lo : lo + 4000] = v
        return out

    # ---- backward induction over rounds
    def solve_opt(self, chunk=4):
        W = self.grid_beliefs()
        G = len(self.GU)
        Vn = None
        for r in range(self.R - 1, 0, -1):
            vals = np.concatenate(
                [
                    self.opt_stage(self.root(W[i : i + chunk]), 0, Vn)
                    for i in range(0, len(W), chunk)
                ]
            )
            Vn = vals.reshape(G, G)
            print(f"optimum: round {r + 1} solved", file=sys.stderr, flush=True)
        return float(self.opt_stage(self.root(np.full((1, 3), 1 / 3)), 0, Vn)[0])

    def solve_pol(self, pol, chunk=64):
        W = self.grid_beliefs()
        G = len(self.GU)
        M0 = self.myopic_best(self.root(W)).reshape(G, G)
        Vn = None
        for r in range(self.R - 1, 0, -1):
            vals = np.concatenate(
                [
                    self.pol_stage(pol, self.root(W[i : i + chunk]), 0, r, Vn, M0)
                    for i in range(0, len(W), chunk)
                ]
            )
            Vn = vals.T.reshape(K, G, G)
        return self.pol_stage(pol, self.root(np.full((1, 3), 1 / 3)), 0, 0, Vn, M0)[0]


def bracket(path: str) -> dict[str, dict[str, float]]:
    """Per tier: best public quoter (lower) and the round-1 relaxation (upper), % of oracle."""
    rows = [json.loads(ln) for ln in Path(path).read_text(encoding="utf-8").splitlines() if ln]
    by = defaultdict(dict)
    for r in rows:
        by[r["agent"]][r["session"]] = r
    oracle = by.pop("oracle")
    tier_of = {s: r["tier"] for s, r in oracle.items()}
    out = {}
    for tier in sorted(set(tier_of.values()), key=["open", "mixed", "tight"].index):
        ss = [s for s, t in tier_of.items() if t == tier]
        total = sum(oracle[s]["xpnl_alpha"] for s in ss)
        later = sum(sum(oracle[s]["rounds"][1:]) for s in ss)
        public = {a: per for a, per in by.items() if all(s in per for s in ss)}
        best = max(sum(per[s]["xpnl_alpha"] for s in ss) for per in public.values())
        best_r1 = max(sum(per[s]["rounds"][0] for s in ss) for per in public.values())
        top = max(public, key=lambda a: sum(public[a][s]["xpnl_alpha"] for s in ss))
        out[tier] = {
            "sessions": len(ss),
            "best_public": 100 * best / total,
            "best_public_agent": top,
            "relaxation": 100 * (best_r1 + later) / total,
        }
    return out


def miniature(rho: float, rounds: int, quotes: int, grid: int) -> dict[str, float]:
    x = np.linspace(0, 1, grid)
    toy = Miniature(rho, quotes, rounds, sym=True, grid=0.5 * (1 - np.cos(np.pi * x)))
    started = time.time()
    orc = sum(toy.solve_pol(("oracle", k))[k] for k in range(K))
    res = {"oracle_value_sd": orc / toy.sd}
    policies = {
        "myopic": ("myopic",),
        "fixed-low": ("fixed", 0),
        "fixed-mid": ("fixed", 1),
        "fixed-high": ("fixed", 2),
        "lookahead-w1": ("look", 1),
        "lookahead-w4": ("look", 4),
        "lookahead-left": ("look", "R"),
    }
    for name, pol in policies.items():
        res[name] = 100 * float(toy.solve_pol(pol).sum()) / orc
        print(f"{name:15s} {res[name]:6.1f} ({time.time() - started:.0f}s)", file=sys.stderr)
    res["optimum"] = 100 * toy.solve_opt() / orc
    print(f"{'optimum':15s} {res['optimum']:6.1f} ({time.time() - started:.0f}s)", file=sys.stderr)
    return res


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bracket")
    b.add_argument("path")
    m = sub.add_parser("miniature")
    m.add_argument("--rho", type=float, required=True)
    m.add_argument("--rounds", type=int, default=6)
    m.add_argument("--quotes", type=int, default=2, help="quotes before and after the reveal")
    m.add_argument("--grid", type=int, default=15)
    args = p.parse_args()
    if args.cmd == "bracket":
        for tier, row in bracket(args.path).items():
            print(
                f"{tier}: best public {row['best_public']:.1f} ({row['best_public_agent']}), "
                f"relaxation {row['relaxation']:.1f}, {row['sessions']} sessions"
            )
    else:
        res = miniature(args.rho, args.rounds, args.quotes, args.grid)
        print(json.dumps({"rho": args.rho, "rounds": args.rounds, **res}, sort_keys=True))


if __name__ == "__main__":
    main()
