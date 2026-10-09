"""Game families: construction invariants, determinism, exact tables, and text/table agreement."""

from __future__ import annotations

import itertools
import re
from collections import Counter, defaultdict
from fractions import Fraction
from math import comb

import numpy as np
import pytest
from conftest import FAMILY_NAMES, SEEDS

from mmarena.games import FAMILIES, VARIANTS, Game, make_game
from mmarena.games.base import MAX_OUTCOMES

ALL = [(f, v, s) for f in FAMILY_NAMES for v in VARIANTS for s in SEEDS]
_CACHE: dict[tuple[str, str, int], Game] = {}


def game(family: str, variant: str, seed: int) -> Game:
    key = (family, variant, seed)
    if key not in _CACHE:
        _CACHE[key] = make_game(family, seed, variant)
    return _CACHE[key]


def value_dist(values: np.ndarray, prob: np.ndarray) -> dict[float, float]:
    out: dict[float, float] = defaultdict(float)
    for v, p in zip(values, prob, strict=True):
        out[round(float(v), 9)] += float(p)
    return dict(out)


def max_diff(a: dict, b: dict) -> float:
    return max(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in set(a) | set(b))


def test_families_registry() -> None:
    assert set(FAMILIES) == set(FAMILY_NAMES)
    assert VARIANTS == ("classic", "perturbed")
    with pytest.raises(KeyError):
        make_game("roulette", 0)
    with pytest.raises(ValueError):
        make_game("dice", 0, "weird")


# --------------------------------------------------------------------------- invariants


@pytest.mark.parametrize("family", FAMILY_NAMES)
@pytest.mark.parametrize("variant", VARIANTS)
def test_build_invariants(family: str, variant: str) -> None:
    for seed in SEEDS:
        g = game(family, variant, seed)
        n = len(g.prob)
        assert 1 < n <= MAX_OUTCOMES
        assert g.outcomes.shape == (n, len(g.components))
        assert g.value.shape == (n,)
        assert np.all(g.prob > 0), "zero-probability rows must be dropped"
        assert g.prob.sum() == pytest.approx(1.0, abs=1e-12)
        assert np.all(np.isfinite(g.value))
        # no duplicate outcome rows (each hidden state enumerated once)
        assert len({tuple(r) for r in g.outcomes}) == n
        # levels / level_index consistent
        assert np.array_equal(g.levels[g.level_index], g.value)
        assert np.all(np.diff(g.levels) > 0)
        assert g.v_min <= g.prior_mean <= g.v_max
        assert g.prior_std > 0
        # reveal groups: non-empty, disjoint, in range
        flat = [c for grp in g.reveals for c in grp]
        assert all(len(grp) > 0 for grp in g.reveals)
        assert len(flat) == len(set(flat))
        assert all(0 <= c < len(g.components) for c in flat)
        assert g.n_stages == len(g.reveals) + 1
        assert g.n_steps == g.n_stages * g.market.quotes_per_stage
        # revealing everything must not determine the value in every case for sum-type games
        d = g.to_dict()
        assert d["n_outcomes"] == n and d["id"] == g.id
        m = g.market
        assert 0 < m.alpha < 1 and m.noise_scale > 0 and m.tick > 0


@pytest.mark.parametrize("family", ["coin", "urn"])
@pytest.mark.parametrize("variant", VARIANTS)
def test_latent_component_never_revealed(family: str, variant: str) -> None:
    for seed in SEEDS:
        g = game(family, variant, seed)
        assert g.components[0] in ("coin", "red balls")
        assert all(0 not in grp for grp in g.reveals), (seed, g.reveals)


@pytest.mark.parametrize("family", ["dice", "cards"])
@pytest.mark.parametrize("variant", VARIANTS)
def test_last_item_stays_hidden(family: str, variant: str) -> None:
    for seed in SEEDS:
        g = game(family, variant, seed)
        flat = {c for grp in g.reveals for c in grp}
        assert len(flat) == len(g.components) - 1


