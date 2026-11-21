# Methodology: session suites (core-v2)

This page defines the session suites that sit beside core-v1: the game, the exact posterior,
the score and its anchors, the reference quoters, the suites, what the report prints, and the
known limits. core-v1 ([methodology.md](methodology.md)) is unchanged: its suites, prompt,
scoring and published results are pinned by `tests/test_v1_frozen.py`.

## 1. What changes from core-v1

| | core-v1 | core-v2 |
| --- | --- | --- |
| unit | an episode: one game, one hidden outcome | a session: one game for 6 rounds, a fresh hidden outcome each round |
| hidden from the market maker | the outcome | the outcome and the informed share `α` |
| `α` | disclosed | one of {0.05, 0.5, 0.9}, prior 1/3 each, fixed per session |
| noise scale `s` | disclosed, 0.75-1.5 prior sd | disclosed, `ρ` x prior sd by tier |
| feedback | none | the settlement value after each round |
| score anchor (100) | the myopic Bayes quoter | the known-`α` oracle |
| quotes per run | 860 | 1,080 |

Only the informed share is hidden. Hiding the noise scale as well was tried while designing the
suite and added little: the profit curve is flat around the best width, and most of the
expected profit sits in sessions where any reasonable width does well. With a toxic regime
(`α = 0.9`) the informed share is different: the best quote when `α = 0.05` loses heavily
when `α = 0.9`, and a quote wide enough for `α = 0.9` earns almost nothing when `α = 0.05`.
The disclosed noise ratio `ρ = s / prior sd` is the difficulty dial: the smaller it is, the more
adverse selection dominates and the more learning `α` is worth.

## 2. The session game

A session takes one perturbed core-v1 game (dice, cards, transform, coin or urn), keeps its
first reveal group, sets two quotes per stage and plays it for six rounds against the same crowd
of counterparties. In each round:

1. a fresh hidden outcome is drawn from the game's prior, independently of earlier rounds;
2. the market maker posts two quotes (stage 1), part of the outcome is revealed, it posts two
   more (stage 2);
3. the contract settles: only the settlement value becomes public (components that were never
   revealed stay hidden), the position is closed at it, and the next round starts flat.

Each quote meets one counterparty, exactly as in core-v1: informed with probability `α` (it
knows the settlement value), otherwise a noise trader valuing the contract at the public fair
value plus Normal noise of scale `s`. The inventory limit and tick are core-v1's draw for the
game; the limit applies within a round. `s` is `ρ` times the game's prior sd, rounded to two
significant figures as in core-v1. Everything is disclosed except `α`, including its prior.

The suite fixes each session's true regime so that each tier and family block holds each regime
equally often, in a seeded random order. Per session the regime is still uniform over the
three values, which is what the prompt states; the balance removes regime-sampling noise from
the scores.

## 3. Exact posterior

The public posterior is a weight matrix `W[k, i]` over (regime `k`, outcome `i`) for the current
round and a regime belief `w_α[k]` carried across rounds (`mmarena.joint.JointPosterior`):

- round start: `W = w_α ⊗ prior`;
- reveal: multiply by the indicator of consistency and renormalise;
- trade or no trade at `(b, a)` with public mean `μ`: multiply `W[k, i]` by
  `α_k·1[V_i > a] + (1 − α_k)·Φ((μ − a)/s)` for a buy, the mirror for a sell, the complement
  for no trade (core-v1's likelihood with `α` indexed by `k`);
- settlement at value `v`: `w_α[k] ∝ Σ_{i: V_i = v} W[k, i]`. The fill probabilities depend on
  the outcome only through its value, so the value is all the update needs.

`μ` is the mean of `V` under `W`, a function of public information only, so the noise traders'
centre is well defined. With one regime every operation reduces to core-v1's `market.py`
(tested on random states). The state is `3 x |Ω|` numbers; a baseline session runs in about
0.1 s.

## 4. The score

Every quote is scored with two exact one-step expectations:

- `ev`: given public information (under `W`), core-v1's `EV_t` with a sum over regimes;
- `ev_alpha`: given public information and the session's true `α` (row `k*` of `W`,
  renormalised, with `α_{k*}`).

