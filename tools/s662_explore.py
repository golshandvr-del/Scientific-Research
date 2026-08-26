# -*- coding: utf-8 -*-
"""
s662_explore.py — اسکنر اکتشافی S662 (فقط نیمهٔ اول — مسیر C)
================================================================================
پیش‌ثبت حاکم: results/S662_PREREG_SUPERTREND_FLIP_CONTINUATION_XAUUSD.md

سیگنال = رویداد flip سوپرترند (ماشین حالت تریلینگ ATR — تعریف کلاسیک Seban):
  flip به +1 ⇒ LONG در open کندل بعد؛ flip به −1 ⇒ SHORT. (ذاتاً لبه‌ای)

شبکهٔ قفل‌شده: TF∈{H3,H6,H8,H12,D1} × p∈{10,21} × m∈{2.0,3.0} = 20 بازو.
هندسهٔ ثابت: RR=1.0 (TP=SL)، SL=1.618×میانهٔ ATR34 نیمهٔ اول، max_hold=55.
"""
from __future__ import annotations

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

try:
    from numba import njit
    HAVE_NUMBA = True
except Exception:                                        # pragma: no cover
    HAVE_NUMBA = False

OUT = os.path.join(ROOT, 'results', '_scan_S662')
os.makedirs(OUT, exist_ok=True)

PERIODS = (10, 21)
MULTS = (2.0, 3.0)
RR = 1.0
SL_MULT = 1.618
ATR_P = 34
MAX_HOLD = 55
WARMUP = 250
K_UNC = 300
SEED = 20260817

TFS = ['H3', 'H6', 'H8', 'H12', 'D1']
ASSET = 'XAUUSD'


def atr_wilder(h, l, c, period):
    prev_c = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    out = np.empty_like(tr)
    out[0] = tr[0]
    alpha = 1.0 / period
    for i in range(1, len(tr)):
        out[i] = out[i - 1] + alpha * (tr[i] - out[i - 1])
    return out


def _supertrend_py(h, l, c, atr, m):
    """ماشین حالت سوپرترند کلاسیک (ratcheting علّی). خروجی trend∈{+1,−1}."""
    n = len(c)
    hl2 = (h + l) / 2.0
    ub = hl2 + m * atr          # باند بالا خام
    lb = hl2 - m * atr          # باند پایین خام
    fub = np.empty(n)           # باند بالا نهایی (ratchet)
    flb = np.empty(n)
    trend = np.empty(n, np.int8)
    fub[0] = ub[0]
    flb[0] = lb[0]
    trend[0] = 1
    for i in range(1, n):
        # ratcheting: باند فقط سخت می‌شود مگر close قبلی آن را شکسته باشد
        if ub[i] < fub[i - 1] or c[i - 1] > fub[i - 1]:
            fub[i] = ub[i]
        else:
            fub[i] = fub[i - 1]
        if lb[i] > flb[i - 1] or c[i - 1] < flb[i - 1]:
            flb[i] = lb[i]
        else:
            flb[i] = flb[i - 1]
        # flip با عبور close از باند فعال
        if trend[i - 1] == 1:
            trend[i] = -1 if c[i] < flb[i] else 1
        else:
            trend[i] = 1 if c[i] > fub[i] else -1
    return trend


if HAVE_NUMBA:
    _supertrend = njit(cache=True)(_supertrend_py)
else:
    _supertrend = _supertrend_py


def _wr(t):
    if t is None or len(t) == 0:
        return None
    return float((t['pnl_pip'].values > 0).mean())


