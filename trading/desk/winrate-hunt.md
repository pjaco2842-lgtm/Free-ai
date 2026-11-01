# Win rate is a dial — measured, 2026-11-01

Every setting below is one rule family swept over a 0.1R–3.0R target grid at five stops, on daily bars, costs included (commission + a tick of slippage a side), close resolution. 12000 settings scored. `need` = micros required to earn $500 in the average session at that setting; `stop share` = one stop at that size as a share of the $1000 buffer.

## The dial: ES prior-low limit, 1.0 ATR stop, target from 0.2R to 3.0R

| target | trades | win | $/trade | $/session | micros for $500 | stop share | pass@x2 | blow@x2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.1R | 1093 | 55.1% | -46.44 | -23.90 | — | — | 0.0% | 46.1% |
| 0.2R | 1093 | 55.2% | -33.75 | -16.79 | — | — | 0.7% | 39.6% |
| 0.3R | 1093 | 55.2% | -23.59 | -11.16 | — | — | 3.0% | 35.3% |
| 0.4R | 1093 | 55.2% | -15.34 | -6.49 | — | — | 4.6% | 34.4% |
| 0.5R | 1093 | 55.2% | -8.49 | -2.50 | — | — | 8.3% | 32.9% |
| 0.6R | 1093 | 55.2% | -2.95 | +0.64 | x777 | 36633% | 9.6% | 32.9% |
| 0.7R | 1093 | 55.2% | +1.43 | +3.05 | x164 | 7726% | 11.0% | 31.7% |
| 0.8R | 1093 | 55.2% | +4.84 | +5.03 | x99 | 4687% | 11.7% | 31.7% |
| 0.9R | 1093 | 55.2% | +7.43 | +6.50 | x77 | 3627% | 12.0% | 31.7% |
| 1.0R | 1093 | 55.2% | +9.45 | +7.74 | x65 | 3044% | 11.5% | 31.7% |
| 1.1R | 1093 | 55.2% | +11.06 | +8.77 | x57 | 2688% | 11.1% | 32.2% |
| 1.2R | 1093 | 55.2% | +12.21 | +9.48 | x53 | 2487% | 10.2% | 32.3% |
| 1.3R | 1093 | 55.2% | +13.10 | +10.06 | x50 | 2342% | 10.1% | 32.3% |
| 1.4R | 1093 | 55.2% | +13.72 | +10.43 | x48 | 2260% | 9.8% | 32.3% |
| 1.5R | 1093 | 55.2% | +14.18 | +10.71 | x47 | 2201% | 9.8% | 32.3% |
| 1.6R | 1093 | 55.2% | +14.52 | +10.95 | x46 | 2152% | 9.4% | 32.3% |
| 1.7R | 1093 | 55.2% | +14.79 | +11.17 | x45 | 2109% | 9.4% | 32.3% |
| 1.8R | 1093 | 55.2% | +14.98 | +11.32 | x44 | 2082% | 9.4% | 32.3% |
| 1.9R | 1093 | 55.2% | +15.12 | +11.43 | x44 | 2062% | 9.4% | 32.3% |
| 2.0R | 1093 | 55.2% | +15.24 | +11.53 | x43 | 2045% | 9.4% | 32.3% |
| 2.1R | 1093 | 55.2% | +15.35 | +11.62 | x43 | 2028% | 9.4% | 32.3% |
| 2.2R | 1093 | 55.2% | +15.46 | +11.72 | x43 | 2011% | 9.4% | 32.3% |
| 2.3R | 1093 | 55.2% | +15.56 | +11.82 | x42 | 1994% | 9.4% | 32.3% |
| 2.4R | 1093 | 55.2% | +15.67 | +11.91 | x42 | 1978% | 9.4% | 32.3% |
| 2.5R | 1093 | 55.2% | +15.75 | +12.01 | x42 | 1962% | 9.4% | 32.3% |
| 2.6R | 1093 | 55.2% | +15.84 | +12.11 | x41 | 1946% | 9.4% | 32.3% |
| 2.7R | 1093 | 55.2% | +15.93 | +12.21 | x41 | 1931% | 9.4% | 32.3% |
| 2.8R | 1093 | 55.2% | +16.01 | +12.30 | x41 | 1916% | 9.4% | 32.3% |
| 2.9R | 1093 | 55.2% | +16.10 | +12.40 | x40 | 1901% | 9.4% | 32.3% |
| 3.0R | 1093 | 55.2% | +16.13 | +12.44 | x40 | 1894% | 9.4% | 32.3% |

## Highest win rate in the whole sweep

Ignoring money entirely, this is as high as the win rate goes.

**CL=F open_gap lb1 gap=any, 1.0 ATR stop, 0.1R target** — 1319 trades, **82.8% win rate**, $-16.80/trade, $-12.00/session.
It cannot earn $500 in a session at any size: the average session is zero or negative.
Traded at that required size over 944 rolling 20-session windows: pass 0.0%, blow 6.7%, reached target 0.0%, **net -6.7**.
At the honest x2: pass 1.7%, blow 30.5%, net -28.8.

## Highest win rate that still makes money

The dial turned as far as it goes without the dollars turning negative.

**NQ=F open_gap lb1 gap=any, 2.0 ATR stop, 0.1R target** — 1273 trades, **78.5% win rate**, $+14.08/trade, $+13.93/session.
To earn $500 in the average session: **x36 micros**, whose single stop is **9766%** of the $1000 buffer — one losing trade ends the account.
Traded at that required size over 945 rolling 20-session windows: pass 50.3%, blow 49.4%, reached target 75.1%, **net +0.8**.
At the honest x2: pass 39.3%, blow 37.8%, net +1.5.

## Highest win rate at or above 70% that still makes money

The ask, taken literally: 70%+ and positive expectancy.

**NQ=F open_gap lb1 gap=any, 2.0 ATR stop, 0.1R target** — 1273 trades, **78.5% win rate**, $+14.08/trade, $+13.93/session.
To earn $500 in the average session: **x36 micros**, whose single stop is **9766%** of the $1000 buffer — one losing trade ends the account.
Traded at that required size over 945 rolling 20-session windows: pass 50.3%, blow 49.4%, reached target 75.1%, **net +0.8**.
At the honest x2: pass 39.3%, blow 37.8%, net +1.5.

## ...and the best of those that the $1,000 buffer can actually carry

Same, restricted to settings whose required size does not risk the whole buffer on one stop.