Both are unbiased for realised profit for any quote rule that uses public information only, and
`ev` is the posterior mean of `ev_alpha`. The **score is `ev_alpha`**:

    score = 100 x Σ_sessions Σ_quotes ev_alpha / Σ_sessions oracle ev_alpha

with each session in its game's prior-sd units. **100 is the profit of a quoter who is told the
informed share** and quotes the myopic optimum for it (the `oracle`, on its own path); 0 is never
quoting; a negative score is an expected loss. `ev_alpha` is the only expectation that is
unbiased for the oracle (its quote depends on `α`), so numerator and denominator share one
footing, and it removes the luck of which regime a session drew. `ev` is kept in the traces for
the pricing diagnostic. The choice of numerator was fixed before any LLM run.

Quotes are parsed, snapped and voided exactly as in core-v1 (last JSON object with both keys,
nulls allowed, non-finite, crossed and unreadable replies score zero for that quote). No reply
can score above the oracle's `ev_alpha` or the myopic learner's `ev` at the same state; the
reference optimum searches both sides over the whole tick range and returns the best uncrossed
pair, and a test feeds adversarial replies through the parser and the engine.

## 5. Reference quoters

All are white-box Python agents on exact posteriors (`mmarena.agents.session_baselines`).

| name | belief | quote rule | role |
| --- | --- | --- | --- |
| `oracle` | public posterior given the true `α` (privileged) | myopic optimum for that `α` | the 100-point anchor |
| `bayes-lookahead`, `-w2`, `-w4`, `-w8` | exact public joint posterior | immediate `ev` plus weight x expected myopic-optimal `ev` of the next quote, across fills, reveals and settlements | public quoters that value what a quote teaches |
| `bayes-optimist` | exact | myopic optimum with regime weights tilted toward profitable regimes, `w_k·exp(γ v_k / max v)` | a cheap exploring heuristic |
| `bayes` | exact | myopic optimum | the exact per-state reference of every diagnostic |
| `bayes-thompson` | exact | samples a regime each round, quotes as the oracle would | textbook exploration |
| `bayes-nolearn` | exact value belief given each regime, regime weights pinned to the prior | myopic optimum | the value of learning `α` |
| `bayes-fixed-low`, `-high` | core-v1's Bayes with `α` assumed 0.05 / 0.9 | myopic optimum | a wrong fixed guess |
| `bayes-noflow` | reveals and settlements only | myopic optimum | the value of order flow |
| `bayes-mean` | exact | public mean ± k public sds | belief without pricing |
| `glosten-milgrom` | exact | zero-profit quote | the competitive quote; a simulator check |
| `static`, `random` | none | as core-v1 | floors |

Only the oracle is told `α`, through a hook that the engine calls only for agents that declare
privileged access; the observation every other agent and the prompt are built from has no field
for the regime or any hidden outcome.

Because `α` lasts the whole session, what a quote teaches pays on every later quote, and plain
one-step lookahead (weight 1) prices it for one quote only. A larger weight on the next quote's
value probes more: on the tight tier weight 8 earns 65.7% of the oracle against 55.8% for
weight 1 (150 sessions; section 6). The best weight differs by tier, so "the best public
quoter" is a moving target, and no hypothesis or denominator depends on it.

## 6. The ceiling

The oracle cannot be reached by a quoter that has to learn `α`, and the best such quoter is not
computable for these sessions: at each round start the state is a belief over `α` (a continuum),
and within a round every candidate quote must be followed through fills, the reveal and the
settlement. The suite therefore keeps the oracle as the fixed 100 and prints beside every score
an **estimated ceiling** (`ce-1` in the report): the best score a quoter that does not know `α`
could reach, with a bracket. It is never a denominator, and later versions may tighten it.

