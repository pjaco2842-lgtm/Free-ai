# The ATR grid on a 25K

Generated 2026-10-31T04:18Z · $25,000 start · $24,000 opening floor, trailing the highest close and locking at $25,100 · +$1,250 target · consistency ≤ 40% · one micro contract · trade record 2023-01-01 onward

The question was whether a wider stop buys a higher win rate, and whether that buys a
higher chance of passing. The first half is mechanically true — a 2.5 ATR stop is hit
far less often than a 0.75 ATR stop, so the win rate rises — and the second half is
where it breaks: on a 25K the buffer is $1,000, and one micro of NQ at 1.0 ATR risks
about $1,060 today, so a wider stop does not buy a higher chance of passing, it buys a
larger share of the account lost when the rule is wrong.

## The stop axis

| stop | median risk | win% | $/trade | trades stopped | pass% | breach% |
|---|---|---|---|---|---|---|
| 0.5A | $343 | 43% | $-21 | 39% | 25% | 75% |
| 0.75A | $514 | 50% | $+14 | 18% | 41% | 58% |
| 1A | $686 | 54% | $+29 | 8% | 52% | 47% |
| 1.5A | $1,028 | 52% | $+31 | 2% | 57% | 42% |
| 2A | $1,371 | 52% | $+31 | 0% | 57% | 42% |
| 2.5A | $1,714 | 52% | $+31 | 0% | 56% | 43% |

## Every line

`fits?` is the line's median session risk against the $1,000 buffer: `yes` at half of
it or less, `tight` inside it, `no` beyond it. `pass%` reaches +$1,250 from every
starting trade; `cons%` is the share that also keeps the best day under 40% of the
profit.

