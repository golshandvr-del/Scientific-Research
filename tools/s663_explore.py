# -*- coding: utf-8 -*-
"""
s663_explore.py — اسکنر اکتشافی S663 (فقط نیمهٔ اول — مسیر C)
================================================================================
پیش‌ثبت حاکم: results/S663_PREREG_DIURNAL_SLOT_SHOCK_CONTINUATION_XAUUSD.md (bfbc9b66)

سیگنال = شوکِ استانداردشده با σ «اسلاتِ روزانه»:
  σ_slot(t) = RMS بازده‌های W کندلِ گذشته‌ی *همان ساعتِ روز* (فقط گذشته)
  z_t = r_t / σ_slot(t);  z ≥ θ ⇒ LONG در open بعد؛ z ≤ −θ ⇒ SHORT (follow)
بازوی کنترل (P1، فقط اندازه‌گیری): σ_time = RMS بازده‌های W کندلِ متوالیِ گذشته.

شبکهٔ قفل‌شده: TF∈{H3,H6,H8,H12} × W∈{34,89} × θ∈{2.0,2.618} = 16 بازو.
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

OUT = os.path.join(ROOT, 'results', '_scan_S663')
os.makedirs(OUT, exist_ok=True)

WINDOWS = (34, 89)
THETAS = (2.0, 2.618)
RR = 1.0
SL_MULT = 1.618
ATR_P = 34
MAX_HOLD = 55
WARMUP = 250
K_UNC = 300
SEED = 20260818

TFS = ['H3', 'H6', 'H8', 'H12']
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


def log_ret(c):
    r = np.zeros(len(c))
    r[1:] = np.log(c[1:] / c[:-1])
    return r


def sigma_time(r, W):
    """RMS بازده‌های W کندل متوالیِ *قبل از* t (t خودش حذف). NaN تا W نمونه."""
    n = len(r)
    out = np.full(n, np.nan)
    cs = np.concatenate(([0.0], np.cumsum(r * r)))
    # پنجره [t-W, t-1]
    for t in range(W, n):
        out[t] = np.sqrt((cs[t] - cs[t - W]) / W)
    return out


def sigma_slot(r, hour, W):
    """RMS بازده‌های W کندلِ گذشتهٔ همان اسلات (hour) که پیش از t بسته‌اند."""
    n = len(r)
    out = np.full(n, np.nan)
    for hv in np.unique(hour):
        idx = np.flatnonzero(hour == hv)
        rs = r[idx]
        cs = np.concatenate(([0.0], np.cumsum(rs * rs)))
        for j in range(W, len(idx)):
            # پنجره‌ی j-W..j-1 در فهرست همان اسلات ⇒ همه قبل از idx[j]
            out[idx[j]] = np.sqrt((cs[j] - cs[j - W]) / W)
    return out


def shock_signals(r, sig, theta, valid):
    z = np.where(np.isfinite(sig) & (sig > 0), r / np.where(sig > 0, sig, 1.0),
                 0.0)
    le = (z >= theta)
    sh = (z <= -theta)
    # لبهٔ رویداد: کندل قبلی هم شوکِ هم‌جهت نباشد
    le &= ~np.concatenate(([False], le[:-1]))
    sh &= ~np.concatenate(([False], sh[:-1]))
    le &= valid
    sh &= valid
    return le, sh, z


def _wr(t):
    if t is None or len(t) == 0:
        return None
    return float((t['pnl_pip'].values > 0).mean())


def _cell(tr, unc_mean, base):
    ncell = 0 if tr is None else len(tr)
    row = dict(base, n=ncell)
    if ncell >= 10:
        w = _wr(tr)
        u = unc_mean
        se_bin = np.sqrt(max(u * (1 - u), 1e-9) / ncell)
        dl = tr['direction'].values
        nl = int((dl == 'long').sum())
        ns = ncell - nl
        wl = float((tr['pnl_pip'].values[dl == 'long'] > 0).mean()) if nl else None
        ws = float((tr['pnl_pip'].values[dl == 'short'] > 0).mean()) if ns else None
        row.update(wr=round(w * 100, 3), uncond=round(u * 100, 3),
                   lift_pp=round((w - u) * 100, 3),
                   z_screen=round((w - u) / se_bin, 3),
                   n_long=nl, wr_long=None if wl is None else round(wl * 100, 2),
                   n_short=ns, wr_short=None if ws is None else round(ws * 100, 2),
                   net_pip=round(float(tr['pnl_pip'].sum()), 1))
    return row


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
    hour = np.ascontiguousarray(d['hour'][:half], dtype=np.int16)
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
    zmask = np.zeros(ne, bool)
    for _ in range(K_UNC):
        pick = rng.choice(vidx, size=min(200, len(vidx)), replace=False)
        m_ = np.zeros(ne, bool)
        m_[pick] = True
        tr = se.simulate_trades(dfe, m_, zmask, sl_pip, tp_pip, ASSET,
                                max_hold=MAX_HOLD, allow_overlap=True)
        w = _wr(tr)
        if w is not None:
            wrs.append(w)
    unc = dict(mean=float(np.mean(wrs)), sd=float(np.std(wrs)),
               hi=float(np.max(wrs)), k=len(wrs))

    r = log_ret(c)
    cells = []
    controls = []
    for W in WINDOWS:
        s_slot = sigma_slot(r, hour, W)
        s_time = sigma_time(r, W)
        for th in THETAS:
            le, sh, _ = shock_signals(r, s_slot, th, valid)
            tr = se.simulate_trades(dfe, le, sh, sl_pip, tp_pip, ASSET,
                                    max_hold=MAX_HOLD, allow_overlap=False)
            cells.append(_cell(tr, unc['mean'],
                               dict(W=W, theta=th, sigma='slot', rr=RR,
                                    sl_pip=sl_pip, tp_pip=tp_pip,
                                    n_sig_long=int(le.sum()),
                                    n_sig_short=int(sh.sum()))))
            # بازوی کنترل P1 (فقط اندازه‌گیری — تصمیمی روی آن نیست)
            le2, sh2, _ = shock_signals(r, s_time, th, valid)
            tr2 = se.simulate_trades(dfe, le2, sh2, sl_pip, tp_pip, ASSET,
                                     max_hold=MAX_HOLD, allow_overlap=False)
            controls.append(_cell(tr2, unc['mean'],
                                  dict(W=W, theta=th, sigma='time', rr=RR,
                                       sl_pip=sl_pip, tp_pip=tp_pip,
                                       n_sig_long=int(le2.sum()),
                                       n_sig_short=int(sh2.sum()))))

    res = dict(tf=tf, src=src, n_total=n, half=half, n_explore=ne,
               sl_pip=round(sl_pip, 6), tp_pip=round(tp_pip, 6),
               atr_period=ATR_P, max_hold=MAX_HOLD, uncond=unc,
               seed=SEED, k_unc=K_UNC,
               slots=sorted(int(x) for x in np.unique(hour)),
               elapsed_s=round(time.time() - t0, 1),
               cells=cells, controls_P1=controls)
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
