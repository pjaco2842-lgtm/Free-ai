#!/usr/bin/env python3
"""Does predicting tomorrow's efficiency ratio improve the book?

The claim from the video: a logistic regression over 15 price-movement measurements
predicts the next day's efficiency ratio (ER), high-ER days earn far more than low-ER
days, and skipping the low ones improves almost every metric out of sample.

Tested here the only way that can settle it on this repo's data:

  * ER is Kaufman's: |close[t] - close[t-k]| / sum of |step| over the same window.
  * Features are built from bars up to the PREVIOUS close. Nothing from the day being
    predicted is read, so a signal for a session is knowable before that session opens.
  * The model is trained on everything before 2023 and judged only on 2023 onward.
  * The gate is scored on the book itself (prior-low limit, 0.5 ATR, tp2, one micro),
    against a control that drops the same number of random days, 400 times.

The trap this exposes: the book already fires on fewer than half of sessions. A gate
that raises dollars per trade while cutting the number of trades can *lower* dollars
per session, and dollars per session is what decides the funding date.

    python3 er_gate.py
"""
from __future__ import annotations

import json
import random
import statistics
from pathlib import Path

import numpy as np

import edge_causal as E

ROOT = Path(__file__).resolve().parent
DESK = ROOT / "desk"
CSV = ROOT / "data" / "ES_F_1d.csv"
SPLIT = "2023-01-01"
ER_K = 10
ER_THRESHOLD = 0.30          # "high efficiency" = moved in one direction more than 30%
N_FEATURES = 15


def er(close: list[float], i: int, k: int = ER_K) -> float:
    num = abs(close[i] - close[i - k])
    den = sum(abs(close[j] - close[j - 1]) for j in range(i - k + 1, i + 1))
    return num / den if den else 0.0


def ema(vals: list[float], span: int) -> list[float]:
    out, a = [], 2.0 / (span + 1.0)
    for v in vals:
        out.append(v if not out else a * v + (1 - a) * out[-1])
    return out


def features(D: dict, i: int) -> list[float] | None:
    """Everything knowable at the close before session i. Fifteen numbers."""
    c, o, h, l, atr = D["c"], D["o"], D["h"], D["l"], D["atr"]
    if i < 30 or atr[i - 1] <= 0:
        return None
    rets = [c[j] / c[j - 1] - 1 for j in range(i - 20, i)]
    rng5 = statistics.fmean(h[j] - l[j] for j in range(i - 5, i))
    bar = h[i - 1] - l[i - 1]
    e20, e50, e200 = D["ema20"][i - 1], D["ema50"][i - 1], D["ema200"][i - 1]
    return [
        c[i - 1] / c[i - 2] - 1,                       # 1 ret 1
        c[i - 1] / c[i - 3] - 1,                       # 2 ret 2
        c[i - 1] / c[i - 6] - 1,                       # 3 ret 5
        c[i - 1] / c[i - 11] - 1,                      # 4 ret 10
        atr[i - 1] / c[i - 1],                         # 5 ATR as % of price
        rng5 / atr[i - 1],                             # 6 recent range vs ATR
        (c[i - 1] - l[i - 1]) / bar if bar else 0.5,   # 7 where it closed in the bar
        o[i - 1] / c[i - 2] - 1,                       # 8 overnight gap
        c[i - 1] / e20 - 1,                            # 9 distance from EMA20
        c[i - 1] / e50 - 1,                            # 10 distance from EMA50
        c[i - 1] / e200 - 1,                           # 11 distance from EMA200
        statistics.pstdev(rets[-5:]) / (statistics.pstdev(rets) or 1e-9),  # 12 vol burst
        statistics.fmean(1.0 if c[j] > c[j - 1] else 0.0
                         for j in range(i - 10, i)),   # 13 up-day fraction
        er(c, i - 1),                                  # 14 yesterday's own efficiency
        (max(h[i - 20:i]) - c[i - 1]) / atr[i - 1],    # 15 distance under the 20-day high
    ]


def fit(X: np.ndarray, y: np.ndarray, iters: int = 3000, lr: float = 0.3,
        l2: float = 0.01) -> np.ndarray:
    """Plain logistic regression. No dependency, and the coefficients stay readable."""
    w = np.zeros(X.shape[1] + 1)
    Xb = np.hstack([np.ones((len(X), 1)), X])
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-Xb @ w))
        grad = Xb.T @ (p - y) / len(y) + l2 * np.r_[0.0, w[1:]]
        w -= lr * grad
    return w


def predict(w: np.ndarray, X: np.ndarray) -> np.ndarray:
    Xb = np.hstack([np.ones((len(X), 1)), X])
    return 1.0 / (1.0 + np.exp(-Xb @ w))