- From below: the best public quoter run (lookahead with weights 1 to 8).
- From above: a relaxation that tells every quoter `α` for free after round 1; no public
  quoter can beat "best public profit in round 1, the oracle's afterwards" (an estimate,
  because the best round-1 profit is taken over the quoters run).
- In between: a miniature of the game (two four-sided dice, the same fill model, prior and
  noise ratios, six rounds of four quotes) solved exactly by dynamic programming on a menu of
  symmetric quotes, with the value between rounds interpolated on a belief grid
  (`scripts/ceiling_v2.py miniature`). There the best lookahead variant is within a few points
  of the optimum, which is why the estimate sits just above the suite's best lookahead variant.

Share of the oracle, %; the suite rows are 150 sessions per tier (`scripts/headroom_v2.py`, base
seed 50000; open tier at `ρ` 0.85), the miniature rows `scripts/ceiling_v2.py miniature`:

| | open | mixed | tight |
| --- | ---: | ---: | ---: |
| miniature: exact optimum | 92.9 | 87.4 | 67.1 |
| miniature: best lookahead (weight 1 or 4) | 92.8 | 86.7 | 65.4 |
| miniature: myopic learner | 91.0 | 78.4 | 38.4 |
| suite: relaxation (`α` told after round 1) | 97.0 | 94.8 | 86.0 |
| suite: best lookahead (weight 2 / 4 / 8) | 91.6 | 88.9 | 65.7 |
| suite: `bayes` | 89.0 | 72.3 | 31.6 |
| **ceiling estimate `ce-1`** | **92 (91.6 to 97.0)** | **90 (88.9 to 94.8)** | **67 (65.7 to 86.0)** |

The estimate is the suite's best lookahead plus the miniature's gap between the optimum and the
best lookahead. The pooled core-v2 ceiling is the oracle-weighted mean of the tier estimates,
about 91. On the tight tier the oracle overstates what is attainable by about 33 points: most of
the distance to 100 there cannot be closed by any quoter that has to learn `α`. The number of
rounds is the lever on that ceiling (`--rounds` in the miniature), at the cost of quotes.

For a tier whose ceiling is below 85, the report adds a provisional second column: the share of
the best public quoter run so far (`bayes-lookahead-w8`, tag `ref-1`), so that a quoter near the
optimum reads as near 100 there. It is not the score and is not used in any test.

## 7. Suites

| suite | sessions | quotes | use |
| --- | ---: | ---: | --- |
| `smoke-v2` | 3 (2 rounds) | 24 | CI, quick checks |
| `pilot-v2` | 12: 6 open, 6 mixed | 288 | the LLM pilot |
| `core-v2` | 45: 15 open, 30 mixed | 1,080 | the session leaderboard |
| `tight-v2` | 15 tight | 360 | extension: the reserve of headroom, reported on its own |
| `holdout-v2` | as core-v2, secret | 1,080 | contamination check; not in the repository |

The tiers, on 150 sessions each (`scripts/headroom_v2.py --sessions 150`, with the lookahead
quoters added through `--agents`; share of the oracle, %):

| tier | noise ratio `ρ` | suite | oracle profit per session (prior sd) | share of it in `α = 0.05` sessions | `bayes` | `bayes-nolearn` | `bayes-noflow` | `bayes-optimist` | best lookahead |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| open | 0.85 | core-v2 | 2.93 | 73% | 89.0 | 78.9 | 66.9 | 89.4 | 91.6 (weight 2) |
| mixed | 0.7 | core-v2 | 2.12 | 82% | 72.3 | 56.8 | 44.1 | 83.6 | 88.9 (weight 4) |
| tight | 0.5 | tight-v2 | 1.35 | 91% | 31.6 | 21.0 | 18.9 | 41.5 | 65.7 (weight 8) |

