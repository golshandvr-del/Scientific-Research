# -*- coding: utf-8 -*-
"""
s222_all_timedrift_wr60.py — ارتقای همهٔ لایه‌های زمان-محور به WR ≥ ۶۰٪ (قانونِ احیا)
================================================================================
> قانونِ احیای پروژه (این نشست): WR را به هر قیمتی بالای ۶۰٪ ببر؛ سودِ خالص می‌تواند
> کاهش یابد. تابعِ هدف = بیشینهٔ net مشروط بر WR≥۶۰ + net>0 + گیتِ سختِ ضدِ overfit.

لایه‌های زمان-محورِ فعلی (طبقِ audit، همه زیرِ ۶۰٪):
  • S139 Overnight  (طلا) — hour∈{22,23}                    WR فعلی ۴۲.۲٪
  • S140 Monday     (طلا) — dow=0 & hour∈{18..21}           WR فعلی ۳۹.۷٪
  • S141 Turn-of-Month (طلا) — tom_rel=1 & hour∈{7..12}     WR فعلی ۴۲.۷٪
  • S144 End-of-Month  (طلا) — from_end∈{-6,-7,-8} & h∈{19..23}  WR فعلی ۴۳.۴٪
  • S143 EURUSD Mid-Month — dom∈{3,9,20} & h∈{1..5,11..15}  WR فعلی ۳۴.۰٪
(S142 قبلاً در S221 ارتقا یافت.)

قانونِ مولتی‌تایم‌فریم: طلا از M5 (M1 موجود نیست)؛ EURUSD از M1.
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import strategies.s220_wr60_booster as B

SL_GRID = [80, 100, 150, 200, 300]
TP_GRID = [40, 60, 80, 100, 150, 200]
FILTER_POOL = ['ema20>50', 'ema50>100', 'ema20>50>100', 'price>ema200',
               'rsi40-70', 'rsi<70', 'rsi>50', 'adx>20', 'adx>25', 'pdi>mdi',
               'bull_bar', 'atr<1.8med', 'atr>0.5med']
MAX_FILTERS = 3
MH_BASE_M15 = 96
GOLD_TF = ['M5', 'M15', 'M30', 'H1']
GOLD_MH = {'M5': 288, 'M15': 96, 'M30': 48, 'H1': 24}
EUR_TF = ['M1', 'M5', 'M15', 'M30']
EUR_MH = {'M1': 480, 'M5': 288, 'M15': 96, 'M30': 48}


def assign_from_end(df):
    days = df[['date', 'ym']].drop_duplicates('date').reset_index(drop=True)
    days['rank_in_month'] = days.groupby('ym').cumcount() + 1
    days['cnt_in_month'] = days.groupby('ym')['date'].transform('count')
    days['from_end'] = days['rank_in_month'] - days['cnt_in_month'] - 1
    df['from_end'] = df['date'].map(dict(zip(days['date'], days['from_end']))).astype(int)
    def rel(r):
        return int(r['from_end']) if r['from_end'] >= -2 else int(r['rank_in_month'])
    days['tom_rel'] = days.apply(rel, axis=1)
    df['tom_rel'] = df['date'].map(dict(zip(days['date'], days['tom_rel']))).astype(int)
    return df


# ---- سازنده‌های سیگنالِ پایه (منطقِ ورودِ اصلیِ هر لایه، بدونِ TP/SL) ----
def sig_s139(df):  # Overnight
    return np.isin(df['hour'].values, [22, 23])

def sig_s140(df):  # Monday
    return (df['dow'].values == 0) & np.isin(df['hour'].values, [18, 19, 20, 21])

def sig_s141(df):  # Turn-of-Month
    return (df['tom_rel'].values == 1) & np.isin(df['hour'].values, [7, 8, 9, 10, 11, 12])

def sig_s144(df):  # End-of-Month pre-end
    return np.isin(df['from_end'].values, [-6, -7, -8]) & np.isin(df['hour'].values, [19, 20, 21, 22, 23])

def sig_s143_eur(df):  # EURUSD Mid-Month
    return np.isin(df['dom'].values, [3, 9, 20]) & np.isin(df['hour'].values, [1, 2, 3, 4, 5, 11, 12, 13, 14, 15])


LAYERS = [
    dict(id='S139', name='Overnight',      pair='XAU', sig=sig_s139, needs='cal'),
    dict(id='S140', name='Monday',         pair='XAU', sig=sig_s140, needs='cal'),
    dict(id='S141', name='TurnOfMonth',    pair='XAU', sig=sig_s141, needs='tom'),
    dict(id='S144', name='EndOfMonth',     pair='XAU', sig=sig_s144, needs='tom'),
    dict(id='S143', name='EurMidMonth',    pair='EUR', sig=sig_s143_eur, needs='cal'),
]


def prep(pair, tf, needs):
    name = f'{"XAUUSD" if pair=="XAU" else "EURUSD"}_{tf}'
    df = B.add_indicators(B.add_calendar(B.load(name)))
    df = B.last_n_years(df, 4).reset_index(drop=True)
    df = B.add_calendar(df)
    if needs == 'tom':
        df = assign_from_end(df)
    df = B.add_indicators(df)
    return df


def run_layer(layer):
    pair = layer['pair']
    tfs = GOLD_TF if pair == 'XAU' else EUR_TF
    mhmap = GOLD_MH if pair == 'XAU' else EUR_MH
    asset_base = 'XAUUSD' if pair == 'XAU' else 'EURUSD'
    print("\n" + "=" * 84)
    print(f"لایهٔ {layer['id']} «{layer['name']}» ({asset_base}) — ارتقا به WR≥۶۰٪")
    print("=" * 84)
    res_tf = {}
    for tf in tfs:
        try:
            df = prep(pair, tf, layer['needs'])
        except FileNotFoundError:
            print(f"  [{tf}] داده موجود نیست ⇒ رد.")
            continue
        asset = asset_base if tf == 'M15' else f'{asset_base}_{tf}'
        base = layer['sig'](df)
        nb = int(base.sum())
        mh = mhmap[tf]
        print(f"\n  [{tf}] کندل={len(df):,} mh={mh} سیگنالِ پایه={nb}", flush=True)
        if nb < B.MIN_TRADES:
            print(f"    ⏭️ سیگنالِ پایه < {B.MIN_TRADES} ⇒ رد.")
            continue
        out = B.boost_layer(df, base, asset, mh, SL_GRID, TP_GRID, FILTER_POOL,
                            max_filters=MAX_FILTERS, side='long', top_tpsl=4)
        best = out['best']; bwa = out['best_wr_any']
        if best:
            print(f"    ✅ WR={best['wr']:.1f}% net={best['net']:+,.0f}$ n={best['n']} "
                  f"SL{best['sl']}/TP{best['tp']} f={best['f']}")
            print(f"       گیت: {best['detail']}")
            res_tf[tf] = best
        else:
            msg = f"    ❌ گیت-پاسِ WR≥۶۰ نیافت."
            if bwa:
                msg += f" بهترین WR={bwa['wr']:.1f}% (net={bwa['net']:+,.0f}, SL{bwa['sl']}/TP{bwa['tp']}, f={bwa['f']})"
            print(msg)
            res_tf[tf] = None
    return res_tf


def main():
    print("=" * 84)
    print("S222 — ارتقای همهٔ لایه‌های زمان-محور به WR≥۶۰٪ | max net s.t. WR≥۶۰ + گیتِ سخت")
    print("=" * 84)
    allout = {}
    grand_net = 0.0
    for layer in LAYERS:
        r = run_layer(layer)
        allout[layer['id']] = {tf: v for tf, v in r.items()}
        for tf, v in r.items():
            if v:
                grand_net += v['net']
    print("\n" + "=" * 84)
    print(f"🥇 جمعِ net همهٔ لایه‌های زمان-محورِ گیت-پاسِ WR≥۶۰ (این اسکریپت): {grand_net:+,.0f}$")
    print("=" * 84)
    with open(os.path.join(B.RESULTS, '_s222_all_timedrift_wr60.json'), 'w') as f:
        json.dump(allout, f, ensure_ascii=False, indent=2, default=float)
    print("✅ ذخیره شد: results/_s222_all_timedrift_wr60.json")


if __name__ == '__main__':
    main()
