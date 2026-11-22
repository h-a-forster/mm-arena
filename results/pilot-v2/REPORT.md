# mm-arena session report: pilot-v2

12 sessions. Score: share of the known-regime oracle's expected profit, `100 x sum(ev_alpha) / sum(oracle ev_alpha)`, each session in prior-sd units of its game. 100 is the profit of a quoter who is told the informed share and quotes the myopic optimum for it; 0 is never quoting; negative means an expected loss. Intervals: 95%, bootstrap over sessions within each tier.

The ceiling line (`ce-1`) is an estimate of the best score a quoter that does not know the informed share can reach, with its bracket. It is not a denominator and later versions may tighten it.

## Leaderboard

| agent | pooled | open | mixed | learning response | invalid % | cost USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `oracle` | 100.0 [100.0, 100.0] | 100.0 [100.0, 100.0] | 100.0 [100.0, 100.0] | 1.13 [0.52, 1.83] | 0.0 | - |
| `bayes-lookahead-w2` | 93.2 [87.9, 96.4] | 94.0 [85.5, 99.6] | 92.2 [78.4, 95.7] | 0.92 [0.77, 0.96] | 0.0 | - |
| `bayes-lookahead` | 92.7 [87.5, 95.7] | 93.8 [86.4, 99.2] | 91.3 [76.7, 95.2] | 0.94 [0.84, 0.96] | 0.0 | - |
| `bayes-lookahead-w4` | 92.4 [85.8, 95.5] | 93.6 [81.5, 98.7] | 90.8 [73.7, 94.6] | 0.80 [0.68, 0.83] | 0.0 | - |
| `bayes-optimist` | 91.7 [79.6, 96.2] | 94.4 [75.9, 98.4] | 88.2 [49.0, 95.7] | 0.95 [0.92, 0.98] | 0.0 | - |
| `bayes-lookahead-w8` | 90.8 [81.7, 94.3] | 92.8 [76.8, 97.9] | 88.2 [64.8, 92.9] | 0.67 [0.54, 0.72] | 0.0 | - |
| `bayes` | 89.4 [82.5, 92.7] | 91.4 [85.5, 94.0] | 86.8 [57.4, 93.4] | 1.00 [1.00, 1.00] | 0.0 | - |
| `claude-cli:claude-fable-5-2@high` | 88.8 [79.5, 93.0] | 90.4 [78.0, 95.0] | 86.6 [56.0, 93.4] | 0.95 [0.88, 0.97] | 0.0 | 46.09 |
| `claude-cli:claude-fable-5-2@high#r2` | 88.4 [78.9, 92.5] | 89.1 [65.3, 93.7] | 87.4 [68.2, 93.4] | 0.99 [0.94, 1.00] | 0.0 | 45.10 |
| `bayes-nolearn` | 71.5 [59.2, 82.4] | 76.3 [57.0, 88.5] | 65.6 [43.4, 85.5] | 0.15 [0.09, 0.22] | 0.0 | - |
| `claude-cli:claude-opus-5-5@high#r2` | 71.0 [33.9, 84.0] | 70.8 [-5.0, 88.0] | 71.3 [-11.4, 86.3] | 0.25 [0.09, 0.48] | 0.0 | 13.44 |
| `claude-cli:claude-opus-5-5@high` | 70.0 [25.2, 84.9] | 71.6 [-28.5, 89.4] | 68.1 [-52.0, 87.3] | 0.39 [0.21, 0.50] | 0.0 | 13.28 |
| `bayes-mean` | 65.1 [29.1, 77.4] | 70.4 [-7.3, 84.3] | 58.3 [-37.1, 74.2] | 0.05 [-0.00, 0.12] | 0.0 | - |
| `bayes-thompson` | 63.1 [42.2, 80.1] | 77.7 [55.1, 97.1] | 44.6 [-25.3, 71.7] | 0.76 [0.67, 0.84] | 0.0 | - |
| `claude-cli:claude-haiku-5-5@high` | 56.4 [-2.0, 77.6] | 53.2 [-123.0, 84.0] | 60.3 [-17.7, 75.4] | 0.34 [0.12, 0.48] | 0.0 | 1.82 |
| `bayes-noflow` | 48.6 [-0.4, 70.4] | 55.7 [-41.3, 77.7] | 39.5 [-67.7, 77.3] | 0.08 [-0.00, 0.23] | 0.0 | - |
| `bayes-fixed-high` | 30.3 [16.5, 60.9] | 28.2 [10.3, 81.8] | 33.0 [15.9, 94.9] | 0.28 [-0.15, 0.60] | 0.0 | - |
| `bayes-fixed-low` | 13.0 [-175.9, 73.4] | 35.7 [-255.9, 89.0] | -15.7 [-549.5, 85.8] | -0.00 [-0.03, 0.04] | 0.0 | - |
| `glosten-milgrom` | 8.6 [-29.3, 24.4] | 12.8 [-44.4, 24.4] | 3.3 [-111.1, 32.9] | 1.22 [1.19, 1.29] | 0.0 | - |
| `claude-cli:claude-sonnet-5-5@high` | 3.1 [-162.5, 60.4] | -17.3 [-518.0, 68.6] | 28.9 [-229.2, 75.5] | 0.05 [-0.07, 0.13] | 0.0 | 6.58 |
| `static` | 0.2 [-167.2, 54.8] | 3.3 [-336.7, 66.6] | -3.8 [-363.2, 61.5] | 0.00 [-0.00, 0.02] | 0.0 | - |
| `random` | -273.3 [-781.5, -103.9] | -236.0 [-1164.2, -57.9] | -320.7 [-1597.3, -84.8] | 0.03 [-0.01, 0.07] | 0.0 | - |
| ceiling (estimate, `ce-1`) | about 91 (90 to 96) | about 92 (92 to 97) | about 90 (89 to 95) | - | - | - |

