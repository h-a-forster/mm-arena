# Pre-registration: core-v2

Written 2026-11-21, before any LLM run on a session suite. This file changes only by dated
amendments appended at the end; the text above them is never edited. The design, scoring and
suites are described in [methodology-v2.md](methodology-v2.md).

## Frozen before the pilot

- Suite files `core-v2`, `tight-v2` and `pilot-v2` (content hashes below; `mm-arena suite-hash`
  prints them), prompt version v2.0 (golden hashes pinned in `tests/test_prompt_v2.py`), the
  scoring and report code at the commit that adds this file, and this analysis plan.
- The numerator of every score: `ev_alpha`, the exact expected profit of each quote given public
  information and the session's true informed share. `ev` stays in the traces for the pricing
  diagnostic only.
- The tiers: core-v2 is 15 open and 30 mixed sessions (1,080 quotes per run). The tight tier is
  the separate extension suite `tight-v2`, reported in its own section and never pooled with
  core-v2.

| suite | content SHA-256 (`mm-arena suite-hash`) |
| --- | --- |
| `core-v2` | `3eb25ccd1c25dcd728d7e8c5bedfdef4e6a80a885991cfc59481d65e5365a098` |
| `tight-v2` | `a2e73b4d140c3260002bf76ae57c0f1bfe7c09df489a7ab6dc254d47e28b836e` |
| `pilot-v2` | `0baf28dc83ab0caa75cfa9561b539138a17d0e98dc84983824e5d14cbd5c575a` |
| `holdout-v2` (not published) | `c7eea06e8a94741aa4bb22ba6c6451c371bfcf2a2ae9c055b74c50499f5126cd` |

## Primary metric

The pooled oracle share on core-v2: `100 x sum(ev_alpha) / sum(oracle ev_alpha)` over the 45
sessions, each session in its game's prior-sd units, where the oracle is the known-regime
myopic quoter on its own path. Interval: 95% bootstrap over sessions, stratified by tier.
Every table prints the estimated ceiling (`ce-1`) beside the scores; it is never a denominator.

Secondary: the tier scores, the score by true regime, the shortfall identity and the skill-axis
table of the report.

## Pilot (two stages; no pilot trace enters a confirmatory test)

Stage 1: Fable 5.2, Opus 5.5 and Haiku 5.5 at high effort, one run each on `pilot-v2` (12
sessions: 6 open, 6 mixed, each regime twice per tier). Read-outs: learning response, the share
of quotes in rounds 1 and 2 tighter than the myopic Bayes quote, the score by true regime, and
tokens and cost per quote. Decision rule: go to stage 2 only if at least one of Fable 5.2 and
Opus 5.5 has a learning response whose 95% bootstrap interval lies above 0.3. If neither does,
the two top setups do not differ in kind on this task; core-v2 is reported as the headroom
suite beside core-v1, which stays the resolution suite.

Stage 2: a second run of Fable 5.2 and Opus 5.5 at high effort on `pilot-v2`, to estimate the
run-to-run SD. For each pilot session `s` and each of the two setups,
`v_s = (x_s1 - x_s2)^2 / 2` is the per-session run variance (`x` in prior-sd units); averaging
`v_s` over the two setups, the projected core-v2 run SD of the pooled score is
`sigma = 100 x sqrt((45 / 12) x sum_s v_s) / O`, with `O` the oracle's total on core-v2.

## Replicates

After stage 2, each setup in family A gets `n = 2 x (2.8 x sigma / delta)^2` runs (rounded up),
for the smallest pooled difference `delta` worth detecting, capped by budget. `delta` and the
cap are recorded in an amendment before the first full run. A pooled difference below the
detectable difference `2.8 x sigma x sqrt(2 / n)` is reported as "not separated".

## Setups

Fable 5.2, Opus 5.5, Sonnet 5.5 and Haiku 5.5 at high effort, with the replicate count above for
the two top setups and one run otherwise; the same four at low effort, one run each. All runs on
one Claude Code version, recorded in each trace's provenance. Replicates are named `#rN` and run
without the response cache.

## Hypotheses and tests

Paired tests use per-session differences of run-averaged values; sign flips are exact up to 14
sessions and use 10,000 random flips otherwise. One-sided where stated.

- **H1 (separation).** Fable 5.2 @high and Opus 5.5 @high are separated on the pooled score if
  the point estimate of their gap is at least 3 pooled run-to-run SDs and the Welch test on run
  means has p below 0.05. With three runs each the SD has four degrees of freedom; the report
  states it. Family A also holds the two-sided paired sign-flip test of every pair of the eight
  primary setups (four models at two efforts) on the pooled score.
