# mm-arena report: core-v1

13 agents, up to 120 episodes on 60 games. Reference: `bayes` (myopic Bayes-optimal quoter). Intervals: 95% game-clustered bootstrap, 2000 draws.

## Leaderboard

| # | agent | edge captured % [95% CI] | P(best) | xpnl/sd | pnl/sd | mid abs z | beta flow | beta reveal | invalid % | dominated % | USD/episode |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `bayes` | 100.0 [100.0, 100.0] | 1.00 | 1.511 | 1.207 | 0.07 | 1.00 | 1.00 | 0.0 | 0.0 | - |
| 2 | `claude-cli:claude-fable-5-1@high` | 90.7 [87.5, 93.3] | 0.00 | 1.370 | 1.257 | 0.23 | 1.03 | 0.99 | 0.0 | 0.0 | 0.8970 |
| 3 | `bayes-noflow` | 88.5 [83.9, 92.1] | 0.00 | 1.337 | 1.150 | 0.34 | 0.00 | 0.93 | 0.0 | 0.0 | - |
| 4 | `claude-cli:claude-opus-5-5@high` | 87.7 [83.7, 91.2] | 0.00 | 1.325 | 1.107 | 0.23 | 0.98 | 1.03 | 0.0 | 0.0 | 0.3102 |
| 5 | `claude-cli:claude-haiku-5-5@high` | 79.9 [72.9, 85.2] | 0.00 | 1.207 | 0.971 | 0.29 | 0.30 | 0.91 | 0.0 | 0.0 | 0.0249 |
| 6 | `claude-cli:claude-sonnet-5-5@high` | 69.2 [63.8, 74.8] | 0.00 | 1.045 | 0.906 | 0.34 | 0.66 | 0.90 | 0.0 | 0.0 | 0.1459 |
| 7 | `claude-cli:claude-opus-5-5@low` | 60.0 [56.4, 63.7] | 0.00 | 0.907 | 0.710 | 0.37 | 0.84 | 0.94 | 0.0 | 0.0 | 0.1619 |
| 8 | `claude-cli:claude-fable-5-1@low` | 59.8 [55.7, 64.0] | 0.00 | 0.904 | 0.820 | 0.29 | 0.98 | 0.94 | 0.0 | 0.0 | 0.4253 |
| 9 | `static` | 47.4 [36.2, 56.3] | 0.00 | 0.716 | 0.438 | 0.92 | 0.00 | 0.00 | 0.0 | 1.2 | - |
| 10 | `claude-cli:claude-sonnet-5-5@low` | 14.8 [5.8, 22.1] | 0.00 | 0.223 | 0.072 | 0.46 | 0.33 | 0.83 | 0.0 | 0.0 | 0.0879 |
| 11 | `glosten-milgrom` | 4.3 [3.7, 5.0] | 0.00 | 0.065 | 0.046 | 0.05 | 0.96 | 1.00 | 0.0 | 0.0 | - |
| 12 | `claude-cli:claude-haiku-5-5@low` | -0.4 [-13.7, 10.7] | 0.00 | -0.007 | -0.239 | 0.40 | 0.17 | 0.87 | 0.0 | 0.0 | 0.0077 |
| 13 | `random` | -80.3 [-107.7, -58.1] | 0.00 | -1.213 | -1.502 | 1.28 | -0.02 | 0.15 | 0.0 | 4.1 | - |

## By family and variant