Oracle profit per session (prior sd): open 2.87, mixed 2.27.

## Score by true regime

Share of the oracle within each regime, and for the most informed regime the expected profit per session in prior sd (the oracle earns little there, so a share is unstable).

| agent | open, alpha 0.05 | open, alpha 0.5 | open, alpha 0.9 (sd per session) | mixed, alpha 0.05 | mixed, alpha 0.5 | mixed, alpha 0.9 (sd per session) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `oracle` | 100.0 | 100.0 | +0.25 | 100.0 | 100.0 | +0.13 |
| `bayes-lookahead-w2` | 94.4 | 101.3 | +0.06 | 94.2 | 94.7 | -0.02 |
| `bayes-lookahead` | 94.0 | 100.8 | +0.08 | 94.1 | 89.7 | -0.00 |
| `bayes-lookahead-w4` | 94.8 | 100.9 | +0.01 | 94.0 | 93.2 | -0.08 |
| `bayes-optimist` | 98.4 | 93.1 | +0.01 | 97.1 | 78.0 | -0.20 |
| `bayes-lookahead-w8` | 94.8 | 100.3 | -0.05 | 93.4 | 86.7 | -0.14 |
| `bayes` | 92.2 | 93.7 | +0.13 | 91.8 | 85.3 | -0.13 |
| `claude-cli:claude-fable-5-2@high` | 92.4 | 94.0 | +0.03 | 92.6 | 84.1 | -0.16 |
| `claude-cli:claude-fable-5-2@high#r2` | 93.6 | 91.3 | -0.11 | 91.1 | 86.9 | -0.07 |
| `bayes-nolearn` | 76.2 | 99.8 | -0.28 | 62.0 | 100.0 | -0.23 |
| `claude-cli:claude-opus-5-5@high#r2` | 90.2 | 67.2 | -0.98 | 90.0 | 46.7 | -0.53 |
| `claude-cli:claude-opus-5-5@high` | 92.8 | 66.0 | -1.06 | 90.5 | 56.4 | -0.91 |
| `bayes-mean` | 85.7 | 75.8 | -0.90 | 74.6 | 65.5 | -0.88 |
| `bayes-thompson` | 75.6 | 87.6 | +0.13 | 53.3 | 71.3 | -0.78 |
| `claude-cli:claude-haiku-5-5@high` | 86.8 | 64.5 | -2.22 | 78.6 | 39.7 | -0.58 |
| `bayes-noflow` | 72.3 | 86.3 | -1.54 | 49.0 | 97.7 | -1.28 |
| `bayes-fixed-high` | 9.7 | 76.8 | +0.25 | 14.6 | 93.5 | +0.13 |
| `bayes-fixed-low` | 98.0 | 33.3 | -3.81 | 101.5 | -28.7 | -5.96 |
| `glosten-milgrom` | 26.7 | -2.0 | -0.55 | 33.8 | -82.2 | -0.35 |
| `claude-cli:claude-sonnet-5-5@high` | 81.7 | -3.7 | -6.59 | 83.1 | 23.9 | -2.72 |
| `static` | 78.2 | -1.3 | -4.64 | 59.1 | 65.7 | -4.30 |
| `random` | -6.3 | -431.0 | -11.17 | -58.6 | -274.2 | -14.78 |

