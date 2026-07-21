# -*- coding: utf-8 -*-
"""
s145d_mtf_breakout_trail.py — MTF Breakout LONG با خروجِ «بگذار بردها بدوند» (trailing)
================================================================================
> قانونِ شمارهٔ ۱: هدف فقط «سودِ خالصِ بیشتر» است — نه WR.
> سودِ خالص = جمعِ سودِ XAUUSD + EURUSD.
================================================================================
مسیرِ کشف تا اینجا:
  s145/s145b : mean-reversion به S/R ⇒ بی‌لبه (MFE≈MAE).
  s145c      : trend-aligned breakout LONG + فیلترِ روندِ قوی ⇒ PF تا ۰.۹۸ (هنوز زیان).
اکنون درسِ اثبات‌شدهٔ پروژه (s118 «بگذار بردها بدوند») را اعمال می‌کنیم:
  به‌جای TP سقفِ ثابت، یک **trailing stop** بعد از رسیدن به سطحِ break-even بگذار تا
  بردهای بزرگِ روندی تا انتها بدوند. این تنها راهی است که در تاریخِ پروژه توانست
  لبهٔ نازکِ اسکالپ را از هزینهٔ تراکنش عبور دهد.

خروجِ پیاده‌سازی‌شده:
  - SL اولیه = sl_mult × ATR زیرِ ورود.
  - وقتی سود ≥ be_trig × ATR شد ⇒ SL به break-even (+قفلِ کوچک).
  - سپس trailing: SL همیشه trail_mult × ATR زیرِ بالاترین high دیده‌شده.
  - سقفِ زمانی max_hold کندل.
همه forward-safe (تصمیمِ trail روی high/low کندلِ جاری، اجرا intrabar).
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
from strategies.s145c_mtf_breakout_long import gen_breakout_long, build_trendstr, ev


def backtest_trail(m5, sig, atr_arr, sl_mult, be_trig, trail_mult, max_hold=120):
    openv = m5['open'].values; high = m5['high'].values
    low = m5['low'].values; close = m5['close'].values
    n = len(m5)
    trades, sl_dists = [], []
    i = 1
    while i < n - 1:
        if sig[i] != 1 or np.isnan(atr_arr[i]) or atr_arr[i] <= 0:
            i += 1; continue
        eb = i + 1; entry = openv[eb]; a = atr_arr[i]
        init_sl = entry - sl_mult * a
        sl = init_sl
        sl_dist = entry - init_sl
        be_level = entry + be_trig * a
        max_high = entry
        moved_be = False
        ep = None; oc = None; xb = None
        for j in range(eb, min(eb + max_hold, n)):
            hi, lo = high[j], low[j]
            # ابتدا SL چک شود (محافظه‌کارانه)
            if lo <= sl:
                ep = sl; oc = 'win' if sl >= entry else 'loss'; xb = j; break
            # به‌روزرسانیِ بالاترین high و trailing
            if hi > max_high:
                max_high = hi
            if not moved_be and hi >= be_level:
                sl = max(sl, entry + 0.1 * a)  # قفلِ کوچکِ break-even
                moved_be = True
            if moved_be:
                new_sl = max_high - trail_mult * a
                if new_sl > sl:
                    sl = new_sl
        if ep is None:
            xb = min(eb + max_hold - 1, n - 1); ep = close[xb]
            oc = 'win' if ep > entry else 'loss'
        raw = (ep - entry) - COST_PRICE
        trades.append({'pnl': raw, 'signal_bar': i, 'exit_bar': xb, 'outcome': oc})
        sl_dists.append(sl_dist)
        i = xb + 1
    return pd.DataFrame(trades), np.array(sl_dists)


def wf_folds(tr, sld, n, nfolds=4):
    bounds = np.linspace(0, n, nfolds + 1).astype(int)
    out = []
    for k in range(nfolds):
        lo, hi = bounds[k], bounds[k+1]
        m = (tr['signal_bar'] >= lo) & (tr['signal_bar'] < hi)
        s = ev(tr[m].reset_index(drop=True), sld[m.values]) if m.sum() > 0 else None
        out.append(s['net_profit'] if s else None)
    return out


if __name__ == '__main__':
    print("Loading XAUUSD M5 + M15 ...")
    m5 = load('XAUUSD', 'M5'); m15 = load('XAUUSD', 'M15')
    ctx15 = build_m15_context(m15); ctx = map_m15_to_m5(m5, ctx15)
    atr_arr = atr_np(m5, 14)
    ts = build_trendstr(m5, m15)
    n = len(m5); mid = n // 2
    thr = np.nanquantile(ts[ts > 0], 0.5)

    print("\n=== SWEEP: breakout LONG + trailing exit ('let winners run') ===")
    best = None
    for lb in [40, 60]:
        for cd in [12, 24]:
            sig = gen_breakout_long(m5, ctx, lookback=lb, cooldown=cd, ts=ts, ts_thr=thr)
            if (sig != 0).sum() < 50:
                continue
            for sl_mult in [1.5, 2.0, 3.0]:
                for be_trig in [1.0, 1.5, 2.0]:
                    for trail_mult in [1.5, 2.0, 3.0]:
                        for mh in [120, 240]:
                            tr, sld = backtest_trail(m5, sig, atr_arr, sl_mult, be_trig, trail_mult, mh)
                            full = ev(tr, sld)
                            if full is None:
                                continue
                            m1 = tr['signal_bar'] < mid
                            h1 = ev(tr[m1].reset_index(drop=True), sld[m1.values]) if m1.sum() else None
                            h2 = ev(tr[~m1].reset_index(drop=True), sld[(~m1).values]) if (~m1).sum() else None
                            folds = wf_folds(tr, sld, n)
                            both = h1 and h2 and h1['net_profit'] > 0 and h2['net_profit'] > 0
                            wf_ok = all(f is not None and f > 0 for f in folds)
                            gate = both and wf_ok and full['net_profit'] > 0 and not full['ruined']
                            if gate:
                                print(f"✅ lb={lb} cd={cd} sl={sl_mult} be={be_trig} tr={trail_mult} mh={mh} "
                                      f"n={full['n_trades']} netP={full['net_profit']:+.0f}$ "
                                      f"WR={full['win_rate']:.0f}% PF={full['profit_factor']:.2f} "
                                      f"DD={full['max_dd_pct']:.0f}% Sh={full['sharpe']:.2f}")
                                if best is None or full['net_profit'] > best[0]['net_profit']:
                                    best = (full, lb, cd, sl_mult, be_trig, trail_mult, mh)
    print("\n=== BEST (all gates green) ===")
    if best:
        s, lb, cd, slm, be, trm, mh = best
        print(f"lb={lb} cd={cd} sl_mult={slm} be_trig={be} trail_mult={trm} max_hold={mh}")
        print(f"netP={s['net_profit']:+.0f}$ n={s['n_trades']} WR={s['win_rate']:.1f}% "
              f"PF={s['profit_factor']:.2f} DD={s['max_dd_pct']:.1f}% Sharpe={s['sharpe']:.2f}")
    else:
        print("هیچ ترکیبی همهٔ گیت‌ها را عبور نکرد.")
