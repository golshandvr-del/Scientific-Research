# -*- coding: utf-8 -*-
"""S986 — اسکنِ اکتشافیِ «شکستِ اکسترممِ شوک» (فقط نیمهٔ اول — مسیر C)
================================================================================
پیش‌ثبت: results/S986_PREREG_SHOCK_EXTREME_BREAK.md (کامیت ddd5c3d9، پیش از این فایل)

تعریفِ منجمدِ رویداد (عیناً از پیش‌ثبت):
  ATR21 EWM با شیفتِ ۱ (atr21[i-1]) برای شوک؛ ATR100 برای هندسهٔ براکت.
  کندلِ شوک i: high[i]-low[i] >= θ×ATR21[i-1]؛ جهت = sign(close[i]-open[i]) (بدنهٔ صفر ⇒ حذف). بدونِ ρ.
  پنجرهٔ مسلح i+1..i+W:
    LONG-trigger: اولین j با close[j] > high[i]   (شوکِ صعودی)
    SHORT-trigger: اولین j با close[j] < low[i]   (شوکِ نزولی)
    ابطال: close[j] < low[i] (صعودی) / close[j] > high[i] (نزولی) پیش از trigger ⇒ منسوخ. پایانِ پنجره ⇒ منسوخ.
    شوکِ جدید در پنجره ⇒ جانشینِ آرمینگِ قدیمی.
  اصلی = ادامه در جهتِ شکست؛ آینه = برعکس.
  کنترلِ P1 (فقط ابطال‌گر، نه داوری): ورود در closeِ همان کندل‌های شوک، بدونِ شرطِ شکست، همان هندسه.
  ورود در closeِ کندلِ trigger (شبیه‌ساز: openِ بعدی). allow_overlap=False. max_hold=32.

فضا: 2 θ × 2 W × 2 جهت × 2 SL_k × 2 RR = 32 بازو/کارت × 19 TF = 608.
اجرا:  python3 strategies/s986_shock_extreme_break_scan.py --tf M1
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

OUT = 'results/_s986'
ASSET = 'XAUUSD'

THETAS = (1.618, 2.618)            # شوک × ATR21[i-1]
WINDOWS = (3, 8)                   # پنجرهٔ مسلح (کندل)
GEOMS = tuple((k, rr) for k in (1.2, 1.8) for rr in (1.3, 1.6))  # TP>SL همیشه
MAX_HOLD = 32
ATR_SHOCK = 21
ATR_GEOM = 100
N_ARMS_CARD = len(THETAS) * len(WINDOWS) * 2 * len(GEOMS)  # 32


def atr_arr(df, p):
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    pc = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1.0 / p, adjust=False).mean().to_numpy()


def shock_candles(df, atr21, theta):
    """شوک‌ها با ATR علّی (شیفتِ ۱). خروجی: بولی shock، جهتِ بدنه."""
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    o = df['open'].to_numpy(float)
    c = df['close'].to_numpy(float)
    atr_prev = np.concatenate([[np.nan], atr21[:-1]])
    rng = h - l
    with np.errstate(invalid='ignore'):
        shock = (rng >= theta * atr_prev) & (rng > 0) & np.isfinite(atr_prev)
    shock[:ATR_GEOM + 1] = False                        # گرم‌شدن
    body_sgn = np.sign(c - o)
    shock &= body_sgn != 0
    return shock, body_sgn


def break_signals(df, shock, body_sgn, W):
    """رویدادهای شکستِ اکسترمم. خروجی: (long_trig, short_trig, immediate_long, immediate_short, stats)."""
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    n = len(c)
    lt = np.zeros(n, dtype=bool)
    st = np.zeros(n, dtype=bool)
    armed = None      # (i, dir, hi, lo, expires)
    n_shock = 0
    n_trig = 0
    n_invalid = 0
    n_expire = 0
    n_replace = 0
    for j in range(n):
        if armed is not None:
            i, d, hi, lo, exp_ = armed
            if d > 0:
                if c[j] > hi:
                    lt[j] = True; n_trig += 1; armed = None
                elif c[j] < lo:
                    n_invalid += 1; armed = None
            else:
                if c[j] < lo:
                    st[j] = True; n_trig += 1; armed = None
                elif c[j] > hi:
                    n_invalid += 1; armed = None
            if armed is not None and j >= exp_:
                n_expire += 1; armed = None
        if shock[j]:
            n_shock += 1
            if armed is not None:
                n_replace += 1
            armed = (j, int(body_sgn[j]), h[j], l[j], j + W)
    imm_l = shock & (body_sgn > 0)
    imm_s = shock & (body_sgn < 0)
    stats = dict(n_shock=n_shock, n_trig=n_trig, n_invalid=n_invalid,
                 n_expire=n_expire, n_replace=n_replace)
    return lt, st, imm_l, imm_s, stats


def binom_z(wins, n, p0):
    if n == 0:
        return 0.0
    se_ = np.sqrt(p0 * (1 - p0) / n)
    return ((wins / n) - p0) / se_ if se_ > 0 else 0.0


def _eval(df, ls, ss, sl_pip, tp_pip, cost_pip):
    t = se.simulate_trades(df, ls, ss, sl_pip, tp_pip, ASSET,
                           max_hold=MAX_HOLD, allow_overlap=False)
    n = len(t)
    if n == 0:
        return None
    wins = int((t['outcome'] == 'win').sum())
    wr = wins / n * 100.0
    be = (sl_pip + cost_pip) / (sl_pip + tp_pip) * 100.0
    return dict(n=n, wr=round(wr, 2), be=round(be, 2), lift=round(wr - be, 2),
                z=round(binom_z(wins, n, be / 100.0), 2),
                net_pip=round(float(t['pnl_pip'].sum()), 1))


def scan_card(tf, verbose=True):
    t0 = time.time()
    d = fd.load_fast(ASSET, tf)
    df_all = fd.as_dataframe(d)
    n_all = len(df_all)
    half = n_all // 2
    df = df_all.iloc[:half].reset_index(drop=True)   # 🔒 فقط نیمهٔ اول (مسیر C)
    src = d['src']
    assert 'mt5_full' in src, f'دادهٔ کامل نیست: {src}'
    if verbose:
        print(f'[{tf}] src={src}', flush=True)
        print(f'[{tf}] bars_total={n_all:,}  bars_search={len(df):,} (نیمهٔ اول — مسیر C)', flush=True)

    atr21 = atr_arr(df, ATR_SHOCK)
    a100 = atr_arr(df, ATR_GEOM)
    pip = se.ASSETS[ASSET]['pip']
    sl_base_pip = float(np.nanmedian(a100[ATR_GEOM:])) / pip
    cost_pip = se.ASSETS[ASSET]['spread_pip'] + 2.0 * se.ASSETS[ASSET]['slip_pip']

    rows = []
    controls = []      # P1: ورودِ فوری در close شوک (فقط ابطال‌گر — نه بازوی داوری)
    n_arms = 0
    for theta in THETAS:
        shock, body_sgn = shock_candles(df, atr21, theta)
        for W in WINDOWS:
            lt, st, imm_l, imm_s, stats = break_signals(df, shock, body_sgn, W)
            for mode in ('main', 'mirror'):
                ls, ss = (lt, st) if mode == 'main' else (st, lt)
                for sl_k, rr in GEOMS:
                    n_arms += 1
                    sl_pip = sl_base_pip * sl_k
                    tp_pip = sl_pip * rr
                    r = _eval(df, ls, ss, sl_pip, tp_pip, cost_pip)
                    if r is None or r['n'] < 30:
                        continue
                    r.update(theta=theta, W=W, mode=mode, sl_k=sl_k, rr=rr,
                             sl_pip=round(sl_pip, 2), tp_pip=round(tp_pip, 2), **stats)
                    rows.append(r)
            if verbose:
                print(f'[{tf}]   θ={theta} W={W} shocks={stats["n_shock"]} trig={stats["n_trig"]} '
                      f'invalid={stats["n_invalid"]} expire={stats["n_expire"]} '
                      f'replace={stats["n_replace"]}  ({time.time()-t0:.0f}s)', flush=True)
        # کنترلِ P1 برای این θ (مستقل از W) — follow در close شوک
        for sl_k, rr in GEOMS:
            sl_pip = sl_base_pip * sl_k
            tp_pip = sl_pip * rr
            r = _eval(df, imm_l, imm_s, sl_pip, tp_pip, cost_pip)
            if r is not None:
                r.update(theta=theta, sl_k=sl_k, rr=rr, kind='P1_control_immediate_follow')
                controls.append(r)
    rows.sort(key=lambda r: r['z'], reverse=True)
    out = dict(tf=tf, asset=ASSET, src=src, bars_total=n_all, bars_search=len(df),
               path='C (search=first half only)', n_arms=n_arms,
               declared_space=N_ARMS_CARD, sl_base_pip=round(sl_base_pip, 2),
               cost_pip=cost_pip, max_hold=MAX_HOLD, elapsed_s=round(time.time() - t0, 1),
               results=rows, p1_controls=controls)
    os.makedirs(OUT, exist_ok=True)
    with open(f'{OUT}/scan_{tf}.json', 'w') as f:
        json.dump(out, f, ensure_ascii=False)
    if verbose:
        print(f'[{tf}] arms={n_arms} valid(n>=30)={len(rows)} elapsed={out["elapsed_s"]}s', flush=True)
        print(f'[{tf}] ── ۱۰ بازوی برتر (بر z) ──', flush=True)
        for r in rows[:10]:
            print(f"  θ={r['theta']:<5} W={r['W']} {r['mode'][:4]:4s} slk={r['sl_k']} rr={r['rr']} "
                  f"n={r['n']:<5} wr={r['wr']:6.2f}% be={r['be']:5.2f}% "
                  f"lift={r['lift']:+6.2f}pp z={r['z']:+6.2f} net={r['net_pip']:+.0f}pip", flush=True)
        print(f'[{tf}] ── کنترلِ P1 (ورودِ فوری در close شوک، follow) ──', flush=True)
        for r in controls:
            print(f"  θ={r['theta']:<5} slk={r['sl_k']} rr={r['rr']} n={r['n']:<5} "
                  f"lift={r['lift']:+6.2f}pp z={r['z']:+6.2f}", flush=True)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--tf', default='M1')
    a = ap.parse_args()
    scan_card(a.tf)
