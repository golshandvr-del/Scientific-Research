# -*- coding: utf-8 -*-
"""S984 — اسکنِ اکتشافیِ «بازپس‌گیریِ بازِ روز» (فقط نیمهٔ اول — مسیر C)
================================================================================
پیش‌ثبت: results/S984_PREREG_DAILY_OPEN_RECLAIM.md (کامیت fdf04f52، پیش از این فایل)

تعریفِ منجمدِ رویداد (عیناً از پیش‌ثبت):
  مرزِ روز: شکافِ زمانی > دورهٔ اسمی + 1800s یا تغییرِ تاریخِ UTC (کنوانسیونِ s420 — هرگز hour==1).
  لنگر DO = openِ اولین کندلِ روز. ATR_day = ATR(100) کندلِ قبلِ شروعِ روز (منجمد؛ صفر نشت).
  گشت: بیشینهٔ high/low نسبت به DO در هر سو از آخرین رویداد؛ ریست پس از هر رویداد.
  رویداد در j (غیرِ اولِ روز): sign(close[j]−DO) ≠ sign(close[j−1]−DO)، فقط اگر
  گشتِ بیشینه در سمتِ قبلی ≥ q×ATR_day.
  اصلی: عبورِ صعودی ⇒ LONG، نزولی ⇒ SHORT (momentum). آینه: برعکس (fade).
  ورود در closeِ کندلِ عبور. allow_overlap=False.

فضا: 3 q × 2 جهت × 2 SL_k × 2 RR = 24 بازو/کارت × 19 TF = 456.
اجرا:  python3 strategies/s984_daily_open_reclaim_scan.py --tf M1
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

OUT = 'results/_s984'
ASSET = 'XAUUSD'

Q_EXC = (0.5, 1.3, 2.1)            # حداقلِ گشتِ قبلی ×ATR_day — عینِ پیش‌ثبت
GEOMS = tuple((k, rr) for k in (1.2, 1.8) for rr in (1.3, 1.6))  # TP>SL همیشه
MAX_HOLD = 64
ATR_P = 100
GAP_EXTRA_S = 1800                 # کنوانسیونِ s420
N_ARMS_CARD = len(Q_EXC) * 2 * len(GEOMS)  # 24


def atr_arr(df, p=ATR_P):
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    pc = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1.0 / p, adjust=False).mean().to_numpy()


def day_starts(df):
    """اندیس‌های شروعِ روزِ بروکر — کنوانسیونِ s420 (ایمن به DST، هرگز hour==1):
    شکافِ زمانی > دورهٔ اسمی + 1800s یا تغییرِ تاریخِ UTC."""
    t = df['time'].to_numpy()
    if np.issubdtype(t.dtype, np.datetime64):
        ts = t.astype('datetime64[s]').astype(np.int64)
    else:
        ts = t.astype(np.int64)
    gap = np.diff(ts)
    period = float(np.median(gap))
    dates = pd.to_datetime(ts, unit='s').date
    new_day = np.zeros(len(df), dtype=bool)
    new_day[0] = True
    new_day[1:] = (gap > period + GAP_EXTRA_S) | (dates[1:] != dates[:-1])
    return np.where(new_day)[0]


def reclaim_signals(df, a, q):
    """رویدادهای بازپس‌گیریِ DO. خروجی: (up_cross, dn_cross) بولی روی کندلِ عبور."""
    c = df['close'].to_numpy(float)
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    o = df['open'].to_numpy(float)
    n = len(c)
    up = np.zeros(n, dtype=bool)
    dn = np.zeros(n, dtype=bool)

    ds = day_starts(df)
    ds = ds[ds > ATR_P]  # گرم‌شدنِ ATR
    if len(ds) == 0:
        return up, dn
    bounds = list(ds) + [n]

    for di in range(len(ds)):
        d0, d_end = bounds[di], bounds[di + 1]
        do = o[d0]
        atr_d = float(a[d0 - 1])            # منجمد در شروعِ روز — صفر نشت
        if not np.isfinite(atr_d) or atr_d <= 0:
            continue
        need = q * atr_d
        exc_above = 0.0
        exc_below = 0.0
        for j in range(d0, d_end):
            # به‌روزرسانیِ گشت با اکسترممِ همین کندل
            if h[j] - do > exc_above:
                exc_above = h[j] - do
            if do - l[j] > exc_below:
                exc_below = do - l[j]
            if j == d0:
                continue                    # کندلِ اولِ روز: عبور تعریف نمی‌شود
            prev_d = c[j - 1] - do
            cur_d = c[j] - do
            if prev_d == 0.0 or cur_d == 0.0:
                continue
            if (prev_d > 0) == (cur_d > 0):
                continue
            if cur_d > 0:                   # عبورِ صعودی — سمتِ قبلی: زیر
                if exc_below >= need:
                    up[j] = True
                    exc_above = 0.0
                    exc_below = 0.0
            else:                           # عبورِ نزولی — سمتِ قبلی: بالا
                if exc_above >= need:
                    dn[j] = True
                    exc_above = 0.0
                    exc_below = 0.0
    return up, dn


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
    n_days = len(day_starts(df))

    rows = []
    n_arms = 0
    for q in Q_EXC:
        up, dn = reclaim_signals(df, a, q)
        n_evt = int(up.sum() + dn.sum())
        for mode in ('main', 'mirror'):
            if mode == 'main':
                ls, ss = up, dn
            else:
                ls, ss = dn, up
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
                rows.append(dict(q=q, mode=mode, sl_k=sl_k, rr=rr,
                                 sl_pip=round(sl_pip, 2), tp_pip=round(tp_pip, 2),
                                 n_events=n_evt, n=n, wr=round(wr, 2),
                                 be=round(be, 2), lift=round(lift, 2),
                                 z=round(z, 2), net_pip=round(net, 1)))
        if verbose:
            print(f'[{tf}]   q={q} events={n_evt}  ({time.time()-t0:.0f}s)', flush=True)
    rows.sort(key=lambda r: r['z'], reverse=True)
    out = dict(tf=tf, asset=ASSET, src=src, bars_total=n_all, bars_search=len(df),
               path='C (search=first half only)', n_arms=n_arms,
               declared_space=N_ARMS_CARD, n_days=n_days,
               sl_base_pip=round(sl_base_pip, 2), cost_pip=cost_pip,
               max_hold=MAX_HOLD, elapsed_s=round(time.time() - t0, 1),
               results=rows)
    os.makedirs(OUT, exist_ok=True)
    with open(f'{OUT}/scan_{tf}.json', 'w') as f:
        json.dump(out, f, ensure_ascii=False)
    if verbose:
        print(f'[{tf}] days={n_days} arms={n_arms} valid(n>=30)={len(rows)} elapsed={out["elapsed_s"]}s', flush=True)
        print(f'[{tf}] ── ۱۰ بازوی برتر (بر z) ──', flush=True)
        for r in rows[:10]:
            print(f"  q={r['q']:<4} {r['mode'][:4]:4s} slk={r['sl_k']} rr={r['rr']} "
                  f"n={r['n']:<6} wr={r['wr']:6.2f}% be={r['be']:5.2f}% "
                  f"lift={r['lift']:+6.2f}pp z={r['z']:+6.2f} net={r['net_pip']:+.0f}pip", flush=True)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--tf', default='M1')
    a = ap.parse_args()
    scan_card(a.tf)
