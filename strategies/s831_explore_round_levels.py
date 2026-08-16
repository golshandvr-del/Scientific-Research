# -*- coding: utf-8 -*-
"""
S831 — کاوشِ ۱: رفتار قیمت در اعداد رند (استخرهای نقدینگی) — XAUUSD-H1
=========================================================================
فقط پنجره‌ی اکتشاف (۶۰٪ اول = تا کندل 54798 = 2020-05-27) دیده می‌شود.

فرضیه: سفارش‌ها/استاپ‌های انسانی روی مضارب رند دلاری ($10/$25/$50/$100)
جمع می‌شوند. برخورد قیمت با این سطوح رفتار غیرتصادفی دارد:
  (الف) بازگشت از سطح (دیوار سفارش) — fade
  (ب) جاروی نقدینگی: عبور کوتاه از سطح، فعال‌شدن استاپ‌ها، سپس بازگشت — sweep-reversal
مزیت ساختاری: سطوح با قیمت جابه‌جا می‌شوند ⇒ مستقل از رژیم رانش (درس S830).

بخش A — سرشماری و آمار بازده رو به جلو پس از «لمس» سطح، به تفکیک:
  جهت رویکرد (از پایین/از بالا) × اندازه‌ی شبکه G × افق
بخش B — آمار sweep-reversal: عبور از سطح و بسته‌شدن آن‌سوی، سپس چه؟
"""
import sys, os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd

SPLIT_IDX = 54798
WARMUP = 600

d = fd.load_fast('XAUUSD', 'H1')
df_h = d['high'][:SPLIT_IDX].astype(np.float64)
df_l = d['low'][:SPLIT_IDX].astype(np.float64)
df_c = d['close'][:SPLIT_IDX].astype(np.float64)
df_o = d['open'][:SPLIT_IDX].astype(np.float64)
n = len(df_c)
print(f'explore bars={n:,}  src={d["src"]}', flush=True)
print(f'price range: {df_c.min():.0f} .. {df_c.max():.0f}', flush=True)

# ATR برای نرمال‌سازی بازده‌ها
prev_c = np.concatenate([[df_c[0]], df_c[:-1]])
tr = np.maximum(df_h - df_l, np.maximum(np.abs(df_h - prev_c), np.abs(df_l - prev_c)))
atr = np.empty_like(tr); atr[0] = tr[0]
a = 1.0 / 34
for i in range(1, len(tr)):
    atr[i] = atr[i-1] + a * (tr[i] - atr[i-1])

HORIZONS = [3, 8, 21]

print('\n===== (A) touch-and-hold: لمس سطح بدون بسته‌شدن آن‌سو =====', flush=True)
print('event: کندل i سطح L را لمس می‌کند (low<=L<=high)؛ ۸ کندل قبل لمس نبوده', flush=True)
for G in (10.0, 25.0, 50.0, 100.0):
    # نزدیک‌ترین سطح به close قبلی
    lev = np.round(prev_c / G) * G
    touch = (df_l <= lev) & (lev <= df_h)
    # از پایین: close قبلی زیر سطح؛ از بالا: بالای سطح
    from_below = prev_c < lev
    # فیلتر «تازگی»: در ۸ کندل قبل لمسی نبوده
    fresh = np.ones(n, bool)
    for j in range(1, 9):
        sh = np.concatenate([np.zeros(j, bool), touch[:-j]])
        fresh &= ~sh
    ev = touch & fresh
    ev[:WARMUP] = False
    for side, name in ((from_below, 'from_below'), (~from_below, 'from_above')):
        idx = np.where(ev & side)[0]
        idx = idx[idx < n - max(HORIZONS) - 1]
        if len(idx) < 100:
            print(f'  G={G:5.0f} {name}: n={len(idx)} — کم، رد', flush=True)
            continue
        row = f'  G={G:5.0f} {name}: n={len(idx):6,}'
        for H in HORIZONS:
            fwd = (df_c[idx + H] - df_c[idx]) / atr[idx]   # بر حسب ATR
            m = fwd.mean(); sd = fwd.std(ddof=1); z = m / (sd / np.sqrt(len(fwd)))
            row += f'  fwd{H}: {m:+.4f}ATR(z={z:+5.1f})'
        print(row, flush=True)

print('\n===== (B) sweep-reversal: عبور و بسته‌شدن آن‌سوی سطح =====', flush=True)
print('event: کندل i از پایین سطح L را می‌شکند و بالای آن می‌بندد (یا برعکس)', flush=True)
for G in (10.0, 25.0, 50.0, 100.0):
    lev = np.round(prev_c / G) * G
    # شکست صعودی: قبلی زیر سطح، این کندل بالای سطح می‌بندد و high از سطح رد شده
    brk_up = (prev_c < lev) & (df_c > lev) & (df_h >= lev)
    brk_dn = (prev_c > lev) & (df_c < lev) & (df_l <= lev)
    for msk, name in ((brk_up, 'break_up'), (brk_dn, 'break_dn')):
        m2 = msk.copy(); m2[:WARMUP] = False
        idx = np.where(m2)[0]
        idx = idx[idx < n - max(HORIZONS) - 1]
        if len(idx) < 100:
            print(f'  G={G:5.0f} {name}: n={len(idx)} — کم، رد', flush=True)
            continue
        row = f'  G={G:5.0f} {name}: n={len(idx):6,}'
        for H in HORIZONS:
            fwd = (df_c[idx + H] - df_c[idx]) / atr[idx]
            m = fwd.mean(); sd = fwd.std(ddof=1); z = m / (sd / np.sqrt(len(fwd)))
            row += f'  fwd{H}: {m:+.4f}ATR(z={z:+5.1f})'
        print(row, flush=True)

print('\n===== (C) عمق نفوذ: جارو (نفوذ کم‌عمق و بازگشت) در برابر شکست واقعی =====', flush=True)
print('event: high از سطح رد شده ولی close زیر سطح مانده (جاروی صعودیِ ناکام) و برعکس', flush=True)
for G in (25.0, 50.0, 100.0):
    lev = np.round(prev_c / G) * G
    # جاروی بالای سطح: از پایین آمده، high>=lev اما close<lev (رد شدن ناکام)
    sweep_up_fail = (prev_c < lev) & (df_h >= lev) & (df_c < lev)
    # جاروی زیر سطح: از بالا آمده، low<=lev اما close>lev
    sweep_dn_fail = (prev_c > lev) & (df_l <= lev) & (df_c > lev)
    for msk, name in ((sweep_up_fail, 'sweep_up_fail(→short?)'), (sweep_dn_fail, 'sweep_dn_fail(→long?)')):
        m2 = msk.copy(); m2[:WARMUP] = False
        idx = np.where(m2)[0]
        idx = idx[idx < n - max(HORIZONS) - 1]
        if len(idx) < 100:
            print(f'  G={G:5.0f} {name}: n={len(idx)} — کم، رد', flush=True)
            continue
        row = f'  G={G:5.0f} {name}: n={len(idx):6,}'
        for H in HORIZONS:
            fwd = (df_c[idx + H] - df_c[idx]) / atr[idx]
            m = fwd.mean(); sd = fwd.std(ddof=1); z = m / (sd / np.sqrt(len(fwd)))
            row += f'  fwd{H}: {m:+.4f}ATR(z={z:+5.1f})'
        print(row, flush=True)

print('\n[S831 explore-1 complete]', flush=True)
