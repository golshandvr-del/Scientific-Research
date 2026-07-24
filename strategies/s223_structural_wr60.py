# -*- coding: utf-8 -*-
"""
s223_structural_wr60.py — ارتقای لایه‌های ساختاری/رژیم‌محور به WR ≥ ۶۰٪ (قانونِ احیا)
================================================================================
> قانونِ احیای پروژه (این نشست): WR را به هر قیمتی بالای ۶۰٪ ببر؛ سودِ خالص می‌تواند
> کاهش یابد. تابعِ هدف = بیشینهٔ net مشروط بر WR≥۶۰ + net>0 + گیتِ سختِ ضدِ overfit.

لایه‌های ساختاریِ فعلی (همه زیرِ ۶۰٪ طبقِ audit):
  • SHORT-MA-Confluence (طلا، Short) — کراسِ نزولیِ میانگینِ [EMA50,EMA100,SMA200]  WR ۴۸.۷٪
  • S168 Brooks High-2 (طلا، Long)  — شمارندهٔ two-legged pullback                WR ~۴۸.۸٪
  • S168 Brooks Low-2  (طلا، Short) — قرینه                                         (بررسی)

منطقِ پایه از audit و s168_brooks_high2_low2 بازتولید می‌شود؛ سپس boost_layer برای
یافتنِ TP/SL + فیلترهایی که WR را به ≥۶۰٪ برسانند اجرا می‌شود.

قانونِ مولتی‌تایم‌فریم: طلا از M5 (M1 موجود نیست).
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import strategies.s220_wr60_booster as B
from engine import indicators as ind
from s168_brooks_high2_low2 import count_high2_low2

SL_GRID = [80, 100, 150, 200, 300]
TP_GRID = [40, 60, 80, 100, 150, 200]
FILTER_POOL = ['ema20>50', 'ema50>100', 'ema20>50>100', 'price>ema200',
               'rsi40-70', 'rsi<70', 'rsi>50', 'adx>20', 'adx>25', 'pdi>mdi',
               'bull_bar', 'atr<1.8med', 'atr>0.5med']
MAX_FILTERS = 3
GOLD_TF = ['M5', 'M15', 'M30', 'H1']
GOLD_MH = {'M5': 288, 'M15': 96, 'M30': 48, 'H1': 24}


def base_short_ma(df):
    """SHORT-MA-Confluence: قیمت میانگینِ [EMA50,EMA100,SMA200] را رو به پایین می‌شکند ⇒ Short."""
    c = df['close']
    e50 = ind.ema(c, 50).values
    e100 = ind.ema(c, 100).values
    s200 = ind.sma(c, 200).values
    mid = np.nanmean(np.column_stack([e50, e100, s200]), axis=1)
    price = c.values
    prev_above = np.r_[False, price[:-1] > mid[:-1]]
    sh = prev_above & (price < mid)
    return np.nan_to_num(sh, nan=False).astype(bool)


def base_brooks(df, side, ema_fast=20, ema_slow=50):
    """Brooks High-2 (long) / Low-2 (short) — ورود روی کندلِ بعدی (shift)."""
    long_evt, short_evt = count_high2_low2(df, ema_fast, ema_slow)
    long_sig = pd.Series(long_evt).shift(1).fillna(False).to_numpy()
    short_sig = pd.Series(short_evt).shift(1).fillna(False).to_numpy()
    return long_sig if side == 'long' else short_sig


def boost(tag, df, base_sig, asset, mh, side):
    n_base = int(base_sig.sum())
    print(f"  [{tag}] کندل={len(df):,} mh={mh} سیگنالِ پایه={n_base}", flush=True)
    if n_base < B.MIN_TRADES:
        print(f"    ⏭️  سیگنالِ پایه < {B.MIN_TRADES} ⇒ رد.")
        return None
    out = B.boost_layer(df, base_sig, asset, mh, SL_GRID, TP_GRID, FILTER_POOL,
                        max_filters=MAX_FILTERS, side=side, top_tpsl=4)
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


def run_gold_layer(name, sig_fn, side):
    print("\n" + "=" * 84)
    print(f"لایهٔ {name} (XAUUSD, {side}) — ارتقا به WR≥۶۰٪")
    print("=" * 84)
    res = {}
    for tf in GOLD_TF:
        df = B.add_indicators(B.add_calendar(B.load(f'XAUUSD_{tf}')))
        df = B.last_n_years(df, 4)
        df = B.add_indicators(B.add_calendar(df.copy().reset_index(drop=True)))
        base = sig_fn(df)
        # M15 از کلیدِ پایهٔ 'XAUUSD' استفاده می‌کند؛ بقیه TFها کلیدِ per-TF
        asset = 'XAUUSD' if tf == 'M15' else f'XAUUSD_{tf}'
        best = boost(tf, df, base, asset, GOLD_MH[tf], side)
        if best:
            res[tf] = best
    return res


def main():
    print("=" * 84)
    print("S223 — ارتقای لایه‌های ساختاری/رژیم‌محور به WR≥۶۰٪ | max net s.t. WR≥۶۰ + گیت")
    print("=" * 84)
    all_res = {}

    all_res['SHORT_MA'] = run_gold_layer('SHORT-MA-Confluence', base_short_ma, 'short')
    all_res['BROOKS_HIGH2'] = run_gold_layer('Brooks High-2', lambda d: base_brooks(d, 'long'), 'long')
    all_res['BROOKS_LOW2'] = run_gold_layer('Brooks Low-2', lambda d: base_brooks(d, 'short'), 'short')

    total = 0.0
    for layer, tfres in all_res.items():
        for tf, b in tfres.items():
            total += b['net']
    print("\n" + "=" * 84)
    print(f"🥇 جمعِ net همهٔ لایه‌های ساختاریِ گیت-پاسِ WR≥۶۰ (این اسکریپت): {total:+,.0f}$")
    print("=" * 84)

    out = os.path.join(ROOT, 'results', '_s223_structural_wr60.json')
    with open(out, 'w') as f:
        json.dump(all_res, f, ensure_ascii=False, indent=1, default=float)
    print(f"✅ ذخیره شد: {out}")


if __name__ == '__main__':
    main()
