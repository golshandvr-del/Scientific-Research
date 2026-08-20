# -*- coding: utf-8 -*-
"""
s661_explore.py — اسکنر اکتشافی S661 (فقط نیمهٔ اول — مسیر C)
================================================================================
پیش‌ثبت حاکم: results/S661_PREREG_FISHER_SATURATION_POOLED_XAUUSD.md

فرضیه: اشباع تبدیل فیشر (|fisher| > t) روی طلای مومنتوم-پایدار ⇒ تداوم.
  LONG:  لبهٔ صعودیِ [fisher(p) > +t]
  SHORT: لبهٔ صعودیِ [fisher(p) < −t]   (متقارن؛ تریگر لبه‌ای عین S660 ①)

شبکهٔ قفل‌شده (عیناً از پیش‌ثبت §۴ — نه بیشتر، نه کمتر):
  TF ∈ {H3,H6,H8,H12,D1} × p ∈ {9,13,21} × t ∈ {1.5,2.0} = 30 بازو.
  هندسهٔ ثابت: RR=1.0 (TP=SL — درس S602)، SL=1.618×میانهٔ ATR34 نیمهٔ اول،
  max_hold=55، WARMUP=250، allow_overlap=False.

گاردها: BUG-PIPGUESS (pip از se.ASSETS)، BUG-GEOMDRIFT (هندسه در JSON ذخیره؛
داور از همین JSON می‌خواند)، Fisher هم‌ارزِ بیت‌به‌بیتِ بانک (پاریتی‌تست پایین).
خروجی: results/_scan_S661/explore_<TF>.json — چک‌پوینت per-TF (قانون افزایشی).
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

OUT = os.path.join(ROOT, 'results', '_scan_S661')
os.makedirs(OUT, exist_ok=True)

# ── شبکهٔ قفل‌شده (پیش‌ثبت §۴) ────────────────────────────────────────────────
PERIODS = (9, 13, 21)
THRS = (1.5, 2.0)
RR = 1.0                 # ثابت — TP=SL (درس S602)
SL_MULT = 1.618
ATR_P = 34
MAX_HOLD = 55
WARMUP = 250
K_UNC = 300
SEED = 20260816

TFS = ['H3', 'H6', 'H8', 'H12', 'D1']   # زیر H3 = cost-dead (گرادیان S660)
ASSET = 'XAUUSD'


# ── Fisher Transform — هم‌ارز engine/indicator_bank.py::fisher (خط ۳۴۳) ─────
def _fisher_core_py(mv, hh, ll, p):
    n = len(mv)
    out = np.full(n, np.nan)
    v = 0.0
    prev_f = 0.0
    for i in range(p - 1, n):
        rng = hh[i] - ll[i]
        if rng == 0.0:
            rng = 1e-10
        v = 0.66 * (2.0 * (mv[i] - ll[i]) / rng - 1.0) + 0.67 * v
        vv = v
        if vv > 0.999:
            vv = 0.999
        elif vv < -0.999:
            vv = -0.999
        f = 0.5 * np.log((1.0 + vv) / (1.0 - vv)) + 0.5 * prev_f
        out[i] = f
        prev_f = f
    return out


if HAVE_NUMBA:
    _fisher_core = njit(cache=True)(_fisher_core_py)
else:
    _fisher_core = _fisher_core_py


def _roll_extrema(x: np.ndarray, p: int):
    """بیشینه/کمینهٔ غلتان پنجرهٔ p (هم‌ارز pandas rolling(p).max/min)."""
    import pandas as pd
    s = pd.Series(x)
    return s.rolling(p).max().values, s.rolling(p).min().values


def fisher_fast(high: np.ndarray, low: np.ndarray, p: int) -> np.ndarray:
    med = (np.asarray(high, np.float64) + np.asarray(low, np.float64)) / 2.0
    hh, ll = _roll_extrema(med, p)
    return _fisher_core(med, np.nan_to_num(hh, nan=0.0),
                        np.nan_to_num(ll, nan=0.0), p)


def _parity_test():
    """پاریتی بیت‌به‌بیت با نسخهٔ بانک روی دادهٔ مصنوعی."""
    import pandas as pd
    from engine.indicator_bank import fisher as bank_fisher
    rng = np.random.default_rng(7)
    n = 800
    c = 100 + np.cumsum(rng.normal(0, 1, n))
    h = c + np.abs(rng.normal(0, .5, n))
    l = c - np.abs(rng.normal(0, .5, n))
    df = pd.DataFrame({'open': c, 'high': h, 'low': l, 'close': c})
    for p in PERIODS:
        a = bank_fisher(df, p).values
        b = fisher_fast(h, l, p)
        m = ~np.isnan(a)
        assert np.allclose(a[m], b[m], atol=1e-10), f'parity FAIL p={p}'
    print('پاریتی fisher_fast با بانک: OK (سه دوره)', flush=True)


def atr_pips(h, l, c, pip, period=ATR_P):
    prev_c = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    out = np.empty_like(tr)
    out[0] = tr[0]
    alpha = 1.0 / period
    for i in range(1, len(tr)):
        out[i] = out[i - 1] + alpha * (tr[i] - out[i - 1])
    return out / pip


def _wr(t):
    if t is None or len(t) == 0:
        return None
    return float((t['pnl_pip'].values > 0).mean())


def scan_tf(tf: str) -> dict:
    t0 = time.time()
    # بارگذاری ناب (پادزهر OOM — درس S660)
    d = fd.load_fast(ASSET, tf)
    src = d['src']
    n = len(d['close'])
    half = n // 2                      # مرز مسیر C — نیمهٔ دوم لمس نمی‌شود
    import pandas as pd
    o = np.ascontiguousarray(d['open'][:half], dtype=np.float64)
    h = np.ascontiguousarray(d['high'][:half], dtype=np.float64)
    l = np.ascontiguousarray(d['low'][:half], dtype=np.float64)
    c = np.ascontiguousarray(d['close'][:half], dtype=np.float64)
    del d
    dfe = pd.DataFrame({'open': o, 'high': h, 'low': l, 'close': c})
    pip = se.ASSETS[ASSET]['pip']      # BUG-PIPGUESS
    ne = len(dfe)

    apips = atr_pips(h, l, c, pip)
    sl_pip = float(SL_MULT * np.median(apips[WARMUP:]))
    tp_pip = sl_pip * RR

    fish = {p: fisher_fast(h, l, p) for p in PERIODS}

    valid = np.zeros(ne, bool)
    valid[WARMUP:ne - MAX_HOLD - 1] = True
    vidx = np.flatnonzero(valid)
    rng = np.random.default_rng(SEED)

    # خط مبنای بی‌قید غربالگری (فقط رتبه‌بندی؛ حکم = مدل صفر کانونی داور)
    wrs = []
    z = np.zeros(ne, bool)
    for _ in range(K_UNC):
        pick = rng.choice(vidx, size=min(200, len(vidx)), replace=False)
        m = np.zeros(ne, bool)
        m[pick] = True
        tr = se.simulate_trades(dfe, m, z, sl_pip, tp_pip, ASSET,
                                max_hold=MAX_HOLD, allow_overlap=True)
        w = _wr(tr)
        if w is not None:
            wrs.append(w)
    unc = dict(mean=float(np.mean(wrs)), sd=float(np.std(wrs)),
               hi=float(np.max(wrs)), k=len(wrs))

    cells = []
    for p in PERIODS:
        F = fish[p]
        for thr in THRS:
            cl = F > thr
            cs = F < -thr
            le = cl & ~np.concatenate(([False], cl[:-1]))
            sh = cs & ~np.concatenate(([False], cs[:-1]))
            le &= valid
            sh &= valid
            tr = se.simulate_trades(dfe, le, sh, sl_pip, tp_pip, ASSET,
                                    max_hold=MAX_HOLD, allow_overlap=False)
            ncell = 0 if tr is None else len(tr)
            row = dict(p=p, thr=thr, rr=RR, sl_pip=sl_pip, tp_pip=tp_pip,
                       n=ncell, n_sig_long=int(le.sum()),
                       n_sig_short=int(sh.sum()))
            if ncell >= 10:
                w = _wr(tr)
                u = unc['mean']
                lift = (w - u) * 100.0
                se_bin = np.sqrt(max(u * (1 - u), 1e-9) / ncell)
                zb = (w - u) / se_bin
                dl = tr['direction'].values if 'direction' in tr else None
                nl = int((dl == 'long').sum()) if dl is not None else None
                wl = (float((tr['pnl_pip'].values[dl == 'long'] > 0).mean())
                      if dl is not None and nl else None)
                ns = (ncell - nl) if nl is not None else None
                ws = (float((tr['pnl_pip'].values[dl == 'short'] > 0).mean())
                      if dl is not None and ns else None)
                row.update(wr=round(w * 100, 3), uncond=round(u * 100, 3),
                           lift_pp=round(lift, 3), z_screen=round(zb, 3),
                           n_long=nl, wr_long=None if wl is None else round(wl * 100, 2),
                           n_short=ns, wr_short=None if ws is None else round(ws * 100, 2),
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
          f'cells={len(cells)} t={res["elapsed_s"]}s -> {fp}', flush=True)
    return res


def main():
    _parity_test()
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
