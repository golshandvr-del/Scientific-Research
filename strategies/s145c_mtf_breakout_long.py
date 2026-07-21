# -*- coding: utf-8 -*-
"""
s145c_mtf_breakout_long.py — MTF Trend-Aligned Breakout (فقط LONG) روی M5
================================================================================
> قانونِ شمارهٔ ۱: هدف فقط «سودِ خالصِ بیشتر» است — نه WR.
> سودِ خالص = جمعِ سودِ XAUUSD + EURUSD.
================================================================================
مسیرِ کشف (صداقتِ علمی — همه ثبت می‌شود):
  • s145  : ورودِ mean-reversion «لمسِ سطح S/R» ⇒ فاجعه (WR 5٪، ruined).
  • s145b : ورودِ «bounce تأییدشده» از سطح ⇒ باز هم بی‌لبه (MFE≈MAE، pos% 51٪).
  • ممیزیِ MFE/MAE ثابت کرد bounce از S/R لبه ندارد، اما **breakout هم‌جهت با روندِ
    M15 لبهٔ واقعی دارد** — و **فقط در سمتِ LONG** (طلا سویهٔ صعودیِ ساختاری دارد؛
    short بی‌لبه بود: pos% 47٪). این با کلِ تاریخِ پروژه هم‌خوان است (تنها ۱ لایهٔ short).

هستهٔ نهایی (این فایل):
  گیتِ HTF: روندِ M15 صعودی (EMA50>EMA200 روی M15، forward-safe map به M5).
  ماشهٔ LTF: close کندلِ M5 بالاترین high در `lookback` کندلِ اخیر را رد کند (breakout)
             ∧ کندلِ صعودی (close>open).
  خروجِ پنهان: TP/SL بر حسبِ ATR(M5) — کاربر عدد نمی‌بیند.
  فقط LONG. کول‌داونِ ضدِ over-trade.
================================================================================
"""
import os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine.capital_engine import run_capital_backtest
from strategies.s145_mtf_structure_scalp import (
    load, ema_np, atr_np, build_m15_context, map_m15_to_m5,
    PIP, CONTRACT, COST_PRICE, INITIAL_CAPITAL, RISK_PCT)


def gen_breakout_long(m5, ctx, lookback=20, cooldown=12):
    n = len(m5)
    close = m5['close'].values; openv = m5['open'].values; high = m5['high'].values
    trend = ctx['m15_trend'].values
    sig = np.zeros(n, dtype=np.int8)
    last = -10**9
    for i in range(lookback, n):
        if i - last < cooldown:
            continue
        if trend[i] == 1:
            hh = high[i-lookback:i].max()
            if close[i] > hh and close[i] > openv[i]:
                sig[i] = 1
                last = i
    return sig


def backtest_long(m5, sig, atr_arr, tp_mult, sl_mult, max_hold=60):
    openv = m5['open'].values; high = m5['high'].values
    low = m5['low'].values; close = m5['close'].values
    n = len(m5)
    trades, sl_dists = [], []
    i = 1
    while i < n - 1:
        if sig[i] != 1 or np.isnan(atr_arr[i]) or atr_arr[i] <= 0:
            i += 1; continue
        eb = i + 1; entry = openv[eb]; a = atr_arr[i]
        tp = entry + tp_mult * a
        sl = entry - sl_mult * a
        sl_dist = entry - sl
        ep = None; oc = None; xb = None
        for j in range(eb, min(eb + max_hold, n)):
            if low[j] <= sl:
                ep = sl; oc = 'loss'; xb = j; break
            if high[j] >= tp:
                ep = tp; oc = 'win'; xb = j; break
        if ep is None:
            xb = min(eb + max_hold - 1, n - 1); ep = close[xb]
            oc = 'win' if ep > entry else 'loss'
        raw = (ep - entry) - COST_PRICE
        trades.append({'pnl': raw, 'signal_bar': i, 'exit_bar': xb, 'outcome': oc})
        sl_dists.append(sl_dist)
        i = xb + 1
    return pd.DataFrame(trades), np.array(sl_dists)