# --------------------------------------------------------------------------- determinism


@pytest.mark.parametrize("family", FAMILY_NAMES)
@pytest.mark.parametrize("variant", VARIANTS)
def test_deterministic(family: str, variant: str) -> None:
    for seed in (0, 7, 123):
        a, b = make_game(family, seed, variant), make_game(family, seed, variant)
        assert a.id == b.id
        assert np.array_equal(a.outcomes, b.outcomes)
        assert np.array_equal(a.prob, b.prob)
        assert np.array_equal(a.value, b.value)
        assert a.reveals == b.reveals
        assert a.description == b.description and a.contract == b.contract
        assert a.market == b.market


@pytest.mark.parametrize("family", FAMILY_NAMES)
def test_perturbed_seeds_differ(family: str) -> None:
    gs = [game(family, "perturbed", s) for s in SEEDS]
    ids = {g.id for g in gs}
    specs = {(g.description, g.contract) for g in gs}
    assert len(ids) == len(gs), "perturbed games should have unique ids"
    assert len(specs) >= 0.8 * len(gs)


@pytest.mark.parametrize("family", FAMILY_NAMES)
def test_classic_table_fixed_across_seeds(family: str) -> None:
    ref = game(family, "classic", 0)
    for s in SEEDS[1:]:
        g = game(family, "classic", s)
        assert g.description == ref.description and g.contract == ref.contract
        assert np.array_equal(g.prob, ref.prob) and np.array_equal(g.value, ref.value)


@pytest.mark.parametrize("family", FAMILY_NAMES)
def test_ids_are_content_hashes(family: str) -> None:
    """Classic seeds that draw the same market build the same game, and share its id."""
    games = [game(family, "classic", s) for s in SEEDS]
    by_id: dict[str, object] = {}
    for g in games:
        ref = by_id.setdefault(g.id, g)
        assert ref.market == g.market and ref.description == g.description


def test_id_depends_on_reveal_schedule() -> None:
    g = make_game("dice", 3, "perturbed")
    other = Game(
        family=g.family,
        variant=g.variant,
        title=g.title,
        description=g.description,
        contract=g.contract,
        components=g.components,
        outcomes=g.outcomes,
        prob=g.prob,
        value=g.value,
        reveals=tuple(reversed(g.reveals)) if len(g.reveals) > 1 else (),
        market=g.market,
        params=g.params,
        seed=g.seed,
    )
    assert other.reveals != g.reveals
    assert other.id != g.id


# --------------------------------------------------------------------------- classic moments


def test_classic_dice_is_3d6() -> None:
    g = game("dice", "classic", 0)
    assert len(g.components) == 3
    assert g.prior_mean == pytest.approx(10.5, abs=1e-12)
    assert g.prior_std**2 == pytest.approx(35 / 4, abs=1e-12)
    d = value_dist(g.value, g.prob)
    assert d[3.0] == pytest.approx(1 / 216) and d[18.0] == pytest.approx(1 / 216)
    assert d[10.0] == pytest.approx(27 / 216)


def test_classic_cards_three_from_52() -> None:
    g = game("cards", "classic", 0)
    assert len(g.components) == 3
    assert g.prior_mean == pytest.approx(21.0, abs=1e-12)
    # var of sum of 3 draws w/o replacement: 3*s2 - 6*s2/51 with s2 = (13^2 - 1) / 12
    s2 = 168 / 12
    assert g.prior_std**2 == pytest.approx(3 * s2 - 6 * s2 / 51, abs=1e-9)
    d = value_dist(g.value, g.prob)
    # three aces: 4/52 * 3/51 * 2/50
    assert d[3.0] == pytest.approx(4 * 3 * 2 / (52 * 51 * 50))


def test_classic_transform_is_product_of_two_dice() -> None:
    g = game("transform", "classic", 0)
    assert len(g.components) == 2
    assert g.prior_mean == pytest.approx(12.25, abs=1e-12)
    assert "product" in g.contract


