# -*- coding: utf-8 -*-
"""
S177-FILTER — «Reversal-Bar-Quality» به‌عنوان فیلترِ تأیید روی لایه‌های مرزی (قانونِ همپوشانی)
================================================================================
هدفِ پروژه: بیشینه‌سازیِ سودِ خالص (XAUUSD+EURUSD)؛ WR فقط کفِ ۴۰٪.

منشأ: در S177-finalize دیدیم که سیگنالِ reversal-bar (فصلِ ۵ Brooks) یک لبهٔ *واقعی*
است (Δ نسبت به baseline long-bias = +$1,840، خام WF 4/4)، اما ۶۶٪ با اجتماعِ LONGِ
طلا همپوشان و سهمِ مستقلش n<30 می‌شود ⇒ به‌عنوان لایهٔ مستقل ثبت‌ناپذیر.

طبقِ **قانونِ همپوشانیِ صریحِ پرامپت** («از درصدِ همپوشان به‌عنوان فیلتر استفاده کن و
WR را بالا ببر؛ این را به مراحلِ بعد موکول نکن»)، پیش از هر تصمیمِ نهایی این آزمون:

  فیلترِ `recent-reversal(w)` = «آیا در w کندلِ اخیر یک bull-reversal-bar قوی (طبقِ
  هندسهٔ فصلِ ۵) رخ داده؟» را روی لایه‌های مرزیِ LONG (S140 Monday⁺، S142 Mid-Month،
  S143 EURUSD Mid-Month⁺) AND می‌کنیم. اگر WR↑ و net↑ هم‌زمان ⇒ بهبودِ ثبت‌پذیر
  (راهِ اولِ پروژه). سپس اعتبارسنجیِ walk-forward + هر دو نیمه.

گیت (سیب‌به‌سیب با S170/S171): WR_new≥WR_base و ≥40 و net_new≥net_base و n≥30،
سپس walk-forward هر ۴ پنجره net>0 و WR≥40 و هر دو نیمه مثبت.
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(__file__))
import s171_brooks_signs_of_strength_filter as G   # load, lastn, cal, confirms, stats, sim, KEYS
import s177_brooks_reversal_bar as R
from engine import indicators as ind

WR_FLOOR = 40.0


def recent_reversal_filter(df, side, w, tail_frac=0.5, up_frac=0.35, cc=4, hh=3, lb=20,
                           ema_fast=10, ema_slow=30):
    """فیلتر: «آیا در w کندلِ اخیر یک reversal-bar (طبقِ هندسهٔ S177) رخ داده؟»
    سیگنالِ reversal خودش قبلاً shift(1) شده (causal). سپس rolling-max روی w کندل."""
    rev = R.reversal_bar_signals(df, side, tail_frac, up_frac, cc, hh, lb, ema_fast, ema_slow)
    recent = pd.Series(rev.astype(float)).rolling(w, min_periods=1).max().to_numpy() > 0
    return recent


def walk_forward_layer(df, sig, sl, tp, mh, asset, nwin=4):
    n = len(df); out = []
    z = np.zeros(len(df), bool)
    for k in range(nwin):
        a = int(n * k / nwin); b = int(n * (k + 1) / nwin)
        sub = df.iloc[a:b].reset_index(drop=True)
        sg = sig[a:b]
        z2 = np.zeros(len(sub), bool)
        if sg.sum() < 5:
            out.append((0.0, 0.0, 0)); continue
        t = G.sim(sub, sg, z2, sl, tp, mh, asset)
        r = G.stats(t, asset)
        out.append((round(r['net'], 1), round(r['wr'], 1), int(r['n'])))
    return out


def halves_layer(df, sig, sl, tp, mh, asset):
    z = np.zeros(len(df), bool)
    n = len(df); h = n // 2
    t1 = G.sim(df.iloc[:h].reset_index(drop=True), sig[:h], z[:h], sl, tp, mh, asset)
    t2 = G.sim(df.iloc[h:].reset_index(drop=True), sig[h:], z[h:], sl, tp, mh, asset)
    r1 = G.stats(t1, asset); r2 = G.stats(t2, asset)
    return r1['net'], r2['net']


def evaluate_layer(name, df, base_sig, sl, tp, mh, asset):
    z = np.zeros(len(df), bool)
    base = G.stats(G.sim(df, base_sig, z, sl, tp, mh, asset), asset)
    variants = []
    for w in (24, 48, 96, 192):
        for (tf, uf) in [(0.5, 0.35), (0.33, 0.25)]:
            filt = recent_reversal_filter(df, 'long', w, tail_frac=tf, up_frac=uf)
            sig = base_sig & filt
            r = G.stats(G.sim(df, sig, z, sl, tp, mh, asset), asset)
            variants.append(dict(mode=f'rev_w{w}_tf{tf}_uf{uf}', w=w, tf=tf, uf=uf, **r))

    def ok(v):
        return (v['n'] >= 30 and v['wr'] >= WR_FLOOR and v['wr'] >= base['wr']
                and v['net'] >= base['net'])
    accepted = [v for v in variants if ok(v)]
    accepted.sort(key=lambda v: v['net'], reverse=True)
    best = accepted[0] if accepted else None

    valid = None
    if best:
        filt = recent_reversal_filter(df, 'long', best['w'], tail_frac=best['tf'], up_frac=best['uf'])
        sig = base_sig & filt
        wf = walk_forward_layer(df, sig, sl, tp, mh, asset)
        h1, h2 = halves_layer(df, sig, sl, tp, mh, asset)
        wf_ok = all(x[0] > 0 and x[1] >= WR_FLOOR for x in wf)
        both_ok = (h1 > 0 and h2 > 0)
        valid = dict(wf=wf, wf_ok=wf_ok, h1=round(h1, 1), h2=round(h2, 1), both_ok=both_ok,
                     final_ok=bool(wf_ok and both_ok))
    return dict(name=name, asset=asset, base=base, variants=variants,
                best_filter=best, delta_net=(best['net'] - base['net']) if best else 0.0,
                valid=valid)


def main():
    print("=" * 100)
    print("S177-FILTER — «recent Reversal-Bar» به‌عنوان فیلترِ تأیید روی لایه‌های مرزیِ LONG")
    print("گیت: WR↑ (≥base و ≥40) و net↑ (≥base) + walk-forward 4/4 + هر دو نیمه. هدف=سودِ خالص.")
    print("=" * 100, flush=True)

    layers = []

    dfx = G.cal(G.lastn(G.cal(G.load('XAUUSD_M15'))))
    sc_g = G.confirms(dfx, G.KEYS)
    b140 = ((dfx['dow'].values == 0) & np.isin(dfx['hour'].values, [18, 19, 20, 21])) & (sc_g >= 3)
    layers.append(evaluate_layer('S140 Monday+', dfx, b140, 100, 300, 96, 'XAUUSD'))
    b142 = np.isin(dfx['dom'].values, [10, 13, 20]) & np.isin(dfx['hour'].values, list(range(1, 13)))
    layers.append(evaluate_layer('S142 Mid-Month', dfx, b142, 100, 500, 96, 'XAUUSD'))

    dfe = G.cal(G.lastn(G.cal(G.load('EURUSD_M15'))))
    sc_e = G.confirms(dfe, G.KEYS)
    b143 = (np.isin(dfe['dom'].values, [3, 9, 20]) &
            np.isin(dfe['hour'].values, [1, 2, 3, 4, 5, 11, 12, 13, 14, 15]) & (sc_e >= 2))
    layers.append(evaluate_layer('S143 EURUSD Mid-Month+', dfe, b143, 20, 40, 96, 'EURUSD'))

    total_delta = 0.0
    for L in layers:
        b = L['base']
        print(f"\n### {L['name']} ({L['asset']}) ###")
        print(f"  base: net=${b['net']:+,.0f} WR={b['wr']:.1f}% n={b['n']} PF={b['pf']:.2f}")
        if L['best_filter']:
            v = L['best_filter']
            print(f"  فیلترِ برنده [{v['mode']}]: net=${v['net']:+,.0f} WR={v['wr']:.1f}% n={v['n']} "
                  f"PF={v['pf']:.2f} ⇒ Δnet=${L['delta_net']:+,.0f}")
            if L['valid']:
                vv = L['valid']
                print(f"    walk-forward: {'/'.join(f'{x[0]:+.0f}' for x in vv['wf'])}  "
                      f"WF_ok={vv['wf_ok']} h1={vv['h1']} h2={vv['h2']} both={vv['both_ok']} "
                      f"=> {'✅ ثبت‌پذیر' if vv['final_ok'] else '⛔ اعتبارسنجی رد'}")
                if vv['final_ok']:
                    total_delta += L['delta_net']
        else:
            print("  ⛔ هیچ فیلتری هم‌زمان WR↑ و net↑ نداد.")

    print("\n" + "=" * 100)
    print(f"مجموعِ Δ سودِ خالصِ ثبت‌پذیر از فیلترِ reversal-bar: ${total_delta:+,.0f}")
    print("=" * 100)

    with open('results/_s177_filter.json', 'w') as f:
        json.dump(dict(layers=layers, total_delta=total_delta), f,
                  ensure_ascii=False, indent=1, default=float)
    print("✅ ذخیره شد: results/_s177_filter.json")


if __name__ == '__main__':
    main()
