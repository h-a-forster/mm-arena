"""Session specs, the format-2 suite loader and the suite tools."""

from __future__ import annotations

import dataclasses
from collections import Counter
from pathlib import Path

import pytest

from mmarena.joint import Regimes
from mmarena.sessions import (
    Session,
    SessionBlock,
    SessionSpec,
    balanced_regimes,
    make_session,
    render_suite_toml,
    session_from_dict,
    suite_hash,
)
from mmarena.suite import Suite, builtin_suites, load_suite

REGIMES = Regimes.of([0.05, 0.5, 0.9])


def format2_suites() -> list[str]:
    return [n for n in builtin_suites() if getattr(load_suite(n), "format", 1) == 2]


def test_smoke_v2_ids_are_stable() -> None:
    s = load_suite("smoke-v2")
    assert [x.id for x in s.sessions()] == ["dice-se2f1c7aa", "coin-saafb8a6e", "urn-s458e11bd"]
    assert [x.regime for x in s.sessions()] == [0, 2, 1]
    assert len(s.episodes_list()) == 3


def test_format1_suites_still_load_as_suites() -> None:
    for name in ("core-v1", "full-v1", "smoke"):
        assert isinstance(load_suite(name), Suite)


@pytest.mark.parametrize("name", ["smoke-v2", "core-v2", "tight-v2", "pilot-v2"])
def test_session_games_never_collide_with_core_v1(name: str) -> None:
    if name not in builtin_suites():
        pytest.skip(f"{name} not built yet")
    v1 = {g.id for s in ("core-v1", "full-v1", "smoke") for g in load_suite(s).games()}
    sessions = list(load_suite(name).sessions())
    ids = [s.id for s in sessions]
    assert len(set(ids)) == len(ids)
    assert not {s.game.id for s in sessions} & v1
    for s in sessions:
        assert s.game.variant == "perturbed" and len(s.game.reveals) == 1
        assert s.game.market.quotes_per_stage == 2 and s.game.market.informed_noise == 0


def test_public_spec_has_no_truth() -> None:
    fields = {f.name for f in dataclasses.fields(SessionSpec)}
    assert fields == {"game", "regimes", "rounds"}
    a = make_session("dice", 123, 0.7, REGIMES, 0, 6, "mixed")
    b = make_session("dice", 123, 0.7, REGIMES, 2, 6, "mixed")
    assert a.id == b.id  # the id never encodes the regime
    assert a.spec.to_dict() == b.spec.to_dict()
    assert "regime" not in a.spec.to_dict()


def test_session_round_trips_through_its_dict() -> None:
    s = make_session("coin", 77, 0.7, REGIMES, 1, 6, "mixed", salt="ab")
    t = session_from_dict(s.to_dict())
    assert (t.id, t.regime, t.tier, t.game.id) == (s.id, s.regime, s.tier, s.game.id)
    bad = {**s.to_dict(), "id": "coin-sdeadbeef"}
    with pytest.raises(ValueError):
        session_from_dict(bad)


def test_noise_scale_is_the_rounded_ratio_of_prior_sd() -> None:
    s = make_session("urn", 31, 0.7, REGIMES, 0, 6)
    assert s.game.market.noise_scale == float(f"{0.7 * s.game.prior_std:.2g}")
    assert s.game.market.alpha == pytest.approx(REGIMES.mean_alpha)


def test_balanced_regimes() -> None:
    r = balanced_regimes(9, 3, [1, 2])
    assert Counter(r) == {0: 3, 1: 3, 2: 3}
    assert r == balanced_regimes(9, 3, [1, 2])
    with pytest.raises(ValueError):
        balanced_regimes(4, 3, 0)


@pytest.mark.parametrize("name", ["core-v2", "tight-v2"])
def test_regimes_balanced_within_each_tier_and_family(name: str) -> None:
    if name not in builtin_suites():
        pytest.skip(f"{name} not built yet")
    blocks = Counter()
    for s in load_suite(name).sessions():
        blocks[(s.tier, s.game.family, s.regime)] += 1
    by_block: dict[tuple[str, str], list[int]] = {}
    for (tier, fam, _), n in blocks.items():
        by_block.setdefault((tier, fam), []).append(n)
    for counts in by_block.values():
        assert len(counts) == 3 and len(set(counts)) == 1


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "s.toml"
    p.write_text(text, encoding="utf-8")
    return p


