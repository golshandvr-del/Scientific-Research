# -*- coding: utf-8 -*-
"""
s664_explore.py — اسکنر اکتشافی S664 (فقط نیمهٔ اول — مسیر C)
================================================================================
پیش‌ثبت حاکم: results/S664_PREREG_ENGLE_SHOCK_THINTAIL_REGIME_XAUUSD.md (a246d7cc)

سیگنال = شوکِ انگل (RiskMetrics σ، |z|≥2.618 منجمد، follow) با گیتِ رژیمِ دم‌نازک:
  K_t = excess kurtosis(z_{t-W}..z_{t-1});  ورود اگر K_t ≤ median(K_{t-233..t-1})
کنترل‌ها (اندازه‌گیری): مکمل (K_t > median) و بی‌گیت (پایهٔ S840/S602).
P3: هم‌بستگی باینری گیت K با گیت آرامش σ (S606) روی رویدادها.

شبکهٔ قفل‌شده: TF∈{H6,H8,H12} × W∈{55,89} = 6 بازو.
هندسه: RR=1.0، SL=1.618×میانهٔ ATR34 نیمهٔ اول، max_hold=34.
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

OUT = os.path.join(ROOT, 'results', '_scan_S664')
os.makedirs(OUT, exist_ok=True)

WINDOWS = (55, 89)
THETA = 2.618
LAMBDA = 0.94
MED_W = 233
RR = 1.0
SL_MULT = 1.618
ATR_P = 34
MAX_HOLD = 34
WARMUP = 250
K_UNC = 300
SEED = 20260819

TFS = ['H6', 'H8', 'H12']
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


def ewma_sigma(r, lam=LAMBDA, init=100):
    """σ_t علّی: σ²_t = λσ²_{t-1} + (1-λ) r²_{t-1}. عیناً S602/S606."""
    n = len(r)
    var = np.full(n, np.nan)
    v0 = float(np.mean(r[1:init + 1] ** 2))
    var[init] = v0
    for t in range(init + 1, n):
        var[t] = lam * var[t - 1] + (1.0 - lam) * r[t - 1] ** 2
    return np.sqrt(var)


def rolling_excess_kurt_past(x, W):
    """K_t = excess kurtosis of x[t-W..t-1] (خودِ t خارج). NaN تا W نمونهٔ معتبر."""
    n = len(x)
    out = np.full(n, np.nan)
    xx = np.where(np.isfinite(x), x, 0.0)
    ok = np.isfinite(x).astype(float)
    def csum(a):
        return np.concatenate(([0.0], np.cumsum(a)))
    c0, c1, c2 = csum(ok), csum(xx), csum(xx ** 2)
    c3, c4 = csum(xx ** 3), csum(xx ** 4)
    for t in range(W, n):
        lo, hi = t - W, t          # پنجره [t-W, t-1]
        m = c0[hi] - c0[lo]
        if m < W:                  # همهٔ W نمونه باید معتبر باشند
            continue
        s1 = (c1[hi] - c1[lo]) / m
        s2 = (c2[hi] - c2[lo]) / m
        s3 = (c3[hi] - c3[lo]) / m
        s4 = (c4[hi] - c4[lo]) / m
        var = s2 - s1 ** 2
        if var <= 0:
            continue
        mu4 = s4 - 4 * s1 * s3 + 6 * s1 ** 2 * s2 - 3 * s1 ** 4
        out[t] = mu4 / var ** 2 - 3.0
    return out


def rolling_median_past(x, W):
    """median(x[t-W..t-1]) — فقط گذشته. NaN تا W نمونهٔ معتبر."""
    n = len(x)
    out = np.full(n, np.nan)
    for t in range(W, n):
        win = x[t - W:t]
        win = win[np.isfinite(win)]
        if len(win) >= W // 2:
            out[t] = np.median(win)
    return out


def build_signals(c, W, valid):
    """برمی‌گرداند dict از ماسک‌های (le, sh) برای gated/complement/ungated و
    بردارهای گیت‌ها برای P3."""
    r = log_ret(c)
    sig = ewma_sigma(r)
    z = np.where(np.isfinite(sig) & (sig > 0), r / np.where(sig > 0, sig, 1.0), 0.0)
    shock_l = z >= THETA
    shock_s = z <= -THETA
    # لبهٔ رویداد
    shock_l &= ~np.concatenate(([False], shock_l[:-1]))
    shock_s &= ~np.concatenate(([False], shock_s[:-1]))
    shock_l &= valid
    shock_s &= valid

    K = rolling_excess_kurt_past(z, W)
    K_med = rolling_median_past(K, MED_W)
    gate_thin = np.isfinite(K) & np.isfinite(K_med) & (K <= K_med)
    gate_fat = np.isfinite(K) & np.isfinite(K_med) & (K > K_med)
    # گیت آرامش S606 برای P3 (فقط اندازه‌گیری)
    sig_med = rolling_median_past(sig, MED_W)
    calm = np.isfinite(sig) & np.isfinite(sig_med) & (sig <= sig_med)
    defined = np.isfinite(K) & np.isfinite(K_med)

    return dict(
        gated=(shock_l & gate_thin, shock_s & gate_thin),
        complement=(shock_l & gate_fat, shock_s & gate_fat),
        ungated=(shock_l & defined, shock_s & defined),
        gate_thin=gate_thin, calm=calm, defined=defined,
        events=(shock_l | shock_s) & defined, K=K, z=z)


def _wr(t):
    if t is None or len(t) == 0:
        return None
    return float((t['pnl_pip'].values > 0).mean())


def _cell(tr, u, base):
    ncell = 0 if tr is None else len(tr)
    row = dict(base, n=ncell)
    if ncell >= 10:
        w = _wr(tr)
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
    assert 'mt5_full' in src, f'E-16! {src}'
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
    u = unc['mean']

    cells = []
    for W in WINDOWS:
        S = build_signals(c, W, valid)
        row = dict(W=W, theta=THETA, rr=RR, sl_pip=sl_pip, tp_pip=tp_pip)
        for arm in ('gated', 'complement', 'ungated'):
            le, sh = S[arm]
            tr = se.simulate_trades(dfe, le, sh, sl_pip, tp_pip, ASSET,
                                    max_hold=MAX_HOLD, allow_overlap=False)
            row[arm] = _cell(tr, u, dict(n_sig_long=int(le.sum()),
                                        n_sig_short=int(sh.sum())))
        # P3: هم‌بستگی باینری گیت دم‌نازک با گیت آرامش روی رویدادها
        ev = S['events']
        a = S['gate_thin'][ev].astype(float)
        b = S['calm'][ev].astype(float)
        phi = float(np.corrcoef(a, b)[0, 1]) if ev.sum() > 5 and a.std() > 0 and b.std() > 0 else None
        row['P3'] = dict(n_events=int(ev.sum()),
                         pass_rate_thin=round(float(a.mean()), 3),
                         pass_rate_calm=round(float(b.mean()), 3),
                         phi_thin_calm=None if phi is None else round(phi, 3))
        cells.append(row)

    res = dict(tf=tf, src=src, n_total=n, half=half, n_explore=ne,
               sl_pip=round(sl_pip, 6), tp_pip=round(tp_pip, 6),
               theta=THETA, lam=LAMBDA, med_w=MED_W,
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
