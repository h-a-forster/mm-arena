"""Write the session suite files, or a held-out suite, from their generation rules.

    uv run python scripts/make_suites_v2.py            # check the committed files
    uv run python scripts/make_suites_v2.py --write    # (re)write them; released files never change
    uv run python scripts/make_suites_v2.py --holdout PATH

Released suites (game seeds ``30000 + 1000 x family + 100 x tier + i``; families dice, cards,
transform, coin, urn = 0..4; tiers open, mixed, tight = 0..2; regimes balanced within each
family and tier, in the order of a permutation seeded by ``[2611, tier, family]``):

- ``core-v2``: per family 3 open and 6 mixed sessions (45 sessions, 1,080 quotes);
- ``tight-v2``: per family 3 tight sessions (15 sessions), the extension suite;
- ``pilot-v2``: 6 open and 6 mixed sessions, families cycled, each regime twice per tier,
  game seeds offset by 50 from the core blocks.

``--holdout PATH`` writes a suite with core-v2's blocks but secret game seeds, secret regime
orders and a 32-byte random salt (all from the operating system's random source), and prints
its SHA-256 (``mm-arena suite-hash``). Keep the file outside the repository; publish only the
hash.
"""

from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

from mmarena.sessions import SessionBlock, balanced_regimes, render_suite_toml, suite_hash
from mmarena.suite import SUITE_DIR

FAMILIES = ("dice", "cards", "transform", "coin", "urn")
TIER_INDEX = {"open": 0, "mixed": 1, "tight": 2}
NOISE_RATIO = {"open": 0.85, "mixed": 0.7, "tight": 0.5}
PERM_SEED = 2611
ROUNDS = 6


def _seed(family: int, tier: str, offset: int = 0) -> int:
    return 30000 + 1000 * family + 100 * TIER_INDEX[tier] + offset


def core_blocks(per_tier: dict[str, int]) -> list[SessionBlock]:
    out = []
    for tier, n in per_tier.items():
        for fi, fam in enumerate(FAMILIES):
            regs = balanced_regimes(n, 3, [PERM_SEED, TIER_INDEX[tier], fi])
            out.append(SessionBlock(fam, tier, _seed(fi, tier), tuple(regs)))
    return out


def pilot_blocks() -> list[SessionBlock]:
    out = []
    for tier, start in (("open", 0), ("mixed", 1)):
        regs = balanced_regimes(6, 3, [PERM_SEED, TIER_INDEX[tier], 99])
        fams = [(start + i) % len(FAMILIES) for i in range(6)]
        for fi in sorted(set(fams)):
            mine = tuple(r for f, r in zip(fams, regs, strict=True) if f == fi)
            out.append(SessionBlock(FAMILIES[fi], tier, _seed(fi, tier, 50), mine))
    return out


def released() -> dict[str, str]:
    tiers = {t: NOISE_RATIO[t] for t in ("open", "mixed")}
    return {
        "core-v2": render_suite_toml(
            "core-v2",
            "Five families; 15 open and 30 mixed sessions of 6 rounds (1,080 quotes); "
            "hidden informed share.",
            tiers,
            core_blocks({"open": 3, "mixed": 6}),
            ROUNDS,
        ),
        "tight-v2": render_suite_toml(
            "tight-v2",
            "Extension: 15 tight sessions of 6 rounds (360 quotes); hidden informed share.",
            {"tight": NOISE_RATIO["tight"]},
            core_blocks({"tight": 3}),
            ROUNDS,
        ),
        "pilot-v2": render_suite_toml(
            "pilot-v2",
            "Pilot: 6 open and 6 mixed sessions of 6 rounds (288 quotes); hidden informed share.",
            tiers,
            pilot_blocks(),
            ROUNDS,
        ),
    }


def holdout() -> str:
    rng = secrets.SystemRandom()
    blocks = []
    for tier, n in (("open", 3), ("mixed", 6)):
        for fam in FAMILIES:
            regs = [0, 1, 2] * (n // 3)
            rng.shuffle(regs)
            blocks.append(SessionBlock(fam, tier, rng.randrange(10**6, 2**31 - 1000), tuple(regs)))
    return render_suite_toml(
        "holdout-v2",
        "Held-out twin of core-v2: same blocks, secret seeds and salt.",
        {t: NOISE_RATIO[t] for t in ("open", "mixed")},
        blocks,
        ROUNDS,
        salt=secrets.token_hex(32),
    )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--write", action="store_true", help="write the suite files")
    p.add_argument("--holdout", help="write a held-out suite to this path (outside the repo)")
    args = p.parse_args()
    if args.holdout:
        path = Path(args.holdout)
        if path.exists():
            sys.exit(f"{path} exists; a held-out suite is written once")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(holdout(), encoding="utf-8", newline="\n")
        print(f"{path}: sha256 {suite_hash(path)}")
        return
    bad = []
    for name, text in released().items():
        path = SUITE_DIR / f"{name}.toml"
        if args.write:
            if path.exists() and path.read_text(encoding="utf-8") != text:
                sys.exit(f"{path} differs from its rule; released suites are never edited")
            path.write_text(text, encoding="utf-8", newline="\n")
        elif not path.exists() or path.read_text(encoding="utf-8") != text:
            bad.append(name)
        print(f"{name}: sha256 {suite_hash(path) if path.exists() else '-'}")
    if bad:
        sys.exit(f"suite files differ from their rules: {bad}")


if __name__ == "__main__":
    main()