def test_classic_coin_and_urn_means() -> None:
    coin = game("coin", "classic", 0)
    assert coin.prior_mean == pytest.approx(0.5 * 3 + 0.5 * 6)
    urn = game("urn", "classic", 0)
    assert urn.prior_mean == pytest.approx(5.0)
    assert value_dist(urn.value, urn.prob) == pytest.approx({float(r): 1 / 11 for r in range(11)})


# ------------------------------------------------------------------ Monte Carlo of the process


def _coin_mc(params: dict, mult: int, n_sim: int, rng: np.random.Generator) -> tuple[dict, dict]:
    biases = np.asarray(params["biases"], dtype=float)
    prior = np.asarray(params["prior"], dtype=float)
    n = params["n"]
    which = rng.choice(len(biases), size=n_sim, p=prior / prior.sum())
    flips = (rng.random((n_sim, n)) < biases[which][:, None]).astype(int)
    rows = np.column_stack([which, flips])
    joint = Counter(map(tuple, rows.tolist()))
    vals = Counter((mult * flips.sum(axis=1)).tolist())
    return (
        {k: c / n_sim for k, c in joint.items()},
        {float(k): c / n_sim for k, c in vals.items()},
    )


def _urn_mc(params: dict, mult: int, n_sim: int, rng: np.random.Generator) -> tuple[dict, dict]:
    size, k = params["size"], params["k"]
    if params["prior"] == "uniform":
        reds = rng.integers(0, size + 1, size=n_sim)
    else:
        reds = (rng.random((n_sim, size)) < params["p_red"]).sum(axis=1)
    # random permutation of the urn; the first k balls are the draws
    keys = rng.random((n_sim, size))
    order = np.argsort(keys, axis=1)[:, :k]
    draws = (order < reds[:, None]).astype(int)  # balls 0..r-1 are red
    rows = np.column_stack([reds, draws])
    joint = Counter(map(tuple, rows.tolist()))
    vals = Counter((mult * reds).tolist())
    return (
        {k_: c / n_sim for k_, c in joint.items()},
        {float(k_): c / n_sim for k_, c in vals.items()},
    )


@pytest.mark.parametrize("family", ["coin", "urn"])
@pytest.mark.parametrize("variant", VARIANTS)
def test_latent_families_match_monte_carlo(family: str, variant: str) -> None:
    rng = np.random.default_rng(20261009)
    n_sim = 60_000
    tol = 5 * np.sqrt(0.25 / n_sim)  # 5 sd of a frequency
    for seed in SEEDS[:6]:
        g = game(family, variant, seed)
        hp, mult = g.params["hidden"], g.params["mult"]
        sim = _coin_mc if family == "coin" else _urn_mc
        joint_mc, val_mc = sim(hp, mult, n_sim, rng)
        joint = {
            tuple(int(x) for x in r): float(p) for r, p in zip(g.outcomes, g.prob, strict=True)
        }
        assert max_diff(joint, joint_mc) < tol, (family, variant, seed)
        assert max_diff(value_dist(g.value, g.prob), val_mc) < tol, (family, variant, seed)


def test_dice_and_cards_match_monte_carlo() -> None:
    rng = np.random.default_rng(7)
    n_sim = 60_000
    tol = 5 * np.sqrt(0.25 / n_sim)
    for seed in SEEDS[:5]:
        g = game("dice", "perturbed", seed)
        cols = []
        for die in g.params["hidden"]["dice"]:
            w = np.asarray(die["weights"], dtype=float)
            cols.append(rng.choice(np.asarray(die["faces"], float), size=n_sim, p=w / w.sum()))
        mc = Counter(np.sum(cols, axis=0).tolist())
        assert max_diff(value_dist(g.value, g.prob), {k: c / n_sim for k, c in mc.items()}) < tol
        g = game("cards", "perturbed", seed)
        deck = [int(v) for v, c in g.params["hidden"]["deck"].items() for _ in range(c)]
        k = g.params["hidden"]["k"]
        idx = np.argsort(rng.random((n_sim, len(deck))), axis=1)[:, :k]
        sums = np.asarray(deck, dtype=float)[idx].sum(axis=1)
        mc = Counter(sums.tolist())
        assert max_diff(value_dist(g.value, g.prob), {k_: c / n_sim for k_, c in mc.items()}) < tol


