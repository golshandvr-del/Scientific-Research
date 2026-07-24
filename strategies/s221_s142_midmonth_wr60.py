# -*- coding: utf-8 -*-
"""
s221_s142_midmonth_wr60.py — ارتقای WR لایهٔ S142 (Mid-Month Drift طلا) به ≥۶۰٪
================================================================================
> قانونِ احیای پروژه (این نشست): WR را به هر قیمتی بالای ۶۰٪ ببر؛ سودِ خالص می‌تواند
> کاهش یابد به شرطِ تضمینِ WR≥۶۰٪. تابعِ هدف = بیشینهٔ net مشروط بر WR≥۶۰ و net>0 و
> گیتِ سختِ ضدِ overfit (هر دو نیمه + ۴/۴ walk-forward مثبت، n≥۳۰).

لایهٔ پایه (S142): روزهای تقویمیِ {۱۰,۱۳,۲۰} ماه، ساعتِ {۱..۱۲} UTC، LONG طلا.
  نسخهٔ رکورد: SL100/TP500/mh96 ⇒ WR=۳۵.۵٪، net=+$21,012 (audit ۴ ساله).
  ❌ زیرِ کفِ ۶۰٪. این اسکریپت با دو اهرم (بازطراحیِ TP/SL + فیلترها) WR را بالا می‌برد.

قانونِ مولتی‌تایم‌فریم: XAUUSD M5, M15, M30, H1 مستقل (M1 برای طلا موجود نیست ⇒ از M5 شروع).
================================================================================
"""
import os, sys, json, itertools
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import strategies.s220_wr60_booster as B
from engine import scalp_engine as se

# TFهای طلا برای این لایه. mh هر TF نسبت به M15 مقیاس می‌شود (M15=96 پایه).
TF_LIST = ['M5', 'M15', 'M30', 'H1']
MH_BASE_M15 = 96
MH_SCALE = {'M5': 3.0, 'M15': 1.0, 'M30': 0.5, 'H1': 0.25}

# فضای TP/SL (بر حسبِ pip موتور، pip=0.10 برای طلا). WR-friendly تا نامتقارن.
# نکته: برای WR بالا، TP کوچک نسبت به SL کلیدی است.
SL_GRID = [80, 100, 150, 200, 300]
TP_GRID = [40, 60, 80, 100, 150, 200]

# مجموعه فیلترهای کاندید (ترکیب تا ۳تایی برای مهارِ فضای جستجو؛ User Note: بدونِ سقف،
# اما عملاً ۳ فیلترِ قوی معمولاً کافی است — اگر لازم شد تا ۴ گسترش می‌دهیم).
FILTER_POOL = ['ema20>50', 'ema50>100', 'ema20>50>100', 'price>ema200',
               'rsi40-70', 'rsi<70', 'rsi>50', 'adx>20', 'adx>25', 'pdi>mdi',
               'bull_bar', 'atr<1.8med', 'atr>0.5med']
MAX_FILTERS = 3


def base_signal_s142(df):
    """سیگنالِ پایهٔ S142: روزهای {۱۰,۱۳,۲۰}، ساعتِ {۱..۱۲}."""
    return (np.isin(df['dom'].values, [10, 13, 20]) &
            np.isin(df['hour'].values, list(range(1, 13))))


def run_tf(tf):
    asset = 'XAUUSD' if tf == 'M15' else f'XAUUSD_{tf}'
    df = B.add_indicators(B.add_calendar(B.load(f'XAUUSD_{tf}')))
    df = B.last_n_years(df, 4)
    df = B.add_indicators(B.add_calendar(df.copy().reset_index(drop=True)))
    n = len(df)
    zeros = np.zeros(n, bool)
    mh = max(4, int(round(MH_BASE_M15 * MH_SCALE[tf])))

    base = base_signal_s142(df)
    n_base = int(base.sum())
    print(f"\n[{tf}] کندل={n:,}  mh={mh}  سیگنالِ پایه(S142)={n_base}", flush=True)
    if n_base < B.MIN_TRADES:
        print(f"  ⏭️  سیگنالِ پایه کمتر از {B.MIN_TRADES} ⇒ رد این TF.")
        return None

    F = B.build_filters(df)
    # فهرستِ ترکیب‌های فیلتر: از صفر (فقط بازطراحیِ TP/SL) تا MAX_FILTERS
    filter_combos = [()]
    for k in range(1, MAX_FILTERS + 1):
        filter_combos += list(itertools.combinations(FILTER_POOL, k))

    best = None
    best_wr_any = None  # بهترین WR حتی اگر net منفی (برای گزارشِ تشخیصی)
    tested = 0
    for fcombo in filter_combos:
        fmask = base.copy()
        for fname in fcombo:
            fmask = fmask & F[fname]
        if int(fmask.sum()) < B.MIN_TRADES:
            continue
        for sl in B.__dict__.get('SL_GRID_OVERRIDE', SL_GRID):
            for tp in TP_GRID:
                tested += 1
                res = B.eval_signal(df, fmask, zeros, sl, tp, mh, asset)
                if res is None or res['n'] < B.MIN_TRADES:
                    continue
                if best_wr_any is None or res['wr'] > best_wr_any['wr']:
                    best_wr_any = dict(wr=res['wr'], net=res['net'], n=res['n'],
                                       sl=sl, tp=tp, f=fcombo)
                # قیدِ اصلی: WR≥۶۰ و net>0
                if res['wr'] >= B.WR_FLOOR and res['net'] > 0:
                    passed, detail = B.antioverfit_gates(res, df)
                    if passed:
                        cand = dict(wr=res['wr'], net=res['net'], n=res['n'],
                                    pf=res['pf'], sl=sl, tp=tp, mh=mh,
                                    f=list(fcombo), detail=detail)
                        # بیشینهٔ net میانِ گیت-پاس‌ها
                        if best is None or cand['net'] > best['net']:
                            best = cand
    print(f"  تعدادِ پیکربندیِ آزموده‌شده: {tested}")
    if best:
        print(f"  ✅ برنده: WR={best['wr']:.1f}%  net={best['net']:+,.0f}$  n={best['n']}  "
              f"SL{best['sl']}/TP{best['tp']} mh{best['mh']}")
        print(f"     فیلترها: {best['f']}")
        print(f"     گیت: {best['detail']}")
    else:
        if best_wr_any:
            print(f"  ❌ هیچ پیکربندیِ WR≥۶۰ با net>0 و گیت-پاس یافت نشد.")
            print(f"     بهترین WR ممکن: {best_wr_any['wr']:.1f}% (net={best_wr_any['net']:+,.0f}, "
                  f"SL{best_wr_any['sl']}/TP{best_wr_any['tp']}, f={best_wr_any['f']})")
    return dict(tf=tf, best=best, best_wr_any=best_wr_any)


def main():
    print("=" * 92)
    print("S221 — ارتقای S142 (Mid-Month طلا) به WR≥۶۰٪ | تابعِ هدف: max net s.t. WR≥۶۰ + گیتِ سخت")
    print("=" * 92)
    out = {}
    for tf in TF_LIST:
        r = run_tf(tf)
        if r:
            out[tf] = dict(
                best=r['best'],
                best_wr_any=r['best_wr_any'],
            )
    with open(os.path.join(B.RESULTS, '_s221_s142_wr60.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print("\n✅ ذخیره شد: results/_s221_s142_wr60.json")


if __name__ == '__main__':
    main()
