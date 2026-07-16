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
# ind.adx برمی‌گرداند: (adx, plus_di, minus_di) — عنصرِ اول را می‌گیریم.
adx_series, plus_di, minus_di = ind.adx(df, 14)
adx = adx_series.values
plus_di = plus_di.values
minus_di = minus_di.values

# آستانهٔ رنج: ADX پایین
for ADX_TH in (18, 20, 22, 25):
    range_regime = adx < ADX_TH
    print(f"\nADX<{ADX_TH}: {int(np.nansum(range_regime))} کندل ({np.nanmean(range_regime)*100:.1f}%)")

# افقِ سنجشِ حرکتِ مطلوب (کندل)
HORIZON = 24   # ۶ ساعت — کافی برای برگشت به میانهٔ کانال
EDGE_FRAC = 0.20

def fav_rate(sig_idx, is_long, tp_dist_arr, sl_dist_arr):
    """معیارِ درست: بعد از ورود در open کندلِ بعد، اول TP خورد یا SL؟
       (شبیه‌سازیِ ساده‌ی first-touch؛ در ابهامِ یک کندل، محافظه‌کارانه SL).
       TP/SL بر حسبِ فاصلهٔ ATR (نه drift مطلق) → مستقل از روندِ بلندمدت.
       این معیار همان چیزی است که drift صعودیِ طلا را خنثی می‌کند."""
    good = 0; tot = 0
    for i in sig_idx:
        eb = i + 1
        if eb + HORIZON >= n:
            continue
        entry = c[i]   # تقریبِ ورود (open کندلِ بعد ≈ close فعلی)
        tp = tp_dist_arr[i]; sl = sl_dist_arr[i]
        if tp <= 0 or sl <= 0:
            continue
        hit = None
        for j in range(eb, eb + HORIZON):
            hi = h[j]; lo = l[j]
            if is_long:
                tp_hit = hi >= entry + tp
                sl_hit = lo <= entry - sl
            else:
                tp_hit = lo <= entry - tp
                sl_hit = hi >= entry + sl
            if tp_hit and sl_hit:
                hit = 'sl'; break   # ابهام → محافظه‌کارانه SL
            if tp_hit:
                hit = 'tp'; break
            if sl_hit:
                hit = 'sl'; break
        if hit is not None:
            good += 1 if hit == 'tp' else 0
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

    # رنج‌بونس با TP/SL متعادلِ ATR (نه نیم‌عرضِ دور). چند نسبت را می‌سنجیم تا
    # ببینیم برگشتِ کوتاه از لبه winrate بالای break-even دارد یا نه.
    for tp_m, sl_m in [(1.0, 1.0), (1.0, 1.5), (0.75, 1.0), (1.5, 1.0)]:
        be = sl_m / (tp_m + sl_m) * 100   # نرخِ سربه‌سر
        tp_dist = tp_m * atr
        sl_dist = sl_m * atr
        lr, ln = fav_rate(long_sig, True, tp_dist, sl_dist)
        sr, sn = fav_rate(short_sig, False, tp_dist, sl_dist)
        flag = ''
        if sr > be + 2: flag = ' ←SHORT edge!'
        if lr > be + 2: flag += ' ←LONG edge!'
        print(f"  DON={DON} TP={tp_m}×SL={sl_m}× (BE={be:.0f}%): "
              f"LONG WR={lr:.1f}%(n{ln}) SHORT WR={sr:.1f}%(n{sn}){flag}")
    print()