## Shortfall to the oracle

In oracle points: shortfall = pricing + information + path + residual, exactly. Pricing: expected profit given up against the myopic Bayes quote given public information. Information: what not knowing the informed share still costs at the agent's states. Path: the oracle on its own path minus the oracle at the agent's states. Residual: regime luck of the agent's quotes against the Bayes quotes at the same states (zero in expectation for public quote rules).

| agent | tier | shortfall | pricing | information | path | residual |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `oracle` | open | 0.0 | 7.0 | 13.3 | 0.0 | -20.3 |
| `oracle` | mixed | 0.0 | 11.6 | 30.8 | 0.0 | -42.4 |
| `oracle` | pooled | 0.0 | 9.0 | 21.0 | 0.0 | -30.0 |
| `bayes-lookahead-w2` | open | 6.0 | 1.5 | 7.4 | -3.4 | 0.6 |
| `bayes-lookahead-w2` | mixed | 7.8 | 1.9 | 5.9 | 0.1 | -0.0 |
| `bayes-lookahead-w2` | pooled | 6.8 | 1.7 | 6.7 | -1.9 | 0.3 |
| `bayes-lookahead` | open | 6.2 | 0.9 | 7.8 | -3.0 | 0.5 |
| `bayes-lookahead` | mixed | 8.7 | 1.1 | 6.8 | 0.4 | 0.3 |
| `bayes-lookahead` | pooled | 7.3 | 1.0 | 7.4 | -1.5 | 0.4 |
| `bayes-lookahead-w4` | open | 6.4 | 2.7 | 7.1 | -4.0 | 0.6 |
| `bayes-lookahead-w4` | mixed | 9.2 | 3.2 | 5.2 | -0.2 | 0.9 |
| `bayes-lookahead-w4` | pooled | 7.6 | 2.9 | 6.3 | -2.3 | 0.7 |
| `bayes-optimist` | open | 5.6 | 1.6 | 7.7 | -0.7 | -3.1 |
| `bayes-optimist` | mixed | 11.8 | 2.7 | 8.9 | -0.2 | 0.3 |
| `bayes-optimist` | pooled | 8.3 | 2.1 | 8.3 | -0.5 | -1.6 |
| `bayes-lookahead-w8` | open | 7.2 | 4.2 | 7.1 | -4.2 | 0.2 |
| `bayes-lookahead-w8` | mixed | 11.8 | 5.6 | 5.8 | -0.6 | 1.0 |
| `bayes-lookahead-w8` | pooled | 9.2 | 4.8 | 6.5 | -2.6 | 0.5 |
| `bayes` | open | 8.6 | 0.0 | 7.5 | 1.1 | 0.0 |
| `bayes` | mixed | 13.2 | 0.0 | 12.0 | 1.2 | 0.0 |
| `bayes` | pooled | 10.6 | 0.0 | 9.5 | 1.2 | 0.0 |
| `claude-cli:claude-fable-5-2@high` | open | 9.6 | 2.1 | 7.6 | -1.0 | 0.9 |
| `claude-cli:claude-fable-5-2@high` | mixed | 13.4 | 1.9 | 12.9 | -2.0 | 0.6 |
| `claude-cli:claude-fable-5-2@high` | pooled | 11.2 | 2.0 | 9.9 | -1.5 | 0.8 |
| `claude-cli:claude-fable-5-2@high#r2` | open | 10.9 | 1.4 | 9.1 | -0.1 | 0.5 |
| `claude-cli:claude-fable-5-2@high#r2` | mixed | 12.6 | 1.9 | 11.7 | -1.7 | 0.7 |
| `claude-cli:claude-fable-5-2@high#r2` | pooled | 11.6 | 1.6 | 10.2 | -0.8 | 0.6 |
| `bayes-nolearn` | open | 23.7 | 16.0 | 5.7 | -0.4 | 2.4 |
| `bayes-nolearn` | mixed | 34.4 | 23.6 | 15.3 | 0.6 | -5.1 |
| `bayes-nolearn` | pooled | 28.5 | 19.4 | 9.9 | 0.0 | -0.9 |
| `claude-cli:claude-opus-5-5@high#r2` | open | 29.2 | 27.4 | 7.5 | -3.1 | -2.6 |
| `claude-cli:claude-opus-5-5@high#r2` | mixed | 28.7 | 23.9 | 27.3 | -14.1 | -8.3 |
| `claude-cli:claude-opus-5-5@high#r2` | pooled | 29.0 | 25.9 | 16.2 | -7.9 | -5.2 |
| `claude-cli:claude-opus-5-5@high` | open | 28.4 | 25.5 | 6.6 | -2.1 | -1.5 |
| `claude-cli:claude-opus-5-5@high` | mixed | 31.9 | 22.4 | 9.4 | -2.1 | 2.2 |
| `claude-cli:claude-opus-5-5@high` | pooled | 30.0 | 24.1 | 7.8 | -2.1 | 0.1 |
| `bayes-mean` | open | 29.6 | 27.3 | 6.9 | -4.9 | 0.2 |
| `bayes-mean` | mixed | 41.7 | 39.4 | 8.3 | -1.9 | -4.1 |
| `bayes-mean` | pooled | 34.9 | 32.7 | 7.5 | -3.6 | -1.7 |
| `bayes-thompson` | open | 22.3 | 7.6 | 13.2 | 0.6 | 0.8 |
| `bayes-thompson` | mixed | 55.4 | 16.6 | 34.1 | 0.5 | 4.1 |
| `bayes-thompson` | pooled | 36.9 | 11.6 | 22.4 | 0.6 | 2.3 |
| `claude-cli:claude-haiku-5-5@high` | open | 46.8 | 33.2 | 11.8 | -3.1 | 4.9 |
| `claude-cli:claude-haiku-5-5@high` | mixed | 39.7 | 30.3 | 11.0 | -0.8 | -0.8 |
| `claude-cli:claude-haiku-5-5@high` | pooled | 43.6 | 31.9 | 11.4 | -2.0 | 2.4 |
| `bayes-noflow` | open | 44.3 | 30.9 | 6.7 | -0.9 | 7.5 |
| `bayes-noflow` | mixed | 60.5 | 42.0 | 18.2 | 0.6 | -0.3 |
| `bayes-noflow` | pooled | 51.4 | 35.8 | 11.8 | -0.2 | 4.1 |
| `bayes-fixed-high` | open | 71.8 | 18.0 | 32.0 | 3.6 | 18.3 |
| `bayes-fixed-high` | mixed | 67.0 | 17.9 | 64.7 | 3.3 | -18.9 |
| `bayes-fixed-high` | pooled | 69.7 | 17.9 | 46.5 | 3.4 | 1.9 |
| `bayes-fixed-low` | open | 64.3 | 62.4 | 6.1 | -3.0 | -1.2 |
| `bayes-fixed-low` | mixed | 115.7 | 118.9 | 9.3 | -5.8 | -6.7 |
| `bayes-fixed-low` | pooled | 87.0 | 87.4 | 7.5 | -4.3 | -3.6 |
| `glosten-milgrom` | open | 87.2 | 86.6 | 3.7 | -2.0 | -1.1 |
| `glosten-milgrom` | mixed | 96.7 | 87.3 | 10.0 | 0.4 | -0.9 |
| `glosten-milgrom` | pooled | 91.4 | 86.9 | 6.5 | -1.0 | -1.0 |
| `claude-cli:claude-sonnet-5-5@high` | open | 117.3 | 115.4 | 7.3 | -3.3 | -2.1 |
| `claude-cli:claude-sonnet-5-5@high` | mixed | 71.1 | 62.4 | 11.1 | -2.0 | -0.5 |
| `claude-cli:claude-sonnet-5-5@high` | pooled | 96.9 | 92.0 | 9.0 | -2.7 | -1.4 |
| `static` | open | 96.7 | 91.1 | 6.8 | -2.2 | 1.1 |
| `static` | mixed | 103.8 | 95.8 | 8.3 | -2.0 | 1.7 |
| `static` | pooled | 99.8 | 93.2 | 7.5 | -2.2 | 1.3 |
| `random` | open | 336.0 | 334.8 | 4.9 | -1.4 | -2.3 |
| `random` | mixed | 420.7 | 409.1 | 9.6 | -1.5 | 3.4 |
| `random` | pooled | 373.3 | 367.6 | 7.0 | -1.4 | 0.2 |

