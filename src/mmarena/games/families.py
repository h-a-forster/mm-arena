"""Procedural game families.

Every family has a ``classic`` variant (the textbook interview question) and a ``perturbed``
variant drawn from a seed: odd dice, small custom decks, unusual contracts, latent parameters.
Perturbed instances are new on every seed, so a model cannot recall the answer; the gap between
classic and perturbed scores is a contamination probe. Market parameters are drawn from the same
distribution for both variants so the comparison is matched.
"""

from __future__ import annotations

import itertools
import zlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

import numpy as np

from mmarena.games.base import Game, Market

VARIANTS = ("classic", "perturbed")


@dataclass
class Hidden:
    """Hidden state before a contract is attached."""

    components: tuple[str, ...]
    outcomes: np.ndarray
    prob: np.ndarray
    description: str
    reveals: tuple[tuple[int, ...], ...]
    params: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- helpers


def _fmt(x: float) -> str:
    return f"{x:g}"


def _frac(p: float, denom: int = 100) -> str:
    return str(Fraction(p).limit_denominator(denom))


def _nice(x: float) -> float:
    """Round to two significant figures."""
    return float(f"{x:.2g}")


def _cartesian(values: Sequence[np.ndarray], probs: Sequence[np.ndarray]):
    grids = np.meshgrid(*values, indexing="ij")
    pgrids = np.meshgrid(*probs, indexing="ij")
    outcomes = np.stack([g.ravel() for g in grids], axis=1).astype(float)
    prob = np.prod(np.stack([g.ravel() for g in pgrids], axis=1), axis=1)
    return outcomes, prob


def _collapse(faces: Sequence[float], weights: Sequence[float]) -> tuple[np.ndarray, np.ndarray]:
    """Merge repeated face values into one entry with summed probability."""
    vals, inv = np.unique(np.asarray(faces, dtype=float), return_inverse=True)
    w = np.bincount(inv, weights=np.asarray(weights, dtype=float))
    return vals, w / w.sum()


def _ordinal(i: int) -> str:
    return ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth"][i]


# --------------------------------------------------------------------------- hidden states


def _dice(rng: np.random.Generator, classic: bool, n: int | None = None) -> Hidden:
    if classic:
        n = n or 3
        dice = [([1, 2, 3, 4, 5, 6], [1 / 6] * 6, False)] * n
    else:
        n = n or int(rng.choice([2, 3, 4], p=[0.3, 0.5, 0.2]))
        dice = []
        loaded = int(rng.integers(n)) if rng.random() < 0.3 else -1
        for i in range(n):
            k = int(rng.choice([4, 6, 8]))
            faces = sorted(int(v) for v in rng.integers(0, 13, size=k))
            if i == loaded:
                tenths = rng.multinomial(10 - k, np.full(k, 1 / k)) + 1
                dice.append((faces, list(tenths / 10), True))
            else:
                dice.append((faces, [1 / k] * k, False))
    lines = []
    vals, probs = [], []
    for i, (faces, weights, is_loaded) in enumerate(dice):
        if is_loaded:
            body = ", ".join(
                f"{f} (prob {_frac(w, 10)})" for f, w in zip(faces, weights, strict=True)
            )
            lines.append(f"- Die {i + 1} ({len(faces)} faces, loaded): {body}.")
        else:
            body = ", ".join(str(f) for f in faces)
            lines.append(f"- Die {i + 1} ({len(faces)} faces, each equally likely): {body}.")
        v, p = _collapse(faces, weights)
        vals.append(v)
        probs.append(p)
    outcomes, prob = _cartesian(vals, probs)
    word = {2: "Two", 3: "Three", 4: "Four"}[n]
    repeats = any(len(set(f)) < len(f) for f, _, _ in dice)
    note = " Repeated numbers are separate faces." if repeats else ""
    desc = f"{word} dice are rolled independently.{note}\n" + "\n".join(lines)
    order = list(range(n)) if classic else [int(i) for i in rng.permutation(n)]
    reveals = tuple((c,) for c in order[: n - 1])
    params = {"dice": [{"faces": f, "weights": [round(x, 6) for x in w]} for f, w, _ in dice]}
    return Hidden(tuple(f"die {i + 1}" for i in range(n)), outcomes, prob, desc, reveals, params)


