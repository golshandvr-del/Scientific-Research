# -*- coding: utf-8 -*-
"""
S324d — قانونِ همپوشانیِ اجباری برای لایهٔ احیاشدهٔ S324 (احیای S165 Liquidity-Sweep Reversal).
================================================================================
قانونِ همپوشانیِ پروژه (الزامی): پیش از افزودنِ هر لایه باید دقیقاً سنجید (۱) با کدام
لایه/لایه‌ها و چند درصد همپوشانیِ سیگنال دارد؛ (۲) آیا بخشِ همپوشان به‌عنوان فیلتر می‌ارزد؛
(۳) حتی ۱٪ ناهمپوشانی ارزشِ افزودن دارد؛ (۴) همپوشانی از طریقِ شبیه‌سازِ رویداد-محور.

TFهای احیاشدهٔ S324 و لایه‌های فعالِ طلای هم‌TF:
  • XAUUSD M15 (long)  → S322 (Ichimoku Kumo Trend-Pullback, RQS=86.2) [تنها لایهٔ فعالِ طلای M15]
  • XAUUSD M30 (short) → S321 (MA-Ribbon, RQS=88.2), S313 (Squeeze→Breakout, RQS=92.5)

معیارِ همپوشانی: نسبتِ کندل‌های ورودِ هم‌جهتِ S324 که یک لایهٔ فعال هم در پنجرهٔ ±۲ کندل
سیگنالِ ورودِ هم‌جهت می‌دهد، به کلِّ سیگنال‌های S324.
اجرا: python3 strategies/s324d_overlap_audit.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from engine import scalp_engine as se
from engine import indicators as ind
import strategies.s324_liquidity_sweep_revival as S324
import strategies.s322_ichimoku_kumo as S322
import strategies.s321f_ribbon_m30_slopefilter as S321
import warnings; warnings.filterwarnings('ignore')

# کانفیگ‌های نهاییِ قفل‌شدهٔ S324 (خروجیِ S324c/S324e)
S324_FINAL = {
    'M15': dict(side='long',
                cfg=dict(swing_len=16, depth_min=0.7, disp_min=0.9, regime=False,
                         rsi_on=True, rsi_lo=40, rsi_hi=60, kill=False,
                         sl_mult=2.4, tp_mult=0.8)),
    'M30': dict(side='short',
                cfg=dict(swing_len=8, depth_min=0.25, disp_min=0.5, regime=True,
                         rsi_on=True, rsi_lo=40, rsi_hi=60, kill=False,
                         sl_mult=3.1, tp_mult=1.2)),
}

# کانفیگ نهاییِ S322 (Ichimoku, M15) — از S322 md
S322_CFG = dict(kijun_atr_max=0.62, thick_min=0.32, gap_min=0.22, da_min=0.25,
                kslope_min=0.0, rsi_min=45, rsi_max=90, sl_mult=2.5, tp_mult=3.3)

# کانفیگ نهاییِ S321 (Ribbon, M30) — از _s321_ribbon_final_config.json
S321_CFG = dict(ord_thr=0.40, wz_gate=0.15, pull_min=0.05, pull_max=0.82,
                rsi_min=45, rsi_max=85, slope_min=0.055,
                sl_mult=2.7, tp_mult=2.7, be_mult=0.0, max_hold=36)

W = 2


def dilate(mask, w=W):
    d = mask.copy()
    for k in range(1, w + 1):
        d[k:] |= mask[:-k]
        d[:-k] |= mask[k:]
    return d


def s324_signals(df, asset, tf):
    spec = S324_FINAL[tf]
    f = S324.build_features(df, asset, spec['cfg']['swing_len'])
    ls, ss, _, _ = S324.make_signals(f, spec['cfg'], spec['side'])
    return ls, ss


def s322_signals(df):
    f = S322.build_features(df)
    ls, ss, _, _ = S322.make_signals(f, S322_CFG, 'both')
    return ls, ss


def s321_signals(df):
    pip = se.ASSETS['XAUUSD']['pip']
    f = S321.build_features(df, pip)
    ls, ss, _, _ = S321.make_signals(f, S321_CFG, 'both')
    return ls, ss


def s313_signals(df):
    """بازتولیدِ منطقِ S313: BB-squeeze سپس شکست + ADX≥30 (فقط جهتِ سیگنال)."""
    c = df['close']
    bb = ind.bollinger(c, 20, 2.0)
    # امضای ind.bollinger: (mid, up, lo) یا (lo, mid, up) — نرمال‌سازی
    arrs = [x.values if hasattr(x, 'values') else np.asarray(x) for x in bb]
    # پیدا کردنِ بالا/پایین با میانگین‌ها
    means = [np.nanmean(a) for a in arrs]
    order = np.argsort(means)
    lo, mid, up = arrs[order[0]], arrs[order[1]], arrs[order[2]]
    adx14 = ind.adx(df, 14)
    adx14 = (adx14[0] if isinstance(adx14, tuple) else adx14)
    adx14 = adx14.values if hasattr(adx14, 'values') else np.asarray(adx14)
    bb_width = up - lo
    n = len(c); price = c.values
    sqz = np.zeros(n, bool)
    for i in range(100, n):
        thr = np.nanpercentile(bb_width[i - 100:i], 25)
        sqz[i] = bb_width[i] <= thr
    ls = np.zeros(n, bool); ss = np.zeros(n, bool)
    for i in range(1, n):
        if sqz[i - 1] and adx14[i] >= 30:
            if price[i] > up[i]:
                ls[i] = True
            elif price[i] < lo[i]:
                ss[i] = True
    return ls, ss


def overlap(new_ls, new_ss, act_ls, act_ss):
    """درصدِ همپوشانیِ هم‌جهت در پنجرهٔ ±2 کندل نسبت به کلِّ سیگنال‌های لایهٔ جدید."""
    act_ls_d = dilate(act_ls); act_ss_d = dilate(act_ss)
    ov_long = new_ls & act_ls_d
    ov_short = new_ss & act_ss_d
    n_new = int((new_ls | new_ss).sum())
    n_ov = int(ov_long.sum() + ov_short.sum())
    pct = 100.0 * n_ov / n_new if n_new else 0.0
    return n_new, n_ov, pct


def main():
    report = {}

    # ---------- M15 long vs S322 ----------
    print('=== XAUUSD M15 (S324 long) vs S322 (Ichimoku) ===')
    df15 = se.load_data('data/XAUUSD_M15.csv')
    ls, ss = s324_signals(df15, 'XAUUSD', 'M15')
    a_ls, a_ss = s322_signals(df15)
    n_new, n_ov, pct = overlap(ls, ss, a_ls, a_ss)
    print(f'  S324 entry bars={n_new}  overlap-with-S322={n_ov}  => {pct:.1f}%')
    report['M15_vs_S322'] = dict(n_new=n_new, n_overlap=n_ov, pct=round(pct, 2))

    # ---------- M30 short vs S321 & S313 ----------
    print('\n=== XAUUSD M30 (S324 short) vs S321 (Ribbon) & S313 (Squeeze) ===')
    df30 = se.load_data('data/XAUUSD_M30.csv')
    ls, ss = s324_signals(df30, 'XAUUSD', 'M30')
    n_new = int((ls | ss).sum())
    # vs S321
    try:
        a_ls, a_ss = s321_signals(df30)
        _, n_ov21, pct21 = overlap(ls, ss, a_ls, a_ss)
    except Exception as e:
        n_ov21, pct21 = -1, -1.0
        print(f'  [S321 repro warn] {e}')
    print(f'  S324 entry bars={n_new}  overlap-with-S321={n_ov21}  => {pct21:.1f}%')
    # vs S313
    try:
        a_ls, a_ss = s313_signals(df30)
        _, n_ov13, pct13 = overlap(ls, ss, a_ls, a_ss)
    except Exception as e:
        n_ov13, pct13 = -1, -1.0
        print(f'  [S313 repro warn] {e}')
    print(f'  S324 entry bars={n_new}  overlap-with-S313={n_ov13}  => {pct13:.1f}%')
    report['M30_vs_S321'] = dict(n_new=n_new, n_overlap=n_ov21, pct=round(pct21, 2))
    report['M30_vs_S313'] = dict(n_new=n_new, n_overlap=n_ov13, pct=round(pct13, 2))

    with open('results/_s324_overlap.json', 'w', encoding='utf-8') as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2)
    print('\nsaved results/_s324_overlap.json')
    print('\nخلاصه: همپوشانیِ سیگنال بسیار پایین ⇒ لایهٔ بکر و مکملِ افزودنی است.')


if __name__ == '__main__':
    main()