## Skill axes

Learning response: coefficient on the myopic Bayes quote's half-width when the agent's half-width is regressed on the Bayes and the prior-regime half-widths together, at the same states (1: widths follow the evidence on the informed share as the Bayes quote does; 0: they follow the prior-regime quote or neither). Mass on truth: mean posterior mass on the true regime at the start of each round, along the agent's own path. Probing: share of two-sided quotes in rounds 1 and 2 tighter than the Bayes quote. Width: total width over the Bayes quote's at the same states. Mid error: mean |mid - public mean| in public posterior sds.

| agent | learning response | mass on truth, rounds 1-6 | probing % | width | mid error |
| --- | ---: | ---: | ---: | ---: | ---: |
| `oracle` | 1.13 [0.52, 1.83] | 0.33 / 0.47 / 0.49 / 0.53 / 0.59 / 0.61 | 38 | 1.24 | 0.24 |
| `bayes-lookahead-w2` | 0.92 [0.77, 0.96] | 0.33 / 0.57 / 0.62 / 0.69 / 0.79 / 0.74 | 53 | 0.95 | 0.17 |
| `bayes-lookahead` | 0.94 [0.84, 0.96] | 0.33 / 0.56 / 0.61 / 0.68 / 0.77 / 0.72 | 38 | 0.96 | 0.17 |
| `bayes-lookahead-w4` | 0.80 [0.68, 0.83] | 0.33 / 0.58 / 0.67 / 0.75 / 0.83 / 0.85 | 52 | 0.92 | 0.20 |
| `bayes-optimist` | 0.95 [0.92, 0.98] | 0.33 / 0.54 / 0.56 / 0.61 / 0.68 / 0.65 | 69 | 0.94 | 0.18 |
| `bayes-lookahead-w8` | 0.67 [0.54, 0.72] | 0.33 / 0.61 / 0.68 / 0.79 / 0.88 / 0.89 | 56 | 0.90 | 0.19 |
| `bayes` | 1.00 [1.00, 1.00] | 0.33 / 0.50 / 0.52 / 0.58 / 0.64 / 0.60 | 0 | 1.00 | 0.19 |
| `claude-cli:claude-fable-5-2@high` | 0.95 [0.88, 0.97] | 0.33 / 0.52 / 0.55 / 0.60 / 0.65 / 0.64 | 36 | 0.98 | 0.14 |
| `claude-cli:claude-fable-5-2@high#r2` | 0.99 [0.94, 1.00] | 0.33 / 0.45 / 0.54 / 0.60 / 0.65 / 0.65 | 34 | 0.99 | 0.15 |
| `bayes-nolearn` | 0.15 [0.09, 0.22] | 0.33 / 0.51 / 0.58 / 0.66 / 0.70 / 0.68 | 19 | 1.05 | 0.35 |
| `claude-cli:claude-opus-5-5@high#r2` | 0.25 [0.09, 0.48] | 0.33 / 0.54 / 0.59 / 0.66 / 0.72 / 0.68 | 62 | 0.73 | 0.26 |
| `claude-cli:claude-opus-5-5@high` | 0.39 [0.21, 0.50] | 0.33 / 0.56 / 0.69 / 0.78 / 0.84 / 0.79 | 66 | 0.74 | 0.17 |
| `bayes-mean` | 0.05 [-0.00, 0.12] | 0.33 / 0.57 / 0.65 / 0.74 / 0.83 / 0.89 | 68 | 0.74 | 0.02 |
| `bayes-thompson` | 0.76 [0.67, 0.84] | 0.33 / 0.40 / 0.48 / 0.54 / 0.65 / 0.68 | 19 | 1.04 | 0.27 |
| `claude-cli:claude-haiku-5-5@high` | 0.34 [0.12, 0.48] | 0.33 / 0.47 / 0.55 / 0.66 / 0.74 / 0.73 | 44 | 0.85 | 0.31 |
| `bayes-noflow` | 0.08 [-0.00, 0.23] | 0.33 / 0.42 / 0.52 / 0.61 / 0.62 / 0.65 | 8 | 1.12 | 0.48 |
| `bayes-fixed-high` | 0.28 [-0.15, 0.60] | 0.33 / 0.34 / 0.34 / 0.38 / 0.37 / 0.37 | 0 | 1.56 | 0.39 |
| `bayes-fixed-low` | -0.00 [-0.03, 0.04] | 0.33 / 0.64 / 0.73 / 0.78 / 0.88 / 0.90 | 94 | 0.58 | 0.55 |
| `glosten-milgrom` | 1.22 [1.19, 1.29] | 0.33 / 0.68 / 0.72 / 0.80 / 0.84 / 0.88 | 94 | 0.67 | 0.24 |
| `claude-cli:claude-sonnet-5-5@high` | 0.05 [-0.07, 0.13] | 0.33 / 0.62 / 0.71 / 0.82 / 0.84 / 0.84 | 65 | 0.65 | 0.50 |
| `static` | 0.00 [-0.00, 0.02] | 0.33 / 0.55 / 0.69 / 0.77 / 0.79 / 0.78 | 28 | 1.00 | 1.09 |
| `random` | 0.03 [-0.01, 0.07] | 0.33 / 0.60 / 0.69 / 0.79 / 0.84 / 0.87 | 78 | 0.51 | 1.33 |