def _cards(rng: np.random.Generator, classic: bool, k: int | None = None) -> Hidden:
    if classic:
        k = k or 3
        counts = {v: 4 for v in range(1, 14)}
        deck_desc = (
            "A standard 52-card deck is shuffled. Card values: Ace = 1, 2-10 face value, "
            "Jack = 11, Queen = 12, King = 13."
        )
    else:
        k = k or int(rng.choice([2, 3]))
        m = int(rng.integers(4, 9))
        values = sorted(int(v) for v in rng.choice(np.arange(0, 16), size=m, replace=False))
        counts = {v: int(c) for v, c in zip(values, rng.integers(1, 5, size=m), strict=True)}
        while sum(counts.values()) < k + 2:
            counts[values[0]] += 1
        parts = ", ".join(f"{c} card{'s' if c > 1 else ''} worth {v}" for v, c in counts.items())
        deck_desc = f"A custom deck of {sum(counts.values())} cards is shuffled: {parts}."
    values = np.array(sorted(counts), dtype=float)
    cnt = np.array([counts[int(v)] for v in values], dtype=float)
    total = cnt.sum()
    rows, ps = [], []
    for combo in itertools.product(range(len(values)), repeat=k):
        left = cnt.copy()
        p = 1.0
        for j, idx in enumerate(combo):
            if left[idx] <= 0:
                p = 0.0
                break
            p *= left[idx] / (total - j)
            left[idx] -= 1
        if p > 0:
            rows.append(values[list(combo)])
            ps.append(p)
    outcomes = np.array(rows, dtype=float)
    prob = np.array(ps)
    desc = f"{deck_desc} {k} cards are dealt face down, without replacement."
    reveals = tuple((c,) for c in range(k - 1))
    params = {"deck": {str(int(v)): int(c) for v, c in counts.items()}, "k": k}
    return Hidden(
        tuple(f"card {i + 1}" for i in range(k)), outcomes, prob / prob.sum(), desc, reveals, params
    )


# --------------------------------------------------------------------------- families


@dataclass
class Spec:
    title: str
    hidden: Hidden
    contract: str
    value: np.ndarray
    params: dict[str, Any]


def fam_dice(rng: np.random.Generator, classic: bool) -> Spec:
    h = _dice(rng, classic)
    return Spec(
        "Dice sum",
        h,
        "The contract settles at the sum of all the dice.",
        h.outcomes.sum(axis=1),
        {"hidden": h.params},
    )


def fam_cards(rng: np.random.Generator, classic: bool) -> Spec:
    h = _cards(rng, classic)
    return Spec(
        "Card sum",
        h,
        "The contract settles at the sum of the dealt cards' values.",
        h.outcomes.sum(axis=1),
        {"hidden": h.params},
    )


_TRANSFORMS: dict[str, tuple[str, Callable[[np.ndarray, Any], np.ndarray]]] = {
    "max": ("the largest of the {items}", lambda x, _: x.max(axis=1)),
    "min": ("the smallest of the {items}", lambda x, _: x.min(axis=1)),
    "range": (
        "the largest minus the smallest of the {items}",
        lambda x, _: x.max(axis=1) - x.min(axis=1),
    ),
    "product": ("the product of the {items}", lambda x, _: x.prod(axis=1)),
    "count": (
        "10 times the number of {items} showing at least {t}",
        lambda x, t: 10.0 * (x >= t).sum(axis=1),
    ),
}


