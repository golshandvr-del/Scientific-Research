# -*- coding: utf-8 -*-
"""
s146_mtf_scalp_realcost.py — بازآزماییِ MTF Structure-Gated Scalp با هزینهٔ واقعیِ کاربر
========================================================================================
پاسخِ مستقیم به User Note (نشستِ ۲۰۲۶-۰۷):
  «اگر اطلاعاتِ فعلی برای تستِ استراتژی‌ها اشتباه بوده، اصلاحش کن. برای استراتژیِ
   خودت هم همین را اعمال کن.»

تفاوت با s145d:
  • هزینه از engine/market_spec.py خوانده می‌شود (اسپردِ واقعیِ ۰.۴۰$/اونس = 40$/لات).
  • کمیسیونِ جدا = ۰ (کاربر کمیسیونِ جدا ندارد ⇒ رفعِ دوباره‌شماریِ ۷$/لات).
  • هم LONG و هم SHORT آزموده می‌شود (تصحیحِ ادعایِ نادرستِ قبلی دربارهٔ short).

منطق پایه همان s145d است: روند و breakout روی زمینهٔ M15 گیت می‌شود، اجرا روی M5.
"""
import os
import sys
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine.capital_engine import run_capital_backtest
from engine.market_spec import get_spec
from strategies.s145_mtf_structure_scalp import (
    load, ema_np, atr_np, build_m15_context, map_m15_to_m5)
from strategies.s145c_mtf_breakout_long import build_trendstr

SPEC = get_spec('XAUUSD')
PIP = SPEC['pip']
CONTRACT = SPEC['contract_size']
COST_PRICE = SPEC['cost_price']          # 0.40$/اونس (هزینهٔ واقعی)
COMMISSION = SPEC['commission_per_lot']  # 0.0
INITIAL_CAPITAL = 10000.0
RISK_PCT = 1.0


def gen_breakout(m5, ctx, direction, lookback=40, cooldown=24, ts=None, ts_thr=None):
    """breakout در جهتِ روندِ M15. direction=+1 فقط long, -1 فقط short, 0 هر دو."""
    n = len(m5)
    close = m5['close'].values; openv = m5['open'].values
    high = m5['high'].values; low = m5['low'].values
    trend = ctx['m15_trend'].values
    sig = np.zeros(n, dtype=np.int8)
    last = -10**9
    for i in range(lookback, n - 1):
        if i - last < cooldown:
            continue
        t = trend[i]
        if np.isnan(t):
            continue
        # فیلترِ قدرتِ روند
        if ts is not None and ts_thr is not None:
            if np.isnan(ts[i]) or abs(ts[i]) < ts_thr:
                continue
        if t == 1 and direction in (0, 1):
            if close[i] > high[i-lookback:i].max() and close[i] > openv[i]:
                sig[i] = 1; last = i
        elif t == -1 and direction in (0, -1):
            if close[i] < low[i-lookback:i].min() and close[i] < openv[i]:
                sig[i] = -1; last = i
    return sig


def backtest_trail(m5, sig, atr_arr, sl_mult, be_trig, trail_mult, max_hold):
    """خروجِ trailing «بگذار بردها بدوند» برای هر دو جهت، با هزینهٔ واقعی."""
    openv = m5['open'].values; high = m5['high'].values
    low = m5['low'].values; close = m5['close'].values
    n = len(m5)
    idx = np.where(sig != 0)[0]
    trades = []; sl_dists = []
    for i in idx:
        eb = i + 1
        if eb >= n:
            continue
        s = sig[i]; entry = openv[eb]; a = atr_arr[i]
        if a <= 0 or np.isnan(a):
            continue
        if s == 1:
            sl = entry - sl_mult * a
            be_level = entry + be_trig * a
            extreme = entry
        else:
            sl = entry + sl_mult * a
            be_level = entry - be_trig * a
            extreme = entry
        sl_dist = abs(entry - sl)
        xb = min(eb + max_hold, n - 1)
        ep = close[xb]; oc = 'loss'
        for j in range(eb, min(eb + max_hold, n)):
            hi = high[j]; lo = low[j]
            if s == 1:
                if lo <= sl:
                    ep = sl; oc = 'win' if sl >= entry else 'loss'; xb = j; break
                extreme = max(extreme, hi)
                if extreme >= be_level:
                    sl = max(sl, entry + 0.1 * a)
                    sl = max(sl, extreme - trail_mult * a)
            else:
                if hi >= sl:
                    ep = sl; oc = 'win' if sl <= entry else 'loss'; xb = j; break
                extreme = min(extreme, lo)
                if extreme <= be_level:
                    sl = min(sl, entry - 0.1 * a)
                    sl = min(sl, extreme + trail_mult * a)
        else:
            ep = close[min(eb + max_hold, n - 1)]
            oc = 'win' if (ep - entry) * s > 0 else 'loss'
        raw = (ep - entry) * s - COST_PRICE     # هزینهٔ واقعی
        trades.append({'pnl': raw, 'signal_bar': i, 'exit_bar': xb, 'outcome': oc})
        sl_dists.append(sl_dist)
    return pd.DataFrame(trades), np.array(sl_dists)