| agent | cards | coin | dice | transform | urn | classic | perturbed | classic - perturbed [95% CI] |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `bayes` | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 0.0 [0.0, 0.0] |
| `claude-cli:claude-fable-5-1@high` | 87.2 | 90.9 | 91.1 | 95.4 | 88.5 | 91.5 | 90.1 | 1.4 [-3.9, 6.8] |
| `bayes-noflow` | 76.6 | 92.8 | 89.3 | 95.6 | 84.4 | 88.5 | 88.5 | -0.1 [-8.1, 7.9] |
| `claude-cli:claude-opus-5-5@high` | 83.1 | 89.6 | 89.3 | 92.6 | 83.0 | 89.1 | 86.8 | 2.3 [-4.7, 9.5] |
| `claude-cli:claude-haiku-5-5@high` | 43.8 | 87.7 | 76.6 | 91.1 | 85.9 | 82.8 | 78.1 | 4.8 [-8.6, 16.8] |
| `claude-cli:claude-sonnet-5-5@high` | 60.8 | 66.4 | 74.8 | 76.2 | 66.4 | 76.9 | 64.4 | 12.5 [1.9, 22.5] |
| `claude-cli:claude-opus-5-5@low` | 52.5 | 60.6 | 63.1 | 66.6 | 55.8 | 66.0 | 56.4 | 9.6 [2.8, 16.9] |
| `claude-cli:claude-fable-5-1@low` | 58.9 | 56.9 | 58.2 | 72.7 | 55.9 | 59.0 | 60.3 | -1.3 [-9.4, 6.5] |
| `static` | 4.2 | 52.2 | 57.9 | 61.4 | 45.3 | 50.4 | 45.5 | 4.9 [-15.5, 24.9] |
| `claude-cli:claude-sonnet-5-5@low` | -11.2 | 15.0 | 8.8 | 29.7 | 23.5 | 28.1 | 6.6 | 21.5 [7.4, 35.6] |
| `glosten-milgrom` | 2.9 | 5.6 | 3.9 | 3.1 | 4.9 | 4.8 | 4.0 | 0.8 [-0.5, 2.2] |
| `claude-cli:claude-haiku-5-5@low` | -67.5 | 0.4 | -9.4 | 28.0 | 22.6 | 10.1 | -6.9 | 17.0 [-9.4, 39.3] |
| `random` | -171.7 | -85.8 | -62.9 | -32.7 | -76.0 | -67.6 | -88.1 | 20.5 [-31.4, 70.6] |

Edge captured %, per family and per variant. Classic games are textbook questions; perturbed games are drawn fresh per seed. A positive gap that excludes zero suggests recall of known answers.

## Pairwise vs `bayes`

| agent | `bayes` minus agent, pp [95% CI] | games | p | p (Holm) |
| --- | ---: | ---: | ---: | ---: |
| `bayes-noflow` | 11.5 [7.9, 16.1] | 60 | <0.001 | 0.008 |
| `claude-cli:claude-fable-5-1@high` | 9.3 [6.7, 12.5] | 60 | <0.001 | 0.008 |
| `claude-cli:claude-fable-5-1@low` | 40.2 [36.0, 44.3] | 60 | <0.001 | 0.008 |
| `claude-cli:claude-haiku-5-5@high` | 20.1 [14.8, 27.1] | 60 | <0.001 | 0.008 |
| `claude-cli:claude-haiku-5-5@low` | 100.4 [89.3, 113.7] | 60 | <0.001 | 0.008 |
| `claude-cli:claude-opus-5-5@high` | 12.3 [8.8, 16.3] | 60 | <0.001 | 0.008 |
| `claude-cli:claude-opus-5-5@low` | 40.0 [36.3, 43.6] | 60 | <0.001 | 0.008 |
| `claude-cli:claude-sonnet-5-5@high` | 30.8 [25.2, 36.2] | 60 | <0.001 | 0.008 |
| `claude-cli:claude-sonnet-5-5@low` | 85.2 [77.9, 94.2] | 60 | <0.001 | 0.008 |
| `glosten-milgrom` | 95.7 [95.0, 96.3] | 60 | <0.001 | 0.008 |
| `random` | 180.3 [158.1, 207.7] | 60 | <0.001 | 0.008 |
| `static` | 52.6 [43.7, 63.8] | 60 | <0.001 | 0.008 |

Difference in edge captured on shared episodes. p: game-level sign-flip permutation test. Holm correction across all agent pairs (see `summary.json`).

## Variance: realized vs expected P&L

