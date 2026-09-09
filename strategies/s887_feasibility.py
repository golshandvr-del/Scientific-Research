#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S887 — امکان‌سنجی «شوک خط‌راست» (Straight-Line Shock) — فقط نیمهٔ اول، فقط شمارش.

رویداد: کندل TF درشت با range ≥ θ×ATR21[t−1] (لنگر بزرگی — اثبات‌شده در S965/S919)
+ گیت مسیر درون‌کندلی: از زیرکندل‌های M15 همان بازه، کارایی مسیر
    eff = |close_T − open_T| / Σ|Δclose_sub|   (Kaufman-style، اما روی مسیرِ واقعیِ درونِ کندل)
eff ≥ φ ⇒ مسیر یکنوا (سفارش‌های آگاهانهٔ یک‌سویه) ؛ eff پایین ⇒ زیگزاگ (نویز/نقدینگی).
جهت: follow (بدنه). زیرکندل‌ها به بازهٔ [t_open, t_open+TF) نگاشت می‌شوند (فقط اطلاعات
تا بستهٔ کندل t — بدون نگاه به آینده). هیچ شبیه‌سازی معامله‌ای در این فایل نیست.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from tools import s434_fast_data as fd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUB_TF = 'M15'


def atr_prev(high, low, close, p=21):
    """ATR وایلدر (ساده: میانگین غلتان TR) — مقدار در t از کندل‌های ≤ t−1 (علّی)."""
    n = len(high)
    pc = np.empty(n); pc[0] = close[0]; pc[1:] = close[:-1]
    tr = np.maximum(high - low, np.maximum(np.abs(high - pc), np.abs(low - pc)))
    atr = np.full(n, np.nan)
    cs = np.cumsum(tr)
    atr[p:] = (cs[p:] - cs[:-p]) / p          # میانگین tr[t-p+1..t]
    out = np.full(n, np.nan); out[1:] = atr[:-1]   # شیفت یک کندل → علّی
    return out


def path_efficiency(t_open, tf_minutes, sub_time, sub_open, sub_close, open_T, close_T):
    """برای هر کندل درشت، eff = |close_T−open_T| / Σ|Δclose زیرکندل‌ها| (اولین Δ نسبت به open_T).
    NaN اگر کمتر از ۲ زیرکندل در بازه."""
    n = len(t_open)
    eff = np.full(n, np.nan); nsub = np.zeros(n, dtype=int)
    end = t_open + tf_minutes * 60
    lo = np.searchsorted(sub_time, t_open, side='left')
    hi = np.searchsorted(sub_time, end, side='left')
    for i in range(n):
        a, b = lo[i], hi[i]
        k = b - a
        nsub[i] = k
        if k < 2:
            continue
        c = sub_close[a:b]
        path = abs(c[0] - open_T[i]) + np.abs(np.diff(c)).sum()
        if path > 0:
            eff[i] = abs(close_T[i] - open_T[i]) / path
    return eff, nsub


def straight_shock_signals(d_big, d_sub, tf, theta, phi, rho_min=0.0):
    """برمی‌گرداند (long_sig, short_sig, eff, shock_mask) روی کندل‌های درشت."""
    h, l, c, o, t = d_big['high'], d_big['low'], d_big['close'], d_big['open'], d_big['time']
    atr = atr_prev(h, l, c, 21)
    rng = h - l
    shock = rng >= theta * atr
    eff, nsub = path_efficiency(t, fd.TF_MINUTES[tf], d_sub['time'], d_sub['open'],
                                d_sub['close'], o, c)
    ok = shock & (eff >= phi) & (nsub >= 2)
    if rho_min > 0:
        with np.errstate(divide='ignore', invalid='ignore'):
            rho = np.where(rng > 0, np.abs(c - o) / rng, 0.0)
        ok &= rho >= rho_min
    ls = ok & (c > o); ss = ok & (c < o)
    return ls, ss, eff, shock


def main():
    d_sub_full = fd.load_fast('XAUUSD', SUB_TF)
    assert 'mt5_full' in d_sub_full['src'], f'E-16 trap: {d_sub_full["src"]}'
    out = {}
    for tf in ['H1', 'H2', 'H4', 'H6', 'H8', 'H12', 'D1']:
        d = fd.load_fast('XAUUSD', tf)
        assert 'mt5_full' in d['src'], f'E-16 trap: {d["src"]}'
        n = len(d['close']); half = n // 2
        big = {k: np.asarray(d[k][:half], dtype=np.float64) for k in ('time', 'open', 'high', 'low', 'close')}
        t_end = big['time'][-1] + fd.TF_MINUTES[tf] * 60
        m = d_sub_full['time'] < t_end
        sub = {k: np.asarray(d_sub_full[k][m], dtype=np.float64) for k in ('time', 'open', 'close')}
        yrs = (big['time'][-1] - big['time'][0]) / (365.25 * 86400)
        res = {}
        for th in [1.618, 2.618]:
            for ph in [0.0, 0.5, 0.618, 0.786]:
                ls, ss, eff, shock = straight_shock_signals(big, sub, tf, th, ph)
                res[f'th{th}_phi{ph}'] = {'events': int(ls.sum() + ss.sum()), 'long': int(ls.sum()),
                                         'short': int(ss.sum()), 'per_year': round((ls.sum() + ss.sum()) / yrs, 1)}
        e = eff[np.isfinite(eff)]
        res['eff_quantiles_all_bars'] = {q: round(float(np.quantile(e, q)), 3) for q in (0.25, 0.5, 0.75, 0.9)}
        es = eff[shock & np.isfinite(eff)]
        res['eff_median_shock_bars'] = round(float(np.median(es)), 3) if len(es) else None
        out[tf] = res
        print(tf, json.dumps(res), flush=True)
    with open(os.path.join(ROOT, 'results', '_s887_feasibility.json'), 'w') as f:
        json.dump(out, f, indent=1)


if __name__ == '__main__':
    main()
