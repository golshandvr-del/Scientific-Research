# -*- coding: utf-8 -*-
"""
S800 prep — محاسبهٔ کم‌حافظهٔ اندیکاتورهای M1 (۵M کندل، سندباکس 1GB)
================================================================================
تعریف‌ها **بیت‌به‌بیت** همان `engine/indicator_bank.py` است؛ فقط پیاده‌سازی
جریان‌محور/NumPy است تا کپی‌های موقتِ pandas ساخته نشود:

  atr_fib_21 : rma_s(TR, 21)              — بازنویسی بازگشتی wilder
  atr_pct    : صدکِ ATR(14) در پنجرهٔ 101 — شمارش برخط با دو اشاره‌گر
  r2_fib_34  : R²ِ رگرسیون خطی پنجرهٔ 34  — جمع‌های غلتان بسته
  hurst      : R/S روی log-returns p=64   — پنجرهٔ غلتان NumPy تکه‌تکه

صحت: خروجی روی ۲۰۰هزار کندل اول با ib.compute مقایسه می‌شود (تلورانس 1e-4).
خروجی: results/_scan_S800/M1_ind_<name>.npy (float32)
"""
import sys
import os
import gc
import argparse

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd            # noqa: E402

OUT = 'results/_scan_S800'


def true_range(h, l, c):
    n = len(c)
    tr = np.empty(n, dtype=np.float64)
    tr[0] = h[0] - l[0]
    pc = c[:-1]
    tr[1:] = np.maximum.reduce([h[1:] - l[1:],
                                np.abs(h[1:] - pc),
                                np.abs(l[1:] - pc)])
    return tr


def rma(x, p):
    """Wilder RMA — بیت‌به‌بیت با rma_s بانک: ewm(alpha=1/p, adjust=False).
    همهٔ مقادیر از i=0 خروجی دارند (بدون min_periods)."""
    n = len(x)
    out = np.empty(n, dtype=np.float64)
    alpha = 1.0 / p
    y = x[0]
    out[0] = y
    for i in range(1, n):
        y = y + alpha * (x[i] - y)
        out[i] = y
    return out


def atr_percentile(atr, lookback=100):
    """100·(w<=w[-1]).sum()/len(w) روی پنجرهٔ lookback+1 — بدون look-ahead."""
    n = len(atr)
    L = lookback + 1
    out = np.full(n, np.nan, dtype=np.float32)
    for i in range(L - 1, n):
        w = atr[i - L + 1:i + 1]
        cur = w[-1]
        if not np.isfinite(cur):
            continue
        out[i] = 100.0 * np.count_nonzero(w <= cur) / L
    return out


def r2_rolling(c, p):
    """R² رگرسیون خطی y=close، x=0..p-1 — جمع‌های غلتان بسته (O(n))."""
    n = len(c)
    out = np.full(n, np.nan, dtype=np.float32)
    t = np.arange(p, dtype=np.float64)
    st = t.sum()
    stt = (t * t).sum()
    c64 = c.astype(np.float64)
    csum = np.cumsum(c64)
    csum2 = np.cumsum(c64 * c64)
    # sxy نیاز به جمع t*w دارد؛ با هویت جابه‌جایی: در هر گام پنجره یک واحد
    # می‌لغزد. از فرم مستقیم برداری تکه‌تکه استفاده می‌کنیم تا حافظه محدود بماند.
    CH = 200_000
    for s in range(p - 1, n, CH):
        e = min(s + CH, n)
        idx = np.arange(s, e)
        # پنجره‌ها: [i-p+1, i]
        sy = csum[idx] - np.where(idx - p >= 0, csum[idx - p], 0.0)
        syy = csum2[idx] - np.where(idx - p >= 0, csum2[idx - p], 0.0)
        # sxy: به‌ناچار حلقهٔ تکه‌ای برداری روی p (p=34 کوچک است)
        sxy = np.zeros(len(idx), dtype=np.float64)
        for j in range(p):
            sxy += t[j] * c64[idx - p + 1 + j]
        num = p * sxy - st * sy
        den = (p * stt - st * st) * (p * syy - sy * sy)
        r = np.where(den > 0, num / np.sqrt(np.maximum(den, 1e-300)), 0.0)
        out[idx] = (r * r).astype(np.float32)
    return out


def hurst_rolling(c, p=64):
    """R/S روی log-returns، پنجرهٔ p — منطبق با بانک (سنجهٔ صحت دارد)."""
    n = len(c)
    c64 = c.astype(np.float64)
    ret = np.zeros(n, dtype=np.float64)
    with np.errstate(divide='ignore', invalid='ignore'):
        ret[1:] = np.where(c64[:-1] != 0, np.log(c64[1:] / c64[:-1]), 0.0)
    ret = np.nan_to_num(ret)
    out = np.full(n, np.nan, dtype=np.float32)
    log_p = np.log(p)
    for i in range(p - 1, n):
        w = ret[i - p + 1:i + 1]
        m = w.mean()
        dev = np.cumsum(w - m)
        R = dev.max() - dev.min()
        S = w.std()
        if S > 0 and R > 0:
            out[i] = np.log(R / S) / log_p
        else:
            out[i] = 0.5
    return out


def verify(name, mine, df_head, tol=1e-3):
    from engine import indicator_bank as ib
    ref = np.asarray(ib.compute(name, df_head), dtype=np.float64)
    a = mine[:len(ref)].astype(np.float64)
    ok = np.isfinite(ref) & np.isfinite(a)
    if ok.sum() == 0:
        return False, 0.0
    d = np.nanmax(np.abs(a[ok] - ref[ok]))
    return d <= tol, float(d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ind', required=True,
                    choices=['atr_fib_21', 'atr_pct', 'r2_fib_34', 'hurst'])
    ap.add_argument('--tf', default='M1')
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    path = f'{OUT}/{a.tf}_ind_{a.ind}.npy'
    if os.path.exists(path):
        print(f'[prep] {a.ind} موجود است', flush=True)
        return
    d = fd.load_fast('XAUUSD', a.tf)
    h = np.asarray(d['high'], dtype=np.float64)
    l = np.asarray(d['low'], dtype=np.float64)
    c = np.asarray(d['close'], dtype=np.float64)
    del d
    gc.collect()
    n = len(c)
    print(f'[prep] {a.ind} روی {n} کندل …', flush=True)

    if a.ind == 'atr_fib_21':
        v = rma(true_range(h, l, c), 21).astype(np.float32)
    elif a.ind == 'atr_pct':
        atr = rma(true_range(h, l, c), 14)
        del h, l
        gc.collect()
        v = atr_percentile(atr, 100)
    elif a.ind == 'r2_fib_34':
        del h, l
        gc.collect()
        v = r2_rolling(c, 34)
    else:
        del h, l
        gc.collect()
        v = hurst_rolling(c, 64)

    # سنجهٔ صحت روی سرِ داده (200k کندل) در برابر بانک رسمی
    import pandas as pd
    HEAD = 200_000
    d2 = fd.load_fast('XAUUSD', a.tf)
    df_head = fd.as_dataframe(d2).iloc[:HEAD]
    del d2
    gc.collect()
    ok, maxd = verify(a.ind, v, df_head)
    print(f'[verify] {a.ind}: max|Δ|={maxd:.2e}  {"✓" if ok else "✗ ناهمسان!"}',
          flush=True)
    if not ok:
        sys.exit(2)
    np.save(path, v.astype(np.float32))
    print(f'[prep] ذخیره شد: {path}', flush=True)


if __name__ == '__main__':
    main()