def ev(trades, sl_dist):
    if trades is None or len(trades) == 0:
        return None
    stats, _ = run_capital_backtest(
        trades, sl_dist, initial_capital=INITIAL_CAPITAL,
        risk_pct=RISK_PCT, commission_per_lot=COMMISSION,  # کمیسیون=۰
        contract_size=CONTRACT)
    return stats


def wf_folds(trades, sl_dist, n_bars, k=4):
    edges = [int(n_bars * j / k) for j in range(k + 1)]
    out = []
    sb = trades['signal_bar'].values
    for j in range(k):
        m = (sb >= edges[j]) & (sb < edges[j+1])
        if m.sum() == 0:
            out.append(0.0); continue
        s = ev(trades[m].reset_index(drop=True), sl_dist[m])
        out.append(s['net_profit'] if s else 0.0)
    return out


if __name__ == '__main__':
    print("Loading XAUUSD M5 + M15 (هزینهٔ واقعیِ کاربر) ...")
    print(f"COST_PRICE={COST_PRICE:.2f}$/اونس ({COST_PRICE*CONTRACT:.0f}$/لات)  "
          f"commission={COMMISSION:.1f}$/لات")
    m5 = load('XAUUSD', 'M5'); m15 = load('XAUUSD', 'M15')
    ctx15 = build_m15_context(m15); ctx = map_m15_to_m5(m5, ctx15)
    atr = atr_np(m5, 14)
    ts = build_trendstr(m5, m15)
    n = len(m5); mid = n // 2
    ts_thr = np.nanquantile(np.abs(ts[np.isfinite(ts)]), 0.5)

    print("\n=== بازآزماییِ بهترین کانفیگِ s145 (lb40 cd24 sl3 be2 trail3 mh240) با هزینهٔ واقعی ===")
    for direction, name in [(1, 'LONG-only'), (-1, 'SHORT-only'), (0, 'BOTH')]:
        sig = gen_breakout(m5, ctx, direction, 40, 24, ts=ts, ts_thr=ts_thr)
        tr, sld = backtest_trail(m5, sig, atr, 3.0, 2.0, 3.0, 240)
        s = ev(tr, sld)
        if s is None:
            print(f"{name}: بدونِ معامله"); continue
        m1 = tr['signal_bar'] < mid
        h1 = ev(tr[m1].reset_index(drop=True), sld[m1.values]) if m1.sum() else None
        h2 = ev(tr[~m1].reset_index(drop=True), sld[(~m1).values]) if (~m1).sum() else None
        folds = wf_folds(tr, sld, n)
        fs = ",".join(f"{f:+.0f}" for f in folds)
        print(f"{name:11s}: netP={s['net_profit']:+.0f}$ n={s['n_trades']} "
              f"WR={s['win_rate']:.0f}% PF={s['profit_factor']:.2f} "
              f"DD={s['max_dd_pct']:.0f}% h1={h1['net_profit'] if h1 else 0:+.0f} "
              f"h2={h2['net_profit'] if h2 else 0:+.0f} folds=[{fs}]")