- **H2 (learning).** For each high-effort setup: the learning response is above 0 (one-sided,
  session bootstrap), and the setup beats `bayes-nolearn` on the mixed tier (one-sided paired).
- **H3 (probing).** At least one setup beats the myopic `bayes` on the mixed tier (one-sided
  paired). Descriptive companion: a setup that does has a smaller information gap than `bayes`.
- **H4 (gradient).** For each setup, its oracle share is lower on the mixed tier than on the open
  tier (one-sided, session bootstrap).
- **H5 (effort).** For each model, high effort beats low effort on the pooled score (one-sided
  paired).

No hypothesis is defined relative to a quoter that a later version can improve (such as
`bayes-lookahead`): only the oracle and the myopic learner are exact and fixed. The headroom on
the tight tier is reported descriptively in the `tight-v2` section (scores, the ceiling estimate
and the share of the best public quoter run so far), not tested.

**Multiple testing.** Holm within each family: (A) the pairwise tests among the eight primary
setups; (B) H2 and H3; (C) H4 and H5. Results live in `results/core-v2/`; core-v1's
families are unchanged.

## Run-to-run and held-out

The report prints the SD of run scores per setup and the Welch test for each pair of setups
with at least two runs. The held-out suite `holdout-v2` (same blocks as core-v2, secret seeds,
secret regime orders and a secret salt; only its hash is public) gets one run of the two top
setups. The public-minus-held-out pooled score is reported with a bootstrap interval over the
sessions of both suites; the two suites have different games, so the comparison is not paired.
The same deterministic quoter differs between two 45-session suites by an SD of about 2 to 5
pooled points from the draw of games alone, before run noise, so only a gap of roughly 10
points or more is evidence of contamination. It is not a hypothesis test.

## Stopping and exclusions

A run counts when all of its sessions have status `ok`. Provider failures are retried and never
scored; a reply that cannot be read scores zero for that quote, as in core-v1. No session is
dropped for any other reason. Any deviation from this plan is reported with the results, with
its reason.

## Amendments

### 2026-11-21: the learning response (H2 and pilot stage 1)

Made before any LLM run on a session suite: no LLM trace of any session suite exists.

**Why.** As first defined, the learning response was the slope of (agent half-width minus
prior-regime half-width) on (Bayes half-width minus prior-regime half-width). The prior-regime
half-width was on both sides, so a width that follows neither quote read above 0: `static`
0.32 and `random` 0.36 on core-v2. H2's first clause could be met without learning anything.

**What changes.**

1. The learning response is the coefficient on the myopic Bayes quote's half-width when the
   agent's half-width is regressed, by least squares with an intercept, on the Bayes and the
   prior-regime half-widths together, over the quotes where all three are two-sided, in prior-sd
   units. Interval and one-sided p-value: the session bootstrap, stratified by tier, as before.
   On core-v2 it reads 1.00 for `bayes`, 0.95 for `bayes-optimist`, 0.85 for `bayes-thompson`,
   0.58 for `bayes-lookahead-w8`, 0.12 for `bayes-nolearn`, 0.04 for `bayes-mean`, 0.00 for
   `static` and -0.01 for `random`. This statistic replaces the first one in H2's first clause,
   in the stage-1 read-out and decision rule, and in the report. Nothing else in the report
   code changes a number: scores, intervals and the other tests are as frozen.
2. Stage-1 decision rule: go to stage 2 only if at least one of Fable 5.2 and Opus 5.5 has a
   learning response whose 95% bootstrap interval lies above **0.25** (was 0.3, for the first
   statistic).
3. H2 keeps its wording: the learning response is above 0 (one-sided, session bootstrap), and
   the setup beats `bayes-nolearn` on the mixed tier (one-sided paired). Families and Holm are
   unchanged.
4. The reference quoters' traces are written to the pilot's run directory before any LLM run
   (`mm-arena run --agent baselines --suite pilot-v2`), so that their values print beside the
   models'.

**Calibration of the threshold.** Reference quoters under the decision-noise model of
[methodology-v2.md](methodology-v2.md) section 10, at its noise level (x1) and at twice it (x2,
about the ratio of real to modelled run noise on core-v1), on `pilot-v2`, each run scored by
the report: `scripts/learning_response_v2.py`, 40 noise seeds per quoter and 24 for
`bayes-lookahead-w8` (`--bases bayes-lookahead-w8 --seeds 24`). Cells: learning response, mean
(SD) over runs; then the number of runs whose 95% interval lies above the threshold.

