# -*- coding: utf-8 -*-
"""S982 — اسکنِ اکتشافیِ «بازپس‌گیریِ بازِ هفته» (فقط نیمهٔ اول — مسیر C)
================================================================================
پیش‌ثبت: results/S982_PREREG_WEEKLY_OPEN_RECLAIM.md (کامیت 35fdc49c، پیش از این فایل)

تعریفِ منجمد (عیناً از پیش‌ثبت):
  شروعِ هفته: فاصلهٔ زمانی با کندلِ قبل > 40000s ⇒ لنگر WO = openِ همان کندل.
  ATR_wk = ATR(100) در لحظهٔ شروعِ هفته (منجمد در طولِ هفته).
  رویداد: عبورِ close از WO (تغییرِ علامتِ close−WO نسبت به کندلِ قبل)،
  فقط اگر از آخرین عبور، بیشینهٔ گشت در سمتِ قبلی ≥ q×ATR_wk بوده باشد.
  اصلی: عبورِ صعودی⇒LONG، نزولی⇒SHORT (momentum) | آینه: برعکس (fade).
  پس از رویداد، گشت ریست. ورود در closeِ کندلِ عبور. یک ورود/کندل.

فضا: 3 گشت × 2 جهت × 4 هندسه = 24 بازو/کارت.
اجرا:  python3 strategies/s982_weekly_open_reclaim_scan.py --tf M1
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

OUT = 'results/_s982'
ASSET = 'XAUUSD'

EXC_Q = (0.5, 1.3, 2.1)           # حداقلِ گشتِ قبلی × ATR_wk — غیررند، عینِ پیش‌ثبت
GEOMS = tuple((k, rr) for k in (1.2, 1.8) for rr in (1.3, 1.6))  # TP>SL همیشه
MAX_HOLD = 64
ATR_P = 100
WEEK_GAP_S = 40000.0
N_ARMS_CARD = len(EXC_Q) * 2 * len(GEOMS)  # 24


def atr_arr(df, p=ATR_P):
    h = df['high'].to_numpy(float); l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    pc = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1.0 / p, adjust=False).mean().to_numpy()


def reclaim_signals(df, a, q):
    """رویدادِ بازپس‌گیریِ WO با فیلترِ گشتِ قبلی.

    خروجی: (cross_up, cross_dn) بولی — عبورِ صعودی/نزولیِ close از WO با گشتِ کافی.
    forward-safe: WO = openِ کندلِ اولِ هفته (در openِ همان کندل معلوم)؛
    ATR_wk از کندلِ قبل از شروعِ هفته (a[i-1])؛ رویداد بر مبنای closeِ j و j−1.
    """
    t = df['time'].to_numpy(float)   # یونیکس‌ثانیه (تأییدشده از fd.as_dataframe)
    c = df['close'].to_numpy(float)
    o = df['open'].to_numpy(float)
    n = len(df)
    cross_up = np.zeros(n, bool)
    cross_dn = np.zeros(n, bool)
    wo = np.nan
    atr_wk = np.nan
    max_exc = 0.0      # بیشینهٔ گشت در سمتِ فعلی از آخرین عبور/شروع (به واحدِ قیمت)
    prev_side = 0      # علامتِ close−WO کندلِ قبل
    for j in range(1, n):
        if t[j] - t[j - 1] > WEEK_GAP_S:
            wo = o[j]
            atr_wk = a[j - 1] if a[j - 1] > 0 else np.nan
            max_exc = 0.0
            prev_side = 0   # هفتهٔ نو؛ سمتِ قبلی از closeِ همین کندل تعیین می‌شود
        if not np.isfinite(wo) or not np.isfinite(atr_wk):
            continue
        side = 1 if c[j] > wo else (-1 if c[j] < wo else 0)
        if side != 0 and prev_side != 0 and side != prev_side:
            # عبور رخ داد — شرطِ گشتِ قبلی
            if max_exc >= q * atr_wk:
                if side > 0:
                    cross_up[j] = True
                else:
                    cross_dn[j] = True
            max_exc = abs(c[j] - wo)   # ریست: گشتِ سمتِ جدید از همین‌جا
        else:
            max_exc = max(max_exc, abs(c[j] - wo))
        if side != 0:
            prev_side = side
    return cross_up, cross_dn


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
    for q in EXC_Q:
        cu, cd = reclaim_signals(df, a, q)
        n_evt = int(cu.sum() + cd.sum())
        for mode in ('main', 'mirror'):
            if mode == 'main':      # momentum: up⇒LONG, dn⇒SHORT
                ls, ss = cu, cd
            else:                   # fade
                ls, ss = cd, cu
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
               declared_space=N_ARMS_CARD, sl_base_pip=round(sl_base_pip, 2),
               cost_pip=cost_pip, max_hold=MAX_HOLD,
               elapsed_s=round(time.time() - t0, 1), results=rows)
    os.makedirs(OUT, exist_ok=True)
    with open(f'{OUT}/scan_{tf}.json', 'w') as f:
        json.dump(out, f, ensure_ascii=False)
    if verbose:
        print(f'[{tf}] arms={n_arms} valid(n>=30)={len(rows)} elapsed={out["elapsed_s"]}s', flush=True)
        for r in rows[:8]:
            print(f"  q={r['q']:<4} {r['mode'][:4]:4s} slk={r['sl_k']} rr={r['rr']} "
                  f"n={r['n']:<6} wr={r['wr']:6.2f}% be={r['be']:5.2f}% "
                  f"lift={r['lift']:+6.2f}pp z={r['z']:+6.2f} net={r['net_pip']:+.0f}pip", flush=True)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--tf', default='M1')
    a = ap.parse_args()
    scan_card(a.tf)
