# -*- coding: utf-8 -*-
"""
s145b_mtf_scalp_explore.py — اکتشافِ پارامتر + منطقِ بهترِ ورود برای MTF Scalp
================================================================================
> قانونِ شمارهٔ ۱: هدف فقط «سودِ خالصِ بیشتر» است — نه WR.
> سودِ خالص = جمعِ سودِ XAUUSD + EURUSD.
================================================================================
درسِ s145 (نسخهٔ اول): ورودِ خام «در لمسِ سطح» فاجعه بود (WR 5٪، ruined) چون:
  ۱) sig در «لمس» فعال می‌شد ولی قیمت اغلب از سطح رد می‌شد (breakout به‌جای bounce).
  ۲) TP=2×ATR خیلی دور و SL نزدیک ⇒ عملاً همیشه SL.
اصلاح‌ها:
  A) ورود فقط پس از «bounce تأییدشده»: قیمت به سطح نزدیک شد (کندلِ قبل) و کندلِ فعلی
     با close در جهتِ روند بسته شد و از سطح فاصله گرفت (rejection واقعی).
  B) SL ساختاری: کمی زیرِ خودِ سطحِ حمایت (long) / بالای مقاومت (short) + بافرِ ATR.
  C) کول‌داون بینِ سیگنال‌ها برای کاهشِ over-trading.
  D) جاروِ (tp_mult, sl_buffer, near_tol, cooldown) با گیت‌های both-halves + WF.
================================================================================
"""
import os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine.structure import pivots, sr_levels
from engine.capital_engine import run_capital_backtest
from strategies.s145_mtf_structure_scalp import (
    load, ema_np, atr_np, build_m15_context, map_m15_to_m5,
    PIP, CONTRACT, COST_PRICE, INITIAL_CAPITAL, RISK_PCT)


def generate_signals_v2(m5, ctx, near_tol=0.0006, cooldown=12):
    """ورودِ bounce-confirmed:
    long: روندِ M15 صعودی ∧ کندلِ قبلی low نزدیکِ حمایت ∧ کندلِ فعلی close>open ∧
          close کندلِ فعلی از حمایت فاصله گرفته (بازگشت واقعی).
    short: قرینه روی مقاومت."""
    n = len(m5)
    close = m5['close'].values
    openv = m5['open'].values
    low = m5['low'].values
    high = m5['high'].values
    trend = ctx['m15_trend'].values
    sup = ctx['m15_support'].values
    res = ctx['m15_resistance'].values

    sig = np.zeros(n, dtype=np.int8)
    last_sig = -10**9
    for i in range(2, n):
        if i - last_sig < cooldown:
            continue
        t = trend[i]
        if np.isnan(t):
            continue
        if t == 1 and not np.isnan(sup[i]):
            touched = low[i-1] <= sup[i] * (1 + near_tol)
            above = low[i-1] >= sup[i] * (1 - near_tol*2)  # واقعاً نزدیکِ سطح، نه خیلی زیرِ آن
            bounce = close[i] > openv[i] and close[i] > sup[i]
            if touched and above and bounce:
                sig[i] = 1
                last_sig = i
        elif t == -1 and not np.isnan(res[i]):
            touched = high[i-1] >= res[i] * (1 - near_tol)
            below = high[i-1] <= res[i] * (1 + near_tol*2)
            bounce = close[i] < openv[i] and close[i] < res[i]
            if touched and below and bounce:
                sig[i] = -1
                last_sig = i
    return sig


def backtest_struct(m5, sig, ctx, atr_arr, tp_mult, sl_buffer_mult, max_hold=60):
    """SL ساختاری (زیر/بالای سطح + بافرِ ATR)، TP = tp_mult × فاصلهٔ ریسک."""
    openv = m5['open'].values
    high = m5['high'].values
    low = m5['low'].values
    close = m5['close'].values
    sup = ctx['m15_support'].values
    res = ctx['m15_resistance'].values
    n = len(m5)
    trades, sl_dists = [], []
    i = 2
    while i < n - 1:
        s = sig[i]
        if s == 0 or np.isnan(atr_arr[i]) or atr_arr[i] <= 0:
            i += 1; continue
        entry_bar = i + 1
        entry = openv[entry_bar]
        a = atr_arr[i]
        if s == 1:
            sl = sup[i] - sl_buffer_mult * a
            risk = entry - sl
            if risk <= 0:
                i += 1; continue
            tp = entry + tp_mult * risk
        else:
            sl = res[i] + sl_buffer_mult * a
            risk = sl - entry
            if risk <= 0:
                i += 1; continue
            tp = entry - tp_mult * risk
        sl_dist = abs(entry - sl)
        exit_price = None; outcome = None; exit_bar = None
        for j in range(entry_bar, min(entry_bar + max_hold, n)):
            hi, lo = high[j], low[j]
            if s == 1:
                hit_sl = lo <= sl; hit_tp = hi >= tp
            else:
                hit_sl = hi >= sl; hit_tp = lo <= tp
            if hit_sl:
                exit_price = sl; outcome = 'loss'; exit_bar = j; break
            if hit_tp:
                exit_price = tp; outcome = 'win'; exit_bar = j; break
        if exit_price is None:
            exit_bar = min(entry_bar + max_hold - 1, n - 1)
            exit_price = close[exit_bar]
            outcome = 'win' if ((exit_price - entry) * s) > 0 else 'loss'
        raw = (exit_price - entry) * s - COST_PRICE
        trades.append({'pnl': raw, 'signal_bar': i, 'exit_bar': exit_bar, 'outcome': outcome})
        sl_dists.append(sl_dist)
        i = exit_bar + 1
    return pd.DataFrame(trades), np.array(sl_dists)