| quoter with decision noise | x1: mean (SD) | above 0.2 | above 0.25 | above 0.3 | above 0.35 | x2: mean (SD) | above 0.2 | above 0.25 | above 0.3 | above 0.35 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `bayes` | 0.92 (0.13) | 40/40 | 40/40 | 40/40 | 40/40 | 0.95 (0.20) | 40/40 | 40/40 | 39/40 | 39/40 |
| `bayes-optimist` | 0.88 (0.12) | 40/40 | 40/40 | 40/40 | 40/40 | 0.88 (0.19) | 40/40 | 40/40 | 38/40 | 37/40 |
| `bayes-thompson` | 0.75 (0.14) | 40/40 | 40/40 | 40/40 | 39/40 | 0.78 (0.30) | 34/40 | 33/40 | 31/40 | 28/40 |
| `bayes-lookahead-w8` | 0.57 (0.09) | 24/24 | 24/24 | 22/24 | 18/24 | 0.54 (0.14) | 21/24 | 18/24 | 15/24 | 14/24 |
| `bayes-fixed-high` | 0.33 (0.16) | 8/40 | 3/40 | 2/40 | 0/40 | 0.42 (0.26) | 7/40 | 5/40 | 4/40 | 2/40 |
| `bayes-nolearn` | 0.19 (0.07) | 1/40 | 0/40 | 0/40 | 0/40 | 0.18 (0.13) | 0/40 | 0/40 | 0/40 | 0/40 |
| `bayes-mean` | 0.04 (0.05) | 0/40 | 0/40 | 0/40 | 0/40 | 0.03 (0.09) | 0/40 | 0/40 | 0/40 | 0/40 |
| `static` | -0.01 (0.05) | 0/40 | 0/40 | 0/40 | 0/40 | -0.03 (0.10) | 0/40 | 0/40 | 0/40 | 0/40 |

The rule for choosing it: at x1 the highest lower interval bound of any run of the three quoters
that do not learn the informed share (`bayes-nolearn`, `bayes-mean`, `static`) is 0.203 and the
lowest of any run of the four that do (the first four rows) is 0.293; the threshold is the
midpoint, rounded to 0.25. At 0.25 every learning run passes at x1 and 131 of 144 at x2, the
misses being the two quoters that depart from the Bayes width on purpose; no run of the three
non-learners passes at either level. `bayes-fixed-high` assumes the most informed crowd
throughout and matches the Bayes quote whenever the evidence points there; it passes in 3 and 5
of 40 runs, and its score by true regime shows what it is. A quoter that probes reads below 1
(0.54 to 0.57 here) because it sets widths the Bayes quote does not.

**What H2's first clause tests after the change.** The one-sided p-value against 0 is below
0.05 in 2 of 40 runs of noisy `static` at x1 and 1 of 40 at x2 (first statistic: its interval
lay above 0 in 15 of 16 runs), in 6 and 5 of 40 runs of `bayes-mean`, and in every run of the
four learning quoters but one. It is also below 0.05 in 33 and 18 of 40 runs of
`bayes-nolearn`, whose width still moves a little with the evidence (0.12 to 0.19): the first
clause shows that a setup's widths respond to the evidence at all, and the second clause is
what separates a setup from `bayes-nolearn`.

### 2026-11-21: replicate count, budget and run plan (after pilot stage 2)

Made after the pilot and before any LLM run on `core-v2`, `holdout-v2` or `tight-v2`.

**Pilot.** Stage 1 ran Fable 5.2, Opus 5.5 and Haiku 5.5 at high effort on `pilot-v2`, plus
Sonnet 5.5 at high effort as an extra check of the run path (not in the stage-1 plan; like every
pilot trace, it enters no test). Every session of every run had status `ok` and no quote was
unreadable. Stage-1 decision rule: Fable 5.2's learning response was 0.95 with 95% interval
[0.88, 0.97], above 0.25, so stage 2 ran (a second run of Fable 5.2 and Opus 5.5 at high
effort, without the response cache).

**Code changed since the freeze.** Two commits landed after pilot stage 1 started and before
stage 2: 0262290 computes the prior mean of the informed share in plain floats, left to right,
because a BLAS dot product rounded its last bit differently by machine and the value is hashed
into every session id; with the new code the session ids equal the published ones and those of
every pilot trace, so no game and no score changed. 0262290 and 5f67b30 also make the report
divide before scaling (the oracle scores exactly 100 in every bootstrap draw) and report a
learning response below 1e-9 as exactly 0. Only p-values of statistics that are exactly zero in
exact arithmetic changed; no suite changed, and no score beyond floating-point rounding.

