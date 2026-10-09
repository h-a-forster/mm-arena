"""Command-line interface: ``mm-arena run | report | play | show | games | prompt | suites``."""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

from mmarena import __version__


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._@-]+", "_", name).strip("_") or "agent"


def cmd_run(args: argparse.Namespace) -> int:
    from mmarena.agents.registry import make_agent_factory
    from mmarena.runner import run_suite
    from mmarena.suite import load_suite

    suite = load_suite(args.suite)
    if args.limit:
        from dataclasses import replace

        suite = replace(suite, episodes=min(suite.episodes, args.limit))
    out_dir = Path(args.out or f"runs/{suite.name}")
    options = {
        k: v
        for k, v in {
            "max_tokens": args.max_tokens,
            "effort": args.effort,
            "cache": not args.no_cache,
            "name": args.name,
        }.items()
        if v is not None
    }
    status = 0
    for spec in args.agent:
        factory = make_agent_factory(spec, **options)
        name = factory().name
        path = out_dir / f"{_safe_name(name)}.jsonl"
        n_total = len(suite.episodes_list())
        started = time.perf_counter()
        print(f"[{name}] {suite.name}: {n_total} episodes -> {path}", file=sys.stderr)

        def progress(trace: dict, done: int, todo: int, name: str = name) -> None:
            tag = "ok" if trace["status"] == "ok" else f"ERROR {trace.get('error')}"
            x = trace.get("xpnl")
            xs = f"xpnl {x:+.2f}" if x is not None else ""
            print(
                f"  [{name}] {done}/{todo} {trace['game']['id']} seed {trace['seed']} {tag} {xs}",
                file=sys.stderr,
            )

        traces = run_suite(
            suite,
            factory,
            path,
            workers=args.workers,
            resume=not args.no_resume,
            on_episode=progress,
        )
        errors = sum(t["status"] != "ok" for t in traces)
        elapsed = time.perf_counter() - started
        print(f"[{name}] done: {len(traces)} run, {errors} errors, {elapsed:.0f}s", file=sys.stderr)
        if errors:
            status = 1
    return status


def cmd_report(args: argparse.Namespace) -> int:
    from mmarena.report import build_report

    report = build_report(args.run_dir, plots=not args.no_plots)
    md = Path(args.run_dir) / "REPORT.md"
    if md.exists() and not args.quiet:
        print(md.read_text(encoding="utf-8"))
    return 0 if report is not None else 1


def cmd_play(args: argparse.Namespace) -> int:
    from mmarena.play import play

    try:
        play(family=args.family, variant=args.variant, seed=args.seed, save_path=args.save)
    except (KeyboardInterrupt, EOFError):
        print("\nquit")
    return 0


def _load_episode(path: str, index: int | None, game_id: str | None, seed: int | None) -> dict:
    from mmarena.runner import read_traces

    traces = read_traces(path)
    if not traces:
        raise SystemExit(f"no traces in {path}")
    if game_id is not None:
        traces = [
            t for t in traces if t["game"]["id"] == game_id and (seed is None or t["seed"] == seed)
        ]
        if not traces:
            raise SystemExit(f"no episode for game {game_id} seed {seed} in {path}")
        return traces[-1]
    return traces[index or 0]


def cmd_show(args: argparse.Namespace) -> int:
    from mmarena.play import review

    trace = _load_episode(args.trace, args.episode, args.game, args.seed)
    print(review(trace))
    if args.plot:
        from mmarena.plots import plot_episode

        plot_episode(trace, args.plot)
        print(f"wrote {args.plot}", file=sys.stderr)
    return 0


def cmd_games(args: argparse.Namespace) -> int:
    from mmarena.suite import load_suite

    suite = load_suite(args.suite)
    rows = [("id", "variant", "outcomes", "prior mean", "prior sd", "alpha", "steps", "title")]
    for g in suite.games():
        rows.append(
            (
                g.id,
                g.variant,
                str(len(g.prob)),
                f"{g.prior_mean:.2f}",
                f"{g.prior_std:.2f}",
                f"{g.market.alpha:g}",
                str(g.n_steps),
                g.title,
            )
        )
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    for r in rows:
        print("  ".join(c.ljust(w) for c, w in zip(r, widths, strict=True)).rstrip())
    print(f"\n{suite.name}: {len(rows) - 1} games x {suite.episodes} episodes", file=sys.stderr)
    return 0


