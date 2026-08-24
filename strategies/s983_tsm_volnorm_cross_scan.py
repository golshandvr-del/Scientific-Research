# -*- coding: utf-8 -*-
"""S983 — اسکنِ اکتشافیِ «عبورِ مومنتومِ نرمال‌شده» TSM (فقط نیمهٔ اول — مسیر C)
================================================================================
پیش‌ثبت: results/S983_PREREG_TSM_VOLNORM_CROSS.md (کامیت f49285ff، پیش از این فایل)

تعریفِ منجمدِ رویداد (عیناً از پیش‌ثبت):
  m(t) = (close[t] − close[t−W]) / (ATR100[t] × √W)   — بدونِ هموارسازی/اسیلاتور.
  رویداد: عبورِ m از آستانهٔ ±θ (m[t−1] < θ ≤ m[t] یا قرینهٔ منفی).
  فقط اولین عبور در هر اپیزود: تا وقتی m به صفر برنگشته، عبورِ مجدد رویداد نیست.
  اصلی (TSM): عبورِ +θ ⇒ LONG، عبورِ −θ ⇒ SHORT (تداوم). آینه: برعکس (fade).
  ورود در closeِ کندلِ عبور. allow_overlap=False. یک ورود/کندل.

فضای جست‌وجو (اعلام‌شده): 2 پنجره × 3 آستانه × 2 جهت × 2 SL_k × 2 RR = 48 بازو/کارت
× 19 TF = 912 آزمایش. میلهٔ نویز: expected_max_z(912)≈3.23.
اجرا:  python3 strategies/s983_tsm_volnorm_cross_scan.py --tf M1
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

OUT = 'results/_s983'
ASSET = 'XAUUSD'

WINDOWS = (34, 89)                 # فیبوناچی — عینِ پیش‌ثبت
THETAS = (0.9, 1.6, 2.4)           # غیررند — عینِ پیش‌ثبت
GEOMS = tuple((k, rr) for k in (1.2, 1.8) for rr in (1.3, 1.6))  # TP>SL همیشه
MAX_HOLD = 64
ATR_P = 100
N_ARMS_CARD = len(WINDOWS) * len(THETAS) * 2 * len(GEOMS)  # 48


def atr_arr(df, p=ATR_P):
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    pc = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1.0 / p, adjust=False).mean().to_numpy()


def tsm_measure(c, a, w):
    """m(t) = Δclose(W) / (ATR100 × √W). NaN در گرم‌شدن."""
    n = len(c)
    m = np.full(n, np.nan)
    dc = c[w:] - c[:-w]
    denom = a[w:] * np.sqrt(float(w))
    with np.errstate(divide='ignore', invalid='ignore'):
        m[w:] = np.where(denom > 0, dc / denom, np.nan)
    m[:max(w, ATR_P)] = np.nan          # گرم‌شدنِ کاملِ ATR و پنجره
    return m


def cross_signals(m, theta):
    """اولین عبورِ ±θ در هر اپیزود (اپیزود با بازگشتِ m به صفر ریست می‌شود).
    خروجی: (up_cross, dn_cross) بولی روی کندلِ عبور."""
    n = len(m)
    up = np.zeros(n, dtype=bool)
    dn = np.zeros(n, dtype=bool)
    armed_up = True    # آیا اپیزودِ مثبتِ جدید مجاز است؟
    armed_dn = True
    for j in range(1, n):
        mj = m[j]
        mp = m[j - 1]
        if not (np.isfinite(mj) and np.isfinite(mp)):
            continue
        # ریستِ اپیزود: بازگشتِ m به صفر (تغییرِ علامت یا صفر)
        if mj <= 0.0:
            armed_up = True
        if mj >= 0.0:
            armed_dn = True
        if armed_up and mp < theta <= mj:
            up[j] = True
            armed_up = False
        if armed_dn and mp > -theta >= mj:
            dn[j] = True
            armed_dn = False
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
    c = df['close'].to_numpy(float)
    pip = se.ASSETS[ASSET]['pip']
    sl_base_pip = float(np.nanmedian(a[ATR_P:])) / pip
    cost_pip = se.ASSETS[ASSET]['spread_pip'] + 2.0 * se.ASSETS[ASSET]['slip_pip']

    rows = []
    n_arms = 0
    for w in WINDOWS:
        m = tsm_measure(c, a, w)
        for theta in THETAS:
            up, dn = cross_signals(m, theta)
            n_evt = int(up.sum() + dn.sum())
            for mode in ('main', 'mirror'):
                # اصلی (TSM تداوم): +θ⇒LONG، −θ⇒SHORT | آینه (fade): برعکس
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
                    rows.append(dict(w=w, theta=theta, mode=mode, sl_k=sl_k, rr=rr,
                                     sl_pip=round(sl_pip, 2), tp_pip=round(tp_pip, 2),
                                     n_events=n_evt, n=n, wr=round(wr, 2),
                                     be=round(be, 2), lift=round(lift, 2),
                                     z=round(z, 2), net_pip=round(net, 1)))
            if verbose:
                print(f'[{tf}]   W={w} θ={theta} events={n_evt}  ({time.time()-t0:.0f}s)', flush=True)
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
            print(f"  W={r['w']:<3} θ={r['theta']:<4} {r['mode'][:4]:4s} "
                  f"slk={r['sl_k']} rr={r['rr']} n={r['n']:<6} wr={r['wr']:6.2f}% "
                  f"be={r['be']:5.2f}% lift={r['lift']:+6.2f}pp z={r['z']:+6.2f} "
                  f"net={r['net_pip']:+.0f}pip", flush=True)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--tf', default='M1')
    a = ap.parse_args()
    scan_card(a.tf)