def scan_tf(tf: str) -> dict:
    t0 = time.time()
    d = fd.load_fast(ASSET, tf)
    src = d['src']
    n = len(d['close'])
    half = n // 2
    import pandas as pd
    o = np.ascontiguousarray(d['open'][:half], dtype=np.float64)
    h = np.ascontiguousarray(d['high'][:half], dtype=np.float64)
    l = np.ascontiguousarray(d['low'][:half], dtype=np.float64)
    c = np.ascontiguousarray(d['close'][:half], dtype=np.float64)
    del d
    dfe = pd.DataFrame({'open': o, 'high': h, 'low': l, 'close': c})
    pip = se.ASSETS[ASSET]['pip']
    ne = len(dfe)

    atr34 = atr_wilder(h, l, c, ATR_P)
    sl_pip = float(SL_MULT * np.median(atr34[WARMUP:] / pip))
    tp_pip = sl_pip * RR

    valid = np.zeros(ne, bool)
    valid[WARMUP:ne - MAX_HOLD - 1] = True
    vidx = np.flatnonzero(valid)
    rng = np.random.default_rng(SEED)

    # خط مبنای بی‌قید غربالگری
    wrs = []
    z = np.zeros(ne, bool)
    for _ in range(K_UNC):
        pick = rng.choice(vidx, size=min(200, len(vidx)), replace=False)
        m_ = np.zeros(ne, bool)
        m_[pick] = True
        tr = se.simulate_trades(dfe, m_, z, sl_pip, tp_pip, ASSET,
                                max_hold=MAX_HOLD, allow_overlap=True)
        w = _wr(tr)
        if w is not None:
            wrs.append(w)
    unc = dict(mean=float(np.mean(wrs)), sd=float(np.std(wrs)),
               hi=float(np.max(wrs)), k=len(wrs))

    cells = []
    for p in PERIODS:
        atrp = atr_wilder(h, l, c, p)
        for m in MULTS:
            trend = _supertrend(h, l, c, atrp, m)
            up = trend == 1
            le = up & ~np.concatenate(([True], up[:-1]))    # flip به +1
            dn = trend == -1
            sh = dn & ~np.concatenate(([False], dn[:-1]))   # flip به −1
            le &= valid
            sh &= valid
            tr = se.simulate_trades(dfe, le, sh, sl_pip, tp_pip, ASSET,
                                    max_hold=MAX_HOLD, allow_overlap=False)
            ncell = 0 if tr is None else len(tr)
            row = dict(p=p, m=m, rr=RR, sl_pip=sl_pip, tp_pip=tp_pip,
                       n=ncell, n_sig_long=int(le.sum()),
                       n_sig_short=int(sh.sum()))
            if ncell >= 10:
                w = _wr(tr)
                u = unc['mean']
                lift = (w - u) * 100.0
                se_bin = np.sqrt(max(u * (1 - u), 1e-9) / ncell)
                zb = (w - u) / se_bin
                dl = tr['direction'].values
                nl = int((dl == 'long').sum())
                ns = ncell - nl
                wl = (float((tr['pnl_pip'].values[dl == 'long'] > 0).mean())
                      if nl else None)
                ws = (float((tr['pnl_pip'].values[dl == 'short'] > 0).mean())
                      if ns else None)
                row.update(wr=round(w * 100, 3), uncond=round(u * 100, 3),
                           lift_pp=round(lift, 3), z_screen=round(zb, 3),
                           n_long=nl,
                           wr_long=None if wl is None else round(wl * 100, 2),
                           n_short=ns,
                           wr_short=None if ws is None else round(ws * 100, 2),
                           net_pip=round(float(tr['pnl_pip'].sum()), 1))
            cells.append(row)

    res = dict(tf=tf, src=src, n_total=n, half=half, n_explore=ne,
               sl_pip=round(sl_pip, 6), tp_pip=round(tp_pip, 6),
               atr_period=ATR_P, max_hold=MAX_HOLD, uncond=unc,
               seed=SEED, k_unc=K_UNC,
               elapsed_s=round(time.time() - t0, 1), cells=cells)
    fp = os.path.join(OUT, f'explore_{tf}.json')
    with open(fp, 'w') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(f'[{tf}] done n_explore={ne:,} sl={sl_pip:.2f}pip '
          f'cells={len(cells)} t={res["elapsed_s"]}s', flush=True)
    return res


def main():
    tfs = sys.argv[1:] or TFS
    for tf in tfs:
        fp = os.path.join(OUT, f'explore_{tf}.json')
        if os.path.exists(fp):
            print(f'[{tf}] SKIP (چک‌پوینت موجود)', flush=True)
            continue
        try:
            scan_tf(tf)
        except Exception as e:                            # noqa: BLE001
            print(f'[{tf}] ERROR: {e!r}', flush=True)


if __name__ == '__main__':
    main()