| line | trades | win | $/trade | net | risk | fits? | pass% | cons% | breach% | days → pass |
|---|---|---|---|---|---|---|---|---|---|---|
| ES nday-fade-5 0.5A tp1 | 525 | 60% | $+33 | $+17,211 | $206 | yes | 81% | 80% | 13% | 36 |
| ES nday-fade-5 0.75A tp1 | 525 | 57% | $+33 | $+17,159 | $309 | yes | 78% | 78% | 19% | 26 |
| ES nr-break-2 1A tp1 | 371 | 58% | $+41 | $+15,291 | $412 | yes | 83% | 77% | 13% | 23 |
| ES nr-break-2 2.5A tp1 | 371 | 59% | $+51 | $+18,843 | $1,030 | no | 87% | 75% | 9% | 22 |
| ES nr-break-2 1.5A tp1 | 371 | 59% | $+50 | $+18,421 | $618 | tight | 87% | 70% | 9% | 21 |
| ES nr-break-2 2A tp1 | 371 | 59% | $+52 | $+19,451 | $824 | tight | 87% | 68% | 9% | 21 |
| ES nr-break-2 1.5A tp2 | 371 | 59% | $+50 | $+18,618 | $618 | tight | 87% | 67% | 9% | 22 |
| ES nday-break-1 1.5A tp1 | 740 | 55% | $+28 | $+21,016 | $610 | tight | 80% | 66% | 18% | 29 |
| ES nday-fade-5 0.5A tp2 | 525 | 50% | $+18 | $+9,451 | $206 | yes | 68% | 65% | 28% | 38 |
| ES nr-break-2 2.5A tp2 | 371 | 59% | $+52 | $+19,297 | $1,030 | no | 87% | 65% | 9% | 21 |
| ES nr-break-2 2A close | 371 | 59% | $+52 | $+19,165 | $824 | tight | 87% | 65% | 9% | 21 |
| ES nr-break-2 2.5A close | 371 | 59% | $+52 | $+19,165 | $1,030 | no | 87% | 65% | 9% | 21 |
| ES nr-break-2 2A tp2 | 371 | 59% | $+51 | $+19,102 | $824 | tight | 87% | 65% | 9% | 21 |
| ES nr-break-2 1.5A close | 371 | 59% | $+51 | $+18,875 | $618 | tight | 87% | 65% | 9% | 21 |
| ES nday-fade-5 1A tp1 | 525 | 54% | $+24 | $+12,741 | $412 | yes | 64% | 64% | 32% | 25 |
| ES nr-break-2 0.75A tp1 | 371 | 54% | $+20 | $+7,539 | $309 | yes | 61% | 61% | 34% | 27 |
| ES nr-break-2 1A tp2 | 371 | 58% | $+45 | $+16,797 | $412 | yes | 81% | 60% | 16% | 22 |
| ES nday-break-1 1A tp1 | 740 | 54% | $+17 | $+12,508 | $406 | yes | 61% | 59% | 34% | 33 |
| ES nr-break-2 1A close | 371 | 58% | $+45 | $+16,511 | $412 | yes | 81% | 56% | 16% | 22 |
| ES nday-break-1 2A tp1 | 740 | 55% | $+32 | $+23,800 | $813 | tight | 84% | 54% | 12% | 29 |
| NQ nday-fade-5 0.5A tp1 | 521 | 57% | $+50 | $+26,126 | $527 | tight | 61% | 54% | 39% | 13 |
| ES nday-break-1 2.5A tp1 | 740 | 55% | $+32 | $+23,530 | $1,016 | no | 83% | 52% | 13% | 28 |
| ES nday-break-1 1.5A tp2 | 740 | 55% | $+30 | $+22,141 | $610 | tight | 83% | 49% | 13% | 28 |
| ES nday-break-1 2A tp2 | 740 | 55% | $+32 | $+23,550 | $813 | tight | 83% | 49% | 13% | 28 |
| ES nday-break-1 2.5A tp2 | 740 | 55% | $+33 | $+24,104 | $1,016 | no | 83% | 49% | 13% | 28 |
| ES nday-break-1 2.5A close | 740 | 55% | $+32 | $+23,972 | $1,016 | no | 83% | 49% | 13% | 28 |
| ES nday-break-1 2A close | 740 | 55% | $+32 | $+23,613 | $813 | tight | 83% | 49% | 13% | 28 |
| ES nday-break-1 1.5A close | 740 | 55% | $+30 | $+22,378 | $610 | tight | 83% | 49% | 13% | 28 |
| NQ nr-break-2 1A tp1 | 368 | 62% | $+109 | $+40,093 | $1,054 | no | 85% | 43% | 14% | 10 |
| NQ nr-break-2 0.75A tp1 | 368 | 58% | $+64 | $+23,685 | $791 | tight | 68% | 41% | 31% | 10 |
| ES nday-break-1 1A close | 740 | 54% | $+20 | $+14,467 | $406 | yes | 65% | 41% | 31% | 29 |
| ES nday-break-1 1A tp2 | 740 | 54% | $+20 | $+14,654 | $406 | yes | 64% | 40% | 32% | 28 |
| ES nr-break-2 0.75A tp2 | 371 | 54% | $+25 | $+9,200 | $309 | yes | 61% | 37% | 35% | 23 |
| ES nr-break-2 0.75A close | 371 | 54% | $+25 | $+9,104 | $309 | yes | 57% | 37% | 40% | 24 |
| NQ prevclose-break 0.75A tp1 | 953 | 50% | $-3 | $-3,076 | $719 | tight | 42% | 30% | 58% | 10 |
| NQ nday-break-1 1A tp1 | 740 | 57% | $+62 | $+46,210 | $1,012 | no | 60% | 30% | 40% | 11 |
| NQ nday-fade-5 0.75A tp1 | 521 | 54% | $+54 | $+27,910 | $791 | tight | 46% | 29% | 54% | 7 |
| ES prevclose-break 1.5A tp1 | 944 | 48% | $-9 | $-8,891 | $601 | tight | 36% | 27% | 64% | 30 |
| ES prevclose-break 2.5A tp1 | 944 | 48% | $-9 | $-8,050 | $1,002 | no | 34% | 26% | 65% | 32 |
| ES prevclose-break 2A tp1 | 944 | 48% | $-7 | $-6,956 | $802 | tight | 36% | 26% | 64% | 31 |
| ES prevclose-break 1.5A tp2 | 944 | 48% | $-10 | $-9,551 | $601 | tight | 34% | 24% | 65% | 33 |
| NQ prevclose-break 0.5A tp1 | 953 | 48% | $-16 | $-15,694 | $480 | yes | 26% | 24% | 74% | 11 |
| NQ nr-break-2 1.5A tp1 | 368 | 62% | $+117 | $+43,186 | $1,581 | no | 89% | 23% | 10% | 10 |
| NQ nr-break-2 2A tp1 | 368 | 62% | $+125 | $+46,164 | $2,108 | no | 90% | 23% | 10% | 10 |
| NQ nr-break-2 2A close | 368 | 62% | $+125 | $+45,841 | $2,108 | no | 90% | 23% | 10% | 10 |
| NQ nr-break-2 2A tp2 | 368 | 62% | $+125 | $+45,841 | $2,108 | no | 90% | 23% | 10% | 10 |
| NQ nr-break-2 2.5A close | 368 | 62% | $+125 | $+45,841 | $2,635 | no | 90% | 23% | 10% | 10 |
| NQ nr-break-2 2.5A tp2 | 368 | 62% | $+125 | $+45,841 | $2,635 | no | 90% | 23% | 10% | 10 |
| NQ nr-break-2 2.5A tp1 | 368 | 62% | $+124 | $+45,613 | $2,635 | no | 90% | 23% | 10% | 10 |
| NQ nr-break-2 1.5A tp2 | 368 | 62% | $+124 | $+45,514 | $1,581 | no | 89% | 23% | 10% | 10 |
| NQ nr-break-2 1.5A close | 368 | 62% | $+123 | $+45,192 | $1,581 | no | 89% | 23% | 10% | 10 |
| ES prevclose-break 1.5A close | 944 | 48% | $-10 | $-9,430 | $601 | tight | 34% | 23% | 66% | 34 |
| ES prevclose-break 2A close | 944 | 48% | $-7 | $-7,027 | $802 | tight | 34% | 23% | 65% | 32 |
| ES prevclose-break 2A tp2 | 944 | 48% | $-8 | $-7,153 | $802 | tight | 34% | 23% | 65% | 32 |
| ES prevclose-break 2.5A tp2 | 944 | 48% | $-8 | $-7,567 | $1,002 | no | 34% | 23% | 65% | 32 |
| ES prevclose-break 2.5A close | 944 | 48% | $-8 | $-7,636 | $1,002 | no | 34% | 23% | 65% | 32 |
| NQ nday-break-1 0.75A tp1 | 740 | 53% | $+18 | $+13,322 | $759 | tight | 38% | 23% | 62% | 9 |
| NQ nr-break-2 1A tp2 | 368 | 62% | $+122 | $+44,983 | $1,054 | no | 85% | 23% | 14% | 10 |
| NQ nr-break-2 1A close | 368 | 62% | $+121 | $+44,660 | $1,054 | no | 85% | 23% | 14% | 10 |
| NQ nday-break-1 2.5A tp1 | 740 | 58% | $+85 | $+63,260 | $2,530 | no | 73% | 22% | 27% | 11 |
| NQ nday-break-1 2.5A close | 740 | 58% | $+84 | $+62,490 | $2,530 | no | 72% | 22% | 27% | 12 |
| NQ nday-break-1 2.5A tp2 | 740 | 58% | $+84 | $+62,490 | $2,530 | no | 72% | 22% | 27% | 12 |
| NQ nday-break-1 2A close | 740 | 58% | $+82 | $+60,971 | $2,024 | no | 72% | 22% | 27% | 12 |
| NQ nday-break-1 2A tp2 | 740 | 58% | $+82 | $+60,971 | $2,024 | no | 72% | 22% | 27% | 12 |
| NQ nday-break-1 2A tp1 | 740 | 58% | $+83 | $+61,617 | $2,024 | no | 73% | 22% | 27% | 11 |
| NQ nday-break-1 1.5A tp2 | 740 | 57% | $+80 | $+59,235 | $1,518 | no | 69% | 22% | 30% | 11 |
| NQ nday-break-1 1.5A close | 740 | 57% | $+80 | $+58,914 | $1,518 | no | 69% | 22% | 30% | 11 |
| NQ nr-break-2 0.75A close | 368 | 58% | $+73 | $+26,920 | $791 | tight | 70% | 21% | 30% | 10 |
| NQ nr-break-2 0.75A tp2 | 368 | 58% | $+70 | $+25,580 | $791 | tight | 70% | 21% | 30% | 10 |
| NQ nday-break-1 1A close | 740 | 57% | $+67 | $+49,397 | $1,012 | no | 59% | 20% | 41% | 10 |
| NQ nday-break-1 1A tp2 | 740 | 57% | $+68 | $+50,043 | $1,012 | no | 59% | 20% | 41% | 10 |
| NQ nday-break-1 1.5A tp1 | 740 | 57% | $+76 | $+56,359 | $1,518 | no | 70% | 20% | 30% | 11 |
| ES prevclose-break 0.5A tp2 | 944 | 42% | $-9 | $-8,855 | $200 | yes | 20% | 20% | 80% | 28 |
| ES prevclose-break 1A tp1 | 944 | 48% | $-13 | $-12,001 | $401 | yes | 20% | 19% | 80% | 27 |
| ES prevclose-break 0.75A tp2 | 944 | 46% | $-10 | $-9,447 | $301 | yes | 27% | 18% | 73% | 27 |
| NQ prevclose-break 1A tp1 | 953 | 50% | $+3 | $+2,483 | $959 | tight | 43% | 18% | 57% | 10 |
| ES nday-break-1 0.75A tp1 | 740 | 50% | $-8 | $-6,006 | $305 | yes | 17% | 17% | 82% | 17 |
| NQ nday-fade-5 1A tp1 | 521 | 50% | $+31 | $+16,301 | $1,054 | no | 42% | 17% | 58% | 7 |
| ES prevclose-break 1A tp2 | 944 | 47% | $-11 | $-10,433 | $401 | yes | 25% | 16% | 75% | 25 |
| ES prevclose-break 0.75A tp1 | 944 | 47% | $-16 | $-14,632 | $301 | yes | 14% | 14% | 86% | 27 |
| NQ nr-break-2 0.5A tp1 | 368 | 45% | $-50 | $-18,307 | $527 | tight | 18% | 13% | 82% | 10 |
| ES prevclose-break 0.75A close | 944 | 46% | $-10 | $-9,425 | $301 | yes | 24% | 13% | 75% | 26 |
| ES prevclose-break 1A close | 944 | 47% | $-11 | $-10,504 | $401 | yes | 23% | 13% | 77% | 23 |
| ES nday-break-1 0.75A tp2 | 740 | 49% | $-6 | $-4,389 | $305 | yes | 26% | 12% | 73% | 22 |
| NQ nday-fade-5 0.5A tp2 | 521 | 45% | $+16 | $+8,430 | $527 | tight | 34% | 12% | 66% | 8 |
| NQ nday-break-1 0.75A close | 740 | 52% | $+24 | $+17,729 | $759 | tight | 42% | 11% | 58% | 9 |
| NQ nday-break-1 0.75A tp2 | 740 | 52% | $+21 | $+15,840 | $759 | tight | 42% | 11% | 58% | 9 |
| ES nday-break-1 0.75A close | 740 | 49% | $-5 | $-4,028 | $305 | yes | 26% | 11% | 73% | 20 |
| ES nr-break-2 0.5A close | 371 | 42% | $-19 | $-6,916 | $206 | yes | 16% | 11% | 83% | 22 |
| ES nr-break-2 0.5A tp2 | 371 | 42% | $-21 | $-7,818 | $206 | yes | 13% | 11% | 86% | 28 |
| NQ nr-break-2 0.5A tp2 | 368 | 43% | $-34 | $-12,448 | $527 | tight | 32% | 10% | 67% | 9 |
| ES prevclose-break 0.5A close | 944 | 42% | $-6 | $-5,644 | $200 | yes | 26% | 10% | 74% | 25 |
| NQ prevclose-break 2A tp1 | 953 | 50% | $+6 | $+6,187 | $1,919 | no | 46% | 10% | 54% | 9 |
| NQ prevclose-break 2.5A close | 953 | 50% | $+6 | $+5,406 | $2,398 | no | 46% | 10% | 54% | 9 |
| NQ prevclose-break 2.5A tp2 | 953 | 50% | $+6 | $+5,406 | $2,398 | no | 46% | 10% | 54% | 9 |
| NQ prevclose-break 2.5A tp1 | 953 | 50% | $+6 | $+5,261 | $2,398 | no | 46% | 10% | 54% | 9 |
| NQ prevclose-break 2A close | 953 | 50% | $+5 | $+4,666 | $1,919 | no | 46% | 10% | 54% | 9 |
| NQ prevclose-break 2A tp2 | 953 | 50% | $+5 | $+4,666 | $1,919 | no | 46% | 10% | 54% | 9 |
| NQ prevclose-break 1.5A tp2 | 953 | 50% | $+5 | $+4,396 | $1,439 | no | 45% | 10% | 55% | 9 |
| NQ prevclose-break 1.5A close | 953 | 50% | $+5 | $+4,346 | $1,439 | no | 45% | 10% | 55% | 9 |
| ES nday-fade-5 0.75A tp2 | 525 | 49% | $-2 | $-1,189 | $309 | yes | 34% | 10% | 64% | 34 |
| NQ prevclose-break 1.5A tp1 | 953 | 50% | $+4 | $+4,202 | $1,439 | no | 46% | 9% | 54% | 9 |
| ES prevclose-break 0.5A tp1 | 944 | 45% | $-20 | $-19,114 | $200 | yes | 10% | 9% | 90% | 38 |
| NQ prevclose-break 0.5A tp2 | 953 | 45% | $+9 | $+8,603 | $480 | yes | 34% | 9% | 66% | 10 |
| ES nday-fade-5 1.5A tp1 | 525 | 50% | $+2 | $+1,071 | $618 | tight | 33% | 8% | 65% | 26 |
| NQ prevclose-break 1A tp2 | 953 | 50% | $+9 | $+8,504 | $959 | tight | 45% | 8% | 55% | 9 |
| NQ prevclose-break 1A close | 953 | 50% | $+7 | $+6,983 | $959 | tight | 45% | 8% | 55% | 9 |
| NQ prevclose-break 0.75A close | 953 | 49% | $+8 | $+7,522 | $719 | tight | 44% | 8% | 56% | 9 |
| NQ prevclose-break 0.75A tp2 | 953 | 49% | $+8 | $+7,377 | $719 | tight | 44% | 7% | 56% | 9 |
| ES nr-break-2 0.5A tp1 | 371 | 42% | $-34 | $-12,519 | $206 | yes | 8% | 5% | 92% | 16 |
| NQ prevclose-break 0.5A close | 953 | 45% | $+16 | $+15,281 | $480 | yes | 40% | 4% | 60% | 10 |
| NQ nday-break-1 0.5A tp1 | 740 | 40% | $-86 | $-63,929 | $506 | tight | 6% | 4% | 93% | 5 |
| NQ nr-break-2 0.5A close | 368 | 43% | $-26 | $-9,387 | $527 | tight | 33% | 4% | 67% | 9 |
| NQ nday-break-1 0.5A tp2 | 740 | 38% | $-71 | $-52,737 | $506 | tight | 12% | 3% | 88% | 6 |
| NQ nday-fade-5 1.5A tp1 | 521 | 48% | $-3 | $-1,606 | $1,581 | no | 33% | 3% | 67% | 9 |
| NQ nday-fade-5 2A tp1 | 521 | 47% | $-28 | $-14,757 | $2,108 | no | 21% | 3% | 78% | 9 |
| NQ nday-fade-5 2.5A tp1 | 521 | 47% | $-30 | $-15,547 | $2,635 | no | 21% | 3% | 78% | 9 |
| NQ nday-fade-5 1.5A close | 521 | 46% | $-30 | $-15,578 | $1,581 | no | 20% | 3% | 80% | 8 |
| NQ nday-fade-5 1.5A tp2 | 521 | 46% | $-30 | $-15,578 | $1,581 | no | 20% | 3% | 80% | 8 |
| NQ nday-fade-5 2.5A close | 521 | 46% | $-33 | $-17,231 | $2,635 | no | 20% | 3% | 80% | 8 |
| NQ nday-fade-5 2.5A tp2 | 521 | 46% | $-33 | $-17,231 | $2,635 | no | 20% | 3% | 80% | 8 |
| NQ nday-fade-5 1A tp2 | 521 | 46% | $-34 | $-17,799 | $1,054 | no | 20% | 3% | 80% | 9 |
| NQ nday-fade-5 2A close | 521 | 46% | $-34 | $-17,801 | $2,108 | no | 20% | 3% | 80% | 8 |
| NQ nday-fade-5 2A tp2 | 521 | 46% | $-34 | $-17,801 | $2,108 | no | 20% | 3% | 80% | 8 |
| NQ nday-fade-5 1A close | 521 | 46% | $-34 | $-17,902 | $1,054 | no | 20% | 3% | 80% | 9 |
| NQ nday-break-1 0.5A close | 740 | 38% | $-68 | $-50,395 | $506 | tight | 14% | 2% | 86% | 5 |
| NQ nday-fade-5 0.75A tp2 | 521 | 47% | $-10 | $-5,456 | $791 | tight | 28% | 2% | 72% | 9 |
| ES nday-fade-5 1A close | 525 | 49% | $-11 | $-5,558 | $412 | yes | 17% | 2% | 82% | 26 |
| ES nday-fade-5 1A tp2 | 525 | 49% | $-11 | $-5,558 | $412 | yes | 17% | 2% | 82% | 26 |
| NQ nday-fade-5 0.75A close | 521 | 45% | $-29 | $-15,272 | $791 | tight | 16% | 2% | 83% | 8 |
| ES nday-fade-5 1.5A close | 525 | 49% | $-9 | $-4,591 | $618 | tight | 19% | 2% | 80% | 26 |
| ES nday-fade-5 1.5A tp2 | 525 | 49% | $-9 | $-4,591 | $618 | tight | 19% | 2% | 80% | 26 |
| ES nday-fade-5 2.5A close | 525 | 49% | $-11 | $-5,717 | $1,029 | no | 15% | 2% | 85% | 18 |
| ES nday-fade-5 2.5A tp1 | 525 | 49% | $-11 | $-5,717 | $1,029 | no | 15% | 2% | 85% | 18 |
| ES nday-fade-5 2.5A tp2 | 525 | 49% | $-11 | $-5,717 | $1,029 | no | 15% | 2% | 85% | 18 |
| ES nday-fade-5 2A close | 525 | 49% | $-11 | $-5,763 | $824 | tight | 18% | 2% | 81% | 24 |
| ES nday-fade-5 2A tp1 | 525 | 49% | $-11 | $-5,763 | $824 | tight | 18% | 2% | 81% | 24 |
| ES nday-fade-5 2A tp2 | 525 | 49% | $-11 | $-5,763 | $824 | tight | 18% | 2% | 81% | 24 |
| ES nday-break-1 0.5A tp2 | 740 | 37% | $-48 | $-35,256 | $203 | yes | 2% | 1% | 98% | 9 |
| NQ nday-fade-5 0.5A close | 521 | 42% | $-33 | $-16,989 | $527 | tight | 10% | 1% | 90% | 7 |
| ES nday-break-1 0.5A close | 740 | 37% | $-45 | $-33,576 | $203 | yes | 4% | 1% | 96% | 10 |
| ES nday-fade-5 0.75A close | 525 | 48% | $-11 | $-5,759 | $309 | yes | 17% | 0% | 82% | 25 |
| ES nday-fade-5 0.5A close | 525 | 46% | $-9 | $-4,926 | $206 | yes | 21% | 0% | 78% | 32 |
| ES nday-break-1 0.5A tp1 | 740 | 38% | $-56 | $-41,806 | $203 | yes | 0% | 0% | 100% | 9 |

