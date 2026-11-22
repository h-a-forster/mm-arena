# mm-arena session report: core-v2

45 sessions. Score: share of the known-regime oracle's expected profit, `100 x sum(ev_alpha) / sum(oracle ev_alpha)`, each session in prior-sd units of its game. 100 is the profit of a quoter who is told the informed share and quotes the myopic optimum for it; 0 is never quoting; negative means an expected loss. Intervals: 95%, bootstrap over sessions within each tier.

The ceiling line (`ce-1`) is an estimate of the best score a quoter that does not know the informed share can reach, with its bracket. It is not a denominator and later versions may tighten it.

## Leaderboard

| agent | pooled | open | mixed | learning response | invalid % | cost USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `oracle` | 100.0 [100.0, 100.0] | 100.0 [100.0, 100.0] | 100.0 [100.0, 100.0] | 0.87 [0.65, 1.06] | 0.0 | - |
| `bayes-lookahead` | 90.2 [86.9, 92.9] | 92.3 [85.6, 95.4] | 88.8 [84.4, 92.2] | 0.85 [0.83, 0.88] | 0.0 | - |
| `bayes-lookahead-w2` | 89.5 [85.5, 92.7] | 91.9 [85.1, 95.1] | 88.0 [82.3, 92.5] | 0.76 [0.71, 0.82] | 0.0 | - |
| `bayes-lookahead-w4` | 88.7 [84.3, 92.0] | 91.7 [84.4, 94.8] | 86.8 [80.5, 91.2] | 0.69 [0.63, 0.76] | 0.0 | - |
| `bayes-lookahead-w8` | 87.7 [82.7, 91.2] | 91.0 [83.4, 94.4] | 85.5 [77.9, 90.3] | 0.58 [0.52, 0.64] | 0.0 | - |
| `bayes-optimist` | 86.9 [80.2, 91.3] | 90.8 [79.3, 95.7] | 84.4 [74.3, 90.3] | 0.95 [0.90, 0.97] | 0.0 | - |
| `claude-cli:claude-fable-5-2@high` | 86.5 [81.6, 89.9] | 90.0 [83.6, 93.6] | 84.1 [76.6, 89.1] | 0.94 [0.89, 0.96] | 0.0 | 176.21 |
| `claude-cli:claude-fable-5-2@high#r2` | 86.0 [81.2, 89.3] | 89.6 [84.0, 92.7] | 83.6 [75.7, 88.7] | 0.94 [0.89, 0.97] | 0.0 | 173.54 |
| `bayes` | 78.2 [70.1, 85.5] | 91.6 [86.4, 94.6] | 69.3 [58.9, 80.1] | 1.00 [1.00, 1.00] | 0.0 | - |
| `bayes-nolearn` | 69.1 [63.1, 75.8] | 81.4 [73.3, 87.4] | 61.0 [55.0, 69.1] | 0.12 [0.05, 0.19] | 0.0 | - |
| `claude-cli:claude-opus-5-5@high#r3` | 68.2 [51.9, 77.9] | 77.0 [50.1, 88.1] | 62.3 [38.2, 75.3] | 0.56 [0.36, 0.71] | 0.0 | 47.91 |
| `bayes-mean` | 65.4 [51.3, 73.8] | 74.0 [48.4, 84.1] | 59.7 [40.1, 70.5] | 0.04 [-0.00, 0.07] | 0.0 | - |
| `claude-cli:claude-opus-5-5@high` | 64.6 [46.3, 75.1] | 74.9 [52.3, 84.9] | 57.8 [27.8, 73.7] | 0.44 [0.33, 0.55] | 0.0 | 49.06 |
| `bayes-thompson` | 62.3 [50.4, 72.1] | 81.5 [66.2, 89.7] | 49.5 [32.8, 64.0] | 0.85 [0.75, 0.91] | 0.0 | - |
| `claude-cli:claude-opus-5-5@high#r2` | 60.5 [40.6, 71.6] | 69.9 [41.3, 83.1] | 54.3 [24.1, 70.1] | 0.45 [0.25, 0.61] | 0.0 | 48.93 |
| `bayes-noflow` | 56.9 [47.5, 64.5] | 70.5 [52.9, 78.3] | 47.9 [37.4, 55.9] | 0.08 [0.01, 0.15] | 0.0 | - |
| `claude-cli:claude-haiku-5-5@high` | 54.8 [33.1, 67.0] | 58.8 [10.8, 77.3] | 52.2 [25.4, 66.6] | 0.47 [0.24, 0.62] | 0.0 | 6.65 |
| `bayes-fixed-high` | 36.3 [28.0, 46.3] | 40.3 [27.4, 59.3] | 33.7 [23.5, 47.3] | 0.25 [0.06, 0.38] | 0.0 | - |
| `claude-cli:claude-opus-5-5@low` | 17.0 [-30.5, 44.2] | 24.4 [-59.5, 59.6] | 12.2 [-56.4, 48.2] | 0.08 [0.05, 0.11] | 0.0 | 22.03 |
| `glosten-milgrom` | 5.0 [-19.3, 19.8] | 8.2 [-24.1, 22.9] | 2.9 [-35.8, 24.6] | 1.23 [1.18, 1.29] | 0.0 | - |
| `bayes-fixed-low` | 4.5 [-64.6, 42.7] | 23.6 [-93.0, 70.4] | -8.2 [-112.4, 45.3] | 0.01 [-0.01, 0.02] | 0.0 | - |
| `static` | 0.3 [-49.3, 29.2] | 16.6 [-76.2, 54.8] | -10.5 [-79.1, 25.8] | -0.00 [-0.00, -0.00] | 0.0 | - |
| `claude-cli:claude-sonnet-5-5@high` | -1.2 [-64.5, 33.7] | 23.3 [-76.0, 62.2] | -17.5 [-119.1, 33.3] | 0.08 [-0.01, 0.16] | 0.0 | 24.69 |
| `random` | -280.7 [-458.8, -182.0] | -208.2 [-493.3, -88.8] | -329.0 [-594.0, -190.1] | -0.01 [-0.04, 0.03] | 0.0 | - |
| ceiling (estimate, `ce-1`) | about 91 (90 to 96) | about 92 (92 to 97) | about 90 (89 to 95) | - | - | - |