# ------------------------------------------------------------------ text-only reconstruction

_NUM = {"Two": 2, "Three": 3, "Four": 4}


def _parse_fraction(s: str) -> float:
    return float(Fraction(s))


def _dice_from_text(desc: str) -> list[list[tuple[float, float]]]:
    m = re.match(r"(Two|Three|Four) dice are rolled independently\.", desc)
    assert m, desc
    lines = re.findall(
        r"^- Die (\d+) \((\d+) faces, (each equally likely|loaded)\): (.*)\.$", desc, re.M
    )
    assert len(lines) == _NUM[m.group(1)], desc
    dice = []
    for i, (idx, nfaces, kind, body) in enumerate(lines):
        assert int(idx) == i + 1
        if kind == "loaded":
            faces = [
                (float(f), _parse_fraction(p))
                for f, p in re.findall(r"(-?\d+) \(prob (\d+(?:/\d+)?)\)", body)
            ]
        else:
            vals = [float(x) for x in body.split(", ")]
            faces = [(v, 1 / len(vals)) for v in vals]
        assert len(faces) == int(nfaces), body
        assert sum(p for _, p in faces) == pytest.approx(1.0)
        dice.append(faces)
    return dice


def _cards_from_text(desc: str) -> tuple[list[float], int]:
    if desc.startswith("A standard 52-card deck"):
        deck = [float(v) for v in range(1, 14) for _ in range(4)]
    else:
        m = re.match(r"A custom deck of (\d+) cards is shuffled: (.*?)\. \d+ cards are dealt", desc)
        assert m, desc
        parts = re.findall(r"(\d+) cards? worth (-?\d+)", m.group(2))
        deck = [float(v) for c, v in parts for _ in range(int(c))]
        assert len(deck) == int(m.group(1)), desc
    k = re.search(r"(\d+) cards are dealt face down, without replacement\.$", desc)
    assert k, desc
    return deck, int(k.group(1))


def _components_from_text(g: Game) -> tuple[list[tuple[float, ...]], list[float]]:
    """Enumerate the hidden state from the description alone (dice or cards)."""
    if "dice are rolled" in g.description:
        dice = _dice_from_text(g.description)
        rows, ps = [], []
        for combo in itertools.product(*dice):
            rows.append(tuple(f for f, _ in combo))
            ps.append(float(np.prod([p for _, p in combo])))
        return rows, ps
    deck, k = _cards_from_text(g.description)
    rows, ps = [], []
    for perm in itertools.permutations(range(len(deck)), k):
        rows.append(tuple(deck[i] for i in perm))
        ps.append(1.0)
    total = len(rows)
    return rows, [p / total for p in ps]


def _apply_contract(contract: str, rows: np.ndarray) -> np.ndarray:
    if contract in (
        "The contract settles at the sum of all the dice.",
        "The contract settles at the sum of the dealt cards' values.",
    ):
        return rows.sum(axis=1)
    m = re.match(r"The contract settles at (.*)\.$", contract)
    assert m, contract
    body = m.group(1)
    if body.startswith("the largest minus the smallest of the "):
        return rows.max(axis=1) - rows.min(axis=1)
    if body.startswith("the largest of the "):
        return rows.max(axis=1)
    if body.startswith("the smallest of the "):
        return rows.min(axis=1)
    if body.startswith("the product of the "):
        return rows.prod(axis=1)
    c = re.match(r"10 times the number of (?:dice|dealt cards) showing at least (-?[\d.]+)$", body)
    assert c, contract
    return 10.0 * (rows >= float(c.group(1))).sum(axis=1)


