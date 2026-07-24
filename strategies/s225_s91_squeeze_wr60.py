# -*- coding: utf-8 -*-
"""
s225_s91_squeeze_wr60.py — احیای استراتژیِ سوختهٔ S91 (Scalp / Squeeze-Breakout طلا) به WR ≥ ۶۰٪
================================================================================
> قانونِ احیای پروژه (این نشست، User Note): «زنده کردنِ استراتژی‌های سوخته — WR را به
> هر قیمتی بالای ۶۰٪ ببر؛ سودِ خالص می‌تواند کاهش یابد به‌شرطِ تضمینِ WR≥۶۰٪».
> تابعِ هدف = بیشینهٔ net مشروط بر WR≥۶۰ + net>0 + گیتِ سختِ ضدِ overfit (h1/h2/walk-forward).

استراتژیِ سوختهٔ S91 (Scalp, WR≈۲۷٪):
  • منطقِ پایهٔ سازنده (از s132_squeeze_breakout_m15.build_entries_squeeze):
      ۱) فشردگیِ بولینگر: BandWidth[i-1] در پایین‌ترین `sqz_pct` صدکِ `sqz_lookback` کندلِ اخیر
         («فنرِ فشرده» — تراکمِ نوسان درست پیش از کندلِ فعلی).
      ۲) شکستِ صعودی: close[i] از بالاترین high در `breakout_lookback` کندلِ گذشته عبور کند.
      ۳) گیتِ روند: EMA50 > EMA200 (فقط انفجارِ هم‌سو با روند).
  • علتِ سوختن: خروجِ scalp با TP/SL خیلی تنگ/نامتقارن + هزینهٔ واقعی روی سیگنالِ پرنویز ⇒ WR≈۲۷٪.

فرضیهٔ احیا: خودِ «انفجار از تراکمِ فنر فشرده» یک لبهٔ ساختاریِ واقعی است؛ اگر به‌جای
scalpِ نامتقارن، خروجِ TP کوچک/SL بزرگ (بستنِ سریعِ سود) + فیلترهای مومنتوم بگذاریم،
WR≥۶۰ می‌دهد. طبق قانونِ مولتی‌تایم‌فریم روی M5→M15→M30→H1 مجزا آزموده می‌شود.
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import strategies.s220_wr60_booster as B
from engine import indicators as ind

SL_GRID = [80, 100, 120, 150, 200, 300]
TP_GRID = [40, 60, 80, 100, 150, 200]
FILTER_POOL = ['ema20>50', 'ema50>100', 'ema20>50>100', 'price>ema200',
               'rsi40-70', 'rsi<70', 'rsi>50', 'adx>20', 'adx>25', 'pdi>mdi',
               'bull_bar', 'atr<1.8med', 'atr>0.5med']
MAX_FILTERS = 3
GOLD_TF = ['M5', 'M15', 'M30', 'H1']
GOLD_MH = {'M5': 288, 'M15': 96, 'M30': 48, 'H1': 24}

# پارامترهای squeeze (هم‌سو با s132)
BB_PERIOD = 20
SQZ_LOOKBACK = 100
SQZ_PCT = 0.15          # پایین‌ترین ۱۵٪ صدکِ bandwidth = فنرِ فشرده
BREAKOUT_LOOKBACK = 10


def base_s91_squeeze(df):
    """Squeeze-Breakout (long) برداری‌شده — معادلِ build_entries_squeeze اما vectorized.
    سیگنال روی close[i]؛ ورود در کندلِ بعد (booster خودش shift(1) می‌زند در eval)."""
    c = df['close']
    h = df['high'].to_numpy(np.float64)
    e50 = ind.ema(c, 50).to_numpy()
    e200 = ind.ema(c, 200).to_numpy()
    _, mid, upper = ind.bollinger(c, BB_PERIOD, 2.0)
    mid = mid.to_numpy(); upper = upper.to_numpy()
    # BandWidth = (upper - mid) / mid  (نیم‌پهنای نرمال‌شده)
    with np.errstate(divide='ignore', invalid='ignore'):
        bw = (upper - mid) / np.where(mid == 0, np.nan, mid)
    bw_s = pd.Series(bw)
    # صدکِ فشردگی: رتبهٔ bw در پنجرهٔ SQZ_LOOKBACK اخیر (۰=فشرده‌ترین)
    bw_pct = bw_s.rolling(SQZ_LOOKBACK).apply(
        lambda w: (w.iloc[-1] >= w).mean(), raw=False).to_numpy()
    # سقفِ اخیر (بیشینهٔ high در BREAKOUT_LOOKBACK کندلِ گذشته، بدونِ خودِ کندل)
    prior_high = pd.Series(h).rolling(BREAKOUT_LOOKBACK).max().shift(1).to_numpy()

    n = len(df)
    sig = np.zeros(n, dtype=bool)
    cval = c.to_numpy(np.float64)
    for i in range(SQZ_LOOKBACK + BB_PERIOD + 1, n):
        if np.isnan(bw_pct[i - 1]) or bw_pct[i - 1] > SQZ_PCT:   # فنرِ فشرده پیش از کندل
            continue
        if not (cval[i] > prior_high[i]):                        # شکستِ صعودی
            continue
        if not (e50[i] > e200[i]):                               # گیتِ روندِ صعودی
            continue
        sig[i] = True
    return sig


def boost(tag, df, base_sig, asset, mh):
    n_base = int(base_sig.sum())
    print(f"  [{tag}] کندل={len(df):,} mh={mh} سیگنالِ پایه={n_base}", flush=True)
    if n_base < B.MIN_TRADES:
        print(f"    ⏭️  سیگنالِ پایه < {B.MIN_TRADES} ⇒ رد.")
        return None
    out = B.boost_layer(df, base_sig, asset, mh, SL_GRID, TP_GRID, FILTER_POOL,
                        max_filters=MAX_FILTERS, side='long', top_tpsl=4)
    best = out['best']; bwa = out['best_wr_any']
    if best:
        print(f"    ✅ WR={best['wr']:.1f}% net={best['net']:+,.0f}$ n={best['n']} "
              f"SL{best['sl']}/TP{best['tp']} f={best['f']}")
        print(f"       گیت: {best['detail']}")
    else:
        w = bwa
        print(f"    ❌ گیت-پاسِ WR≥۶۰ نیافت. بهترین WR={w['wr']:.1f}% "
              f"(net={w['net']:+.0f}, SL{w['sl']}/TP{w['tp']}, f={w['f']})")
    return best


def main():
    print("=" * 84)
    print("S225 — احیای استراتژیِ سوختهٔ S91 (Squeeze-Breakout طلا) به WR≥۶۰٪")
    print("=" * 84)
    out = os.path.join(ROOT, 'results', '_s225_s91_squeeze_wr60.json')
    res = {}
    if os.path.exists(out):
        try:
            res = json.load(open(out))
            print(f"↩️  resume: {list(res.keys())}")
        except Exception:
            res = {}

    for tf in GOLD_TF:
        if tf in res and res[tf]:
            print(f"⏩ رد شد (قبلاً): {tf}")
            continue
        df = B.add_indicators(B.add_calendar(B.load(f'XAUUSD_{tf}')))
        df = B.last_n_years(df, 4)
        df = B.add_indicators(B.add_calendar(df.copy().reset_index(drop=True)))
        base = base_s91_squeeze(df)
        asset = 'XAUUSD' if tf == 'M15' else f'XAUUSD_{tf}'
        best = boost(tf, df, base, asset, GOLD_MH[tf])
        res[tf] = best if best else {}
        with open(out, 'w') as f:
            json.dump(res, f, ensure_ascii=False, indent=1, default=float)
        print(f"💾 ذخیرهٔ افزایشیِ {tf}")

    total = sum(b['net'] for b in res.values() if b)
    print("\n" + "=" * 84)
    print(f"🥇 جمعِ net گیت-پاسِ WR≥۶۰ (S91 احیا): {total:+,.0f}$")
    print("=" * 84)
    print(f"✅ ذخیره شد: {out}")


if __name__ == '__main__':
    main()
