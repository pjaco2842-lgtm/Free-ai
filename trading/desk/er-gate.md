# Predicting tomorrow's efficiency ratio, tested on this book

ER(k=10) >= 30% is called a high-efficiency session. 15 features, all from the closes before the session being predicted. Trained before 2023-01-01, judged on 2023-01-01 onward.

## Does the model predict anything?

| measure | value |
|---|---|
| training rows / test rows | 1521 / 964 |
| high-ER base rate in test | 48.7% |
| test accuracy | 79.8% |
| test AUC | 0.863 |

AUC near 0.50 means the model cannot rank tomorrow's sessions at all; anything at 0.55 and below is not a signal worth gating on.

## Does the gate help the book? (2023 onward, causal fills, one micro)

| set | trades | $/trade | $/session |
|---|---:|---:|---:|
| every trade | 443 | $+32.24 | $+14.82 |
| predicted high ER | 212 | $+39.21 | $+8.62 |
| predicted low ER | 231 | $+25.85 | — |

| control | value |
|---|---|
| random days dropped, 400 trials | $+32.62/trade (p05 $+16.60, p95 $+45.51) |
| gate's percentile among random drops | 76th |
| p-value (random did at least as well) | 0.240 |

**Verdict: the gate is not distinguishable from dropping the same number of days at random.** Predicting the right thing is not enough; the gate has to beat luck on this book, and it does not.

