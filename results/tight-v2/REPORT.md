# mm-arena session report: tight-v2

15 sessions. Score: share of the known-regime oracle's expected profit, `100 x sum(ev_alpha) / sum(oracle ev_alpha)`, each session in prior-sd units of its game. 100 is the profit of a quoter who is told the informed share and quotes the myopic optimum for it; 0 is never quoting; negative means an expected loss. Intervals: 95%, bootstrap over sessions within each tier.

The ceiling line (`ce-1`) is an estimate of the best score a quoter that does not know the informed share can reach, with its bracket. It is not a denominator and later versions may tighten it.
For tiers whose ceiling is below 85 the leaderboard adds the share of the best public quoter run so far (`bayes-lookahead-w8`, tag `ref-1`): a provisional reading aid, not the score.

## Leaderboard

| agent | pooled | tight | tight, % of ref-1 | learning response | invalid % | cost USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `oracle` | 100.0 [100.0, 100.0] | 100.0 [100.0, 100.0] | 228.6 | 0.81 [0.50, 0.97] | 0.0 | - |
| `bayes-lookahead-w8` | 43.7 [1.2, 59.2] | 43.7 [1.2, 59.2] | 100.0 | 0.64 [0.52, 0.74] | 0.0 | - |
| `bayes-optimist` | 43.0 [-14.0, 71.7] | 43.0 [-14.0, 71.7] | 98.4 | 0.96 [0.89, 1.01] | 0.0 | - |
| `bayes-lookahead-w4` | 42.8 [-4.9, 61.4] | 42.8 [-4.9, 61.4] | 97.8 | 0.84 [0.73, 0.91] | 0.0 | - |
| `bayes-lookahead` | 35.8 [0.8, 66.0] | 35.8 [0.8, 66.0] | 82.0 | 1.08 [0.96, 1.20] | 0.0 | - |
| `bayes-lookahead-w2` | 33.3 [-10.0, 60.7] | 33.3 [-10.0, 60.7] | 76.2 | 1.00 [0.85, 1.17] | 0.0 | - |
| `bayes-fixed-high` | 20.2 [5.8, 49.5] | 20.2 [5.8, 49.5] | 46.3 | 0.01 [-0.00, 0.03] | 0.0 | - |
| `bayes-nolearn` | 19.8 [5.5, 49.3] | 19.8 [5.5, 49.3] | 45.4 | 0.00 [-0.00, 0.23] | 0.0 | - |
| `bayes-noflow` | 19.8 [5.5, 49.3] | 19.8 [5.5, 49.3] | 45.4 | -0.00 [-0.44, 0.00] | 0.0 | - |
| `bayes` | 19.8 [5.5, 49.2] | 19.8 [5.5, 49.2] | 45.2 | 1.00 [1.00, 1.00] | 0.0 | - |
| `bayes-mean` | 3.8 [-83.6, 27.0] | 3.8 [-83.6, 27.0] | 8.8 | 0.04 [0.01, 0.08] | 0.0 | - |
| `glosten-milgrom` | -0.2 [-42.7, 17.2] | -0.2 [-42.7, 17.2] | -0.4 | 1.16 [1.14, 1.21] | 0.0 | - |
| `bayes-thompson` | -8.0 [-154.3, 34.1] | -8.0 [-154.3, 34.1] | -18.4 | 0.69 [0.63, 0.82] | 0.0 | - |
| `static` | -93.6 [-427.5, -11.6] | -93.6 [-427.5, -11.6] | -214.1 | -0.00 [-0.00, -0.00] | 0.0 | - |
| `bayes-fixed-low` | -202.3 [-920.1, -13.8] | -202.3 [-920.1, -13.8] | -462.6 | 0.00 [-0.00, 0.00] | 0.0 | - |
| `random` | -522.6 [-1606.6, -238.0] | -522.6 [-1606.6, -238.0] | -1194.9 | 0.00 [-0.06, 0.07] | 0.0 | - |
| ceiling (estimate, `ce-1`) | about 67 (66 to 86) | about 67 (66 to 86) | - | - | - | - |

Oracle profit per session (prior sd): tight 1.40.

## Score by true regime

Share of the oracle within each regime, and for the most informed regime the expected profit per session in prior sd (the oracle earns little there, so a share is unstable).