| agent | SE pnl/sd | SE xpnl/sd | SE ratio | n (pnl) | n (xpnl) | n ratio |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `bayes` | 0.175 | 0.118 | 1.5 | 2661 | 655 | 4.1 |
| `claude-cli:claude-fable-5-1@high` | 0.167 | 0.106 | 1.6 | 2649 | 542 | 4.9 |
| `bayes-noflow` | 0.206 | 0.122 | 1.7 | 3414 | 733 | 4.7 |
| `claude-cli:claude-opus-5-5@high` | 0.149 | 0.105 | 1.4 | 2124 | 533 | 4.0 |
| `claude-cli:claude-haiku-5-5@high` | 0.209 | 0.129 | 1.6 | 3463 | 850 | 4.1 |
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
| `bayes` - `bayes-noflow` | 0.888 | 0.273 | 620 | 59 | 10.6 |
| `bayes` - `claude-cli:claude-fable-5-1@high` | 0.788 | 0.242 | 488 | 47 | 10.6 |
| `bayes` - `claude-cli:claude-fable-5-1@low` | 1.441 | 0.525 | 1630 | 216 | 7.5 |
| `bayes` - `claude-cli:claude-haiku-5-5@high` | 1.025 | 0.408 | 826 | 131 | 6.3 |
| `bayes` - `claude-cli:claude-haiku-5-5@low` | 1.966 | 0.845 | 3033 | 561 | 5.4 |
| `bayes` - `claude-cli:claude-opus-5-5@high` | 0.949 | 0.278 | 708 | 61 | 11.6 |
| `bayes` - `claude-cli:claude-opus-5-5@low` | 1.515 | 0.443 | 1801 | 155 | 11.7 |
| `bayes` - `claude-cli:claude-sonnet-5-5@high` | 1.245 | 0.518 | 1216 | 211 | 5.8 |
| `bayes` - `claude-cli:claude-sonnet-5-5@low` | 1.941 | 0.719 | 2957 | 406 | 7.3 |
| `bayes` - `glosten-milgrom` | 1.652 | 0.881 | 2143 | 610 | 3.5 |
| `bayes` - `random` | 2.152 | 1.307 | 3635 | 1342 | 2.7 |
| `bayes` - `static` | 1.425 | 0.754 | 1594 | 447 | 3.6 |

SE: game-clustered standard error of the mean per-episode score. n: episodes needed to detect a mean difference of 0.1 prior sd per episode at 80% power (two-sided, alpha 0.05). Both scores have the same expectation; xpnl removes the settlement and fill noise. A leaderboard on realized P&L needs n ratio times as many episodes for the same power.

## How to read the metrics

- **edge captured %**: 100 x sum(agent xpnl) / sum(Bayes xpnl) over the same (game, seed) episodes, in prior-sd units. 100 = myopic Bayes-optimal, 0 = never quoting, below 0 = loses money in expectation. Above 100 is possible: the reference is myopic.
- **P(best)**: share of bootstrap draws in which the agent has the highest edge captured.
- **xpnl/sd**: mean expected P&L per episode in prior standard deviations: the sum of the exact one-step expected profit of each quote given the public posterior.
- **pnl/sd**: mean realized P&L per episode in prior standard deviations. Noisy.
- **mid abs z**: mean |mid - mu| / sd over two-sided quotes, where mu and sd are the public posterior mean and sd (sd floored at one tick). Measures belief error. Bayes is not 0: its optimal quote is not centered on mu when the posterior is skewed.
- **beta flow**: slope (through the origin) of the agent's mid change on the Bayes quote's mid change between consecutive steps in the same stage, where only order flow moves the posterior. 1 = updates like Bayes, 0 = ignores order flow, above 1 = overreacts.
- **beta reveal**: the same slope across stage boundaries, where public reveals arrive.
- **invalid %**: steps whose output could not be used (format, exception, non-finite, crossed).
- **dominated %**: steps with a bid above the highest possible value or an ask below the lowest: a certain loss if filled.
- **USD/episode**: API list price of the tokens used (`mmarena.pricing`, prices as of 2026-10-10); the provider's reported cost for models without a listed price.
- **summary.json**: also holds local efficiency, capture and adverse selection, realized P&L by taker type, mid bias and RMSE, width vs Bayes width, fill response, one-sided and no-quote rates, inventory-limit steps, final position, tokens, cost and latency, per agent and per (family, variant).