def fam_transform(rng: np.random.Generator, classic: bool) -> Spec:
    if classic:
        h = _dice(rng, True, n=2)
        name, items = "product", "two dice"
    else:
        base = str(rng.choice(["dice", "cards"]))
        if base == "dice":
            h = _dice(rng, False, n=int(rng.choice([2, 3])))
            items = "dice"
        else:
            h = _cards(rng, False, k=int(rng.choice([2, 3])))
            items = "dealt cards"
        choices = ["max", "min", "range", "count"] + (
            ["product"] if h.outcomes.shape[1] == 2 else []
        )
        name = str(rng.choice(choices))
    t = None
    if name == "count":
        t = float(np.ceil(np.median(np.unique(h.outcomes))))
    text, fn = _TRANSFORMS[name]
    value = fn(h.outcomes, t)
    contract = "The contract settles at " + text.format(items=items, t=_fmt(t or 0)) + "."
    return Spec(
        f"Dice/cards {name}",
        h,
        contract,
        value,
        {"hidden": h.params, "transform": name, "threshold": t},
    )


def fam_coin(rng: np.random.Generator, classic: bool) -> Spec:
    if classic:
        biases, prior, n, mult = [0.5, 1.0], [0.5, 0.5], 6, 1
        groups = [2, 2]
    else:
        nb = int(rng.choice([2, 3]))
        biases = sorted(float(b) for b in rng.choice(np.arange(1, 10) / 10, size=nb, replace=False))
        prior = list(rng.multinomial(10 - nb, np.full(nb, 1 / nb)) / 10 + 0.1)
        n = int(rng.integers(5, 9))
        mult = int(rng.choice([1, 5, 10]))
        n_rev = n - int(rng.integers(1, 3))
        n_groups = int(rng.integers(2, 4))
        cuts = (
            sorted(
                int(c) for c in rng.choice(np.arange(1, n_rev), size=n_groups - 1, replace=False)
            )
            if n_rev >= n_groups
            else []
        )
        bounds = [0, *cuts, n_rev]
        groups = [b - a for a, b in zip(bounds[:-1], bounds[1:], strict=True) if b > a]
    rows, ps = [], []
    for bi, (b, pb) in enumerate(zip(biases, prior, strict=True)):
        for flips in itertools.product([0, 1], repeat=n):
            h = sum(flips)
            p = pb * b**h * (1 - b) ** (n - h)
            if p > 0:
                rows.append((float(bi), *flips))
                ps.append(p)
    outcomes = np.array(rows, dtype=float)
    prob = np.array(ps) / sum(ps)
    value = mult * outcomes[:, 1:].sum(axis=1)
    kinds = ", ".join(
        f"P(heads) = {_fmt(b)} with probability {_frac(p, 10)}"
        for b, p in zip(biases, prior, strict=True)
    )
    desc = (
        f"A coin is picked at random from a set of coins: {kinds}. The coin is not shown. "
        f"It is flipped {n} times. Revealed flips show 1 for heads and 0 for tails."
    )
    contract = (
        "The contract settles at the number of heads in all flips."
        if mult == 1
        else f"The contract settles at {mult} times the number of heads in all flips."
    )
    reveals, start = [], 1
    for g in groups:
        reveals.append(tuple(range(start, start + g)))
        start += g
    h = Hidden(
        ("coin", *(f"flip {i + 1}" for i in range(n))),
        outcomes,
        prob,
        desc,
        tuple(reveals),
        {"biases": biases, "prior": prior, "n": n},
    )
    return Spec("Coin of unknown bias", h, contract, value, {"hidden": h.params, "mult": mult})