| agent | tight, alpha 0.05 | tight, alpha 0.5 | tight, alpha 0.9 (sd per session) |
| --- | ---: | ---: | ---: |
| `oracle` | 100.0 | 100.0 | +0.08 |
| `bayes-lookahead-w8` | 58.5 | -16.0 | -0.38 |
| `bayes-optimist` | 60.6 | -90.9 | -0.30 |
| `bayes-lookahead-w4` | 58.6 | -84.5 | -0.25 |
| `bayes-lookahead` | 40.9 | -23.5 | -0.02 |
| `bayes-lookahead-w2` | 45.9 | -107.2 | -0.10 |
| `bayes-fixed-high` | 13.3 | 100.0 | +0.08 |
| `bayes-nolearn` | 13.3 | 100.0 | +0.06 |
| `bayes-noflow` | 13.3 | 100.0 | +0.06 |
| `bayes` | 13.3 | 100.0 | +0.06 |
| `bayes-mean` | 37.0 | -96.9 | -1.02 |
| `glosten-milgrom` | 15.1 | -155.9 | -0.19 |
| `bayes-thompson` | 46.2 | -169.7 | -1.69 |
| `static` | 28.0 | -566.1 | -3.56 |
| `bayes-fixed-low` | 92.8 | -1564.0 | -8.07 |
| `random` | -81.2 | -2874.1 | -11.44 |

## Shortfall to the oracle

In oracle points: shortfall = pricing + information + path + residual, exactly. Pricing: expected profit given up against the myopic Bayes quote given public information. Information: what not knowing the informed share still costs at the agent's states. Path: the oracle on its own path minus the oracle at the agent's states. Residual: regime luck of the agent's quotes against the Bayes quotes at the same states (zero in expectation for public quote rules).

| agent | tier | shortfall | pricing | information | path | residual |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `oracle` | tight | 0.0 | 21.9 | 31.8 | 0.0 | -53.7 |
| `oracle` | pooled | 0.0 | 21.9 | 31.8 | 0.0 | -53.7 |
| `bayes-lookahead-w8` | tight | 56.3 | 17.8 | 39.0 | -2.2 | 1.7 |
| `bayes-lookahead-w8` | pooled | 56.3 | 17.8 | 39.0 | -2.2 | 1.7 |
| `bayes-optimist` | tight | 57.0 | 4.5 | 41.2 | 8.8 | 2.5 |
| `bayes-optimist` | pooled | 57.0 | 4.5 | 41.2 | 8.8 | 2.5 |
| `bayes-lookahead-w4` | tight | 57.2 | 10.0 | 46.1 | 1.5 | -0.3 |
| `bayes-lookahead-w4` | pooled | 57.2 | 10.0 | 46.1 | 1.5 | -0.3 |
| `bayes-lookahead` | tight | 64.2 | 1.4 | 55.2 | 7.3 | 0.3 |
| `bayes-lookahead` | pooled | 64.2 | 1.4 | 55.2 | 7.3 | 0.3 |
| `bayes-lookahead-w2` | tight | 66.7 | 4.5 | 57.2 | 5.2 | -0.3 |
| `bayes-lookahead-w2` | pooled | 66.7 | 4.5 | 57.2 | 5.2 | -0.3 |
| `bayes-fixed-high` | tight | 79.8 | 1.0 | 73.3 | 10.8 | -5.4 |
| `bayes-fixed-high` | pooled | 79.8 | 1.0 | 73.3 | 10.8 | -5.4 |
| `bayes-nolearn` | tight | 80.2 | 0.1 | 69.6 | 10.8 | -0.4 |
| `bayes-nolearn` | pooled | 80.2 | 0.1 | 69.6 | 10.8 | -0.4 |
| `bayes-noflow` | tight | 80.2 | 0.2 | 69.6 | 10.8 | -0.5 |
| `bayes-noflow` | pooled | 80.2 | 0.2 | 69.6 | 10.8 | -0.5 |
| `bayes` | tight | 80.2 | 0.0 | 69.5 | 10.7 | 0.0 |
| `bayes` | pooled | 80.2 | 0.0 | 69.5 | 10.7 | 0.0 |
| `bayes-mean` | tight | 96.2 | 73.6 | 40.0 | -5.1 | -12.3 |
| `bayes-mean` | pooled | 96.2 | 73.6 | 40.0 | -5.1 | -12.3 |
| `glosten-milgrom` | tight | 100.2 | 45.4 | 45.5 | 9.0 | 0.3 |
| `glosten-milgrom` | pooled | 100.2 | 45.4 | 45.5 | 9.0 | 0.3 |
| `bayes-thompson` | tight | 108.0 | 38.6 | 53.5 | 6.1 | 9.8 |
| `bayes-thompson` | pooled | 108.0 | 38.6 | 53.5 | 6.1 | 9.8 |
| `static` | tight | 193.6 | 155.7 | 51.7 | -7.2 | -6.6 |
| `static` | pooled | 193.6 | 155.7 | 51.7 | -7.2 | -6.6 |
| `bayes-fixed-low` | tight | 302.3 | 241.9 | 49.1 | -10.5 | 21.8 |
| `bayes-fixed-low` | pooled | 302.3 | 241.9 | 49.1 | -10.5 | 21.8 |
| `random` | tight | 622.6 | 571.9 | 58.2 | -7.1 | -0.4 |
| `random` | pooled | 622.6 | 571.9 | 58.2 | -7.1 | -0.4 |