**Run-to-run SD.** With the formula of the pilot section (`O` = 110.61, the oracle's total on
`core-v2`), the projected `core-v2` run SD of the pooled score is `sigma` = 1.20 pooled points
(1.16 if the pilot variance is scaled per tier, 15/6 open and 30/6 mixed; the formula as written
is used).

**Replicates.** `delta` = 3 pooled points, so `n = 2 x (2.8 x 1.20 / 3)^2` rounded up = 3 runs
each for the two top setups, Fable 5.2 @high and Opus 5.5 @high, as the Setups section and H1
say; the Replicates section's "each setup in family A" is read as those two, since the Setups
section gives every other setup one run. A replicate count is never raised after results are
seen. With `n_a` and `n_b` runs, a pooled difference below `2.8 x 1.20 x sqrt(1/n_a + 1/n_b)`
is reported as not separated: 2.74 points for three runs against three, 3.88 for three against
one, 4.75 for one against one.

**Runs, in start order.** `core-v2`: Opus 5.5 @high runs 1 to 3, Fable 5.2 @high runs 1 to 3
(`#r2` and `#r3` without the response cache), Sonnet 5.5 and Haiku 5.5 @high, then Opus,
Sonnet, Haiku and Fable @low, one run each. `holdout-v2`: one run each of Opus 5.5 and Fable 5.2
@high. `tight-v2` (for its descriptive section): one run each of Opus 5.5 and Fable 5.2 @high.
Runs start in this order, at most three at a time, except that a run waits until the earlier run
of its setup on the same suite has ended, a low-effort run until the same model's high-effort
runs on `core-v2` have ended, and a Fable 5.2 run until the weekly usage limit allows it; while a
run waits, runs listed after it may start. Two runs of one setup on one suite never
run side by side. The reference quoters are written to each run directory first.

**Pinned harness.** Every run uses Claude Code 2.1.330, the pilot's version, from a frozen copy
of that release; a run is started only if that copy reports `2.1.330`, and each trace records the
version.

**Budget cap.** All runs above together, at most 1,400 USD at list price as computed by
`mmarena` from each call's tokens (estimate from the pilot's cost per session, taking a
low-effort run to cost no more than the same model's high-effort run: about 1,240 USD). Before
each run starts, the projected total is compared with the cap: the cost so far plus the estimate
for what every started and every not-yet-started run still needs. While it exceeds the cap,
low-effort runs not yet started are cut in the order Haiku, Sonnet, Opus, Fable; if it still
exceeds the cap, no further run starts. A run already started is completed, so its own overrun of
its estimate is the only way the total can pass the cap. Every cut is reported.

**Completion.** A started run is completed: usage limits are waited out; other provider failures
are retried, and a run that makes no progress after six attempts is resumed by hand. No failure
is scored. No run is stopped, repeated or added because of a score.

### 2026-11-22: first release with part of the run plan (deviation)

Made while the runs above were in progress, before any report of an LLM run on `core-v2` had been
generated, and not because of a score: the remaining Fable 5.2 runs depend on a weekly usage limit,
and the results are released now rather than after all of them.

**Run.** On `core-v2`: Opus 5.5 @high runs 1 to 3, Fable 5.2 @high runs 1 and 2, Sonnet 5.5 and
Haiku 5.5 @high, and Opus 5.5 @low, one run each. Every session of every run has status `ok`, no
quote was unreadable, and every trace records Claude Code 2.1.330. Cost at list price: 549 USD.
Runs that had started were completed; the third Opus 5.5 run had ended before the decision and
is included, as planned.

**Deferred.** Fable 5.2 @high run 3; Sonnet 5.5, Haiku 5.5 and Fable 5.2 @low; both `holdout-v2`
runs; both `tight-v2` runs. They are not dropped: they will run later, on the same pinned
harness, and the report will then be regenerated over all runs.

**Effect on the analysis until then.** H1 compares two Fable 5.2 runs with three Opus 5.5 runs
(run SD with three degrees of freedom; a gap below `2.8 x 1.20 x sqrt(1/2 + 1/3)` = 3.07 pooled
points would be reported as not separated). Families A to C hold the tests among the setups run so
far, Holm-adjusted within those, so their adjusted p-values will change when the deferred setups
are added; H5 has Opus 5.5 only. The held-out comparison and the `tight-v2` section are not yet
available. Every confirmatory result in this release is provisional until the plan is complete.