Oracle profit per session (prior sd): open 2.95, mixed 2.21.

## Score by true regime

Share of the oracle within each regime, and for the most informed regime the expected profit per session in prior sd (the oracle earns little there, so a share is unstable).

| agent | open, alpha 0.05 | open, alpha 0.5 | open, alpha 0.9 (sd per session) | mixed, alpha 0.05 | mixed, alpha 0.5 | mixed, alpha 0.9 (sd per session) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `oracle` | 100.0 | 100.0 | +0.27 | 100.0 | 100.0 | +0.18 |
| `bayes-lookahead` | 96.1 | 89.5 | +0.06 | 90.0 | 98.0 | -0.01 |
| `bayes-lookahead-w2` | 95.8 | 89.0 | +0.06 | 89.5 | 100.9 | -0.06 |
| `bayes-lookahead-w4` | 95.7 | 90.2 | +0.02 | 90.4 | 94.0 | -0.12 |
| `bayes-lookahead-w8` | 95.3 | 91.1 | -0.04 | 90.1 | 97.4 | -0.23 |
| `bayes-optimist` | 98.2 | 83.9 | -0.08 | 93.7 | 66.5 | -0.15 |
| `claude-cli:claude-fable-5-2@high` | 93.6 | 88.0 | +0.05 | 89.2 | 79.1 | -0.06 |
| `claude-cli:claude-fable-5-2@high#r2` | 92.2 | 89.4 | +0.08 | 89.1 | 74.6 | -0.04 |
| `bayes` | 94.1 | 89.5 | +0.13 | 66.1 | 89.5 | +0.07 |
| `bayes-nolearn` | 81.4 | 97.7 | -0.14 | 56.3 | 102.5 | -0.10 |
| `claude-cli:claude-opus-5-5@high#r3` | 94.8 | 63.3 | -0.64 | 85.6 | 19.1 | -0.67 |
| `bayes-mean` | 89.2 | 78.1 | -0.87 | 75.0 | 84.1 | -0.98 |
| `claude-cli:claude-opus-5-5@high` | 91.0 | 59.7 | -0.50 | 85.5 | 7.9 | -0.84 |
| `bayes-thompson` | 90.5 | 78.9 | -0.31 | 58.9 | 43.9 | -0.35 |
| `claude-cli:claude-opus-5-5@high#r2` | 91.0 | 46.4 | -0.66 | 85.2 | -7.1 | -0.89 |
| `bayes-noflow` | 79.2 | 80.9 | -0.59 | 50.0 | 75.3 | -0.33 |
| `claude-cli:claude-haiku-5-5@high` | 83.5 | 60.5 | -1.46 | 76.0 | 34.2 | -0.99 |
| `bayes-fixed-high` | 28.8 | 66.8 | +0.27 | 24.1 | 70.3 | +0.18 |
| `claude-cli:claude-opus-5-5@low` | 83.7 | -3.6 | -3.12 | 86.4 | -93.0 | -2.82 |
| `glosten-milgrom` | 31.5 | -20.5 | -0.85 | 35.6 | -116.6 | -0.45 |
| `bayes-fixed-low` | 99.6 | 5.4 | -4.41 | 99.8 | -109.9 | -4.70 |
| `static` | 73.7 | 10.7 | -3.48 | 57.4 | -82.3 | -2.88 |
| `claude-cli:claude-sonnet-5-5@high` | 79.5 | 20.1 | -3.46 | 78.8 | -163.6 | -3.60 |
| `random` | -6.4 | -307.1 | -11.32 | -45.7 | -702.0 | -11.73 |

