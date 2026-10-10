# mm-arena report: core-v1

16 agents, up to 120 episodes on 60 games. Reference: `bayes` (myopic Bayes-optimal quoter). Intervals: 95% game-clustered bootstrap, 2000 draws.

Leaderboard and the sections below it use primary runs only; 2 replicate run(s) (`#rN`, N >= 2) appear in Run-to-run variability.

## Leaderboard

| # | agent | edge captured % [95% CI] | xpnl/sd | pnl/sd | mid abs z | beta flow | beta reveal | invalid % | dominated % | USD/episode |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `bayes-lookahead` | 100.8 [100.2, 101.5] | 1.523 | 1.242 | 0.07 | 1.00 | 1.00 | 0.0 | 0.0 | - |
| 2 | `bayes` | 100.0 [100.0, 100.0] | 1.511 | 1.207 | 0.07 | 1.00 | 1.00 | 0.0 | 0.0 | - |
| 3 | `claude-cli:claude-fable-5-1@high` | 90.7 [87.5, 93.3] | 1.370 | 1.257 | 0.23 | 1.03 | 0.99 | 0.0 | 0.0 | 0.8970 |
| 4 | `bayes-noflow` | 88.5 [83.9, 92.1] | 1.337 | 1.150 | 0.34 | 0.00 | 0.93 | 0.0 | 0.0 | - |
| 5 | `claude-cli:claude-opus-5-5@high` | 87.7 [83.7, 91.2] | 1.325 | 1.107 | 0.23 | 0.98 | 1.03 | 0.0 | 0.0 | 0.3102 |
| 6 | `bayes-mean` | 86.3 [83.0, 89.0] | 1.303 | 1.206 | 0.01 | 1.01 | 0.98 | 0.0 | 0.0 | - |
| 7 | `claude-cli:claude-haiku-5-5@high` | 79.9 [72.9, 85.2] | 1.207 | 0.971 | 0.29 | 0.30 | 0.91 | 0.0 | 0.0 | 0.0249 |
| 8 | `claude-cli:claude-opus-5-5@medium` | 72.7 [67.6, 77.1] | 1.098 | 0.998 | 0.32 | 1.03 | 0.96 | 0.0 | 0.0 | 0.2702 |
| 9 | `claude-cli:claude-sonnet-5-5@high` | 69.2 [63.8, 74.8] | 1.045 | 0.906 | 0.34 | 0.66 | 0.90 | 0.0 | 0.0 | 0.1459 |
| 10 | `claude-cli:claude-opus-5-5@low` | 60.0 [56.4, 63.7] | 0.907 | 0.710 | 0.37 | 0.84 | 0.94 | 0.0 | 0.0 | 0.1619 |
| 11 | `claude-cli:claude-fable-5-1@low` | 59.8 [55.7, 64.0] | 0.904 | 0.820 | 0.29 | 0.98 | 0.94 | 0.0 | 0.0 | 0.4253 |
| 12 | `static` | 47.4 [36.2, 56.3] | 0.716 | 0.438 | 0.92 | 0.00 | 0.00 | 0.0 | 1.2 | - |
| 13 | `claude-cli:claude-sonnet-5-5@low` | 14.8 [5.8, 22.1] | 0.223 | 0.072 | 0.46 | 0.33 | 0.83 | 0.0 | 0.0 | 0.0879 |
| 14 | `glosten-milgrom` | 4.3 [3.7, 5.0] | 0.065 | 0.046 | 0.05 | 0.96 | 1.00 | 0.0 | 0.0 | - |
| 15 | `claude-cli:claude-haiku-5-5@low` | -0.4 [-13.7, 10.7] | -0.007 | -0.239 | 0.40 | 0.17 | 0.87 | 0.0 | 0.0 | 0.0077 |
| 16 | `random` | -80.3 [-107.7, -58.1] | -1.213 | -1.502 | 1.28 | -0.02 | 0.15 | 0.0 | 4.1 | - |

## By family and variant

