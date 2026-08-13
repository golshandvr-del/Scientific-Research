# -*- coding: utf-8 -*-
"""
s660_explore.py — اسکنر اکتشافی S660 (فقط نیمهٔ اول — مسیر C)
================================================================================
پیش‌ثبت حاکم: results/S660_PREREG_EHLERS_MOMENTUM_CONTINUATION_XAUUSD.md
الحاقیه:      results/S660_PREREG_ADDENDUM_NOVELTY_AUDIT.md

فرضیه: ورود در جهتِ اشباعِ laguerre_rsi + تأیید trendflex هم‌جهت = تداوم مومنتوم طلا.

شبکهٔ قفل‌شده (عیناً از پیش‌ثبت — نه بیشتر، نه کمتر):
  gamma ∈ {0.55, 0.618, 0.786} × thr ∈ {85, 90} × tf_period ∈ {21, 34} × RR ∈ {1.0, 1.5}
  = 24 سلول در هر TF × 17 TF = 408 سلول.

🔒 شفاف‌سازی‌های تعریفی که پیش‌ثبت باز گذاشته بود — اینجا و **قبل از هر اجرا**
   قفل می‌شوند (این فایل قبل از execute کامیت می‌شود؛ mökr git = مهر زمانی):
  ① تریگر = **لبهٔ صعودیِ شرط** (شرط این کندل True و کندل قبل False) ⇒ یک
     سیگنال به‌ازای هر اپیزود اشباع؛ level-trigger با allow_overlap=False عملاً
     re-entry زنجیره‌ای می‌ساخت و n را مصنوعی متورم می‌کرد.
     LONG:  LR > thr و TFX > 0   |   SHORT: LR < (100−thr) و TFX < 0  (متقارن)
  ② دورهٔ ATR هندسه = **34** (فیبوناچی): SL_pip = 1.618 × میانهٔ ATR34ِ نیمهٔ
     اول بر حسب pip. (پیش‌ثبت «NATR میانه» گفته بود؛ NATR×قیمت ≡ ATR، پس این
     همان فرمول است با دورهٔ مشخص‌شده. یک عدد برای کل TF — پارامتر آزاد نیست.)
  ③ z غربالگری = دوجمله‌ای در برابر WR بی‌قیدِ نمونه‌گیری‌شده (k=300 زیرنمونهٔ
     تصادفی هم‌اندازه از کندل‌های واجد، همان هندسه). این فقط برای **رتبه‌بندی**
     است؛ حکم نهایی فقط از مدل صفر کانونی k≥500 در داور می‌آید (BUG-NULLUNCOND:
     نال هر سلول با هندسهٔ خودِ همان سلول).
  ④ گاردها: pip از se.ASSETS خوانده می‌شود (BUG-PIPGUESS)؛ هندسه در JSON خروجی
     ذخیره و داور از همین JSON می‌خواند نه بازمحاسبه (BUG-GEOMDRIFT).

خروجی: results/_scan_S660/explore_<TF>.json — بعد از هر TF بلافاصله نوشته
می‌شود (قانون افزایشی؛ سندباکس ناپایدار است).
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
from tools.s670_trendflex_fast import trendflex_fast     # noqa: E402

try:
    from numba import njit
    HAVE_NUMBA = True
except Exception:                                        # pragma: no cover
    HAVE_NUMBA = False

OUT = os.path.join(ROOT, 'results', '_scan_S660')
os.makedirs(OUT, exist_ok=True)

# ── شبکهٔ قفل‌شده (پیش‌ثبت §۳) ────────────────────────────────────────────────
GAMMAS = (0.55, 0.618, 0.786)
THRS = (85.0, 90.0)
TFX_PERIODS = (21, 34)
RRS = (1.0, 1.5)
SL_MULT = 1.618          # × میانهٔ ATR34 نیمهٔ اول (pip)
ATR_P = 34               # شفاف‌سازی ②
MAX_HOLD = 55            # پیش‌ثبت §۳
WARMUP = 250
K_UNC = 300              # زیرنمونه‌های خط مبنای غربالگری (شفاف‌سازی ③)
SEED = 20260813

# ترتیب TFها: M1 اول (فرمان کاربر)، سپس صعودی. EURUSD: هرگز.
TFS = ['M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20', 'M30',
       'H1', 'H2', 'H3', 'H6', 'H8', 'H12', 'D1']
ASSET = 'XAUUSD'


# ── laguerre_rsi سریع (هم‌ارز بانک؛ numba اگر بود) ────────────────────────────
def _lag_levels_py(xv, g):
    n = len(xv)
    L0s = np.empty(n); L1s = np.empty(n); L2s = np.empty(n); L3s = np.empty(n)
    L0 = L1 = L2 = L3 = 0.0
    for i in range(n):
        pL0, pL1, pL2 = L0, L1, L2
        L0 = (1 - g) * xv[i] + g * L0
        L1 = -g * L0 + pL0 + g * L1
        L2 = -g * L1 + pL1 + g * L2
        L3 = -g * L2 + pL2 + g * L3
        L0s[i] = L0; L1s[i] = L1; L2s[i] = L2; L3s[i] = L3
    return L0s, L1s, L2s, L3s


if HAVE_NUMBA:
    _lag_levels = njit(cache=True)(_lag_levels_py)
else:
    _lag_levels = _lag_levels_py


def laguerre_rsi_fast(close: np.ndarray, gamma: float) -> np.ndarray:
    L0, L1, L2, L3 = _lag_levels(np.asarray(close, np.float64), float(gamma))
    cu = np.zeros_like(L0); cd = np.zeros_like(L0)
    for a, b in ((L0, L1), (L1, L2), (L2, L3)):
        up = a >= b
        d = a - b
        cu += np.where(up, d, 0.0)
        cd += np.where(up, 0.0, -d)
    tot = cu + cd
    return np.where(tot != 0, 100.0 * cu / tot, 50.0)


def atr_pips(h, l, c, pip, period=ATR_P):
    prev_c = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    # RMA (وایلدر)
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
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    n = len(df)
    half = n // 2                      # مرز مسیر C — نیمهٔ دوم لمس نمی‌شود
    dfe = df.iloc[:half].reset_index(drop=True)
    pip = se.ASSETS[ASSET]['pip']      # BUG-PIPGUESS: خوانده می‌شود، حدس نه

    c = dfe['close'].values.astype(np.float64)
    h = dfe['high'].values.astype(np.float64)
    l = dfe['low'].values.astype(np.float64)
    ne = len(dfe)

    apips = atr_pips(h, l, c, pip)
    sl_pip = float(SL_MULT * np.median(apips[WARMUP:]))

    # پیش‌محاسبهٔ اندیکاتورها (خارج از حلقهٔ سلول‌ها)
    lr = {g: laguerre_rsi_fast(c, g) for g in GAMMAS}
    tfx = {p: trendflex_fast(c, p) for p in TFX_PERIODS}

    valid = np.zeros(ne, bool)
    valid[WARMUP:ne - MAX_HOLD - 1] = True
    vidx = np.flatnonzero(valid)
    rng = np.random.default_rng(SEED)

    # خط مبنای بی‌قید غربالگری per-RR (هندسه‌محور — شفاف‌سازی ③)
    unc = {}
    for rr in RRS:
        tp = sl_pip * rr
        wrs, szs = [], []
        for _ in range(K_UNC):
            k = 200
            pick = rng.choice(vidx, size=min(k, len(vidx)), replace=False)
            m = np.zeros(ne, bool); m[pick] = True
            z = np.zeros(ne, bool)
            tr = se.simulate_trades(dfe, m, z, sl_pip, tp, ASSET,
                                    max_hold=MAX_HOLD, allow_overlap=True)
            w = _wr(tr)
            if w is not None:
                wrs.append(w); szs.append(len(tr))
        unc[rr] = dict(mean=float(np.mean(wrs)), sd=float(np.std(wrs)),
                       hi=float(np.max(wrs)), k=len(wrs))

    cells = []
    for g in GAMMAS:
        LR = lr[g]
        for thr in THRS:
            for p in TFX_PERIODS:
                TFX = tfx[p]
                cl = (LR > thr) & (TFX > 0)
                cs = (LR < (100.0 - thr)) & (TFX < 0)
                # لبهٔ صعودی شرط (شفاف‌سازی ①)
                le = cl & ~np.concatenate(([False], cl[:-1]))
                sh = cs & ~np.concatenate(([False], cs[:-1]))
                le &= valid; sh &= valid
                for rr in RRS:
                    tp = sl_pip * rr
                    tr = se.simulate_trades(dfe, le, sh, sl_pip, tp, ASSET,
                                            max_hold=MAX_HOLD,
                                            allow_overlap=False)
                    ncell = 0 if tr is None else len(tr)
                    row = dict(gamma=g, thr=thr, tfx_p=p, rr=rr,
                               sl_pip=sl_pip, tp_pip=tp, n=ncell)
                    if ncell >= 10:
                        w = _wr(tr)
                        u = unc[rr]['mean']
                        lift = (w - u) * 100.0
                        se_bin = np.sqrt(max(u * (1 - u), 1e-9) / ncell)
                        zb = (w - u) / se_bin
                        nl = int((tr['side'] == 'long').sum()) if 'side' in tr else None
                        row.update(wr=round(w * 100, 3),
                                   uncond=round(u * 100, 3),
                                   lift_pp=round(lift, 3),
                                   z_screen=round(zb, 3),
                                   n_long=nl,
                                   net_pip=round(float(tr['pnl_pip'].sum()), 1))
                    cells.append(row)

    res = dict(tf=tf, src=d['src'], n_total=n, half=half, n_explore=ne,
               sl_pip=round(sl_pip, 3), atr_period=ATR_P, max_hold=MAX_HOLD,
               uncond=unc, seed=SEED, k_unc=K_UNC,
               elapsed_s=round(time.time() - t0, 1), cells=cells)
    fp = os.path.join(OUT, f'explore_{tf}.json')
    with open(fp, 'w') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(f'[{tf}] done n_explore={ne:,} sl={sl_pip:.2f}pip '
          f'cells={len(cells)} t={res["elapsed_s"]}s -> {fp}', flush=True)
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