## Shortfall to the oracle

In oracle points: shortfall = pricing + information + path + residual, exactly. Pricing: expected profit given up against the myopic Bayes quote given public information. Information: what not knowing the informed share still costs at the agent's states. Path: the oracle on its own path minus the oracle at the agent's states. Residual: regime luck of the agent's quotes against the Bayes quotes at the same states (zero in expectation for public quote rules).

| agent | tier | shortfall | pricing | information | path | residual |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `oracle` | open | 0.0 | 10.7 | 17.6 | 0.0 | -28.4 |
| `oracle` | mixed | 0.0 | 13.5 | 21.1 | 0.0 | -34.6 |
| `oracle` | pooled | 0.0 | 12.4 | 19.7 | 0.0 | -32.1 |
| `bayes-lookahead` | open | 7.7 | 0.7 | 6.3 | -0.3 | 1.0 |
| `bayes-lookahead` | mixed | 11.2 | 1.3 | 11.9 | -2.5 | 0.5 |
| `bayes-lookahead` | pooled | 9.8 | 1.1 | 9.6 | -1.6 | 0.7 |
| `bayes-lookahead-w2` | open | 8.1 | 1.2 | 6.3 | -0.7 | 1.3 |
| `bayes-lookahead-w2` | mixed | 12.0 | 2.6 | 12.0 | -3.0 | 0.4 |
| `bayes-lookahead-w2` | pooled | 10.5 | 2.0 | 9.8 | -2.1 | 0.8 |
| `bayes-lookahead-w4` | open | 8.3 | 2.1 | 6.4 | -1.0 | 0.9 |
| `bayes-lookahead-w4` | mixed | 13.2 | 3.9 | 13.0 | -3.9 | 0.2 |
| `bayes-lookahead-w4` | pooled | 11.3 | 3.2 | 10.3 | -2.7 | 0.5 |
| `bayes-lookahead-w8` | open | 9.0 | 3.8 | 6.9 | -2.4 | 0.8 |
| `bayes-lookahead-w8` | mixed | 14.5 | 6.6 | 12.6 | -5.0 | 0.3 |
| `bayes-lookahead-w8` | pooled | 12.3 | 5.5 | 10.3 | -4.0 | 0.5 |
| `bayes-optimist` | open | 9.2 | 1.5 | 8.4 | -1.1 | 0.3 |
| `bayes-optimist` | mixed | 15.6 | 3.0 | 13.8 | -0.6 | -0.5 |
| `bayes-optimist` | pooled | 13.1 | 2.4 | 11.7 | -0.8 | -0.2 |
| `claude-cli:claude-fable-5-2@high` | open | 10.0 | 1.5 | 9.3 | -1.3 | 0.5 |
| `claude-cli:claude-fable-5-2@high` | mixed | 15.9 | 3.3 | 12.5 | -0.3 | 0.3 |
| `claude-cli:claude-fable-5-2@high` | pooled | 13.5 | 2.6 | 11.2 | -0.7 | 0.4 |
| `claude-cli:claude-fable-5-2@high#r2` | open | 10.4 | 1.4 | 9.1 | -0.2 | 0.2 |
| `claude-cli:claude-fable-5-2@high#r2` | mixed | 16.4 | 3.2 | 13.2 | -0.2 | 0.2 |
| `claude-cli:claude-fable-5-2@high#r2` | pooled | 14.0 | 2.5 | 11.6 | -0.2 | 0.2 |
| `bayes` | open | 8.4 | 0.0 | 8.0 | 0.4 | 0.0 |
| `bayes` | mixed | 30.7 | 0.0 | 27.8 | 3.0 | 0.0 |
| `bayes` | pooled | 21.8 | 0.0 | 19.9 | 1.9 | 0.0 |
| `bayes-nolearn` | open | 18.6 | 10.2 | 8.3 | -1.2 | 1.3 |
| `bayes-nolearn` | mixed | 39.0 | 14.1 | 28.0 | 1.2 | -4.2 |
| `bayes-nolearn` | pooled | 30.9 | 12.5 | 20.1 | 0.2 | -2.0 |
| `claude-cli:claude-opus-5-5@high#r3` | open | 23.0 | 21.8 | 7.5 | -2.3 | -4.0 |
| `claude-cli:claude-opus-5-5@high#r3` | mixed | 37.7 | 28.6 | 16.1 | -2.7 | -4.3 |
| `claude-cli:claude-opus-5-5@high#r3` | pooled | 31.8 | 25.9 | 12.7 | -2.5 | -4.2 |
| `bayes-mean` | open | 26.0 | 21.5 | 8.5 | -3.6 | -0.3 |
| `bayes-mean` | mixed | 40.3 | 31.6 | 11.6 | -4.8 | 1.9 |
| `bayes-mean` | pooled | 34.6 | 27.5 | 10.3 | -4.3 | 1.0 |
| `claude-cli:claude-opus-5-5@high` | open | 25.1 | 21.6 | 7.6 | -2.0 | -2.2 |
| `claude-cli:claude-opus-5-5@high` | mixed | 42.2 | 32.8 | 15.9 | -4.0 | -2.5 |
| `claude-cli:claude-opus-5-5@high` | pooled | 35.4 | 28.3 | 12.6 | -3.2 | -2.4 |
| `bayes-thompson` | open | 18.5 | 8.1 | 8.3 | 0.4 | 1.7 |
| `bayes-thompson` | mixed | 50.5 | 13.1 | 35.7 | 2.5 | -0.8 |
| `bayes-thompson` | pooled | 37.7 | 11.1 | 24.7 | 1.6 | 0.2 |
| `claude-cli:claude-opus-5-5@high#r2` | open | 30.1 | 26.1 | 7.7 | -2.1 | -1.6 |
| `claude-cli:claude-opus-5-5@high#r2` | mixed | 45.7 | 36.0 | 16.7 | -3.7 | -3.3 |
| `claude-cli:claude-opus-5-5@high#r2` | pooled | 39.5 | 32.0 | 13.1 | -3.1 | -2.6 |
| `bayes-noflow` | open | 29.5 | 19.5 | 10.1 | -0.9 | 0.8 |
| `bayes-noflow` | mixed | 52.1 | 25.9 | 31.9 | 2.6 | -8.2 |
| `bayes-noflow` | pooled | 43.1 | 23.4 | 23.2 | 1.2 | -4.6 |
| `claude-cli:claude-haiku-5-5@high` | open | 41.2 | 32.1 | 6.9 | -0.7 | 2.9 |
| `claude-cli:claude-haiku-5-5@high` | mixed | 47.8 | 32.7 | 20.1 | -0.8 | -4.2 |
| `claude-cli:claude-haiku-5-5@high` | pooled | 45.2 | 32.5 | 14.8 | -0.8 | -1.3 |
| `bayes-fixed-high` | open | 59.7 | 35.3 | 21.6 | 5.6 | -2.7 |
| `bayes-fixed-high` | mixed | 66.3 | 14.8 | 42.3 | 6.7 | 2.4 |
| `bayes-fixed-high` | pooled | 63.7 | 23.0 | 34.0 | 6.3 | 0.4 |
| `claude-cli:claude-opus-5-5@low` | open | 75.6 | 67.3 | 5.9 | -1.3 | 3.6 |
| `claude-cli:claude-opus-5-5@low` | mixed | 87.8 | 82.4 | 13.1 | -4.4 | -3.4 |
| `claude-cli:claude-opus-5-5@low` | pooled | 83.0 | 76.4 | 10.3 | -3.1 | -0.6 |
| `glosten-milgrom` | open | 91.8 | 88.4 | 6.6 | -1.5 | -1.7 |
| `glosten-milgrom` | mixed | 97.1 | 84.1 | 13.1 | -0.3 | 0.2 |
| `glosten-milgrom` | pooled | 95.0 | 85.8 | 10.5 | -0.8 | -0.6 |
| `bayes-fixed-low` | open | 76.4 | 65.1 | 6.5 | -1.6 | 6.3 |
| `bayes-fixed-low` | mixed | 108.2 | 105.6 | 16.8 | -6.4 | -7.8 |
| `bayes-fixed-low` | pooled | 95.5 | 89.4 | 12.7 | -4.4 | -2.2 |
| `static` | open | 83.4 | 72.2 | 9.9 | -3.3 | 4.6 |
| `static` | mixed | 110.5 | 101.0 | 14.7 | -4.0 | -1.1 |
| `static` | pooled | 99.7 | 89.5 | 12.8 | -3.8 | 1.2 |
| `claude-cli:claude-sonnet-5-5@high` | open | 76.7 | 72.3 | 7.5 | -2.3 | -0.8 |
| `claude-cli:claude-sonnet-5-5@high` | mixed | 117.5 | 110.5 | 14.2 | -2.9 | -4.3 |
| `claude-cli:claude-sonnet-5-5@high` | pooled | 101.2 | 95.3 | 11.6 | -2.7 | -2.9 |
| `random` | open | 308.2 | 297.7 | 10.9 | -1.8 | 1.3 |
| `random` | mixed | 429.0 | 416.7 | 18.8 | -3.7 | -2.8 |
| `random` | pooled | 380.7 | 369.2 | 15.7 | -3.0 | -1.1 |

