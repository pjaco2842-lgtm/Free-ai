# Independent open-entry research audit

Experimental research only; **no strategy is approved or installed**.

Signal features use only completed prior bars; enter one contract at the next daily-bar open. 12 features × 5 thresholds × 2 comparisons × 2 sides × 5 stops × 5 exits = 6,000 configurations per market, 30,000 total. No filters are tuned using the open. Signals may be duplicates or overlap.

For each market, select the highest training dollars/trade among rules with at least 150 2009–2019 trades, without inspecting later returns. Then evaluate that one frozen rule in 2020–2024 and 2025 onward. **Those periods have already been mined in this project and are not an independent holdout**. Random-side comparison is conditional on the same pre-open selected days and identical stop, exit and costs, 500 draws; it is not a multiple-testing-corrected proof.

Entry is approximated at the daily open with one tick of entry and exit slippage, plus published per-side commissions. Stops round up and targets down to the tick. If both are touched, the stop wins. Stops assume no gap through the stop. Dollar outcomes use micro specifications except NKD, which is a full contract. Yahoo =F is a continuous proxy, not GCZ2026/ESZ2026/NQZ2026/CLZ2026/NKDZ2026 actual fills; roll adjustments, liquidity, session timestamps, holidays and executable open fills remain unverified. Exclude incomplete sessions. Do not use as a paper fill engine.

## ES=F (MES)

- Data: 4486 completed bars, 2009-01-02 through 2026-10-30; SHA-256 of fetched OHLCV 62d8462dc73e765bffba5667463953b7ca814819e6dc3988506f3a49232a3514.
- 6,000 candidate configurations; 5,150 satisfy the training sample minimum.
- Frozen training choice: prior_return_2 < -1; long; stop 1.5 ATR; exit 1.0R.
| period | trades | win | net | per trade |
|---|---:|---:|---:|---:|
| Train 2009–2019 | 317 | 55.2% | $+4,413.75 | $+13.92 |
| Reused 2020–2024 | 161 | 50.3% | $-81.10 | $-0.50 |
| Reused 2025+ | 52 | 57.7% | $+4,340.15 | $+83.46 |
- 2020–2024 random-side Monte Carlo p-value: 0.475 (unadjusted, 161 selected days; not a probability of profitability).
- Illustrative 2023+ close-only account walk from every market session: 784 pass, 34 breach, 146 unfinished of 964 overlapping starts; 0 within 3 sessions; median completed-pass time 309.5 sessions. Intraday breaches and fill uncertainty omitted; not a pass forecast.

## NQ=F (MNQ)

- Data: 4486 completed bars, 2009-01-02 through 2026-10-30; SHA-256 of fetched OHLCV bf5cc89e8756f796f70311aed64014d977cb5b444a5d989533ac37887d36460d.
- 6,000 candidate configurations; 5,150 satisfy the training sample minimum.
- Frozen training choice: prior_return_2 < -1; long; stop 1 ATR; exit 2.0R.
| period | trades | win | net | per trade |
|---|---:|---:|---:|---:|
| Train 2009–2019 | 308 | 58.1% | $+4,830.56 | $+15.68 |
| Reused 2020–2024 | 158 | 52.5% | $+3,373.08 | $+21.35 |
| Reused 2025+ | 56 | 51.8% | $+4,198.20 | $+74.97 |
- 2020–2024 random-side Monte Carlo p-value: 0.202 (unadjusted, 158 selected days; not a probability of profitability).
- Illustrative 2023+ close-only account walk from every market session: 248 pass, 664 breach, 52 unfinished of 964 overlapping starts; 0 within 3 sessions; median completed-pass time 97.5 sessions. Intraday breaches and fill uncertainty omitted; not a pass forecast.

## GC=F (MGC)

- Data: 4485 completed bars, 2009-01-02 through 2026-10-30; SHA-256 of fetched OHLCV ab55d4a7e5c86aa439a7d21d9da4cbda9374cc4955bccf01e2fd79954b0e011e.
- 6,000 candidate configurations; 5,300 satisfy the training sample minimum.
- Frozen training choice: prior_body_vs_prev > 0.5; short; stop 0.25 ATR; exit close.
| period | trades | win | net | per trade |
|---|---:|---:|---:|---:|
| Train 2009–2019 | 767 | 38.5% | $+10,789.79 | $+14.07 |
| Reused 2020–2024 | 346 | 28.6% | $-1,518.60 | $-4.39 |
| Reused 2025+ | 129 | 30.2% | $-612.39 | $-4.75 |
- 2020–2024 random-side Monte Carlo p-value: 0.611 (unadjusted, 346 selected days; not a probability of profitability).
- Illustrative 2023+ close-only account walk from every market session: 145 pass, 797 breach, 22 unfinished of 964 overlapping starts; 0 within 3 sessions; median completed-pass time 75.0 sessions. Intraday breaches and fill uncertainty omitted; not a pass forecast.

## CL=F (MCL)

- Data: 4485 completed bars, 2009-01-02 through 2026-10-30; SHA-256 of fetched OHLCV 0b078bc032880ab2c05dd6828f3b420704181a69dabf8fa3303d72f6f7d7c3de.
- 6,000 candidate configurations; 5,000 satisfy the training sample minimum.
- Frozen training choice: prior_body_atr < -0.5; long; stop 1.5 ATR; exit 2.0R.
| period | trades | win | net | per trade |
|---|---:|---:|---:|---:|
| Train 2009–2019 | 544 | 56.6% | $+6,526.01 | $+12.00 |
| Reused 2020–2024 | 251 | 47.4% | $-1,567.00 | $-6.24 |
| Reused 2025+ | 89 | 51.7% | $+33.00 | $+0.37 |
- 2020–2024 random-side Monte Carlo p-value: 0.645 (unadjusted, 251 selected days; not a probability of profitability).
- Illustrative 2023+ close-only account walk from every market session: 220 pass, 631 breach, 112 unfinished of 963 overlapping starts; 0 within 3 sessions; median completed-pass time 278.5 sessions. Intraday breaches and fill uncertainty omitted; not a pass forecast.

## NKD=F (NKD)

- Data: 4485 completed bars, 2009-01-02 through 2026-10-30; SHA-256 of fetched OHLCV 3682ecf3cd0dbbf2706e7b46280d01722ddbdc7112ea574058f9a4722d7a2f65.
- 6,000 candidate configurations; 5,150 satisfy the training sample minimum.
- Frozen training choice: prior_upper_wick > 0.5; long; stop 1.5 ATR; exit close.
| period | trades | win | net | per trade |
|---|---:|---:|---:|---:|
| Train 2009–2019 | 188 | 49.5% | $+8,267.00 | $+43.97 |
| Reused 2020–2024 | 116 | 51.7% | $+9,269.00 | $+79.91 |
| Reused 2025+ | 43 | 48.8% | $+26,874.50 | $+624.99 |
- 2020–2024 random-side Monte Carlo p-value: 0.226 (unadjusted, 116 selected days; not a probability of profitability).
- Illustrative 2023+ close-only account walk from every market session: 244 pass, 662 breach, 58 unfinished of 964 overlapping starts; 0 within 3 sessions; median completed-pass time 92.5 sessions. Intraday breaches and fill uncertainty omitted; not a pass forecast.