## Run-to-run variability

| setup | runs | pooled scores | run SD |
| --- | ---: | ---: | ---: |
| `claude-cli:claude-fable-5-2@high` | 2 | 88.8, 88.4 | 0.29 |
| `claude-cli:claude-opus-5-5@high` | 2 | 70.0, 71.0 | 0.68 |

| pair | gap | pooled run SD | Welch t (df) | p |
| --- | ---: | ---: | ---: | ---: |
| `claude-cli:claude-fable-5-2@high` - `claude-cli:claude-opus-5-5@high` | +18.0 | 0.52 | 34.50 (1.3) | 0.006 |

## Pre-registered tests

Families as in `docs/prereg-core-v2.md`; p-values Holm-adjusted within each family. Paired tests are sign flips of per-session differences of run-averaged values.

Family A (separation)

| test | value | p | p (Holm) |
| --- | ---: | ---: | ---: |
| claude-cli:claude-fable-5-2@high vs claude-cli:claude-haiku-5-5@high, pooled | - | <0.001 | 0.005 |
| claude-cli:claude-fable-5-2@high vs claude-cli:claude-opus-5-5@high, pooled | - | 0.004 | 0.012 |
| claude-cli:claude-fable-5-2@high vs claude-cli:claude-sonnet-5-5@high, pooled | - | <0.001 | 0.003 |
| claude-cli:claude-haiku-5-5@high vs claude-cli:claude-opus-5-5@high, pooled | - | 0.020 | 0.023 |
| claude-cli:claude-haiku-5-5@high vs claude-cli:claude-sonnet-5-5@high, pooled | - | 0.012 | 0.023 |
| claude-cli:claude-opus-5-5@high vs claude-cli:claude-sonnet-5-5@high, pooled | - | <0.001 | 0.005 |