def evaluate(tr, sld):
    if len(tr) == 0:
        return None
    stats, eq = run_capital_backtest(tr, sld, initial_capital=INITIAL_CAPITAL,
                                     risk_pct=RISK_PCT, commission_per_lot=0.0,
                                     compounding=True, contract_size=CONTRACT)
    return stats


def half_split_eval(m5, sig, ctx, atr_arr, tp_mult, sl_buf, max_hold):
    n = len(m5); mid = n // 2
    tr, sld = backtest_struct(m5, sig, ctx, atr_arr, tp_mult, sl_buf, max_hold)
    if len(tr) == 0:
        return None, None, None
    full = evaluate(tr, sld)
    # both halves بر اساسِ signal_bar
    m1 = tr['signal_bar'] < mid
    h1 = evaluate(tr[m1].reset_index(drop=True), sld[m1.values]) if m1.sum() > 0 else None
    h2 = evaluate(tr[~m1].reset_index(drop=True), sld[(~m1).values]) if (~m1).sum() > 0 else None
    return full, h1, h2


if __name__ == '__main__':
    print("Loading XAUUSD M5 + M15 ...")
    m5 = load('XAUUSD', 'M5')
    m15 = load('XAUUSD', 'M15')
    ctx15 = build_m15_context(m15)
    ctx = map_m15_to_m5(m5, ctx15)
    atr_arr = atr_np(m5, 14)

    print("\n=== SWEEP (bounce-confirmed entry + structural SL) ===")
    best = None
    for near_tol in [0.0004, 0.0006, 0.0010]:
        for cooldown in [6, 12, 24]:
            sig = generate_signals_v2(m5, ctx, near_tol=near_tol, cooldown=cooldown)
            nsig = int((sig != 0).sum())
            if nsig < 30:
                continue
            for tp_mult in [1.5, 2.0, 3.0]:
                for sl_buf in [0.3, 0.6, 1.0]:
                    for max_hold in [60]:
                        full, h1, h2 = half_split_eval(m5, sig, ctx, atr_arr, tp_mult, sl_buf, max_hold)
                        if full is None:
                            continue
                        gate = (h1 and h2 and h1['net_profit'] > 0 and h2['net_profit'] > 0
                                and full['net_profit'] > 0 and not full['ruined'])
                        tag = "✅" if gate else "  "
                        line = (f"{tag} nt={near_tol} cd={cooldown} tp={tp_mult} slb={sl_buf} "
                                f"n={full['n_trades']} netP={full['net_profit']:+.0f}$ "
                                f"WR={full['win_rate']:.0f}% PF={full['profit_factor']:.2f} "
                                f"DD={full['max_dd_pct']:.0f}%")
                        if gate:
                            print(line)
                            if best is None or full['net_profit'] > best[0]['net_profit']:
                                best = (full, near_tol, cooldown, tp_mult, sl_buf, max_hold)
    print("\n=== BEST (gated) ===")
    if best:
        s, nt, cd, tp, slb, mh = best
        print(f"near_tol={nt} cooldown={cd} tp_mult={tp} sl_buf={slb} max_hold={mh}")
        print(f"netP={s['net_profit']:+.0f}$ n={s['n_trades']} WR={s['win_rate']:.1f}% "
              f"PF={s['profit_factor']:.2f} DD={s['max_dd_pct']:.1f}% Sharpe={s['sharpe']:.2f}")
    else:
        print("هیچ ترکیبی گیت‌ها را عبور نکرد.")
