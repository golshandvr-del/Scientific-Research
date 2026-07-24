# -*- coding: utf-8 -*-
"""
s224_s81_swing_wr60.py — احیای استراتژیِ سوختهٔ S81 (Swing-Pullback طلا) به WR ≥ ۶۰٪
================================================================================
> قانونِ احیای پروژه (این نشست): WR را به هر قیمتی بالای ۶۰٪ ببر؛ سودِ خالص می‌تواند
> کاهش یابد. تابعِ هدف = بیشینهٔ net مشروط بر WR≥۶۰ + net>0 + گیتِ سختِ ضدِ overfit.

استراتژیِ سوختهٔ S81:
  • منطقِ پایه (audit خطِ ۲۱۸): EMA20>EMA100  &  RSI14<35  ⇒ Long (pullback در روندِ صعودی)
  • پارامترِ سوختهٔ اصلی: SL120/TP1200/mh144 (نسبتِ TP:SL = ۱:۱۰) ⇒ WR = ۲۸.۲٪  ← سوخت.

فرضیهٔ احیا: با معکوس‌کردنِ نامتقارنیِ TP/SL (TP کوچک/SL بزرگ) + فیلترهای مومنتوم،
همان سیگنالِ pullback باید WR≥۶۰ بدهد. روی چند TF آزموده می‌شود (مولتی‌تایم‌فریم).
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


def base_s81(df):
    """S81 Swing-Pullback: EMA20>EMA100 & RSI14<35 ⇒ Long."""
    c = df['close']
    e20 = ind.ema(c, 20).values
    e100 = ind.ema(c, 100).values
    r14 = ind.rsi(c, 14).values
    ls = (e20 > e100) & (r14 < 35)
    return np.nan_to_num(ls, nan=False).astype(bool)


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
    print("S224 — احیای استراتژیِ سوختهٔ S81 (Swing-Pullback طلا) به WR≥۶۰٪")
    print("=" * 84)
    out = os.path.join(ROOT, 'results', '_s224_s81_swing_wr60.json')
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
        base = base_s81(df)
        asset = 'XAUUSD' if tf == 'M15' else f'XAUUSD_{tf}'
        best = boost(tf, df, base, asset, GOLD_MH[tf])
        res[tf] = best if best else {}
        with open(out, 'w') as f:
            json.dump(res, f, ensure_ascii=False, indent=1, default=float)
        print(f"💾 ذخیرهٔ افزایشیِ {tf}")

    total = sum(b['net'] for b in res.values() if b)
    print("\n" + "=" * 84)
    print(f"🥇 جمعِ net گیت-پاسِ WR≥۶۰ (S81 احیا): {total:+,.0f}$")
    print("=" * 84)
    print(f"✅ ذخیره شد: {out}")


if __name__ == '__main__':
    main()
