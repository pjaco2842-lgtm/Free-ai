# Aggressive sizing: which attempts win accounts and which burn them

Every configuration from the wide sweep, scored on **evaluation outcome** over rolling 20-session windows from 2023-01-01 onward, at 1, 2 and 3 micros. Floor follows the closing high-water mark; the 40% consistency rule must hold when the target is hit; first event — +$1,250 or breach — decides the attempt. A size is only counted if one stop costs under 90% of the buffer.

**37,264 rule/size combinations evaluated.**

| sym | rule | gap/trend/day | bracket | size | stop $ | pass | reached target | blow | **net** |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| ES=F | limit_low_long:1 | any/trend/all | 0.5 ATR tp2 | x1 | $236 | 6.2% | 6.2% | 0.0% | **+6.2%** |
| ES=F | limit_low_long:1 | any/trend/all | 0.5 ATR tp25 | x1 | $236 | 6.0% | 6.0% | 0.0% | **+6.0%** |
| ES=F | limit_low_long:2 | any/trend/all | 0.5 ATR tp2 | x1 | $236 | 5.1% | 5.1% | 0.0% | **+5.1%** |
| ES=F | limit_low_long:1 | against/trend/all | 0.5 ATR tp2 | x1 | $236 | 4.9% | 4.9% | 0.0% | **+4.9%** |
| ES=F | limit_low_long:2 | against/trend/all | 0.5 ATR tp25 | x1 | $236 | 4.9% | 4.9% | 0.0% | **+4.9%** |
| ES=F | limit_low_long:1 | any/trend/all | 0.5 ATR tp15 | x1 | $236 | 4.8% | 4.8% | 0.0% | **+4.8%** |
| ES=F | limit_low_long:1 | any/trend/all | 0.5 ATR tp3 | x1 | $236 | 4.8% | 4.8% | 0.0% | **+4.8%** |
| ES=F | limit_low_long:2 | against/trend/all | 0.5 ATR tp2 | x1 | $236 | 4.8% | 4.8% | 0.0% | **+4.8%** |
| ES=F | limit_low_long:1 | any/trend/all | 0.5 ATR tp4 | x1 | $236 | 4.7% | 4.7% | 0.0% | **+4.7%** |
| ES=F | limit_low_long:1 | against/trend/all | 0.5 ATR tp25 | x1 | $236 | 4.7% | 4.7% | 0.0% | **+4.7%** |
| ES=F | limit_low_long:2 | any/trend/all | 0.5 ATR tp25 | x1 | $236 | 4.7% | 4.7% | 0.0% | **+4.7%** |
| ES=F | limit_low_long:1 | against/trend/all | 0.5 ATR tp15 | x1 | $236 | 4.6% | 4.6% | 0.0% | **+4.6%** |

## The headline

- best net score: **+6.2 points** — ES=F limit_low_long:1 any/trend/all 0.5 ATR tp2 at x1 (pass 6.2%, blow 0.0%)
- combinations with net > 0 (win more accounts than they burn): **792 of 37,264**
- the 'reached target' column is the tell: where it is far above 'pass', the 40% consistency rule — not the dollars — is refusing the pass.

| size | combinations with net > 0 | best net at that size |
|---:|---:|---:|
| x1 | 683 | +6.2% |
| x2 | 94 | +2.3% |
| x3 | 15 | +0.3% |

_Net is accounts won minus accounts lost per attempt. A positive net is the only version of 'we win more than we lose' that survives arithmetic; a negative one means every additional account bought with size is a donation._