| agent | cards | coin | dice | transform | urn | classic | perturbed | classic - perturbed [95% CI] | p | p (Holm) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `bayes-lookahead` | 100.7 | 100.2 | 100.1 | 100.7 | 102.2 | 100.1 | 101.2 | -1.2 [-2.3, -0.4] | - | - |
| `bayes` | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 0.0 [0.0, 0.0] | - | - |
| `claude-cli:claude-fable-5-1@high` | 87.2 | 90.9 | 91.1 | 95.4 | 88.5 | 91.5 | 90.1 | 1.4 [-5.3, 7.7] | 0.721 | 1.000 |
| `bayes-noflow` | 76.6 | 92.8 | 89.3 | 95.6 | 84.4 | 88.5 | 88.5 | -0.1 [-9.0, 9.0] | - | - |
| `claude-cli:claude-opus-5-5@high` | 83.1 | 89.6 | 89.3 | 92.6 | 83.0 | 89.1 | 86.8 | 2.3 [-6.9, 11.2] | 0.648 | 1.000 |
| `bayes-mean` | 90.0 | 82.9 | 88.6 | 79.8 | 90.3 | 87.8 | 85.3 | 2.5 [-4.3, 8.0] | - | - |
| `claude-cli:claude-haiku-5-5@high` | 43.8 | 87.7 | 76.6 | 91.1 | 85.9 | 82.8 | 78.1 | 4.8 [-16.3, 19.5] | 0.538 | 1.000 |
| `claude-cli:claude-opus-5-5@medium` | 67.4 | 72.5 | 76.7 | 80.4 | 66.2 | 76.8 | 70.1 | 6.7 [-4.8, 18.4] | 0.289 | 1.000 |
| `claude-cli:claude-sonnet-5-5@high` | 60.8 | 66.4 | 74.8 | 76.2 | 66.4 | 76.9 | 64.4 | 12.5 [-2.3, 25.5] | 0.092 | 0.644 |
| `claude-cli:claude-opus-5-5@low` | 52.5 | 60.6 | 63.1 | 66.6 | 55.8 | 66.0 | 56.4 | 9.6 [1.8, 17.5] | 0.009 | 0.072 |
| `claude-cli:claude-fable-5-1@low` | 58.9 | 56.9 | 58.2 | 72.7 | 55.9 | 59.0 | 60.3 | -1.3 [-10.2, 6.8] | 0.773 | 1.000 |
| `static` | 4.2 | 52.2 | 57.9 | 61.4 | 45.3 | 50.4 | 45.5 | 4.9 [-18.5, 27.3] | - | - |
| `claude-cli:claude-sonnet-5-5@low` | -11.2 | 15.0 | 8.8 | 29.7 | 23.5 | 28.1 | 6.6 | 21.5 [8.1, 35.7] | 0.006 | 0.054 |
| `glosten-milgrom` | 2.9 | 5.6 | 3.9 | 3.1 | 4.9 | 4.8 | 4.0 | 0.8 [-1.2, 2.8] | - | - |
| `claude-cli:claude-haiku-5-5@low` | -67.5 | 0.4 | -9.4 | 28.0 | 22.6 | 10.1 | -6.9 | 17.0 [-25.7, 45.4] | 0.353 | 1.000 |
| `random` | -171.7 | -85.8 | -62.9 | -32.7 | -76.0 | -67.6 | -88.1 | 20.5 [-38.3, 77.1] | - | - |

Edge captured %, per family and variant. Classic games are textbook questions; perturbed games are drawn fresh per seed. A positive gap that excludes zero suggests recall of known answers. The interval resamples hidden structures: the classic games of a family share one, so they count once, and each perturbed game is its own structure. p is a two-sided bootstrap p-value for a gap of zero, Holm-adjusted across the 9 LLM setups (baselines: -).

## Centring vs width

