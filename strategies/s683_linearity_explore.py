# -*- coding: utf-8 -*-
"""
s683_linearity_explore.py — اکتشافِ S683 فقط روی **نیمهٔ اول** (مسیرِ C)
================================================================================
پیش‌ثبت: results/S683_PREREG_LINEARITY_GRIND.md (کامیت d77b027 — قبل از اجرا).

سیگنال: عبورِ R²ِ رگرسیونِ خطیِ close روی پنجرهٔ L از زیرِ θ به بالایِ θ
(لبهٔ ورود به حالتِ «خطی») ⇒ ورود در جهتِ شیبِ رگرسیون.
گریدِ قفل: L∈{13,21,34,55} × θ∈{0.618,0.786} × rr∈{1,1.5,2} = ۲۴ سلول.

هندسه: SL = 1.618×median(ATR34 نیمهٔ اول)، TP=rr×SL، mh جدولِ قفلِ S680.
نیمهٔ دوم هرگز لمس نمی‌شود.
"""
from __future__ import annotations

import gc
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import scalp_engine as se                    # noqa: E402
from tools import s434_fast_data as fd                   # noqa: E402

OUT_DIR = os.path.join(ROOT, 'results', '_s683_explore')

LS = (13, 21, 34, 55)
THETAS = (0.618, 0.786)
RRS = (1.0, 1.5, 2.0)

MAX_HOLD = {'M1': 34, 'M3': 34, 'M4': 34, 'M5': 34, 'M6': 21, 'M10': 21,
            'M12': 21, 'M15': 21, 'M20': 21, 'M30': 21, 'H1': 13, 'H2': 13,
            'H3': 13, 'H6': 13, 'H8': 13, 'H12': 13, 'D1': 8, 'W1': 8,
            'MN1': 5}


def atr_wilder(h, l, c, per: int) -> np.ndarray:
    n = len(c)
    tr = np.empty(n)
    tr[0] = h[0] - l[0]
    pc = c[:-1]
    tr[1:] = np.maximum(h[1:] - l[1:],
                        np.maximum(np.abs(h[1:] - pc), np.abs(l[1:] - pc)))
    out = np.empty(n)
    out[0] = tr[0]
    a = 1.0 / per
    for i in range(1, n):
        out[i] = out[i - 1] + a * (tr[i] - out[i - 1])
    return out


def rolling_linreg(c: np.ndarray, L: int):
    """شیب و R²ِ OLS روی پنجرهٔ [i-L+1 .. i] — علّی، O(n) با جمع‌های لغزان.

    x = 0..L-1 ثابت است ⇒ Sx, Sxx ثابت. Sy, Syy, Sxy لغزان.
    Sxy_i = Σ_k k·y[i-L+1+k]. با تعریفِ P_i = Σ y (پنجره) و Q_i = Σ (i-idx)·y
    ساده‌تر: Sxy = Σ (L-1-j)·y[i-j] برای j=0..L-1 ⇒ = (L-1)·P_i − Σ j·y[i-j].
    Σ j·y[i-j] را با بازگشت به‌روز می‌کنیم: T_i = T_{i-1} + P_{i-1} − L·y[i-L].
    """
    n = len(c)
    slope = np.full(n, np.nan)
    r2 = np.full(n, np.nan)
    if n < L:
        return slope, r2
    x = np.arange(L, dtype=np.float64)
    Sx = x.sum()
    Sxx = (x * x).sum()
    varx = Sxx - Sx * Sx / L
    cs = np.concatenate(([0.0], np.cumsum(c)))
    cs2 = np.concatenate(([0.0], np.cumsum(c * c)))
    # T_i = Σ_{j=0}^{L-1} j·y[i-j]
    i0 = L - 1
    win = c[0:L]
    T = float((np.arange(L - 1, -1, -1) * win).sum())   # j=L-1 برای y[0]
    for i in range(i0, n):
        P = cs[i + 1] - cs[i + 1 - L]
        Syy = cs2[i + 1] - cs2[i + 1 - L]
        if i > i0:
            # T_i = T_{i-1} + P_{i-1} − L·y[i-L]
            P_prev = cs[i] - cs[i - L]
            T = T + P_prev - L * c[i - L]
        Sxy = (L - 1) * P - T
        covxy = Sxy - Sx * P / L
        vary = Syy - P * P / L
        b = covxy / varx
        slope[i] = b
        r2[i] = (covxy * covxy) / (varx * vary) if vary > 1e-18 else 0.0
    return slope, r2


