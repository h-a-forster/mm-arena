# Audit tasks (2026-10-10) — delete this file in the final commit

An independent audit found no correctness bugs: the tests pass, a rebuild of all 13 trace files matches
the exact posterior (0 mismatches), and the report and figures regenerate byte-for-byte. The work below
is about claims that overreach, stale docs, and upgrades that would convince a skeptical quant reader.
Published numbers are public. Do not silently change existing results: add to them, and keep suite and
prompt versions unchanged so new runs stay comparable.

## A. Claims and inference (code + docs, no LLM calls)

1. **Finding 2 "the shortfall is spread width, not fair value" holds only at low effort.** Mean signed
   mid error is small (at most 0.09 sd), but mean absolute mid error is 0.23-0.46 sd (bayes 0.07,
   bayes-noflow 0.34). The audit swapped components at each agent's own states:
   - sonnet@low: 10.6 as played; 89.8 with the agent's mid and Bayes width; 29.8 with Bayes mid and
     the agent's width.
   - haiku@high: 80.9 / 92.1 / 88.7.
   - fable@high: 90.9 / 95.8 / 94.0.

   Add this centring-vs-width decomposition to the report (all setups) and to the README. Rewrite
   finding 2. Fix the spread-chart subtitle in scripts/figures.py ("LLMs centre their quotes well").
   Width/Bayes metrics skip one-sided quotes (haiku@low quotes one side on 136 of 860 steps): handle or
   disclose this.
2. **Finding 6, classic minus perturbed: the CIs are too narrow.** The 4 classic games in each family
   share identical hidden states, so 20 classic games are 5 structures, but report.py ~210 bootstraps
   them as independent. Use a cluster bootstrap by hidden structure and Holm-correct across the 8 tests.
   After clustering, sonnet@high goes from [1.9, 22.5] to about [-2.1, 25.9]. Soften the finding to
   match.
3. **README cost bullets say "every Sonnet setup scores lower" than haiku@high.** Against sonnet@high
   that is 10.7 points, Holm p = 0.07: not significant, so say so. Also note that haiku@high is the
   least stable top setup (43.8% on cards against 76-91% on the other families).
4. **Wording fixes:**
   - Finding 4 says "after a trade", but beta flow also counts no-trade steps (metrics.py).
   - The "one run per model" limitation is worded backwards. Sampling noise is already in the game
     bootstrap; what's missing is run-level drift (date, server changes).
   - P(best) is always 1.00 for bayes, so it carries no information. Drop or explain it.
5. **Frame the design honestly.** Most of the Bayes edge is monopoly spread earned from noise traders
   whose price sensitivity is disclosed (capture 1.92 vs adverse 0.41 sd per episode). "LLMs quote too
   tight" may partly reflect the competitive-market habit. Say so, and point to glosten-milgrom as the
   competitive quote.

## B. New baselines and headroom (code, no LLM calls)

6. **Belief-isolating baselines:** the true posterior mean plus or minus k posterior sd, with k tuned
   on a separate seed set. Also add the "true posterior mean with the agent's own width"
   counterfactual (this links to item 1). static already scores 47 and bayes-noflow 88.5, so the scale
   needs anchoring. Explain the scale in the README.
7. **If time allows:** estimate headroom above the myopic Bayes reference with a one-step-lookahead
   policy, or an exact DP on the smallest game. Report whether a score of 100 is near-optimal.

## C. Hygiene

8. **Latency:** pick one definition. README and cost.png use provider_latency_s; REPORT.md and
   leaderboard.csv use engine wall clock, which drops to about 0 on cache replay.
9. **Cache-write costs:** record cache_write_1h_tokens in traces (llm.py USAGE_KEYS drops it). Cost
   currently assumes every cache write is a 1-hour write; pricing them as 5-minute writes cuts low-effort
   runs by up to 15% (opus@low 22.59 -> 19.14 per 1k quotes). Disclose this; the frontier doesn't
   change.
10. **anthropic: max_tokens default 8192 (registry.py ~178) can't reproduce haiku@high.** 198 of 860
    claude-cli replies were over 8192 output tokens (p95 14,206; max 43,375). Raise the default or
    document it next to the README claim that the API costs "about the same".
11. **Small fixes:**
    - The README Reproduce step writes 8 untracked episode-*.svg files into docs/figures: gitignore
      them or write them elsewhere.
    - pyproject sdist lists a non-existent top-level `suites`: remove it.
12. **CHANGELOG and CITATION:** the Claude 5.5/Fable results were committed on 2026-10-10 but folded
    into the [0.1.0] - 2026-10-09 entry, and no tag exists. Add a 0.2.0 entry for this work, dated
    today, and update CITATION.cff to match. Do not create tags or releases.
13. **CI:** bump actions/checkout to v7, astral-sh/setup-uv to v10.3.0 (pinned exact; from v8 there
    are no floating tags), and upload-artifact to v7 if it's used. This supersedes dependabot PRs 1 and
    2.

## D. New LLM runs (claude-cli; suite core-v1 unchanged)

Run these in order, stopping when the total list-price cost of the new runs reaches **USD 190**.
Compute the cost from the traces with mmarena.pricing, check it after each run, and don't start a run
whose expected cost would cross the cap.

1. opus 5.5 @high, replicate 2 (about $37).
2. opus 5.5 @medium (new effort point; about $30).
3. haiku 5.5 @high, replicate 2 (about $3).
4. fable 5.1 @high, replicate 2 (about $108).

Use jobs/concurrency the same as the original runs. Commit the traces under results/ (follow the
existing layout; do not overwrite the existing runs). Then add to the README and report:

- A run-to-run variability section: does Fable's +3.0 over opus@high (Holm p = 0.02) survive
  replicates? Pool or compare the runs properly.
- The effort curve for opus (low/medium/high).
- Updated cost and frontier figures.

If a run fails partway, keep what completed and say so. Don't fake numbers.

## Done-check

pytest (including --runslow where reasonable), ruff check and ruff format --check pass; the report and
figures regenerate from committed traces; every README number matches the regenerated report.