| agent | as played | agent mid + Bayes width | Bayes mid + agent width | mean + agent width | covered % | mid bias z | mid abs z | width / Bayes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `bayes-lookahead` | 99.9 | 99.9 | 99.9 | 99.2 | 99.5 | -0.00 | 0.07 | 1.00 |
| `bayes` | 100.0 | 100.0 | 100.0 | 98.9 | 99.1 | 0.01 | 0.07 | 1.00 |
| `claude-cli:claude-fable-5-1@high` | 91.0 | 95.8 | 94.3 | 94.4 | 98.6 | 0.03 | 0.23 | 0.92 |
| `bayes-noflow` | 90.0 | 88.5 | 98.0 | 97.9 | 96.0 | 0.06 | 0.34 | 1.03 |
| `claude-cli:claude-opus-5-5@high` | 88.8 | 95.5 | 91.9 | 92.3 | 97.1 | 0.03 | 0.23 | 0.90 |
| `bayes-mean` | 86.2 | 99.2 | 86.3 | 86.3 | 99.1 | 0.00 | 0.01 | 1.06 |
| `claude-cli:claude-haiku-5-5@high` | 80.7 | 91.8 | 88.5 | 89.3 | 96.6 | 0.00 | 0.29 | 0.94 |
| `claude-cli:claude-opus-5-5@medium` | 74.0 | 92.8 | 80.9 | 82.2 | 95.5 | 0.03 | 0.32 | 0.77 |
| `claude-cli:claude-sonnet-5-5@high` | 71.9 | 91.5 | 78.6 | 80.6 | 92.2 | 0.04 | 0.34 | 0.80 |
| `claude-cli:claude-opus-5-5@low` | 61.6 | 93.2 | 68.6 | 71.3 | 93.1 | 0.03 | 0.37 | 0.61 |
| `claude-cli:claude-fable-5-1@low` | 60.8 | 95.0 | 66.0 | 68.7 | 95.9 | 0.09 | 0.29 | 0.61 |
| `static` | 48.7 | 39.8 | 90.0 | 90.5 | 92.2 | -0.13 | 0.92 | 1.07 |
| `claude-cli:claude-sonnet-5-5@low` | 15.8 | 88.9 | 34.9 | 39.5 | 87.2 | 0.07 | 0.46 | 0.43 |
| `glosten-milgrom` | 4.5 | 94.9 | 5.1 | 9.0 | 92.1 | 0.01 | 0.05 | 0.27 |
| `claude-cli:claude-haiku-5-5@low` | -0.5 | 90.3 | 14.4 | 19.7 | 84.0 | 0.05 | 0.40 | 0.38 |
| `random` | -86.6 | -2.3 | 49.2 | 53.2 | 85.2 | -0.20 | 1.28 | 0.56 |

Expected P&L of each agent's own quotes (as played) and of three counterfactual quotes priced on the same posteriors, as % of the Bayes quoter's expected P&L on the same steps (as played = 100 x local efficiency). A setup whose score jumps when given the Bayes width but not when given the Bayes mid loses mainly on width; the reverse means it loses on centring. Steps without a two-sided agent quote and a Bayes quote (one-sided quotes, inventory-limit steps, invalid replies) keep their as-played value in every column, so the share of steps covered is shown. Mid bias and mid abs are the signed and absolute mid error in posterior sd; width / Bayes is the mean quoted spread over the Bayes spread. Replay check: 0 step(s) where the recomputed value of the as-played quote differs from the trace.

## Pairwise vs `bayes`

| agent | `bayes` minus agent, pp [95% CI] | games | p | p (Holm) |
| --- | ---: | ---: | ---: | ---: |
| `bayes-lookahead` | -0.8 [-1.5, -0.2] | 60 | 0.003 | 0.050 |
| `bayes-mean` | 13.7 [11.0, 17.0] | 60 | <0.001 | 0.012 |
| `bayes-noflow` | 11.5 [7.9, 16.1] | 60 | <0.001 | 0.012 |
| `claude-cli:claude-fable-5-1@high` | 9.3 [6.7, 12.5] | 60 | <0.001 | 0.012 |
| `claude-cli:claude-fable-5-1@low` | 40.2 [36.0, 44.3] | 60 | <0.001 | 0.012 |
| `claude-cli:claude-haiku-5-5@high` | 20.1 [14.8, 27.1] | 60 | <0.001 | 0.012 |
| `claude-cli:claude-haiku-5-5@low` | 100.4 [89.3, 113.7] | 60 | <0.001 | 0.012 |
| `claude-cli:claude-opus-5-5@high` | 12.3 [8.8, 16.3] | 60 | <0.001 | 0.012 |
| `claude-cli:claude-opus-5-5@low` | 40.0 [36.3, 43.6] | 60 | <0.001 | 0.012 |
| `claude-cli:claude-opus-5-5@medium` | 27.3 [22.9, 32.4] | 60 | <0.001 | 0.012 |
| `claude-cli:claude-sonnet-5-5@high` | 30.8 [25.2, 36.2] | 60 | <0.001 | 0.012 |
| `claude-cli:claude-sonnet-5-5@low` | 85.2 [77.9, 94.2] | 60 | <0.001 | 0.012 |
| `glosten-milgrom` | 95.7 [95.0, 96.3] | 60 | <0.001 | 0.012 |
| `random` | 180.3 [158.1, 207.7] | 60 | <0.001 | 0.012 |
| `static` | 52.6 [43.7, 63.8] | 60 | <0.001 | 0.012 |

Difference in edge captured on shared episodes. p: game-level sign-flip permutation test. Holm correction across all agent pairs (see `summary.json`).

## Variance: realized vs expected P&L