Learning the informed share (`bayes` minus `bayes-nolearn`) is worth about 10 points on the
open tier and 16 on the mixed tier; probing (best lookahead minus `bayes`) about 3 and 17. The
open tier's ratio was set to 0.85 rather than 1.0 because a scan of 0.85, 0.9, 0.95 and 1.0 put
the value of learning at 10.1, 8.2, 7.2 and 5.8 points; 0.85 is inside core-v1's range of noise
scales (0.75 to 1.5 prior sd). The mixed and tight tiers sit where the learner falls well
behind the oracle but the oracle still earns well; below `ρ` of about 0.35 no quoter tried
earns anything.

The released suites are small draws from these tiers, so their baseline scores differ from the
table (`results/core-v2/REPORT.md`, `results/tight-v2/REPORT.md`). core-v2 lands close: `bayes`
91.6 open and 69.3 mixed, the best lookahead 92.3 and 88.8. tight-v2's 15 sessions land low:
`bayes` 19.8 and the best lookahead 43.7 [1.2, 59.2], against 31.6 and 65.7 on 150 sessions.
Its scores are best read against its own baselines.

The tight tier is a separate suite because its scores move a lot with the draw of games, its
ceiling is far below 100, and on it the exact learner is hardly distinguishable from a quoter
that never learns: what it separates is quoters that probe from those that do not. It is never
pooled with core-v2.

Game seeds are `30000 + 1000 x family + 100 x tier + i` (pilot blocks offset by 50; smoke-v2
at 35000-35200), disjoint from core-v1 (1000-9007), full-v1, every tuning sample (the ladder
and tuning scripts use 50000-95299 and 131000-135299) and the test sessions (140000 and up).
A session's id hashes its public spec and the suite's salt, never its regime; all random draws
are a function of the session id and seed (common random numbers). `scripts/make_suites_v2.py`
writes the suite files from these rules and checks the committed ones against them.

## 8. Prompt version v2.0

Same structure as core-v1's prompt (`agents/prompt_v2.py`; print one with
`mm-arena prompt --suite core-v2 --session 0`): a system prompt with the rules, a static game
segment, a dynamic state segment; stateless calls; the same reply format. It states that each
round draws a fresh hidden state; that only the settlement value is shown after a round; that
`α` was drawn before the session from the disclosed prior, independently of the game and of the
hidden states, and is the same for every quote; that the noise scale is the same in every
round; that the inventory limit applies within a round; and it defines the public fair value as
the expected settlement value given the game description, this round's revealed values, and
every quote, trade and settlement of the session. The history is raw rows per round, with each
reveal where it happened and the settlement value: no counts, no profit summaries, no tier
names, no strategy hints. The objective is the expected total profit over the session.

## 9. What the report prints

`mm-arena report DIR` (`session_report.py`) prints, per agent:

- the pooled and tier scores, with 95% intervals from a bootstrap over sessions within each
  tier, and the ceiling line;
- the score by true regime: share of the oracle when `α` is 0.05 or 0.5, expected profit per
  session in prior sd when `α` is 0.9 (the oracle earns little there). Most of a tier's oracle
  profit sits in its benign sessions, so a quoter that is merely too tight takes its losses in
  the toxic ones; this split keeps width from being read as learning;
- the **shortfall identity**, exact per session, in oracle points:
  `oracle − agent = pricing + information + path + residual`. Pricing: `Σ (bayes_ev − ev)`,
  what the agent's quotes gave up against the myopic Bayes quote given public information (an
  explorer pays here on purpose). Information: `Σ (oracle ev_alpha − bayes ev_alpha)` at the
  agent's states, what not knowing `α` still costs after what the agent's own quotes revealed.
  Path: the oracle on its own path minus the oracle at the agent's states. Residual: the
  regime luck of the agent's quotes against the Bayes quotes at the same states, zero in
  expectation for any public quote rule;
