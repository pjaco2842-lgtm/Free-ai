# Order flow on 5-minute ES bars — and the power to say anything

13,389 bars across **58 sessions**. Costs: commission plus 2 ticks of slippage per side. Stop 1.0 ATR(5m), exit after a fixed horizon.

**Read this first.** The trade counts look large but the independent unit is the session, and there are only **58** of them: these rules fire repeatedly inside a session, so consecutive trades share the same bars and the same regime. That is why the t-stats below run to -20 while the alpha column sits near zero — the t is inflated by overlap, and the honest sample is 58 sessions, not 3,000 trades. Nothing here can prove an edge; it can only fail to find an obvious one.

| rule | horizon | trades | win | $/trade | null $/trade | alpha | t |
|---|---:|---:|---:|---:|---:|---:|---:|
| delta push + above VWAP (long) | 3 bars | 2969 | 29% | $-7.64 | $-7.47 | **$-0.17** | -19.22 |
| delta push + above VWAP (long) | 6 bars | 2969 | 28% | $-7.64 | $-7.36 | **$-0.27** | -15.06 |
| delta push + above VWAP (long) | 12 bars | 2969 | 24% | $-8.72 | $-7.81 | **$-0.91** | -14.88 |
| delta fade + below VWAP (short) | 3 bars | 2271 | 31% | $-7.67 | $-7.24 | **$-0.42** | -12.25 |
| delta fade + below VWAP (short) | 6 bars | 2270 | 29% | $-8.04 | $-6.97 | **$-1.08** | -10.70 |
| delta fade + below VWAP (short) | 12 bars | 2267 | 24% | $-8.86 | $-7.06 | **$-1.80** | -10.50 |
| cum delta extreme long | 3 bars | 6170 | 29% | $-7.51 | $-7.44 | **$-0.08** | -26.44 |
| cum delta extreme long | 6 bars | 6170 | 28% | $-7.49 | $-7.36 | **$-0.13** | -20.87 |
| cum delta extreme long | 12 bars | 6170 | 24% | $-8.31 | $-7.78 | **$-0.53** | -19.15 |
| cum delta extreme short | 3 bars | 4721 | 31% | $-7.71 | $-7.23 | **$-0.48** | -20.15 |
| cum delta extreme short | 6 bars | 4718 | 30% | $-7.80 | $-6.99 | **$-0.81** | -16.32 |
| cum delta extreme short | 12 bars | 4712 | 24% | $-8.35 | $-7.22 | **$-1.13** | -13.97 |

12 rule/horizon combinations had at least 30 trades. Every one loses roughly the round-trip cost, and every random-entry control loses almost exactly the same amount: the alpha column is between -$0.08 and -$1.80 a trade. That is the answer to the question asked — order-flow proxies built from 5-minute bars are indistinguishable from random entries — and it matches this desk's earlier finding that its intraday book lost about $6.65 a trade to friction. It is not an answer to whether order flow works: that needs tick data and a 10,000-hour eye, which is what the video's author had and still could not automate.

