# Can we pass in 4 sessions?

Every historical 4-session window from 2023-01-01 onward, walked day by day with the trailing floor and the 40% consistency rule enforced. Target +$1,250. One contract set per row; `x2` means two micros on the same signal.

| rule | size | windows | pass | breach | neither | median | p95 | best |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ES prior-low 0.5 ATR tp2 (the book) | x1 | 961 | **0.00%** | 0.0% | 100.0% | $+19 | $+508 | $+1,377 |
| ES prior-low 0.5 ATR tp2 (the book) | x2 | 961 | **0.00%** | 0.9% | 99.1% | $+36 | $+1,016 | $+2,753 |
| NQ prior-low 0.25 ATR tp4 (sweep's best) | x1 | 961 | **0.10%** | 0.2% | 99.7% | $+66 | $+904 | $+2,478 |
| NQ prior-low 0.25 ATR tp4 (sweep's best) | x2 | 961 | **0.10%** | 4.1% | 95.8% | $+108 | $+1,787 | $+4,955 |
| NQ prior-low 0.5 ATR tp2 (sanity) | x1 | 961 | **0.10%** | 1.6% | 98.3% | $+20 | $+856 | $+2,478 |
| NQ prior-low 0.5 ATR tp2 (sanity) | x2 | 961 | **0.10%** | 12.9% | 87.0% | $+13 | $+1,711 | $+4,955 |

## What four sessions can actually deliver

The dollars a window reaches at each probability, so the gap between the target and the account is visible rather than argued about:

| rule | size | 50% of windows reach | 25% | 10% | 5% | best ever |
|---|---:|---:|---:|---:|---:|---:|
| ES prior-low 0.5 ATR tp2 (the book) | x1 | $+19 | $+169 | $+348 | $+508 | $+1,377 |
| ES prior-low 0.5 ATR tp2 (the book) | x2 | $+36 | $+338 | $+695 | $+1,016 | $+2,753 |
| NQ prior-low 0.25 ATR tp4 (sweep's best) | x1 | $+66 | $+369 | $+670 | $+904 | $+2,478 |
| NQ prior-low 0.25 ATR tp4 (sweep's best) | x2 | $+108 | $+730 | $+1,305 | $+1,787 | $+4,955 |
| NQ prior-low 0.5 ATR tp2 (sanity) | x1 | $+20 | $+340 | $+618 | $+856 | $+2,478 |
| NQ prior-low 0.5 ATR tp2 (sanity) | x2 | $+13 | $+663 | $+1,226 | $+1,711 | $+4,955 |

## Reading it

Best pass rate found: **NQ prior-low 0.25 ATR tp4 (sweep's best) at x1 — 0.10% of four-session windows**, against 0.2% breaching the floor.

Median window moves $+66; the 95th percentile moves $+904; the best window in 961 ever recorded moved $+2,478. The target is $1,250.

Per session the target demands **$312.50 a session** for four sessions. The book earns about $15 a session at one micro and $30 at two. That is the whole gap: it is not a missing indicator, it is a factor of ten in dollars per session, and the two ways to close it are more size (which spends the buffer) or more time (which is the four days we do not have).