## Skill axes

Learning response: coefficient on the myopic Bayes quote's half-width when the agent's half-width is regressed on the Bayes and the prior-regime half-widths together, at the same states (1: widths follow the evidence on the informed share as the Bayes quote does; 0: they follow the prior-regime quote or neither). Mass on truth: mean posterior mass on the true regime at the start of each round, along the agent's own path. Probing: share of two-sided quotes in rounds 1 and 2 tighter than the Bayes quote. Width: total width over the Bayes quote's at the same states. Mid error: mean |mid - public mean| in public posterior sds.

| agent | learning response | mass on truth, rounds 1-6 | probing % | width | mid error |
| --- | ---: | ---: | ---: | ---: | ---: |
| `oracle` | 0.87 [0.65, 1.06] | 0.33 / 0.46 / 0.49 / 0.55 / 0.59 / 0.62 | 36 | 1.15 | 0.29 |
| `bayes-lookahead` | 0.85 [0.83, 0.88] | 0.33 / 0.50 / 0.58 / 0.63 / 0.68 / 0.74 | 37 | 0.95 | 0.17 |
| `bayes-lookahead-w2` | 0.76 [0.71, 0.82] | 0.33 / 0.50 / 0.59 / 0.65 / 0.69 / 0.76 | 51 | 0.93 | 0.16 |
| `bayes-lookahead-w4` | 0.69 [0.63, 0.76] | 0.33 / 0.50 / 0.56 / 0.64 / 0.70 / 0.75 | 57 | 0.92 | 0.16 |
| `bayes-lookahead-w8` | 0.58 [0.52, 0.64] | 0.33 / 0.50 / 0.59 / 0.69 / 0.74 / 0.77 | 60 | 0.89 | 0.16 |
| `bayes-optimist` | 0.95 [0.90, 0.97] | 0.33 / 0.49 / 0.54 / 0.59 / 0.64 / 0.70 | 66 | 0.94 | 0.20 |
| `claude-cli:claude-fable-5-2@high` | 0.94 [0.89, 0.96] | 0.33 / 0.45 / 0.53 / 0.59 / 0.66 / 0.71 | 32 | 0.97 | 0.20 |
| `claude-cli:claude-fable-5-2@high#r2` | 0.94 [0.89, 0.97] | 0.33 / 0.47 / 0.54 / 0.60 / 0.65 / 0.71 | 32 | 0.98 | 0.20 |
| `bayes` | 1.00 [1.00, 1.00] | 0.33 / 0.42 / 0.49 / 0.56 / 0.61 / 0.66 | 0 | 1.00 | 0.23 |
| `bayes-nolearn` | 0.12 [0.05, 0.19] | 0.33 / 0.42 / 0.48 / 0.55 / 0.62 / 0.66 | 23 | 1.04 | 0.28 |
| `claude-cli:claude-opus-5-5@high#r3` | 0.56 [0.36, 0.71] | 0.33 / 0.50 / 0.58 / 0.64 / 0.70 / 0.79 | 71 | 0.77 | 0.25 |
| `bayes-mean` | 0.04 [-0.00, 0.07] | 0.33 / 0.49 / 0.60 / 0.71 / 0.78 / 0.83 | 70 | 0.77 | 0.01 |
| `claude-cli:claude-opus-5-5@high` | 0.44 [0.33, 0.55] | 0.33 / 0.49 / 0.58 / 0.66 / 0.71 / 0.79 | 69 | 0.75 | 0.23 |
| `bayes-thompson` | 0.85 [0.75, 0.91] | 0.33 / 0.43 / 0.45 / 0.50 / 0.57 / 0.60 | 26 | 1.02 | 0.28 |
| `claude-cli:claude-opus-5-5@high#r2` | 0.45 [0.25, 0.61] | 0.33 / 0.48 / 0.61 / 0.66 / 0.76 / 0.81 | 73 | 0.75 | 0.24 |
| `bayes-noflow` | 0.08 [0.01, 0.15] | 0.33 / 0.39 / 0.45 / 0.52 / 0.56 / 0.62 | 15 | 1.12 | 0.32 |
| `claude-cli:claude-haiku-5-5@high` | 0.47 [0.24, 0.62] | 0.33 / 0.48 / 0.55 / 0.61 / 0.65 / 0.70 | 38 | 0.90 | 0.24 |
| `bayes-fixed-high` | 0.25 [0.06, 0.38] | 0.33 / 0.35 / 0.40 / 0.42 / 0.44 / 0.46 | 0 | 1.46 | 0.41 |
| `claude-cli:claude-opus-5-5@low` | 0.08 [0.05, 0.11] | 0.33 / 0.53 / 0.68 / 0.76 / 0.85 / 0.89 | 96 | 0.50 | 0.35 |
| `glosten-milgrom` | 1.23 [1.18, 1.29] | 0.33 / 0.56 / 0.69 / 0.79 / 0.85 / 0.88 | 100 | 0.63 | 0.31 |
| `bayes-fixed-low` | 0.01 [-0.01, 0.02] | 0.33 / 0.54 / 0.64 / 0.69 / 0.79 / 0.84 | 93 | 0.59 | 0.49 |
| `static` | -0.00 [-0.00, -0.00] | 0.33 / 0.42 / 0.54 / 0.63 / 0.69 / 0.74 | 28 | 1.03 | 1.10 |
| `claude-cli:claude-sonnet-5-5@high` | 0.08 [-0.01, 0.16] | 0.33 / 0.49 / 0.61 / 0.70 / 0.77 / 0.84 | 68 | 0.64 | 0.48 |
| `random` | -0.01 [-0.04, 0.03] | 0.33 / 0.47 / 0.59 / 0.68 / 0.75 / 0.79 | 79 | 0.56 | 1.42 |