@pytest.mark.parametrize("family", ["dice", "cards", "transform"])
@pytest.mark.parametrize("variant", VARIANTS)
def test_text_matches_table_dice_cards(family: str, variant: str) -> None:
    """A text-only agent must be able to rebuild the exact value distribution."""
    for seed in SEEDS:
        g = game(family, variant, seed)
        if family == "cards" and variant == "classic" and seed > 0:
            continue  # identical to seed 0 and slow to enumerate by permutations
        rows, ps = _components_from_text(g)
        arr = np.asarray(rows, dtype=float)
        assert arr.shape[1] == len(g.components), (seed, g.description)
        val = _apply_contract(g.contract, arr)
        text_dist = value_dist(val, np.asarray(ps))
        assert max_diff(text_dist, value_dist(g.value, g.prob)) < 1e-9, (seed, g.description)
        # each component's marginal matches the text too
        for c in range(arr.shape[1]):
            a = value_dist(arr[:, c], np.asarray(ps))
            b = value_dist(g.outcomes[:, c], g.prob)
            assert max_diff(a, b) < 1e-9, (seed, c)


def _latent_from_text(g: Game) -> tuple[dict[tuple[int, ...], float], dict]:
    desc, contract = g.description, g.contract
    mult_m = re.match(r"The contract settles at (\d+) times", contract)
    mult = int(mult_m.group(1)) if mult_m else 1
    out: dict[tuple[int, ...], float] = defaultdict(float)
    if g.family == "coin":
        coins = re.findall(r"P\(heads\) = ([\d.]+) with probability (\d+(?:/\d+)?)", desc)
        n = int(re.search(r"It is flipped (\d+) times\.", desc).group(1))
        assert coins and sum(_parse_fraction(p) for _, p in coins) == pytest.approx(1.0)
        assert "number of heads in all flips" in contract
        for bi, (b, p) in enumerate(coins):
            b, p = float(b), _parse_fraction(p)
            for flips in itertools.product([0, 1], repeat=n):
                h = sum(flips)
                out[(bi, *flips)] += p * b**h * (1 - b) ** (n - h)
        values = {key: mult * sum(key[1:]) for key in out}
    else:
        size = int(re.match(r"An urn holds (\d+) balls", desc).group(1))
        k = int(re.search(r"(\d+) balls are drawn without replacement", desc).group(1))
        pm = re.search(r"painted red with probability ([\d.]+)\.", desc)
        if pm:
            pr = float(pm.group(1))
            prior = [comb(size, r) * pr**r * (1 - pr) ** (size - r) for r in range(size + 1)]
        else:
            assert f"equally likely to be any of 0, 1, ..., {size}." in desc
            prior = [1 / (size + 1)] * (size + 1)
        assert "number of red balls originally in the urn" in contract
        for r in range(size + 1):
            balls = [1] * r + [0] * (size - r)
            for perm in itertools.permutations(range(size), k):
                out[(r, *(balls[i] for i in perm))] += prior[r] / (
                    comb(size, k) * np.prod(range(1, k + 1))
                )
        values = {key: mult * key[0] for key in out}
    total = sum(out.values())
    return {key: p / total for key, p in out.items() if p > 0}, values


@pytest.mark.parametrize("family", ["coin", "urn"])
@pytest.mark.parametrize("variant", VARIANTS)
def test_text_matches_table_latent(family: str, variant: str) -> None:
    for seed in SEEDS[:12]:
        g = game(family, variant, seed)
        joint_text, values = _latent_from_text(g)
        table = {
            tuple(int(x) for x in r): float(p) for r, p in zip(g.outcomes, g.prob, strict=True)
        }
        assert max_diff(joint_text, table) < 1e-9, (seed, g.description)
        tv = {tuple(int(x) for x in r): float(v) for r, v in zip(g.outcomes, g.value, strict=True)}
        assert all(values[k] == tv[k] for k in tv), (seed, g.contract)
