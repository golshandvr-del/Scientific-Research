# -*- coding: utf-8 -*-
"""S980 — اسکنِ اکتشافیِ FVG Rebalance (فقط نیمهٔ اولِ داده — مسیر C)
================================================================================
پیش‌ثبت: results/S980_PREREG_FVG_REBALANCE_CONTINUATION.md (کامیتِ پیش از این فایل)

تعریفِ منجمدِ رویداد (عیناً از پیش‌ثبت):
  FVG صعودی در i:  high[i-2] < low[i]  → ناحیه [high[i-2], low[i]]
  FVG نزولی در i:  low[i-2]  > high[i] → ناحیه [high[i], low[i-2]]
  ورود: اولین کندلِ j>i که واردِ ناحیه شود؛ closeِ همان کندل؛ هر FVG یک بار.
  انقضا: EXPIRY کندل. فیلترِ اندازه: gap ≥ q×ATR(100).

فضای جست‌وجو (اعلام‌شده): 3 اندازه × 2 انقضا × 2 جهت × 4 هندسه = 48 بازو/کارت.
اجرا:  python3 strategies/s980_fvg_scan.py --tf M1
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se          # noqa: E402
from tools import s434_fast_data as fd         # noqa: E402

OUT = 'results/_s980'
ASSET = 'XAUUSD'

MIN_GAP_ATR = (0.15, 0.40, 0.85)   # غیررند
EXPIRIES = (21, 89)                # فیبوناچی
GEOMS = tuple((k, rr) for k in (1.2, 1.8) for rr in (1.3, 1.6))  # TP>SL همیشه
MAX_HOLD = 64
ATR_P = 100
N_ARMS_CARD = len(MIN_GAP_ATR) * len(EXPIRIES) * 2 * len(GEOMS)  # 48


def atr_arr(df, p=ATR_P):
    h = df['high'].to_numpy(float); l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    pc = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1.0 / p, adjust=False).mean().to_numpy()


def fvg_touch_signals(df, a, min_gap_atr, expiry):
    """سیگنالِ لمسِ FVG — برداریِ ناممکن نیست ولی حلقهٔ ساده کافی و شفاف است.

    خروجی: دو آرایهٔ بولی (touch_bull, touch_bear) روی کندلِ لمس.
    forward-safe: ناحیه در کندلِ i بسته‌شده تعریف می‌شود؛ لمس در j>i.
    """
    h = df['high'].to_numpy(float); l = df['low'].to_numpy(float)
    n = len(df)
    touch_bull = np.zeros(n, bool)
    touch_bear = np.zeros(n, bool)
    # فهرستِ فعال: (bar_created, top, bottom) — هر FVG یک بار مصرف می‌شود
    active_bull = []   # ناحیهٔ [bottom=high[i-2], top=low[i]] ؛ لمس: low[j] <= top
    active_bear = []   # ناحیهٔ [bottom=high[i], top=low[i-2]] ؛ لمس: high[j] >= bottom
    for j in range(2, n):
        # ۱) لمسِ نواحیِ فعال (قبل از ثبتِ ناحیهٔ جدیدِ همین کندل)
        if active_bull:
            keep = []
            touched = False
            for (b0, top, bot) in active_bull:
                if j - b0 > expiry:
                    continue
                if not touched and l[j] <= top:
                    touch_bull[j] = True
                    touched = True   # فقط یک ورود در هر کندل
                else:
                    keep.append((b0, top, bot))
            active_bull = keep
        if active_bear:
            keep = []
            touched = False
            for (b0, top, bot) in active_bear:
                if j - b0 > expiry:
                    continue
                if not touched and h[j] >= bot:
                    touch_bear[j] = True
                    touched = True
                else:
                    keep.append((b0, top, bot))
            active_bear = keep
        # ۲) ثبتِ FVG جدیدِ کندلِ j (لمسش فقط از j+1 ممکن است)
        gap_min = min_gap_atr * a[j]
        if l[j] - h[j - 2] >= gap_min:          # FVG صعودی
            active_bull.append((j, l[j], h[j - 2]))
        if l[j - 2] - h[j] >= gap_min:          # FVG نزولی
            active_bear.append((j, l[j - 2], h[j]))
    return touch_bull, touch_bear


def binom_z(wins, n, p0):
    if n == 0:
        return 0.0
    se_ = np.sqrt(p0 * (1 - p0) / n)
    return ((wins / n) - p0) / se_ if se_ > 0 else 0.0


def scan_card(tf, verbose=True):
    t0 = time.time()
    d = fd.load_fast(ASSET, tf)
    df_all = fd.as_dataframe(d)
    n_all = len(df_all)
    half = n_all // 2
    df = df_all.iloc[:half].reset_index(drop=True)   # 🔒 فقط نیمهٔ اول (مسیر C)
    src = d['src']
    if verbose:
        print(f'[{tf}] src={src}', flush=True)
        print(f'[{tf}] bars_total={n_all:,}  bars_search={len(df):,} (نیمهٔ اول — مسیر C)', flush=True)

    a = atr_arr(df)
    pip = se.ASSETS[ASSET]['pip']
    sl_base_pip = float(np.nanmedian(a[ATR_P:])) / pip
    cost_pip = se.ASSETS[ASSET]['spread_pip'] + 2.0 * se.ASSETS[ASSET]['slip_pip']

    rows = []
    n_arms = 0
    for q in MIN_GAP_ATR:
        for exp_ in EXPIRIES:
            tb, tr_ = fvg_touch_signals(df, a, q, exp_)
            n_evt = int(tb.sum() + tr_.sum())
            for mode in ('continuation', 'mirror'):
                # ادامه: FVG صعودی⇒LONG، نزولی⇒SHORT | آینه: برعکس
                if mode == 'continuation':
                    ls, ss = tb, tr_
                else:
                    ls, ss = tr_, tb
                for sl_k, rr in GEOMS:
                    n_arms += 1
                    sl_pip = sl_base_pip * sl_k
                    tp_pip = sl_pip * rr
                    t = se.simulate_trades(df, ls, ss, sl_pip, tp_pip, ASSET,
                                           max_hold=MAX_HOLD, allow_overlap=False)
                    n = len(t)
                    if n < 30:
                        continue
                    wins = int((t['outcome'] == 'win').sum())
                    wr = wins / n * 100.0
                    be = (sl_pip + cost_pip) / (sl_pip + tp_pip) * 100.0
                    lift = wr - be
                    z = binom_z(wins, n, be / 100.0)
                    net = float(t['pnl_pip'].sum())
                    rows.append(dict(q=q, expiry=exp_, mode=mode, sl_k=sl_k, rr=rr,
                                     sl_pip=round(sl_pip, 2), tp_pip=round(tp_pip, 2),
                                     n_events=n_evt, n=n, wr=round(wr, 2),
                                     be=round(be, 2), lift=round(lift, 2),
                                     z=round(z, 2), net_pip=round(net, 1)))
            if verbose:
                print(f'[{tf}]   q={q} expiry={exp_} events={n_evt}  ({time.time()-t0:.0f}s)', flush=True)
    rows.sort(key=lambda r: r['z'], reverse=True)
    out = dict(tf=tf, asset=ASSET, src=src, bars_total=n_all, bars_search=len(df),
               path='C (search=first half only)', n_arms=n_arms,
               declared_space=N_ARMS_CARD, sl_base_pip=round(sl_base_pip, 2),
               cost_pip=cost_pip, max_hold=MAX_HOLD,
               elapsed_s=round(time.time() - t0, 1), results=rows)
    os.makedirs(OUT, exist_ok=True)
    with open(f'{OUT}/scan_{tf}.json', 'w') as f:
        json.dump(out, f, ensure_ascii=False)
    if verbose:
        print(f'[{tf}] arms={n_arms} valid(n>=30)={len(rows)} elapsed={out["elapsed_s"]}s', flush=True)
        print(f'[{tf}] ── ۱۰ بازوی برتر (بر z) ──', flush=True)
        for r in rows[:10]:
            print(f"  q={r['q']:<5} exp={r['expiry']:<3} {r['mode'][:4]:4s} "
                  f"slk={r['sl_k']} rr={r['rr']} n={r['n']:<7} wr={r['wr']:6.2f}% "
                  f"be={r['be']:5.2f}% lift={r['lift']:+6.2f}pp z={r['z']:+7.2f} "
                  f"net={r['net_pip']:+.0f}pip", flush=True)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--tf', default='M1')
    a = ap.parse_args()
    scan_card(a.tf)