def fam_urn(rng: np.random.Generator, classic: bool) -> Spec:
    if classic:
        size, k, prior_kind, p_red, mult = 10, 3, "uniform", None, 1
    else:
        size = int(rng.integers(6, 13))
        k = int(rng.integers(2, 5))
        prior_kind = str(rng.choice(["uniform", "binomial"]))
        p_red = float(rng.choice([0.3, 0.5, 0.6])) if prior_kind == "binomial" else None
        mult = int(rng.choice([1, 10]))
    from math import comb

    reds = np.arange(size + 1)
    if prior_kind == "uniform":
        prior = np.full(size + 1, 1 / (size + 1))
        prior_text = f"The number of red balls is equally likely to be any of 0, 1, ..., {size}."
    else:
        prior = np.array([comb(size, r) * p_red**r * (1 - p_red) ** (size - r) for r in reds])
        prior_text = f"Each ball was independently painted red with probability {_fmt(p_red)}."
    rows, ps = [], []
    for r in reds:
        for draws in itertools.product([0, 1], repeat=k):
            red_left, blue_left, p = r, size - r, prior[r]
            for j, d in enumerate(draws):
                left = size - j
                if d:
                    p *= red_left / left
                    red_left -= 1
                else:
                    p *= blue_left / left
                    blue_left -= 1
                if p <= 0:
                    break
            if p > 0:
                rows.append((float(r), *draws))
                ps.append(p)
    outcomes = np.array(rows, dtype=float)
    prob = np.array(ps) / sum(ps)
    value = mult * outcomes[:, 0]
    desc = (
        f"An urn holds {size} balls, each red or blue. {prior_text} {k} balls are drawn "
        f"without replacement. Revealed draws show 1 for red and 0 for blue."
    )
    contract = (
        "The contract settles at the number of red balls originally in the urn."
        if mult == 1
        else f"The contract settles at {mult} times the number of red balls originally in the urn."
    )
    reveals = tuple((c,) for c in range(1, k + 1)) if k <= 3 else ((1, 2), (3,), (4,))
    h = Hidden(
        ("red balls", *(f"draw {i + 1}" for i in range(k))),
        outcomes,
        prob,
        desc,
        reveals,
        {"size": size, "k": k, "prior": prior_kind, "p_red": p_red},
    )
    return Spec("Urn of unknown mix", h, contract, value, {"hidden": h.params, "mult": mult})


FAMILIES: dict[str, Callable[[np.random.Generator, bool], Spec]] = {
    "dice": fam_dice,
    "cards": fam_cards,
    "transform": fam_transform,
    "coin": fam_coin,
    "urn": fam_urn,
}


def sample_market(rng: np.random.Generator, prior_std: float) -> Market:
    """Market parameters, drawn identically for classic and perturbed variants."""
    return Market(
        alpha=float(rng.choice([0.2, 0.35, 0.5])),
        noise_scale=_nice(prior_std * float(rng.choice([0.75, 1.0, 1.5]))),
        informed_noise=0.0,
        quotes_per_stage=int(rng.choice([2, 3])),
        inventory_limit=int(rng.choice([3, 4, 5])),
        tick=0.1 if prior_std < 20 else 1.0,
    )


def make_game(
    family: str, seed: int, variant: str = "perturbed", market: Market | None = None
) -> Game:
    """Build one game deterministically from ``(family, variant, seed)``."""
    if family not in FAMILIES:
        raise KeyError(f"unknown family {family!r}; choose from {sorted(FAMILIES)}")
    if variant not in VARIANTS:
        raise ValueError(f"variant must be one of {VARIANTS}")
    tag = zlib.crc32(f"{family}/{variant}".encode())
    rng = np.random.default_rng([int(seed), tag])
    spec = FAMILIES[family](rng, variant == "classic")
    h = spec.hidden
    p = h.prob / h.prob.sum()
    mean = float(p @ spec.value)
    std = float(np.sqrt(p @ (spec.value - mean) ** 2))
    mkt_rng = np.random.default_rng([int(seed), tag, 1])
    market = market or sample_market(mkt_rng, max(std, 1e-9))
    return Game(
        family=family,
        variant=variant,
        title=spec.title,
        description=h.description,
        contract=spec.contract,
        components=h.components,
        outcomes=h.outcomes,
        prob=p,
        value=spec.value,
        reveals=h.reveals,
        market=market,
        params={"variant": variant, **spec.params},
        seed=int(seed),
    )