## Run-to-run variability

| setup | runs | pooled scores | run SD |
| --- | ---: | ---: | ---: |
| `claude-cli:claude-fable-5-2@high` | 2 | 86.5, 86.0 | 0.32 |
| `claude-cli:claude-opus-5-5@high` | 3 | 64.6, 60.5, 68.2 | 3.83 |

| pair | gap | pooled run SD | Welch t (df) | p |
| --- | ---: | ---: | ---: | ---: |
| `claude-cli:claude-fable-5-2@high` - `claude-cli:claude-opus-5-5@high` | +21.8 | 2.72 | 9.81 (2.0) | 0.010 |

## Pre-registered tests

Families as in `docs/prereg-core-v2.md`; p-values Holm-adjusted within each family. Paired tests are sign flips of per-session differences of run-averaged values.

Family A (separation)

| test | value | p | p (Holm) |
| --- | ---: | ---: | ---: |
| claude-cli:claude-fable-5-2@high vs claude-cli:claude-haiku-5-5@high, pooled | - | <0.001 | 0.002 |
| claude-cli:claude-fable-5-2@high vs claude-cli:claude-opus-5-5@high, pooled | - | <0.001 | 0.002 |
| claude-cli:claude-fable-5-2@high vs claude-cli:claude-opus-5-5@low, pooled | - | <0.001 | 0.002 |
| claude-cli:claude-fable-5-2@high vs claude-cli:claude-sonnet-5-5@high, pooled | - | <0.001 | 0.002 |
| claude-cli:claude-haiku-5-5@high vs claude-cli:claude-opus-5-5@high, pooled | - | 0.044 | 0.088 |
| claude-cli:claude-haiku-5-5@high vs claude-cli:claude-opus-5-5@low, pooled | - | <0.001 | 0.002 |
| claude-cli:claude-haiku-5-5@high vs claude-cli:claude-sonnet-5-5@high, pooled | - | <0.001 | 0.002 |
| claude-cli:claude-opus-5-5@high vs claude-cli:claude-opus-5-5@low, pooled | - | <0.001 | 0.002 |
| claude-cli:claude-opus-5-5@high vs claude-cli:claude-sonnet-5-5@high, pooled | - | <0.001 | 0.002 |
| claude-cli:claude-opus-5-5@low vs claude-cli:claude-sonnet-5-5@high, pooled | - | 0.095 | 0.095 |