def _selftest():
    rng = np.random.default_rng(0)
    y = np.cumsum(rng.normal(size=300))
    for L in (13, 34):
        s, r = rolling_linreg(y, L)
        for i in (L - 1, 100, 299):
            w = y[i - L + 1:i + 1]
            x = np.arange(L)
            A = np.vstack([x, np.ones(L)]).T
            b, a = np.linalg.lstsq(A, w, rcond=None)[0]
            pred = a + b * x
            r2 = 1 - ((w - pred) ** 2).sum() / ((w - w.mean()) ** 2).sum()
            assert abs(b - s[i]) < 1e-8, (L, i, b, s[i])
            assert abs(r2 - r[i]) < 1e-8, (L, i, r2, r[i])
    print('[selftest] rolling_linreg == numpy lstsq ✓', flush=True)


def explore(tf: str, asset: str = 'XAUUSD') -> dict:
    t0 = time.time()
    d = fd.load_fast(asset, tf)
    src = d['src']
    df_full = fd.as_dataframe(d)
    del d
    gc.collect()
    n_full = len(df_full)
    n_half = n_full // 2
    df = df_full.iloc[:n_half].reset_index(drop=True)   # فقط نیمهٔ اول
    del df_full
    gc.collect()

    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)

    pip = se.ASSETS[asset]['pip']                        # BUG-PIPGUESS
    cost = se.ASSETS[asset]['spread_pip'] + 2 * se.ASSETS[asset]['slip_pip']

    a34 = atr_wilder(h, l, c, 34)
    sl = round(float(np.median(a34[100:]) / pip) * 1.618, 1)  # غیرگرد
    mh = MAX_HOLD[tf]
    warm = 100

    cells = []
    for L in LS:
        slope, r2 = rolling_linreg(c, L)
        for th in THETAS:
            lin = r2 >= th
            prev = np.concatenate(([False], lin[:-1]))
            edge = lin & ~prev
            long_sig = edge & (slope > 0)
            short_sig = edge & (slope < 0)
            long_sig[:warm] = False
            short_sig[:warm] = False
            nsig = int(long_sig.sum() + short_sig.sum())
            for rr in RRS:
                tp = round(rr * sl, 1)
                if nsig == 0:
                    cells.append(dict(L=L, th=th, rr=rr, n=0, skipped='no_sig'))
                    continue
                tr = se.simulate_trades(df, long_sig, short_sig, sl, tp,
                                        asset, max_hold=mh,
                                        allow_overlap=False)
                if tr is None or len(tr) == 0:
                    cells.append(dict(L=L, th=th, rr=rr, n=0,
                                      skipped='no_trades'))
                    continue
                pnl = tr['pnl_pip'].values
                n = len(pnl)
                wr = 100.0 * float((pnl > 0).mean())
                be = 100.0 * (sl + cost) / (sl + tp)
                lift = wr - be
                zsc = (wr - be) / max(1e-9,
                                      (100.0 * np.sqrt(be / 100 * (1 - be / 100)
                                                       / n)))
                dirv = tr['direction'].values
                nl = int((dirv == 'long').sum()) if dirv.dtype.kind in 'OU' \
                    else int((dirv > 0).sum())
                cells.append(dict(L=L, th=th, rr=rr, n=n, n_long=nl,
                                  n_sig=nsig,
                                  wr=round(wr, 2), be_wr=round(be, 2),
                                  lift_be=round(lift, 2),
                                  exp_pip=round(float(pnl.mean()), 3),
                                  z_screen=round(float(zsc), 2)))
    res = dict(asset=asset, tf=tf, src=src, n_full=n_full, n_half=n_half,
               sl_pip=sl, atr_per=34, sl_mult=1.618, max_hold=mh,
               cost_pip=cost, warm=warm,
               grid_cells=len(LS) * len(THETAS) * len(RRS),
               cells=cells, elapsed_s=round(time.time() - t0, 1))
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, f'explore_{tf}.json'), 'w',
              encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    best = max([x for x in cells if 'skipped' not in x],
               key=lambda x: x['z_screen'], default=None)
    print(f'[{tf}] done {res["elapsed_s"]}s sl={sl} best={best}', flush=True)
    del df
    gc.collect()
    return res


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--tfs', required=True)
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        _selftest()
    for tf in [t.strip() for t in a.tfs.split(',') if t.strip()]:
        try:
            explore(tf)
        except Exception as e:  # noqa: BLE001
            import traceback; traceback.print_exc()
            print(f'!! {tf}: {type(e).__name__}: {e}', flush=True)
        gc.collect()
    print('[explore batch done]', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