## Skill axes

Learning response: coefficient on the myopic Bayes quote's half-width when the agent's half-width is regressed on the Bayes and the prior-regime half-widths together, at the same states (1: widths follow the evidence on the informed share as the Bayes quote does; 0: they follow the prior-regime quote or neither). Mass on truth: mean posterior mass on the true regime at the start of each round, along the agent's own path. Probing: share of two-sided quotes in rounds 1 and 2 tighter than the Bayes quote. Width: total width over the Bayes quote's at the same states. Mid error: mean |mid - public mean| in public posterior sds.

| agent | learning response | mass on truth, rounds 1-6 | probing % | width | mid error |
| --- | ---: | ---: | ---: | ---: | ---: |
| `oracle` | 0.81 [0.50, 0.97] | 0.33 / 0.35 / 0.43 / 0.47 / 0.51 / 0.51 | 32 | 0.90 | 0.33 |
| `bayes-lookahead-w8` | 0.64 [0.52, 0.74] | 0.33 / 0.38 / 0.51 / 0.60 / 0.65 / 0.70 | 62 | 0.82 | 0.34 |
| `bayes-optimist` | 0.96 [0.89, 1.01] | 0.33 / 0.37 / 0.44 / 0.49 / 0.50 / 0.49 | 39 | 0.95 | 0.27 |
| `bayes-lookahead-w4` | 0.84 [0.73, 0.91] | 0.33 / 0.36 / 0.48 / 0.56 / 0.55 / 0.62 | 56 | 0.90 | 0.30 |
| `bayes-lookahead` | 1.08 [0.96, 1.20] | 0.33 / 0.36 / 0.44 / 0.48 / 0.50 / 0.51 | 25 | 1.03 | 0.39 |
| `bayes-lookahead-w2` | 1.00 [0.85, 1.17] | 0.33 / 0.35 / 0.43 / 0.46 / 0.50 / 0.60 | 51 | 0.97 | 0.37 |
| `bayes-fixed-high` | 0.01 [-0.00, 0.03] | 0.33 / 0.31 / 0.31 / 0.33 / 0.33 / 0.33 | 0 | 1.01 | 0.46 |
| `bayes-nolearn` | 0.00 [-0.00, 0.23] | 0.33 / 0.31 / 0.31 / 0.34 / 0.34 / 0.33 | 0 | 1.00 | 0.45 |
| `bayes-noflow` | -0.00 [-0.44, 0.00] | 0.33 / 0.31 / 0.31 / 0.34 / 0.33 / 0.33 | 0 | 1.00 | 0.45 |
| `bayes` | 1.00 [1.00, 1.00] | 0.33 / 0.31 / 0.31 / 0.34 / 0.34 / 0.34 | 0 | 1.00 | 0.44 |
| `bayes-mean` | 0.04 [0.01, 0.08] | 0.33 / 0.41 / 0.55 / 0.68 / 0.72 / 0.77 | 54 | 0.76 | 0.01 |
| `glosten-milgrom` | 1.16 [1.14, 1.21] | 0.33 / 0.46 / 0.58 / 0.58 / 0.62 / 0.66 | 62 | 0.93 | 0.34 |
| `bayes-thompson` | 0.69 [0.63, 0.82] | 0.33 / 0.36 / 0.39 / 0.45 / 0.42 / 0.42 | 25 | 0.90 | 0.39 |
| `static` | -0.00 [-0.00, -0.00] | 0.33 / 0.36 / 0.46 / 0.46 / 0.55 / 0.72 | 38 | 0.86 | 0.75 |
| `bayes-fixed-low` | 0.00 [-0.00, 0.00] | 0.33 / 0.43 / 0.69 / 0.73 / 0.79 / 0.76 | 96 | 0.37 | 0.44 |
| `random` | 0.00 [-0.06, 0.07] | 0.33 / 0.38 / 0.47 / 0.54 / 0.59 / 0.62 | 73 | 0.48 | 1.55 |