Family B (learning and probing)

| test | value | p | p (Holm) |
| --- | ---: | ---: | ---: |
| claude-cli:claude-fable-5-2@high: learning response > 0 | 0.9 | <0.001 | <0.001 |
| claude-cli:claude-fable-5-2@high > bayes-nolearn, mixed tier | - | 0.004 | 0.041 |
| claude-cli:claude-fable-5-2@high > bayes, mixed tier | - | 0.043 | 0.400 |
| claude-cli:claude-haiku-5-5@high: learning response > 0 | 0.5 | <0.001 | <0.001 |
| claude-cli:claude-haiku-5-5@high > bayes-nolearn, mixed tier | - | 0.835 | 1.000 |
| claude-cli:claude-haiku-5-5@high > bayes, mixed tier | - | 0.963 | 1.000 |
| claude-cli:claude-opus-5-5@high: learning response > 0 | 0.4 | <0.001 | <0.001 |
| claude-cli:claude-opus-5-5@high > bayes-nolearn, mixed tier | - | 0.600 | 1.000 |
| claude-cli:claude-opus-5-5@high > bayes, mixed tier | - | 0.841 | 1.000 |
| claude-cli:claude-opus-5-5@low: learning response > 0 | 0.1 | <0.001 | <0.001 |
| claude-cli:claude-opus-5-5@low > bayes-nolearn, mixed tier | - | 0.995 | 1.000 |
| claude-cli:claude-opus-5-5@low > bayes, mixed tier | - | 0.999 | 1.000 |
| claude-cli:claude-sonnet-5-5@high: learning response > 0 | 0.1 | 0.040 | 0.400 |
| claude-cli:claude-sonnet-5-5@high > bayes-nolearn, mixed tier | - | 1.000 | 1.000 |
| claude-cli:claude-sonnet-5-5@high > bayes, mixed tier | - | 1.000 | 1.000 |

Family C (gradient and effort)

| test | value | p | p (Holm) |
| --- | ---: | ---: | ---: |
| claude-cli:claude-fable-5-2@high: open share > mixed share | 5.9 | 0.068 | 0.340 |
| claude-cli:claude-opus-5-5@high: open share > mixed share | 17.2 | 0.100 | 0.398 |
| claude-cli:claude-opus-5-5@high > claude-cli:claude-opus-5-5@low, pooled | - | <0.001 | <0.001 |
| claude-cli:claude-haiku-5-5@high: open share > mixed share | 6.6 | 0.339 | 0.677 |
| claude-cli:claude-opus-5-5@low: open share > mixed share | 12.3 | 0.378 | 0.677 |
| claude-cli:claude-sonnet-5-5@high: open share > mixed share | 40.8 | 0.200 | 0.600 |
