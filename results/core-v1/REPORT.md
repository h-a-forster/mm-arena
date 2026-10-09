# mm-arena report: core-v1

10 agents, up to 60 episodes on 60 games. Reference: `bayes` (myopic Bayes-optimal quoter). Intervals: 95% game-clustered bootstrap, 2000 draws.

## Leaderboard

| # | agent | edge captured % [95% CI] | P(best) | xpnl/sd | pnl/sd | mid abs z | beta flow | beta reveal | invalid % | dominated % | USD/episode |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `bayes` | 100.0 [100.0, 100.0] | 1.00 | 1.517 | 1.314 | 0.08 | 1.00 | 1.00 | 0.0 | 0.0 | - |
| 2 | `claude-cli:claude-opus-5-5@high` | 87.8 [83.2, 91.7] | 0.00 | 1.332 | 1.137 | 0.24 | 0.88 | 1.05 | 0.0 | 0.0 | 0.3122 |
| 3 | `bayes-noflow` | 87.5 [82.3, 91.8] | 0.00 | 1.327 | 1.312 | 0.42 | 0.00 | 0.88 | 0.0 | 0.0 | - |
| 4 | `claude-cli:claude-sonnet-5-5@high` | 67.4 [59.8, 74.9] | 0.00 | 1.023 | 1.005 | 0.41 | 0.66 | 0.87 | 0.0 | 0.0 | 0.1467 |
| 5 | `claude-cli:claude-opus-5-5@low` | 61.9 [57.0, 66.4] | 0.00 | 0.940 | 0.845 | 0.41 | 0.79 | 0.87 | 0.0 | 0.0 | 0.1637 |
| 6 | `static` | 48.7 [34.4, 60.8] | 0.00 | 0.739 | 0.570 | 0.93 | 0.00 | 0.00 | 0.0 | 1.6 | - |
| 7 | `claude-cli:claude-sonnet-5-5@low` | 12.3 [0.3, 22.4] | 0.00 | 0.186 | 0.140 | 0.46 | 0.21 | 0.79 | 0.0 | 0.0 | 0.0878 |
| 8 | `glosten-milgrom` | 4.1 [3.5, 4.8] | 0.00 | 0.063 | 0.004 | 0.05 | 0.91 | 0.98 | 0.0 | 0.0 | - |
| 9 | `claude-cli:claude-haiku-5-5@low` | -0.8 [-14.7, 11.1] | 0.00 | -0.013 | -0.135 | 0.41 | 0.10 | 0.86 | 0.0 | 0.0 | 0.3152 |
| 10 | `random` | -83.2 [-113.7, -57.9] | 0.00 | -1.262 | -1.643 | 1.28 | -0.23 | 0.09 | 0.0 | 4.2 | - |

## By family and variant

| agent | cards | coin | dice | transform | urn | classic | perturbed | classic - perturbed [95% CI] |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `bayes` | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 0.0 [0.0, 0.0] |
| `claude-cli:claude-opus-5-5@high` | 84.4 | 89.2 | 88.8 | 97.2 | 80.4 | 87.9 | 87.8 | 0.1 [-8.0, 8.4] |
| `bayes-noflow` | 69.5 | 90.7 | 89.6 | 96.8 | 85.0 | 86.0 | 88.4 | -2.4 [-12.4, 7.0] |
| `claude-cli:claude-sonnet-5-5@high` | 58.0 | 64.6 | 70.5 | 76.3 | 66.1 | 72.2 | 64.5 | 7.7 [-7.1, 21.5] |
| `claude-cli:claude-opus-5-5@low` | 53.5 | 62.3 | 62.1 | 75.6 | 56.1 | 65.5 | 59.8 | 5.8 [-3.3, 15.2] |
| `static` | -9.3 | 40.3 | 70.7 | 73.2 | 50.1 | 49.0 | 48.5 | 0.5 [-29.1, 27.6] |
| `claude-cli:claude-sonnet-5-5@low` | -21.3 | 18.0 | 5.2 | 31.4 | 17.0 | 25.9 | 4.0 | 21.9 [-0.1, 42.6] |
| `glosten-milgrom` | 2.8 | 5.4 | 4.0 | 2.8 | 4.6 | 4.8 | 3.7 | 1.1 [-0.2, 2.4] |
| `claude-cli:claude-haiku-5-5@low` | -71.3 | 2.6 | -18.2 | 28.0 | 28.6 | 8.8 | -6.7 | 15.5 [-11.4, 39.7] |
| `random` | -174.8 | -107.2 | -65.3 | -23.6 | -68.7 | -70.1 | -91.1 | 21.0 [-36.4, 78.1] |