- skill axes: the **learning response** (the coefficient on the Bayes quote's half-width when the
  agent's half-width is regressed, with an intercept, on the Bayes and the prior-regime half-widths
  together, at the same states, in prior-sd units. The prior-regime quote is the myopic optimum at
  the same state with the public value belief kept and the regime belief put back to the prior. 1:
  the widths follow the evidence on `α` as the Bayes quote does; 0: they follow the prior-regime
  quote or neither. On core-v2 it reads 1.00 for `bayes`, 0.12 for `bayes-nolearn`, 0.00 for
  `static` and -0.01 for `random`; a quoter that probes sets widths the Bayes quote does not and
  reads below 1, 0.58 for `bayes-lookahead-w8`. The reference quoters' own values are printed beside
  each model's), the posterior mass on the true regime at each round start along the agent's path,
  the share of early quotes tighter than the Bayes quote (probing), width relative to the Bayes
  quote, and mid error;
- run-to-run variability (SD of run scores per setup, Welch tests) and the pre-registered test
  families ([prereg-core-v2.md](prereg-core-v2.md)).

The oracle, `bayes` and `bayes-nolearn` are deterministic given a session and seed; when a run
directory lacks their traces the report computes them from the session specs in the traces.
Every other reference quoter has a row only if its traces are in the run directory.
`mm-arena run --agent baselines --suite SUITE --out DIR` writes all of them, and it is run on
a directory before any LLM run is read; the report of an LLM run names the reference quoters
that are absent.

## 10. Statistical power

There are no LLM runs on core-v2 yet, so run-to-run noise is projected with a decision-noise
model (`scripts/power_v2.py`): the Bayes quote's mid moves by Normal(0, 0.25 posterior sds) and
its half-width by a lognormal factor (bias −8%, sd 0.25), half of each variance per session and
half per quote. On core-v1 the same model gives a run SD of 0.95 points, where real setups have
1.5 to 2.0.

On core-v2, 8 noise seeds per quoter (`scripts/power_v2.py --suite core-v2`):

| quoter with decision noise | open (run SD) | mixed (run SD) | pooled (run SD) |
| --- | ---: | ---: | ---: |
| `bayes` | 67.4 (3.58) | 53.3 (3.54) | 58.9 (2.34) |
| `bayes-nolearn` | 58.2 (3.50) | 41.4 (3.81) | 48.1 (2.61) |
| `bayes-optimist` | 66.4 (3.84) | 53.4 (3.22) | 58.6 (1.67) |

The model's pooled run SD is 2.2 points; scaled by core-v1's ratio of real to modelled noise
(1.6 to 2.1) the projected real run SD is 3.5 to 4.6 points. Learning the informed share is
worth 10.8 pooled points under this noise (4.4 model run SDs), while the probing gap of the
noiseless quoters disappears (−0.4): decision noise of this size costs as much as probing
gains. With the replicate rule of the pre-registration and a run SD of 3.5 to 4.6, detecting a
5-point gap takes 8 to 14 runs per setup and a 10-point gap 2 to 4.

What follows: core-v2 resolves differences of kind (not learning `α`, learning it, probing for
it), not the small decision-noise differences core-v1 measures; for those core-v1 is the more
efficient suite. The number of replicates is not fixed in advance: the pre-registration sets it
from the pilot's measured run SD and the smallest gap of interest.

The same noise model, at its level and at twice it, sets the pilot's threshold on the
learning response (`scripts/learning_response_v2.py` on pilot-v2). A run of a quoter that
learns `α` (`bayes`, `bayes-optimist`, `bayes-thompson`, `bayes-lookahead-w8`) has a 95%
interval above 0.25 in 144 of 144 runs and, at twice the noise, in 131 of 144; a run of
`bayes-nolearn`, `bayes-mean` or `static` in none of 120 at either level. The table is in the
pre-registration's amendment of 2026-11-21.

## 11. Contamination

Games are procedurally generated from seeds, and published traces contain the reference quotes
at every visited state, which is the contamination channel. The held-out suite `holdout-v2` has
core-v2's blocks with secret seeds, secret regime orders and a 32-byte secret salt that enters
every session id and so every random draw. It is generated by
`scripts/make_suites_v2.py --holdout PATH` and kept outside the repository; only its content
hash is published:

    holdout-v2  c7eea06e8a94741aa4bb22ba6c6451c371bfcf2a2ae9c055b74c50499f5126cd

`mm-arena suite-hash PATH` recomputes it from the parsed content (independent of formatting and
line endings; any change to a value, the salt included, changes it).

The held-out games are sent to the model provider in the prompts of any run on them. The same
deterministic quoter differs between two 45-session suites by an SD of about 2 to 5 pooled
points from the draw of games alone, before run noise, so only a public-minus-held-out gap of
roughly 10 points or more is evidence of contamination.

## 12. Validity checks

Tests that guard the design (`tests/test_joint.py`, `test_session_engine.py`,
`test_session_baselines.py`, `test_prompt_v2.py`, `test_session_report.py`):

- with one regime the joint posterior, quote values and optimal and zero-profit quotes equal
  core-v1's; the regime update after settlements equals brute-force enumeration;
- the reference optimum is the argmax over every tick-grid pair, for the public and the
  known-regime expectation; no snapped random quote beats it;
- `bayes` and `oracle` reproduce the engine's recorded reference quotes exactly;
- mean realised profit matches `ev` and `ev_alpha` for a public quoter and `ev_alpha` (not
  `ev`) for the oracle, within Monte Carlo error;
- draws are identical across agents and regimes for the same session and seed;
- under a fixed informative quote the posterior mass on the true regime exceeds 0.95 after 30
  rounds; over 30 rounds the myopic learner earns at least 93% of the oracle in rounds 21-30 on
  the open tier (97.0% over 60 sessions). On the mixed tier the same share is about 95% over 60
  sessions but no threshold holds in small samples: in some sessions with `α` of 0.05 or 0.5
  the learner's belief leans toward the toxic regime, its myopic quote moves to the edges of
  the value range, where informed traders cannot trade and fills are rare, and it stops
  learning (ten such sessions of the 60 earn 7% to 86% of the oracle in rounds 21-30). This is
  the incomplete learning of a greedy quoter, which the lookahead quoters exploit;
- the learning response is 1 for `bayes`, near 0 for `static`, `bayes-nolearn` and
  `bayes-noflow`, and 0 for a width that is constant or equal to the prior-regime width;
- lookahead beats the myopic learner on the tight tier, and the ladder oracle > `bayes` >
  `bayes-nolearn` > `bayes-noflow` > `glosten-milgrom` holds on tuning sessions;
- the prompt is identical across regimes at the same public state, and its step-0 hashes are
  pinned.

## 13. Limitations

- Everything in core-v1's limitations that concerns the counterparty model and expected P&L as
  the score applies unchanged.
- The anchor is not attainable and the attainable optimum is only bracketed (section 6). Scores
  near the ceiling estimate should be read as near the best possible, not as weak.
- Three regimes is a small grid; the task is to classify the crowd and to decide how much to
  pay to find out. A finer grid, a hidden noise scale, a hazard of regime change between rounds
  and a lower noise ratio are reserve dials that need no engine change, each a new suite version.
- Run-to-run noise is large relative to core-v1 (section 10); the pooled score is the headline
  and tier scores are secondary.
- The suite balances the regimes while the prompt says `α` was drawn uniformly; both hold per
  session, and the balance is documented here.
- Noise traders centre on the public mean, which now depends on the posterior over `α`. It is
  exact and stated in the prompt, but a model may centre on the reveal-only mean; that shows up
  as mid error.