def ev(tr, sld):
    if len(tr) == 0:
        return None
    s, _ = run_capital_backtest(tr, sld, initial_capital=INITIAL_CAPITAL,
                                risk_pct=RISK_PCT, commission_per_lot=0.0,
                                compounding=True, contract_size=CONTRACT)
    return s


def wf_eval(m5, sig, atr_arr, tp, slm, mh, nfolds=4):
    """walk-forward: تقسیمِ داده به nfolds بازهٔ زمانیِ متوالی؛ سودِ خالصِ هر بازه."""
    n = len(m5); bounds = np.linspace(0, n, nfolds + 1).astype(int)
    tr, sld = backtest_long(m5, sig, atr_arr, tp, slm, mh)
    if len(tr) == 0:
        return None, [None]*nfolds
    full = ev(tr, sld)
    fold_np = []
    for k in range(nfolds):
        lo, hi = bounds[k], bounds[k+1]
        m = (tr['signal_bar'] >= lo) & (tr['signal_bar'] < hi)
        s = ev(tr[m].reset_index(drop=True), sld[m.values]) if m.sum() > 0 else None
        fold_np.append(s['net_profit'] if s else None)
    return full, fold_np


if __name__ == '__main__':
    print("Loading XAUUSD M5 + M15 ...")
    m5 = load('XAUUSD', 'M5'); m15 = load('XAUUSD', 'M15')
    ctx15 = build_m15_context(m15); ctx = map_m15_to_m5(m5, ctx15)
    atr_arr = atr_np(m5, 14)
    n = len(m5); mid = n // 2

    print("\n=== SWEEP: MTF trend-aligned breakout LONG ===")
    best = None
    for lb in [12, 20, 30, 40]:
        for cd in [6, 12, 24]:
            sig = gen_breakout_long(m5, ctx, lookback=lb, cooldown=cd)
            if (sig != 0).sum() < 50:
                continue
            for tp in [1.0, 1.5, 2.0, 3.0]:
                for slm in [1.0, 1.5, 2.0, 3.0]:
                    full, folds = wf_eval(m5, sig, atr_arr, tp, slm, 60)
                    if full is None:
                        continue
                    tr, sld = backtest_long(m5, sig, atr_arr, tp, slm, 60)
                    m1 = tr['signal_bar'] < mid
                    h1 = ev(tr[m1].reset_index(drop=True), sld[m1.values]) if m1.sum() else None
                    h2 = ev(tr[~m1].reset_index(drop=True), sld[(~m1).values]) if (~m1).sum() else None
                    both = h1 and h2 and h1['net_profit'] > 0 and h2['net_profit'] > 0
                    wf_ok = all(f is not None and f > 0 for f in folds)
                    gate = both and wf_ok and full['net_profit'] > 0 and not full['ruined']
                    if gate:
                        print(f"✅ lb={lb} cd={cd} tp={tp} sl={slm} n={full['n_trades']} "
                              f"netP={full['net_profit']:+.0f}$ WR={full['win_rate']:.0f}% "
                              f"PF={full['profit_factor']:.2f} DD={full['max_dd_pct']:.0f}% "
                              f"Sharpe={full['sharpe']:.2f}")
                        if best is None or full['net_profit'] > best[0]['net_profit']:
                            best = (full, lb, cd, tp, slm)
    print("\n=== BEST (all gates green) ===")
    if best:
        s, lb, cd, tp, slm = best
        print(f"lb={lb} cd={cd} tp_mult={tp} sl_mult={slm}")
        print(f"netP={s['net_profit']:+.0f}$ n={s['n_trades']} WR={s['win_rate']:.1f}% "
              f"PF={s['profit_factor']:.2f} DD={s['max_dd_pct']:.1f}% Sharpe={s['sharpe']:.2f}")
    else:
        print("هیچ ترکیبی همهٔ گیت‌ها را عبور نکرد.")