Family B (learning and probing)

| test | value | p | p (Holm) |
| --- | ---: | ---: | ---: |
| claude-cli:claude-fable-5-2@high: learning response > 0 | 0.9 | <0.001 | <0.001 |
| claude-cli:claude-fable-5-2@high > bayes-nolearn, mixed tier | - | 0.188 | 1.000 |
| claude-cli:claude-fable-5-2@high > bayes, mixed tier | - | 0.312 | 1.000 |
| claude-cli:claude-haiku-5-5@high: learning response > 0 | 0.3 | 0.004 | 0.040 |
| claude-cli:claude-haiku-5-5@high > bayes-nolearn, mixed tier | - | 0.656 | 1.000 |
| claude-cli:claude-haiku-5-5@high > bayes, mixed tier | - | 1.000 | 1.000 |
| claude-cli:claude-opus-5-5@high: learning response > 0 | 0.4 | 0.002 | 0.022 |
| claude-cli:claude-opus-5-5@high > bayes-nolearn, mixed tier | - | 0.453 | 1.000 |
| claude-cli:claude-opus-5-5@high > bayes, mixed tier | - | 0.984 | 1.000 |
| claude-cli:claude-sonnet-5-5@high: learning response > 0 | 0.1 | 0.142 | 1.000 |
| claude-cli:claude-sonnet-5-5@high > bayes-nolearn, mixed tier | - | 0.891 | 1.000 |
| claude-cli:claude-sonnet-5-5@high > bayes, mixed tier | - | 1.000 | 1.000 |

Family C (gradient and effort)

| test | value | p | p (Holm) |
| --- | ---: | ---: | ---: |
| claude-cli:claude-fable-5-2@high: open share > mixed share | 3.8 | 0.269 | 1.000 |
| claude-cli:claude-opus-5-5@high: open share > mixed share | 3.5 | 0.436 | 1.000 |
| claude-cli:claude-haiku-5-5@high: open share > mixed share | -7.0 | 0.565 | 1.000 |
| claude-cli:claude-sonnet-5-5@high: open share > mixed share | -46.3 | 0.712 | 1.000 |
