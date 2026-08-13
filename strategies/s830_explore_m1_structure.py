# -*- coding: utf-8 -*-
"""
S830 — کاوشِ اکتشافیِ ساختارِ آماریِ XAUUSD-M1 (فقط ۶۰٪ اولِ داده)
====================================================================
⚠️ این اسکریپت هیچ لایه‌ای نمی‌سازد و هیچ حکمی نمی‌دهد — فقط «گوش‌دادن به داده»
به سبکِ سیمونز است. همهٔ اندازه‌گیری‌ها منحصراً روی ۶۰٪ اولِ تاریخ انجام می‌شود
تا نیمهٔ holdout برای آزمونِ نهاییِ مسیرِ C دست‌نخورده بماند.

سه پرسش:
  Q1: خودهمبستگیِ بازده‌های M1 در لگ‌های 1..10 چقدر است؟ (mean-reversion یا momentum؟)
  Q2: آیا این ساختار بر حسبِ ساعتِ روز فرق می‌کند؟
  Q3: بعد از حرکتِ شدیدِ نرمال‌شده (|r| > k·σ محلی)، بازدهِ آینده چه رفتاری دارد؟
"""
import sys, os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd

d = fd.load_fast('XAUUSD', 'M1')
print('src =', d['src'], flush=True)
n_all = len(d['close'])
split = int(n_all * 0.60)
print(f'bars total = {n_all:,}  |  exploration window = first {split:,} bars', flush=True)

c = d['close'][:split].astype(np.float64)
o = d['open'][:split].astype(np.float64)
h = d['high'][:split].astype(np.float64)
lo = d['low'][:split].astype(np.float64)
t = d['time'][:split]
hour = d['hour'][:split]
dow = d['dow'][:split]

r = np.diff(np.log(c))  # log-returns bar-to-bar
r = np.concatenate([[0.0], r])

# --- Q1: autocorrelation of M1 returns ---
print('\n=== Q1: autocorrelation of M1 log-returns (lags 1..10) ===', flush=True)
rm = r - r.mean()
var = np.mean(rm * rm)
for lag in range(1, 11):
    ac = np.mean(rm[lag:] * rm[:-lag]) / var
    # z of autocorr ~ ac * sqrt(n)
    z = ac * np.sqrt(len(r) - lag)
    print(f'  lag {lag:2d}: ac = {ac:+.5f}   z ≈ {z:+8.1f}', flush=True)

# --- Q2: by hour of day ---
print('\n=== Q2: lag-1 autocorr by hour of day (UTC broker time) ===', flush=True)
for hh in range(24):
    m = hour[1:] == hh
    x, y = rm[1:][m], rm[:-1][m]
    if m.sum() < 1000:
        continue
    ac = np.mean(x * y) / var
    z = ac * np.sqrt(m.sum())
    print(f'  hour {hh:2d}: n={m.sum():8,}  ac1 = {ac:+.5f}  z ≈ {z:+7.1f}', flush=True)

# --- Q3: reaction after extreme normalized move ---
print('\n=== Q3: mean forward return after extreme move (|r| > k*sigma_local) ===', flush=True)
# rolling sigma via EWMA of squared returns (causal)
lam = 0.97
sig2 = np.empty_like(r)
sig2[0] = np.var(r[:1000]) if len(r) > 1000 else np.var(r)
for i in range(1, len(r)):
    sig2[i] = lam * sig2[i-1] + (1 - lam) * r[i] * r[i]
sig = np.sqrt(sig2)
zr = np.divide(r, np.maximum(sig, 1e-12))

for k in (2.0, 3.0, 4.0):
    for direction, mask in (('down', zr < -k), ('up', zr > k)):
        idx = np.where(mask)[0]
        idx = idx[(idx > 100) & (idx < len(r) - 20)]
        if len(idx) < 200:
            continue
        # forward return over next 1, 5, 15 bars
        f1 = np.array([r[i+1] for i in idx])
        f5 = np.array([np.sum(r[i+1:i+6]) for i in idx])
        f15 = np.array([np.sum(r[i+1:i+16]) for i in idx])
        def zstat(x):
            return x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))
        print(f'  k={k} {direction:>4}: n={len(idx):7,}  '
              f'fwd1={f1.mean()*1e5:+.2f}e-5 (z={zstat(f1):+.1f})  '
              f'fwd5={f5.mean()*1e5:+.2f}e-5 (z={zstat(f5):+.1f})  '
              f'fwd15={f15.mean()*1e5:+.2f}e-5 (z={zstat(f15):+.1f})', flush=True)

# --- Q4 (bonus): consecutive same-color candles -> next-bar behavior ---
print('\n=== Q4: after K consecutive same-color M1 candles, next-bar mean return ===', flush=True)
col = np.sign(c - o)  # candle color
for K in (3, 4, 5, 6, 8):
    # run of K consecutive down candles
    run_dn = np.ones(len(c), dtype=bool)
    run_up = np.ones(len(c), dtype=bool)
    for j in range(K):
        run_dn &= np.roll(col, j) == -1
        run_up &= np.roll(col, j) == 1
    run_dn[:K+1] = False; run_up[:K+1] = False
    for name, mask in (('dn', run_dn), ('up', run_up)):
        idx = np.where(mask)[0]
        idx = idx[idx < len(r) - 2]
        if len(idx) < 200:
            continue
        f1 = r[idx + 1]
        zst = f1.mean() / (f1.std(ddof=1) / np.sqrt(len(f1)))
        print(f'  K={K} {name}: n={len(idx):8,}  fwd1={f1.mean()*1e5:+.2f}e-5  z={zst:+6.1f}', flush=True)

print('\n[exploration complete — holdout untouched]', flush=True)
