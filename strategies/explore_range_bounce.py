"""
اکتشاف اولیهٔ edgeِ «رنج‌بونس» (Range Boundary Bounce) — پاسخ به User Note (نکتهٔ دوم).

هدف: پیش از ساختِ استراتژیِ کاملِ S67، بررسی کنیم آیا در بازارِ رنج (ADX پایین)
معاملهٔ برگشتی از لبه‌های کانالِ Donchian یک لبهٔ (edge) واقعی دارد یا نه.

ایده (دقیقاً همان چیزی که کاربر گفت):
  «تریدرها در رنج یک خطِ سقف و یک خطِ کف دارند و بین این دو معامله باز می‌کنند.»

  - رژیمِ رنج: ADX(14) < آستانه  (روندِ ضعیف).
  - خطِ سقف/کف: Donchian(N)  → بالاترین high و پایین‌ترین low در N کندلِ *گذشته*.
    (forward-safe: باند فقط از کندل‌های قبل از سیگنال؛ shift(1) اعمال می‌شود.)
  - ورودِ LONG: close نزدیکِ کفِ کانال (فاصله < edge_frac × عرضِ کانال).
  - ورودِ SHORT: close نزدیکِ سقفِ کانال.

این اسکریپت فقط «نرخِ حرکتِ مطلوب» (fav rate) بعد از سیگنال را می‌سنجد — یک
تخمینِ سریعِ edge، نه بک‌تستِ کامل. اگر fav rate معنی‌دار بالای ۵۰٪ بود، سراغِ
S67 با dynamic-exit می‌رویم.

درسِ قبلی (L29): mean-reversion خامِ BB+RSI در رنج edge نداشت (PF<1). تفاوتِ اینجا:
  (۱) استفاده از Donchian واقعی (سقف/کفِ ساختاری) نه فقط انحرافِ معیار،
  (۲) فیلترِ رژیمِ ADX،
  (۳) سنجشِ چند افقِ زمانی برای دیدنِ اینکه برگشت واقعی است یا ادامهٔ شکست.
"""
import sys; sys.path.insert(0, 'engine')
import numpy as np, pandas as pd
from backtest import load_data
import indicators as ind
import warnings; warnings.filterwarnings('ignore')

df = load_data()
n = len(df)
c = df['close'].values
h = df['high'].values
l = df['low'].values
print(f"داده: {n} کندل XAUUSD M15")

atr = ind.atr(df, 14).values
adx_df = ind.adx(df, 14)
adx = adx_df['adx'].values if isinstance(adx_df, pd.DataFrame) else np.asarray(adx_df)

# آستانهٔ رنج: ADX پایین
for ADX_TH in (18, 20, 22, 25):
    range_regime = adx < ADX_TH
    print(f"\nADX<{ADX_TH}: {int(np.nansum(range_regime))} کندل ({np.nanmean(range_regime)*100:.1f}%)")

# افقِ سنجشِ حرکتِ مطلوب (کندل)
HORIZON = 16   # ۴ ساعت
EDGE_FRAC = 0.20

def fav_rate(sig_idx, is_long):
    """نرخِ حرکتِ مطلوب: بعد از سیگنال، آیا قیمت h کندل بعد در جهتِ معامله رفت؟
       معیارِ ساده: close[i+HORIZON] بهتر از close[i] در جهتِ معامله."""
    good = 0; tot = 0
    for i in sig_idx:
        if i + HORIZON >= n:
            continue
        move = c[i + HORIZON] - c[i]
        if is_long:
            good += 1 if move > 0 else 0
        else:
            good += 1 if move < 0 else 0
        tot += 1
    return (good / tot * 100 if tot else 0.0), tot

ADX_TH = 22
range_regime = adx < ADX_TH
print("\n" + "=" * 60)
print(f"سنجشِ edgeِ رنج‌بونس (ADX<{ADX_TH}, HORIZON={HORIZON}, EDGE_FRAC={EDGE_FRAC})")
print("=" * 60)

for DON in (20, 32, 48, 64):
    # باندِ Donchian از N کندلِ گذشته (shift 1 → forward-safe)
    hh = pd.Series(h).rolling(DON).max().shift(1).values
    ll = pd.Series(l).rolling(DON).min().shift(1).values
    width = hh - ll
    valid = range_regime & ~np.isnan(hh) & ~np.isnan(ll) & (width > 0)

    # فاصلهٔ نسبیِ close از کف/سقف
    dist_from_low = (c - ll) / width
    dist_from_high = (hh - c) / width

    long_sig = np.where(valid & (dist_from_low < EDGE_FRAC))[0]
    short_sig = np.where(valid & (dist_from_high < EDGE_FRAC))[0]

    lr, ln = fav_rate(long_sig, True)
    sr, sn = fav_rate(short_sig, False)
    print(f"Donchian={DON}: LONG(کف→بالا) n={ln} fav={lr:.1f}%  |  "
          f"SHORT(سقف→پایین) n={sn} fav={sr:.1f}%")
