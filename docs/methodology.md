# Methodology

This page defines the game, the reference quoters, the estimator behind every score, and the
known limits of the design.

## 1. The game

A game has a finite hidden state `ω` drawn from a prior `π` (dice faces, cards dealt, a coin's
bias and its flips, an urn's composition and draws). A contract settles at `V(ω)`.

The game runs in stages. Before each stage after the first, some components of `ω` become
public (a die, a card, two flips). Within a stage the market maker posts `quotes_per_stage`
quotes. After the last stage the contract settles.

Each quoting step:

1. The market maker posts a bid `b` and an ask `a` (either side may be empty, `b <= a`).
   Quotes snap outward to the game's tick: bids round down, asks round up.
2. One counterparty arrives.
   - With probability `α` it is **informed**: it knows `V` (optionally with Gaussian noise of
     scale `informed_noise`). It buys one unit if `V > a`, sells one unit if `V < b`.
   - Otherwise it is a **noise trader** with valuation `μ_t + s·ε`, `ε ~ N(0, 1)`, where
     `μ_t = E[V | public information]`. It buys if its valuation is above `a`, sells if below `b`.
3. The fill (or the absence of one) is public.

At `±L` units of inventory the side that would extend the position is pulled. P&L is
`cash + position·V` at settlement.

All parameters (`α`, `s`, `L`, tick, the reveal schedule) are disclosed to the agent. The
benchmark tests reasoning under a known model, not guessing a hidden one.

## 2. Exact posterior

`Ω` is enumerated (at most 250,000 outcomes; most games have a few hundred). The public
posterior is a weight vector over `Ω`:

- a reveal multiplies the weights by the indicator of consistency with the revealed value;
- a trade multiplies by its likelihood. For a buy at the ask,
  `P(buy | ω) = α·1[V(ω) > a] + (1 − α)·Φ((μ_t − a)/s)`; for a sell at the bid,
  `P(sell | ω) = α·1[V(ω) < b] + (1 − α)·Φ((b − μ_t)/s)`; no trade has the complementary
  probability.

The noise-trader term does not depend on `ω`, so a fill moves the posterior only through the
informed term. A buy is evidence that `V > a`; a quiet step is weak evidence that `V` lies
inside the quote.

## 3. Exact one-step value of a quote

Given the posterior at step `t`, the expected profit of a quote is

```
EV_t(b, a) = E[(a − V)·1{buy} + (V − b)·1{sell} | H_t]
           = capture − adverse
capture    = P(buy)·(a − μ_t) + P(sell)·(μ_t − b)
adverse    = E[(V − μ_t)·1{buy} | H_t] + E[(μ_t − V)·1{sell} | H_t]   (always >= 0)
```

`capture` is the spread earned against the current fair value. `adverse` is the expected loss
to counterparties who know more. Both are computed exactly for every quote any agent posts.

## 4. Reference quoters

- **bayes**: exact posterior; each side maximises `EV_t` over the tick grid. It is *myopic*:
  it does not price the information a quote generates or plan inventory. It is the 100-point
  reference, not a proven upper bound; a policy that values information could beat it.
- **bayes-noflow**: same quote rule, but its belief ignores trades. The gap to `bayes` measures
  the value of learning from order flow.
- **glosten-milgrom**: exact posterior; the tightest prices with `EV_t >= 0`, i.e.
  `a = E[V | buy at a]`, `b = E[V | sell at b]`. This is the competitive-dealer quote of
  Glosten and Milgrom (1985). Its expected P&L is close to zero by construction; it checks the
  simulator and shows that a tight market is not a profitable one.
- **static** (prior mean ± one prior sd, never updated) and **random** are floors.

## 5. Expected P&L as the score

Realized P&L is noisy: one informed fill on a wide-support game swings the result by several
standard deviations of `V`. The benchmark scores the sum of exact one-step expectations along
the path the agent actually played:

```
xPnL = Σ_t EV_t
```

Each quote is a function of public information `H_t`, so by the tower property
`E[xPnL] = E[PnL]`: it is an unbiased estimator of expected realized P&L. It removes the luck
of who arrived and what they knew at each step while keeping every consequence of the agent's
choices. Concretely, it integrates out three sources of chance at each step: whether the
counterparty is informed, the noise trader's valuation shock, and the hidden outcome given the
public information at that step. The path itself (which reveals and fills happened) is kept,
so later quotes are scored at the states the agent really reached. The idea matches luck-adjusted evaluation in poker (DIVAT, AIVAT). Realized P&L is
still reported.

Two further variance controls:

- **Common random numbers.** The hidden outcome and every counterparty draw are functions of
  `(game id, episode seed)` only. All agents face the same dice and the same arrivals, so
  comparisons are paired.
- **Clustered inference.** Confidence intervals come from a bootstrap that resamples games
  (keeping all episodes of a game together). Paired differences use a game-level sign-flip
  permutation test with Holm correction across pairs.

## 6. Scores

All money quantities are divided by the game's prior standard deviation of `V` before
averaging, so wide-range games do not dominate.

| Metric | Definition | Ideal |
| --- | --- | --- |
| Edge captured | `100 · Σ xPnL_agent / Σ xPnL_bayes` over the same `(game, seed)` episodes | 100 |
| xPnL/sd, PnL/sd | expected and realized P&L per episode | high |
| Local efficiency | `Σ EV_t(agent) / Σ EV_t(bayes)` at the states the agent actually visited | 1 |
| Capture, adverse | the two terms of `EV_t`, summed per episode | high, low |
| Width / Bayes width | quote width relative to the Bayes quote at the same state | ~1 |
| Mid error | `(mid − μ_t) / max(σ_t, tick)` on two-sided quotes, skipping steps where `V` is already known; mean absolute value, bias, RMSE | ~0 |
| β flow | slope (through the origin) of the agent's mid change on the Bayes quote's mid change, between consecutive steps in the same stage, where only trades move the posterior | 1 |
| β reveal | the same slope across stage boundaries, where reveals arrive | 1 |
| Fill response | share of fills after which the mid moves the right way (up after a buy at the ask) | high |
| Dominated quotes | bid above the highest still-possible value, or ask below the lowest: a sure loss if hit | 0 |
| Invalid | unparseable, crossed or non-finite quotes (both sides pulled for that step) | 0 |

β uses the Bayes quote's mid rather than `μ_t` because the optimal mid is not `μ_t` when the
posterior is skewed; regressed on `μ_t`, the Bayes quoter itself scores about 0.7. The
`μ_t`-based slopes are in `summary.json` as `beta_flow_mu` and `beta_reveal_mu`. β below 1 means
under-reacting to information; above 1 means over-reacting.

Fill response has a selection effect: a buy tends to arrive when the ask is low, so even a
random mid moves up afterwards more often than not. Compare it with the `bayes` row, not 0.5.

## 7. Game families and contamination

| Family | Hidden state | Contract | Latent |
| --- | --- | --- | --- |
| dice | 2-4 dice, custom faces, sometimes loaded | sum | no |
| cards | 2-3 cards from a custom deck, no replacement | sum | no |
| transform | dice or cards | max, min, range, product, count above a threshold | no |
| coin | coin picked from a set of biases, n flips | number of heads (times a multiplier) | bias |
| urn | urn with an unknown number of red balls, k draws | number of red balls | composition |

Each family has a **classic** variant (the textbook interview question: three standard dice,
three cards from a 52-card deck, the product of two dice, a fair-or-double-headed coin, a
uniform urn) and a **perturbed** variant generated from a seed. Market parameters are drawn
from the same distribution for both. A model that scores better on classic than on perturbed
games of the same family is likely recalling, not reasoning; the report shows that gap with a
confidence interval.

Suites are versioned (`core-v1`). A change to a generator that alters any game creates a new
suite version.

## 8. LLM protocol

- One stateless call per quoting step. The prompt holds the rules, the market parameters, the
  revealed components, the full trade history, position and steps left. Run
  `mm-arena prompt` to see it.
- The prompt states the objective (maximise expected profit at settlement) and the rules. It
  gives no strategy hints.
- The answer must end with `{"bid": x, "ask": y}`. One repair turn is allowed on a format
  error; after that the step counts as invalid with both sides pulled.
- Provider failures (auth, rate limits, outages) exclude the episode instead of scoring it.
- Responses can be cached on disk keyed by the full request, so reruns and rescoring are free
  and reproducible.

## 9. Trust model

Python agents receive the `Game` object (the outcome table and market parameters, which are
public information) and are trusted code: a Python agent could recompute the episode's random
draws from the game id and seed. LLM agents see only the rendered prompt.

## 10. Limitations

- The counterparty model is stylised: one arrival per step, unit size, informed traders see
  `V` exactly by default, noise traders value around the exact public mean.
- The reference is myopic Bayes-optimal, not the dynamic optimum.
- The model is fully disclosed. Real desks estimate `α` and `s`; the benchmark isolates
  reasoning given them.
- Small state spaces only (exact enumeration). This is deliberate: every score is exact.
- LLM results depend on prompt wording and provider settings; both are recorded with each run.