| agent | SE pnl/sd | SE xpnl/sd | SE ratio | n (pnl) | n (xpnl) | n ratio |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `bayes-lookahead` | 0.173 | 0.118 | 1.5 | 2631 | 656 | 4.0 |
| `bayes` | 0.175 | 0.118 | 1.5 | 2661 | 655 | 4.1 |
| `claude-cli:claude-fable-5-1@high` | 0.167 | 0.106 | 1.6 | 2649 | 542 | 4.9 |
| `bayes-noflow` | 0.206 | 0.122 | 1.7 | 3414 | 733 | 4.7 |
| `claude-cli:claude-opus-5-5@high` | 0.149 | 0.105 | 1.4 | 2124 | 533 | 4.0 |
| `bayes-mean` | 0.151 | 0.110 | 1.4 | 2018 | 570 | 3.5 |
| `claude-cli:claude-haiku-5-5@high` | 0.209 | 0.129 | 1.6 | 3463 | 850 | 4.1 |
| `claude-cli:claude-opus-5-5@medium` | 0.180 | 0.092 | 2.0 | 2936 | 432 | 6.8 |
| `claude-cli:claude-sonnet-5-5@high` | 0.174 | 0.088 | 2.0 | 2942 | 425 | 6.9 |
| `claude-cli:claude-opus-5-5@low` | 0.198 | 0.078 | 2.5 | 2900 | 309 | 9.4 |
| `claude-cli:claude-fable-5-1@low` | 0.178 | 0.069 | 2.6 | 2605 | 247 | 10.6 |
| `static` | 0.216 | 0.119 | 1.8 | 3672 | 898 | 4.1 |
| `claude-cli:claude-sonnet-5-5@low` | 0.229 | 0.076 | 3.0 | 4145 | 343 | 12.1 |
| `glosten-milgrom` | 0.148 | 0.007 | 22.4 | 2044 | 3 | 952.8 |
| `claude-cli:claude-haiku-5-5@low` | 0.244 | 0.096 | 2.5 | 4810 | 504 | 9.6 |
| `random` | 0.258 | 0.139 | 1.9 | 5459 | 1243 | 4.4 |

| paired difference | SD pnl/sd | SD xpnl/sd | n (pnl) | n (xpnl) | n ratio |
| --- | ---: | ---: | ---: | ---: | ---: |
| `bayes` - `bayes-lookahead` | 0.317 | 0.051 | 79 | 3 | 39.1 |
| `bayes` - `bayes-mean` | 1.047 | 0.207 | 861 | 34 | 25.5 |
| `bayes` - `bayes-noflow` | 0.888 | 0.273 | 620 | 59 | 10.6 |
| `bayes` - `claude-cli:claude-fable-5-1@high` | 0.788 | 0.242 | 488 | 47 | 10.6 |
| `bayes` - `claude-cli:claude-fable-5-1@low` | 1.441 | 0.525 | 1630 | 216 | 7.5 |
| `bayes` - `claude-cli:claude-haiku-5-5@high` | 1.025 | 0.408 | 826 | 131 | 6.3 |
| `bayes` - `claude-cli:claude-haiku-5-5@low` | 1.966 | 0.845 | 3033 | 561 | 5.4 |
| `bayes` - `claude-cli:claude-opus-5-5@high` | 0.949 | 0.278 | 708 | 61 | 11.6 |
| `bayes` - `claude-cli:claude-opus-5-5@low` | 1.515 | 0.443 | 1801 | 155 | 11.7 |
| `bayes` - `claude-cli:claude-opus-5-5@medium` | 1.178 | 0.432 | 1089 | 147 | 7.4 |
| `bayes` - `claude-cli:claude-sonnet-5-5@high` | 1.245 | 0.518 | 1216 | 211 | 5.8 |
| `bayes` - `claude-cli:claude-sonnet-5-5@low` | 1.941 | 0.719 | 2957 | 406 | 7.3 |
| `bayes` - `glosten-milgrom` | 1.652 | 0.881 | 2143 | 610 | 3.5 |
| `bayes` - `random` | 2.152 | 1.307 | 3635 | 1342 | 2.7 |
| `bayes` - `static` | 1.425 | 0.754 | 1594 | 447 | 3.6 |

SE: game-clustered standard error of the mean per-episode score. n: episodes needed to detect a mean difference of 0.1 prior sd per episode at 80% power (two-sided, alpha 0.05). Both scores have the same expectation; xpnl removes the settlement and fill noise. A leaderboard on realized P&L needs n ratio times as many episodes for the same power.

