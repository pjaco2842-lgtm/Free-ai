# Aggressive sizing: which attempts win accounts and which burn them

Every configuration from the wide sweep, scored on **evaluation outcome** over rolling 20-session windows from 2023-01-01 onward, at 1, 2 and 3 micros. Floor follows the closing high-water mark; the 40% consistency rule must hold when the target is hit; first event — +$1,250 or breach — decides the attempt. A size is only counted if one stop costs under 90% of the buffer.

**57,712 rule/size combinations evaluated.**

| sym | rule | gap/trend/day | bracket | size | stop $ | pass | reached target | blow | **net** |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| ES=F | limit_low_long:1 | any/trend/all | 0.25 ATR tp3 | x2 | $236 | 17.7% | 17.9% | 4.3% | **+13.3%** |
| ES=F | limit_low_long:1 | any/trend/all | 0.25 ATR tp4 | x2 | $236 | 17.1% | 17.1% | 4.3% | **+12.8%** |
| ES=F | limit_low_long:1 | any/trend/all | 0.25 ATR tp25 | x2 | $236 | 16.4% | 16.5% | 4.3% | **+12.1%** |
| ES=F | limit_low_long:1 | any/trend/all | 0.25 ATR tp25 | x3 | $354 | 23.9% | 24.0% | 13.8% | **+10.2%** |
| ES=F | limit_low_long:2 | any/trend/all | 0.25 ATR tp25 | x3 | $354 | 16.3% | 16.3% | 6.2% | **+10.1%** |
| ES=F | limit_low_long:2 | any/trend/all | 0.25 ATR tp3 | x2 | $236 | 11.7% | 11.7% | 1.8% | **+9.9%** |
| ES=F | limit_low_long:2 | any/trend/all | 0.25 ATR tp3 | x3 | $354 | 15.9% | 15.9% | 6.1% | **+9.7%** |
| ES=F | limit_low_long:1 | any/trend/all | 0.25 ATR tp2 | x3 | $354 | 23.4% | 23.4% | 13.9% | **+9.5%** |
| ES=F | limit_low_long:2 | any/trend/all | 0.25 ATR tp4 | x2 | $236 | 11.3% | 11.3% | 1.8% | **+9.5%** |
| ES=F | limit_low_long:1 | any/trend/all | 0.25 ATR tp2 | x2 | $236 | 13.1% | 13.1% | 4.3% | **+8.8%** |
| ES=F | limit_low_long:2 | any/trend/all | 0.25 ATR tp25 | x2 | $236 | 10.6% | 10.6% | 1.8% | **+8.8%** |
| ES=F | limit_low_long:2 | any/trend/all | 0.25 ATR tp2 | x3 | $354 | 14.6% | 14.6% | 6.5% | **+8.1%** |
| NQ=F | limit_low_long:2 | any/trend/all | 0.25 ATR tp3 | x1 | $340 | 10.6% | 10.6% | 2.5% | **+8.0%** |
| ES=F | limit_low_long:3 | any/trend/all | 0.25 ATR tp25 | x2 | $236 | 8.8% | 8.8% | 0.7% | **+8.0%** |

## The headline

- best net score: **+13.3 points** — ES=F limit_low_long:1 any/trend/all 0.25 ATR tp3 at x2 (pass 17.7%, blow 4.3%)
- combinations with net > 0 (win more accounts than they burn): **1,527 of 57,712**
- the 'reached target' column is the tell: where it is far above 'pass', the 40% consistency rule — not the dollars — is refusing the pass.

| size | combinations with net > 0 | best net at that size |
|---:|---:|---:|
| x1 | 987 | +8.0% |
| x2 | 342 | +13.3% |
| x3 | 198 | +10.2% |

_Net is accounts won minus accounts lost per attempt. A positive net is the only version of 'we win more than we lose' that survives arithmetic; a negative one means every additional account bought with size is a donation._