def test_format2_loader_validates(tmp_path: Path) -> None:
    good = render_suite_toml("t", "d", {"open": 1.0}, [SessionBlock("dice", "open", 1, (0, 1))])
    s = load_suite(_write(tmp_path, good))
    assert [x.regime for x in s.sessions()] == [0, 1]
    for bad in (
        good.replace('prompt = "v2.0"', 'prompt = "v9"'),
        good.replace('tier = "open"', 'tier = "nope"'),
        good.replace("regimes = [0, 1]", "regimes = [0, 3]"),
        good.replace('family = "dice"', 'family = "chess"'),
        good + "\nsurprise = 1\n",  # lands in the last block
        "surprise = 1\n" + good,
        good.replace("format = 2", "format = 3"),
    ):
        with pytest.raises(ValueError):
            load_suite(_write(tmp_path, bad))


def test_suite_hash_is_stable_and_salt_sensitive(tmp_path: Path) -> None:
    block = [SessionBlock("dice", "open", 1, (0, 1, 2))]
    a = _write(tmp_path, render_suite_toml("h", "d", {"open": 1.0}, block, salt="00ff"))
    h = suite_hash(a)
    crlf = tmp_path / "crlf.toml"
    crlf.write_bytes(a.read_bytes().replace(b"\n", b"\r\n") + b"# comment\r\n")
    assert suite_hash(crlf) == h
    b = tmp_path / "b.toml"
    b.write_text(render_suite_toml("h", "d", {"open": 1.0}, block, salt="00fe"), encoding="utf-8")
    assert suite_hash(b) != h
    salted = list(load_suite(b).sessions())[0]
    plain = list(load_suite(a).sessions())[0]
    assert salted.id != plain.id and salted.game.id == plain.game.id


def test_session_rejects_bad_regime() -> None:
    s = make_session("dice", 5, 1.0, REGIMES, 0, 2)
    with pytest.raises(ValueError):
        Session(s.spec, 3, "open", 1.0, 5)


# Content hashes of the released session suites (``mm-arena suite-hash``); the files never change.
V2_SUITE_SHA256 = {
    "core-v2": "3eb25ccd1c25dcd728d7e8c5bedfdef4e6a80a885991cfc59481d65e5365a098",
    "tight-v2": "a2e73b4d140c3260002bf76ae57c0f1bfe7c09df489a7ab6dc254d47e28b836e",
    "pilot-v2": "0baf28dc83ab0caa75cfa9561b539138a17d0e98dc84983824e5d14cbd5c575a",
}


def test_released_session_suites_follow_their_rules_and_are_pinned() -> None:
    import importlib.util

    script = Path(__file__).resolve().parents[1] / "scripts" / "make_suites_v2.py"
    spec = importlib.util.spec_from_file_location("make_suites_v2", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    from mmarena.suite import SUITE_DIR

    for name, text in mod.released().items():
        path = SUITE_DIR / f"{name}.toml"
        assert path.read_text(encoding="utf-8") == text, name
        assert suite_hash(path) == V2_SUITE_SHA256[name], name


def test_suite_layouts() -> None:
    core = list(load_suite("core-v2").sessions())
    assert Counter(s.tier for s in core) == {"open": 15, "mixed": 30}
    assert sum(s.spec.n_quotes for s in core) == 1080
    tight = list(load_suite("tight-v2").sessions())
    assert Counter(s.tier for s in tight) == {"tight": 15}
    pilot = list(load_suite("pilot-v2").sessions())
    assert Counter((s.tier, s.regime) for s in pilot) == {
        (t, r): 2 for t in ("open", "mixed") for r in range(3)
    }
    seeds = [s.game_seed for x in (core, tight, pilot) for s in x]
    assert len(set(seeds)) == len(seeds) and all(30000 <= x < 35000 for x in seeds)