## Run-to-run variability

| setup | run | episodes | edge captured % [95% CI] | minus first run, pp [95% CI] | p |
| --- | --- | ---: | ---: | ---: | ---: |
| `claude-cli:claude-opus-5-5@high` | r1 | 120 | 87.7 [83.7, 91.2] | - | - |
|  | r2 | 120 | 83.8 [79.8, 87.8] | -3.9 [-6.8, -1.2] | 0.008 |
|  | pooled | 240 | 85.7 [81.9, 89.3] | - | - |
| `claude-cli:claude-haiku-5-5@high` | r1 | 120 | 79.9 [72.9, 85.2] | - | - |
|  | r2 | 120 | 90.4 [87.8, 92.5] | 10.5 [6.2, 16.1] | <0.001 |
|  | pooled | 240 | 85.1 [80.8, 88.6] | - | - |

Pooled comparison of setups with several runs (mean score over runs):

| pair | runs | difference, pp [95% CI] | games | p | p (Holm) |
| --- | ---: | ---: | ---: | ---: | ---: |
| `claude-cli:claude-opus-5-5@high` - `claude-cli:claude-haiku-5-5@high` | 2 / 2 | 0.6 [-4.1, 5.7] | 60 | 0.831 | 0.831 |

The same pairs, run against run (p not adjusted):

| pair | runs | difference, pp [95% CI] | p |
| --- | --- | ---: | ---: |
| `claude-cli:claude-opus-5-5@high` - `claude-cli:claude-haiku-5-5@high` | r1 vs r1 | 7.8 [1.8, 15.1] | 0.011 |
| `claude-cli:claude-opus-5-5@high` - `claude-cli:claude-haiku-5-5@high` | r1 vs r2 | -2.7 [-6.8, 1.1] | 0.239 |
| `claude-cli:claude-opus-5-5@high` - `claude-cli:claude-haiku-5-5@high` | r2 vs r1 | 3.9 [-2.9, 11.8] | 0.296 |
| `claude-cli:claude-opus-5-5@high` - `claude-cli:claude-haiku-5-5@high` | r2 vs r2 | -6.6 [-11.0, -2.2] | 0.005 |

Repeated runs of one setup are scored on the same games and seeds. Intervals here still resample games; the spread between runs shows drift between them (date, sampling, server changes) that a single run cannot. Differences are in edge captured, percentage points, on episodes both runs played; p is a game-level sign-flip test. The pooled edge is 100 x total expected P&L over all runs / total Bayes expected P&L, with all runs' episodes of a game resampled together. Pooled pairs score each episode by the mean over a setup's runs; Holm correction within the pooled table.

## How to read the metrics

- **edge captured %**: 100 x sum(agent xpnl) / sum(Bayes xpnl) over the same (game, seed) episodes, in prior-sd units. 100 = myopic Bayes-optimal, 0 = never quoting, below 0 = loses money in expectation. Above 100 is possible: the reference is myopic.
- **xpnl/sd**: mean expected P&L per episode in prior standard deviations: the sum of the exact one-step expected profit of each quote given the public posterior.
- **pnl/sd**: mean realized P&L per episode in prior standard deviations. Noisy.
- **mid abs z**: mean |mid - mu| / sd over two-sided quotes, where mu and sd are the public posterior mean and sd (sd floored at one tick). Measures belief error. Bayes is not 0: its optimal quote is not centered on mu when the posterior is skewed.
- **beta flow**: slope (through the origin) of the agent's mid change on the Bayes quote's mid change between consecutive steps in the same stage, where only order flow moves the posterior. 1 = updates like Bayes, 0 = ignores order flow, above 1 = overreacts.
- **beta reveal**: the same slope across stage boundaries, where public reveals arrive.
- **invalid %**: steps whose output could not be used (format, exception, non-finite, crossed).
- **dominated %**: steps with a bid above the highest possible value or an ask below the lowest: a certain loss if filled.
- **USD/episode**: API list price of the tokens used (`mmarena.pricing`, prices as of 2026-10-10); the provider's reported cost for models without a listed price.
- **summary.json**: also holds local efficiency, capture and adverse selection, realized P&L by taker type, mid bias and RMSE, width vs Bayes width, fill response, one-sided and no-quote rates, inventory-limit steps, final position, tokens, cost and latency, per agent and per (family, variant), plus the rank distribution (`p_rank1`, `rank_probs`). Latency is the provider-reported time of the model calls when recorded (the engine's wall clock otherwise, which reads about zero on cached replays).