## Books of two and three rules

Built only from lines whose own session risk fits the buffer, with overlapping trade
shapes excluded — two rules that trade the same days are one position sized twice.

| book | legs | trades | win | $/trade | risk | pass% | cons% | breach% | days → pass |
|---|---|---|---|---|---|---|---|---|---|
| nday-fade-5 0.5A tp1 + nr-break-2 1A tp1 | 2 | 896 | 59% | $+36 | $405 | 90% | 88% | 7% | 26 |
| nday-break-1 1.5A tp1 + nday-fade-5 0.5A tp1 | 2 | 1261 | 56% | $+37 | $814 | 72% | 62% | 28% | 14 |
| nr-break-2 1A tp1 + nday-fade-5 0.5A tp1 | 2 | 892 | 57% | $+46 | $512 | 65% | 57% | 34% | 14 |
| nday-fade-5 0.5A tp1 + nr-break-2 0.75A tp1 | 2 | 893 | 59% | $+46 | $732 | 77% | 52% | 23% | 16 |
| nday-fade-5 0.5A tp1 + nr-break-2 0.75A tp1 | 2 | 889 | 58% | $+56 | $714 | 71% | 52% | 28% | 11 |
| nday-break-1 1.5A tp1 + nr-break-2 0.75A tp1 | 2 | 1108 | 56% | $+40 | $644 | 68% | 48% | 32% | 11 |
| nr-break-2 1A tp1 + prevclose-break 0.75A tp1 | 2 | 1324 | 52% | $+9 | $902 | 49% | 36% | 51% | 9 |
| nr-break-2 0.75A tp1 + prevclose-break 0.75A tp1 | 2 | 1321 | 53% | $+16 | $833 | 47% | 33% | 53% | 7 |

## What this says

**Best book for a 25K: nday-fade-5 0.5A tp1 + nr-break-2 1A tp1** — 88% of starting trades pass with the consistency rule intact, 7% breach, $405 of session risk, and a median of 26 sessions to the target.

**Best single line: ES nday-fade-5 0.5A tp1** — 80% pass with consistency, 60% win, $+33 a trade, $206 of risk.

The honest reading of the grid is that the stop distance is not a free dial. Every
step wider trades stop-outs for size: the win rate climbs and the average loss climbs
with it, so the pass rate does not climb at all — it is set by how many buffers one
loss costs, and that is a fact about the contract, not the rule.