def cmd_prompt(args: argparse.Namespace) -> int:
    from mmarena.agents.base import Observation
    from mmarena.agents.prompt import render_prompt
    from mmarena.games import make_game

    game = make_game(args.family, args.seed, args.variant)
    obs = Observation(
        game=game,
        step=0,
        stage=0,
        revealed=(),
        history=(),
        position=0,
        cash=0.0,
        bid_allowed=True,
        ask_allowed=True,
    )
    system, user = render_prompt(obs)
    print("=== system ===\n" + system + "\n\n=== user ===\n" + user)
    return 0


def cmd_suites(args: argparse.Namespace) -> int:
    from mmarena.suite import builtin_suites, load_suite

    for name in builtin_suites():
        s = load_suite(name)
        n = len(s.episodes_list())
        print(f"{name:10s} {n:4d} episodes  {s.description}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mm-arena",
        description="Market-making games as a benchmark for LLM agents.",
    )
    p.add_argument("--version", action="version", version=f"mm-arena {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("run", help="play a suite with one or more agents")
    r.add_argument(
        "--agent",
        action="append",
        required=True,
        help="agent spec, repeatable: bayes, static, anthropic:claude-sonnet-5-5, "
        "openai:gpt-5.1, openai:MODEL@BASE_URL, claude-cli:haiku, ...",
    )
    r.add_argument("--suite", default="core-v1", help="built-in suite name or TOML path")
    r.add_argument("--out", help="run directory (default runs/<suite>)")
    r.add_argument("--workers", type=int, default=4, help="episodes in parallel (default 4)")
    r.add_argument("--max-tokens", type=int, help="LLM output token limit per call")
    r.add_argument("--effort", help="reasoning effort, where the provider supports it")
    r.add_argument("--name", help="override the agent name used in reports")
    r.add_argument("--no-cache", action="store_true", help="disable the LLM response cache")
    r.add_argument("--no-resume", action="store_true", help="discard existing traces and rerun")
    r.add_argument("--limit", type=int, help="cap episodes per game (quick runs)")
    r.set_defaults(func=cmd_run)

    rp = sub.add_parser("report", help="score a run directory: REPORT.md, summary.json, plots")
    rp.add_argument("run_dir")
    rp.add_argument("--no-plots", action="store_true")
    rp.add_argument("--quiet", action="store_true", help="do not print REPORT.md")
    rp.set_defaults(func=cmd_report)

    pl = sub.add_parser("play", help="play a game yourself, then compare with the Bayes quoter")
    pl.add_argument("--family", help="dice, cards, transform, coin, urn (default random)")
    pl.add_argument("--variant", default="perturbed", choices=["classic", "perturbed"])
    pl.add_argument("--seed", type=int)
    pl.add_argument("--save", help="append the trace to this JSONL file")
    pl.set_defaults(func=cmd_play)

    sh = sub.add_parser("show", help="step-by-step review of one episode from a trace file")
    sh.add_argument("trace", help="JSONL trace file")
    sh.add_argument("--episode", type=int, help="line index (default 0)")
    sh.add_argument("--game", help="game id")
    sh.add_argument("--seed", type=int, help="episode seed (with --game)")
    sh.add_argument("--plot", help="also save an episode chart (PNG/SVG)")
    sh.set_defaults(func=cmd_show)

    g = sub.add_parser("games", help="list the games in a suite")
    g.add_argument("--suite", default="core-v1")
    g.set_defaults(func=cmd_games)

    pr = sub.add_parser("prompt", help="print the exact prompt an LLM agent sees at step 0")
    pr.add_argument("--family", default="dice")
    pr.add_argument("--variant", default="perturbed", choices=["classic", "perturbed"])
    pr.add_argument("--seed", type=int, default=0)
    pr.set_defaults(func=cmd_prompt)

    s = sub.add_parser("suites", help="list built-in suites")
    s.set_defaults(func=cmd_suites)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
