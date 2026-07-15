"""
استراتژی ۱۶: Regime-Switching با مدل‌های تخصصی هر رژیم نوسان
=============================================================

مفهوم بنیادی متفاوت از استراتژی‌های ۱–۱۵:
تمام مدل‌های ML قبلی یک **مدل واحد سراسری** آموزش می‌دادند که باید رفتار بازار در
همه‌ی شرایط نوسانی را هم‌زمان یاد می‌گرفت. اما رفتار XAUUSD در رژیم نوسان پایین
(بازار آرام، mean-reverting) با رژیم نوسان بالا (trending/impulsive) اساساً متفاوت
است؛ یک مدل واحد مجبور به «میانگین‌گیری» بین این دو رفتار متضاد می‌شود.

نوآوری: **رژیم‌بندی صریح نوسان + یک مدل تخصصی برای هر رژیم.**
1. رژیم نوسان با صدک ATR نسبی (ATR / ATR_MA200) تعریف می‌شود:
   - LOW  : فشردگی (mean-reversion غالب)
   - MID  : نرمال
   - HIGH : انبساط (momentum/trend غالب)
2. سیگنال پایه: pullback در روند صعودی (long-only، بایاس صعودی طلا).
3. برای هر رژیم، یک LightGBM ensemble جداگانه آموزش می‌بیند و فقط سیگنال‌های
   همان رژیم را در زمان تست فیلتر می‌کند.
4. هدف کاربر (User Note): WR > ۶۰٪ + expectancy مثبت + ≥۳ معامله/روز.

اعتبارسنجی: Purged Walk-Forward با embargo (مثل s15).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np
import pandas as pd
from scipy import stats
import lightgbm as lgb

import indicators as ind
from backtest import load_data, run_backtest
import features as feat


def primary_pullback(df):
    close = df['close']
    ema200 = ind.ema(close, 200); ema50 = ind.ema(close, 50)
    uptrend = (close > ema50) & (ema50 > ema200)
    rsi = ind.rsi(close, 14)
    pullback = (rsi < 55) & (rsi > rsi.shift(1))
    return (uptrend & pullback).fillna(False).values


def volatility_regime(df):
    """رژیم نوسان: 0=LOW,1=MID,2=HIGH بر اساس نسبت ATR به میانگین بلندش (فقط گذشته)."""
    atr = ind.atr(df, 14)
    atr_ma = atr.rolling(200).mean()
    ratio = atr / atr_ma
    # آستانه‌های ثابت و شهودی (بدون نگاه به آینده)
    reg = np.full(len(df), 1, dtype=int)  # MID پیش‌فرض
    reg[(ratio < 0.85).values] = 0        # LOW
    reg[(ratio > 1.20).values] = 2        # HIGH
    reg[ratio.isna().values] = -1
    return reg, ratio.values


def triple_barrier_labels(df, sig_idx, atr, horizon, tp_mult, sl_mult):
    high = df['high'].values; low = df['low'].values; close = df['close'].values
    atr_v = atr.values; n = len(df)
    labels = {}
    for i in sig_idx:
        a = atr_v[i]
        if np.isnan(a) or a <= 0:
            continue
        entry = close[i]; tp = entry + tp_mult * a; sl = entry - sl_mult * a
        lab = 0; end = min(i + 1 + horizon, n)
        for j in range(i + 1, end):
            hit_tp = high[j] >= tp; hit_sl = low[j] <= sl
            if hit_sl and hit_tp: lab = 0; break
            if hit_tp: lab = 1; break
            if hit_sl: lab = 0; break
        labels[i] = lab
    return labels


def regime_walk_forward(df, X, sig_idx, labels, regimes, horizon,
                        n_folds=6, min_train_frac=0.40, embargo=50,
                        thresholds=None, seeds=(42, 7, 123)):
    """
    برای هر رژیم یک مدل جداگانه در هر fold آموزش می‌دهد.
    thresholds: dict{regime: threshold}
    """
    n = len(df)
    sig_idx = np.array(sorted(sig_idx))
    y = np.array([labels[i] for i in sig_idx])
    reg = regimes[sig_idx]                       # رژیم هر سیگنال
    Xv = X.values
    if thresholds is None:
        thresholds = {0: 0.60, 1: 0.62, 2: 0.62}

    start = int(n * min_train_frac)
    bounds = np.linspace(start, n, n_folds + 1).astype(int)
    approved = np.zeros(n, dtype=bool)

    for k in range(n_folds):
        test_lo, test_hi = bounds[k], bounds[k + 1]
        test_mask = (sig_idx >= test_lo) & (sig_idx < test_hi)
        train_cut = test_lo - horizon - embargo
        train_mask = sig_idx < train_cut
        if test_mask.sum() == 0:
            continue

        for rg in (0, 1, 2):
            tr_m = train_mask & (reg == rg)
            te_m = test_mask & (reg == rg)
            if tr_m.sum() < 150 or te_m.sum() == 0:
                continue
            ytr = y[tr_m]
            if len(np.unique(ytr)) < 2:
                continue
            Xtr = Xv[tr_m]; Xte = Xv[te_m]
            proba = np.zeros(te_m.sum())
            for sd in seeds:
                m = lgb.LGBMClassifier(
                    n_estimators=300, learning_rate=0.03, num_leaves=31,
                    max_depth=6, subsample=0.8, colsample_bytree=0.8,
                    min_child_samples=30, reg_lambda=1.0,
                    random_state=sd, n_jobs=-1, verbose=-1)
                m.fit(Xtr, ytr)
                proba += m.predict_proba(Xte)[:, 1]
            proba /= len(seeds)
            thr = thresholds[rg]
            te_rows = sig_idx[te_m]
            approved[te_rows[proba >= thr]] = True
    return approved


def pval_gt(k, n, p0):
    if n == 0: return 1.0
    se = np.sqrt(p0 * (1 - p0) / n)
    z = (k / n - p0) / se
    return 1 - stats.norm.cdf(z)


def main():
    df = load_data(os.path.join(os.path.dirname(__file__), '..', 'data', 'XAUUSD_M15.csv'))
    print(f"کندل: {len(df)}")
    atr = ind.atr(df, 14)
    X_full = feat.build_features(df)
    regimes, ratio = volatility_regime(df)

    prim = primary_pullback(df)
    sig_idx = np.where(prim)[0]
    valid = [i for i in sig_idx if i < len(df) - 60
             and not X_full.iloc[i].isna().any()
             and not np.isnan(atr.values[i]) and regimes[i] >= 0]
    sig_idx = np.array(valid)
    print(f"کاندید اولیه: {len(sig_idx)} | توزیع رژیم: "
          f"LOW={np.sum(regimes[sig_idx]==0)} MID={np.sum(regimes[sig_idx]==1)} "
          f"HIGH={np.sum(regimes[sig_idx]==2)}")

    n_days = df['dt'].dt.normalize().nunique()

    configs = [
        # (tp, sl, hz, {reg:thr})
        (1.0, 1.5, 48, {0: 0.60, 1: 0.62, 2: 0.62}),
        (1.0, 1.5, 48, {0: 0.62, 1: 0.64, 2: 0.64}),
        (1.0, 1.5, 48, {0: 0.58, 1: 0.60, 2: 0.60}),
        (1.2, 1.5, 48, {0: 0.62, 1: 0.64, 2: 0.64}),
        (1.0, 1.3, 40, {0: 0.60, 1: 0.62, 2: 0.62}),
    ]

    for (tp_m, sl_m, hz, thr) in configs:
        be = sl_m / (tp_m + sl_m) * 100
        labels = triple_barrier_labels(df, sig_idx, atr, hz, tp_m, sl_m)
        keys = np.array(sorted(labels.keys()))
        Xk = X_full.iloc[keys].reset_index(drop=True)
        approved = regime_walk_forward(df, Xk, keys, labels, regimes, hz,
                                       thresholds=thr)
        entries = np.zeros(len(df), dtype=bool); entries[approved] = True
        st, tr = run_backtest(df, entries, None, None, 'long', 0.20, hz, False,
                              sl_series=atr.values * sl_m, tp_series=atr.values * tp_m)
        nt = st['n_trades']; wr = st['win_rate']
        pv = pval_gt(round(wr / 100 * nt), nt, be / 100)
        print(f"TP{tp_m}/SL{sl_m} hz{hz} BE{be:.1f}% thr{thr} | "
              f"n={nt} WR={wr:.2f}% exp={st['expectancy']:+.3f}$ "
              f"PnL={st['total_pnl']:+.0f}$ tpd={nt/n_days:.2f} p={pv:.3f}")


if __name__ == '__main__':
    main()