def auc(scores: np.ndarray, y: np.ndarray) -> float:
    pos, neg = scores[y == 1], scores[y == 0]
    if not len(pos) or not len(neg):
        return float("nan")
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def main() -> None:
    D = E.load_csv(str(CSV))
    D["ema20"], D["ema50"], D["ema200"] = (ema(D["c"], s) for s in (20, 50, 200))
    mult, tick = E.SPECS["ES=F"]["mult"], E.SPECS["ES=F"]["tick"]

    rows, y, dates = [], [], []
    for i in range(30, D["n"]):
        f = features(D, i)
        if f is None:
            continue
        rows.append(f)
        y.append(1 if er(D["c"], i) >= ER_THRESHOLD else 0)
        dates.append(D["d"][i])
    X = np.array(rows)
    Y = np.array(y)
    train = np.array([d < SPLIT for d in dates])
    mu, sd = X[train].mean(0), X[train].std(0) + 1e-9
    Xs = (X - mu) / sd
    w = fit(Xs[train], Y[train])
    prob = predict(w, Xs)
    pred = prob >= 0.5

    test = ~train
    acc = float((pred[test] == Y[test]).mean())
    test_auc = auc(prob[test], Y[test])
    base = float(Y[test].mean())

    # ---- does the gate help the book itself?
    trades = E.run_config(D, "limit_low", 1, 0.5, "tp2", "any", "proven", mult, tick)
    by_date = {d: p for d, p in trades}
    tr = [(d, p) for d, p in trades if d >= SPLIT]
    gate = {d: bool(pred[dates.index(d)]) for d, _ in tr} if tr else {}
    kept = [(d, p) for d, p in tr if gate.get(d)]
    dropped = [(d, p) for d, p in tr if not gate.get(d)]
    sessions = sum(1 for d in dates if d >= SPLIT)

    def stats(rec: list[tuple[str, float]]) -> tuple[int, float, float]:
        if not rec:
            return 0, 0.0, 0.0
        return len(rec), statistics.fmean(p for _, p in rec), sum(p for _, p in rec) / sessions

    n_all, avg_all, per_sess_all = stats(tr)
    n_keep, avg_keep, per_sess_keep = stats(kept)
    n_drop, avg_drop, _ = stats(dropped)

    # control: drop the same COUNT at random, 400 times — is the gate better than luck?
    rng = random.Random(7)
    means = []
    for _ in range(400):
        pick = rng.sample(tr, min(n_keep, len(tr))) if tr else []
        means.append(statistics.fmean(p for _, p in pick) if pick else 0.0)
    p_value = (sum(1 for m in means if m >= avg_keep) / len(means)) if means else 1.0
    pct = 100.0 * sum(1 for m in means if m <= avg_keep) / len(means) if means else 0.0

    L = ["# Predicting tomorrow's efficiency ratio, tested on this book", "",
         f"ER(k={ER_K}) >= {ER_THRESHOLD:.0%} is called a high-efficiency session. "
         f"{N_FEATURES} features, all from the closes before the session being predicted. "
         f"Trained before {SPLIT}, judged on {SPLIT} onward.", "",
         "## Does the model predict anything?",
         "", "| measure | value |", "|---|---|",
         f"| training rows / test rows | {int(train.sum())} / {int(test.sum())} |",
         f"| high-ER base rate in test | {100*base:.1f}% |",
         f"| test accuracy | {100*acc:.1f}% |",
         f"| test AUC | {test_auc:.3f} |", "",
         ("AUC near 0.50 means the model cannot rank tomorrow's sessions at all; "
          "anything at 0.55 and below is not a signal worth gating on."),
         "", "## Does the gate help the book? (2023 onward, causal fills, one micro)",
         "", "| set | trades | $/trade | $/session |", "|---|---:|---:|---:|",
         f"| every trade | {n_all} | ${avg_all:+.2f} | ${per_sess_all:+.2f} |",
         f"| predicted high ER | {n_keep} | ${avg_keep:+.2f} | ${per_sess_keep:+.2f} |",
         f"| predicted low ER | {n_drop} | ${avg_drop:+.2f} | — |", "",
         "| control | value |", "|---|---|",
         f"| random days dropped, 400 trials | ${statistics.fmean(means):+.2f}/trade "
         f"(p05 ${sorted(means)[20]:+.2f}, p95 ${sorted(means)[379]:+.2f}) |",
         f"| gate's percentile among random drops | {pct:.0f}th |",
         f"| p-value (random did at least as well) | {p_value:.3f} |", ""]

    if test_auc < 0.55:
        verdict = ("**Verdict: the model cannot rank tomorrow's sessions.** With an AUC this "
                   "close to a coin flip there is nothing to gate on, and any improvement in "
                   "the trade table below is the small-sample luck the control measures.")
    elif p_value > 0.10:
        verdict = ("**Verdict: the gate is not distinguishable from dropping the same number "
                   "of days at random.** Predicting the right thing is not enough; the gate "
                   "has to beat luck on this book, and it does not.")
    elif per_sess_keep <= per_sess_all:
        verdict = ("**Verdict: the gate raises $/trade and lowers $/session.** It removes "
                   "trades, and the funding date is set by dollars per session, so this "
                   "improves the statistic and worsens the schedule.")
    else:
        verdict = ("**Verdict: the gate survives its controls on this sample.** That is a "
                   "reason to paper-test it forward, not to size up: it is one era of one "
                   "instrument and the threshold was chosen after seeing the data.")
    L += [verdict, ""]
    DESK.mkdir(exist_ok=True)
    (DESK / "er-gate.md").write_text("\n".join(L) + "\n")
    # the sessions the gate would allow, so time_to_funded.py can price the filter
    high = sorted(d for d, keep in zip(dates, pred) if keep and d >= SPLIT)
    (DESK / "er-gate-dates.json").write_text(json.dumps(high))
    print("\n".join(L))
    print("wrote desk/er-gate.md")


if __name__ == "__main__":
    main()
