"""Learning response of reference quoters with decision noise, for a threshold on its interval.

    uv run python scripts/learning_response_v2.py [--suite pilot-v2] [--seeds 40] [--scales 1,2]
        [--bases bayes,...] [--out runs/learning-response-v2]

Each run is a reference quoter under the decision-noise model of ``scripts/power_v2.py`` at
``scale`` times its noise sds; a noise seed stands for a run. Every run is scored by the session
report itself, so the learning response and its 95% interval are the ones a model's run gets.
Prints, per noise scale and quoter, the mean and SD of the learning response across runs, the
number of runs whose interval lies above each threshold, and the number whose one-sided
bootstrap p-value against 0 is below 0.05.

Runs are written to ``--out`` one file per run and finished runs are skipped on a rerun.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from power_v2 import NoisyAgent  # noqa: E402

from mmarena.session_engine import run_session  # noqa: E402
from mmarena.session_report import build_session_report  # noqa: E402
from mmarena.suite import load_suite  # noqa: E402

BASES = "bayes,bayes-optimist,bayes-thompson,bayes-fixed-high,bayes-nolearn,bayes-mean,static"
THRESHOLDS = (0.2, 0.25, 0.3, 0.35, 0.4)


def _work(job: tuple[str, str, float, int, str]) -> None:
    suite_name, base, scale, seed, out = job
    path = Path(out) / f"x{scale:g}" / f"noisy-{base}-n{seed}.jsonl"
    sessions = list(load_suite(suite_name).sessions())
    if path.exists() and len(path.read_text(encoding="utf-8").splitlines()) == len(sessions):
        return
    rows = []
    for session in sessions:
        agent = NoisyAgent(base, seed, scale)
        agent.name = path.stem
        trace = run_session(session, agent, 0)
        trace["suite"] = suite_name
        rows.append(json.dumps(trace))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--suite", default="pilot-v2")
    p.add_argument("--seeds", type=int, default=40)
    p.add_argument("--scales", default="1,2")
    p.add_argument("--bases", default=BASES)
    p.add_argument("--out", default="runs/learning-response-v2")
    p.add_argument("--workers", type=int, default=4)
    args = p.parse_args()
    bases, scales = args.bases.split(","), [float(x) for x in args.scales.split(",")]
    jobs = [
        (args.suite, b, x, k, args.out) for x in scales for b in bases for k in range(args.seeds)
    ]
    with Pool(args.workers) as pool:
        pool.map(_work, jobs, chunksize=1)
    head = " | ".join(f"above {t:g}" for t in THRESHOLDS)
    for x in scales:
        with tempfile.TemporaryDirectory() as tmp:
            report = build_session_report(Path(args.out) / f"x{x:g}", out_dir=tmp)
        runs = {a["agent"]: a["learning_response"] for a in report["agents"]}
        print(f"\n{args.suite}, noise x{x:g}\n")
        print(f"| quoter with decision noise | runs | mean (SD) | {head} | p < 0.05 against 0 |")
        print("| --- |" + " ---: |" * (len(THRESHOLDS) + 3))
        for b in bases:
            got = [runs[f"noisy-{b}-n{k}"] for k in range(args.seeds)]
            value = np.array([e["value"] for e in got])
            lo = np.array([e["lo"] for e in got])
            cells = " | ".join(str(int((lo > t).sum())) for t in THRESHOLDS)
            below = sum(e["p_le0"] < 0.05 for e in got)
            spread = f"{value.mean():.2f} ({value.std(ddof=1):.2f})"
            print(f"| `{b}` | {len(got)} | {spread} | {cells} | {below} |")


if __name__ == "__main__":
    main()
