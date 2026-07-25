# -*- coding: utf-8 -*-
"""
S321k — سنجشِ همپوشانیِ لایهٔ جدیدِ S321 (MA-Ribbon) با لایه‌های فعالِ کارتِ M30 طلا
================================================================================
قانونِ همپوشانیِ پروژه (الزامی): پیش از افزودنِ هر لایه باید دقیقاً سنجید با کدام
لایه/لایه‌ها و چند درصد همپوشانیِ سیگنال دارد؛ و آیا بخشِ همپوشان به‌عنوان فیلتر
می‌ارزد یا خیر. لایه‌های فعالِ فعلیِ کارتِ M30 طلا: S313 (Squeeze→Breakout, ADX≥30)،
S215 (Al Brooks Trend-Line)، S219 (Channel).

اینجا همپوشانیِ «نوارِ ورود» را بینِ S321 و S313 (مهم‌ترین، RQS=۹۲.۵) می‌سنجیم.
معیارِ همپوشانی: نسبتِ کندل‌هایی که هر دو لایه هم‌زمان (در پنجرهٔ ±2 کندل) سیگنالِ
ورودِ هم‌جهت می‌دهند، به کلِّ سیگنال‌های S321.
اجرا: python3 strategies/s321k_overlap_check.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from engine import scalp_engine as se
from engine import indicators as ind
import strategies.s321f_ribbon_m30_slopefilter as S

FINAL = dict(ord_thr=0.40, wz_gate=0.15, pull_min=0.05, pull_max=0.82,
             rsi_min=45, rsi_max=85, slope_min=0.055,
             sl_mult=2.7, tp_mult=2.7, be_mult=0.0, max_hold=36)


def s313_signals(df):
    """بازتولیدِ ساده‌شدهٔ منطقِ S313: BB-squeeze سپس شکست + ADX≥30 (فقط جهتِ سیگنال)."""
    c = df['close']
    mid, up, lo = ind.bollinger(c, 20, 2.0)
    up = up.values; lo = lo.values; mid = mid.values
    atr14 = ind.atr(df, 14).values
    adx14 = ind.adx(df, 14)
    adx14 = (adx14[0] if isinstance(adx14, tuple) else adx14)
    adx14 = adx14.values if hasattr(adx14, 'values') else np.asarray(adx14)
    bb_width = (up - lo)
    sp = np.full(len(c), np.nan)
    # squeeze: عرضِ BB در کف ۲۵٪ اخیرِ ۱۰۰ کندل
    w = bb_width
    n = len(w)
    sqz = np.zeros(n, bool)
    for i in range(100, n):
        window = w[i-100:i]
        thr = np.nanpercentile(window, 25)
        sqz[i] = w[i] <= thr
    price = c.values
    long_sig = np.zeros(n, bool); short_sig = np.zeros(n, bool)
    for i in range(1, n):
        if sqz[i-1] and adx14[i] >= 30:
            if price[i] > up[i]:
                long_sig[i] = True
            elif price[i] < lo[i]:
                short_sig[i] = True
    return long_sig, short_sig


def main():
    df = se.load_data('data/XAUUSD_M30.csv')
    pip = se.ASSETS['XAUUSD']['pip']
    feats = S.build_features(df, pip)
    ls_rib, ss_rib, _, _ = S.make_signals(feats, FINAL, 'both')
    ls_313, ss_313 = s313_signals(df)

    n = len(df)
    rib_any = ls_rib | ss_rib
    s313_any = ls_313 | ss_313
    n_rib = int(rib_any.sum()); n_313 = int(s313_any.sum())
    print(f"S321 (ribbon) total entry bars: {n_rib}")
    print(f"S313 (squeeze) total entry bars: {n_313}")

    # همپوشانی در پنجرهٔ ±2 کندل، هم‌جهت
    W = 2
    def dilate(mask):
        d = mask.copy()
        for k in range(1, W + 1):
            d[k:] |= mask[:-k]
            d[:-k] |= mask[k:]
        return d
    s313_long_d = dilate(ls_313); s313_short_d = dilate(ss_313)
    overlap_long = ls_rib & s313_long_d
    overlap_short = ss_rib & s313_short_d
    n_ov = int(overlap_long.sum() + overlap_short.sum())
    pct_of_rib = 100.0 * n_ov / max(1, n_rib)
    print(f"\nهم‌جهت & هم‌زمان (±{W} کندل): {n_ov} bar  = {pct_of_rib:.1f}% از سیگنال‌های S321")
    # همپوشانیِ کلیِ رژیمی (هر جهت، هر زمانِ نزدیک)
    any_overlap = int((rib_any & dilate(s313_any)).sum())
    print(f"همپوشانیِ کلی (هر جهت، ±{W}): {any_overlap} bar = {100.0*any_overlap/max(1,n_rib):.1f}% از S321")
    print(f"\n⇒ ناهمپوشان (سهمِ مستقلِ S321): {100 - pct_of_rib:.1f}%")


if __name__ == '__main__':
    main()