Edge captured %, per family and per variant. Classic games are textbook questions; perturbed games are drawn fresh per seed. A positive gap that excludes zero suggests recall of known answers.

## Pairwise vs `bayes`

| agent | `bayes` minus agent, pp [95% CI] | games | p | p (Holm) |
| --- | ---: | ---: | ---: | ---: |
| `bayes-noflow` | 12.5 [8.2, 17.7] | 60 | <0.001 | 0.004 |
| `claude-cli:claude-haiku-5-5@low` | 100.8 [88.9, 114.7] | 60 | <0.001 | 0.004 |
| `claude-cli:claude-opus-5-5@high` | 12.2 [8.3, 16.8] | 60 | <0.001 | 0.004 |
| `claude-cli:claude-opus-5-5@low` | 38.1 [33.6, 43.0] | 60 | <0.001 | 0.004 |
| `claude-cli:claude-sonnet-5-5@high` | 32.6 [25.1, 40.2] | 60 | <0.001 | 0.004 |
| `claude-cli:claude-sonnet-5-5@low` | 87.7 [77.6, 99.7] | 60 | <0.001 | 0.004 |
| `glosten-milgrom` | 95.9 [95.2, 96.5] | 60 | <0.001 | 0.004 |
| `random` | 183.2 [157.9, 213.7] | 60 | <0.001 | 0.004 |
| `static` | 51.3 [39.2, 65.6] | 60 | <0.001 | 0.004 |

Difference in edge captured on shared episodes. p: game-level sign-flip permutation test. Holm correction across all agent pairs (see `summary.json`).

## Variance: realized vs expected P&L

| agent | SE pnl/sd | SE xpnl/sd | SE ratio | n (pnl) | n (xpnl) | n ratio |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `bayes` | 0.256 | 0.117 | 2.2 | 3097 | 649 | 4.8 |
| `claude-cli:claude-opus-5-5@high` | 0.226 | 0.105 | 2.2 | 2400 | 519 | 4.6 |
| `bayes-noflow` | 0.283 | 0.122 | 2.3 | 3767 | 702 | 5.4 |
| `claude-cli:claude-sonnet-5-5@high` | 0.258 | 0.089 | 2.9 | 3142 | 372 | 8.5 |
| `claude-cli:claude-opus-5-5@low` | 0.256 | 0.081 | 3.2 | 3085 | 311 | 9.9 |
| `static` | 0.282 | 0.137 | 2.0 | 3734 | 889 | 4.2 |
| `claude-cli:claude-sonnet-5-5@low` | 0.306 | 0.096 | 3.2 | 4405 | 432 | 10.2 |
| `glosten-milgrom` | 0.202 | 0.006 | 31.5 | 1917 | 2 | 992.7 |
| `claude-cli:claude-haiku-5-5@low` | 0.323 | 0.105 | 3.1 | 4920 | 520 | 9.5 |
| `random` | 0.310 | 0.168 | 1.8 | 4523 | 1326 | 3.4 |

| paired difference | SD pnl/sd | SD xpnl/sd | n (pnl) | n (xpnl) | n ratio |
| --- | ---: | ---: | ---: | ---: | ---: |
| `bayes` - `bayes-noflow` | 1.017 | 0.267 | 812 | 56 | 14.5 |
| `bayes` - `claude-cli:claude-haiku-5-5@low` | 2.172 | 0.863 | 3705 | 585 | 6.3 |
| `bayes` - `claude-cli:claude-opus-5-5@high` | 1.074 | 0.291 | 905 | 67 | 13.6 |
| `bayes` - `claude-cli:claude-opus-5-5@low` | 1.565 | 0.453 | 1923 | 162 | 11.9 |
| `bayes` - `claude-cli:claude-sonnet-5-5@high` | 1.428 | 0.585 | 1602 | 269 | 6.0 |
| `bayes` - `claude-cli:claude-sonnet-5-5@low` | 2.150 | 0.701 | 3629 | 386 | 9.4 |
| `bayes` - `glosten-milgrom` | 1.773 | 0.878 | 2468 | 606 | 4.1 |
| `bayes` - `random` | 1.985 | 1.332 | 3094 | 1393 | 2.2 |
| `bayes` - `static` | 1.154 | 0.740 | 1046 | 430 | 2.4 |

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
- **summary.json**: also holds local efficiency, capture and adverse selection, realized P&L by taker type, mid bias and RMSE, width vs Bayes width, fill response, one-sided and no-quote rates, inventory-limit steps, final position, tokens, cost and latency, per agent and per (family, variant).
