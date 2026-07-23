# -*- coding: utf-8 -*-
"""
S212c — فیلترِ «عدم‌تقارنِ دیدِ معکوس» (Brooks فصلِ ۹) روی لایه‌های زمان-محورِ مرزی
=================================================================================================
قانونِ همپوشانیِ اجباری (راهِ اولِ پروژه = بهبود): چون کاندیدِ مستقلِ S212 گیت را رد کرد
(WF W4 منفی)، پیش از رفتن به فصلِ بعد، امکانِ استفادهٔ فیلتر روی لایه‌های موجود بررسی می‌شود.

تزِ فصلِ ۹: یک ستاپ که در منظرِ معکوس یک "rounding bottom" (اصلاحِ محدب/کم‌شتاب) دیده می‌شود
تله است. معیارِ عملیاتی (S212.inverse_view_asym): asym بالا ⇒ اصلاحِ اخیر محدب/rounding ⇒ رد.
فیلتر: ورود تنها وقتی مجاز که asym_recent ≤ thr (یا اصلاً اصلاحی نبوده ⇒ nan ⇒ خنثی).

هم‌سو با S170: همان سه لایهٔ مرزی (S140 Monday⁺، S142 Mid-Month، S143 EURUSD Mid-Month⁺)
و همان baseline‌ها. معیارِ پذیرش (قانونِ #۱ = هدف سودِ خالص): **net↑** و WR≥40 (WR نباید افت
کند زیرِ کف). گزارشِ کاملِ گرید + walk-forward برای موردِ برنده.
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import s170_brooks_high2_filter_on_timedrift as B   # load/lastn/cal/sim/stats/confirms/KEYS
import s212_brooks_inverse_view as M
from engine import scalp_engine as se

WR_FLOOR = 40.0
CAP, RISK = 10000.0, 1.0


def recent_asym_ok(df, lb, thr):
    """فیلترِ bool: آیا asymِ اصلاحِ اخیر ≤ thr است (یا اصلاحی نبوده)؟ causal (shift(1))."""
    asym = M.inverse_view_asym(df, lb)
    asym_s = pd.Series(asym).shift(1).to_numpy()
    keep = (asym_s <= thr) | np.isnan(asym_s)
    return keep


def wf_halves(df, sig, sl, tp, mh, asset):
    z = np.zeros(len(df), bool)
    tr = B.sim(df, sig, z, sl, tp, mh, asset)
    if tr is None or len(tr) < 8:
        return None
    _, _, pt = se.run_capital_pertrade(tr, asset, initial_capital=CAP, risk_pct=RISK, compounding=False)
    nu = pt['net_usd'].to_numpy()
    h = len(nu) // 2; q = len(nu) // 4
    h1 = float(nu[:h].sum()); h2 = float(nu[h:].sum())
    wf = [round(float(nu[i*q:(i+1)*q].sum())) for i in range(4)]
    return dict(h1=h1, h2=h2, wf=wf)


def evaluate_layer(name, df, base_sig, sl, tp, mh, asset):
    z = np.zeros(len(df), bool)
    base = B.stats(B.sim(df, base_sig, z, sl, tp, mh, asset), asset)
    variants = []
    for lb in (12, 20, 32):
        for thr in (0.3, 0.5, 1.0, 2.0):
            keep = recent_asym_ok(df, lb, thr)
            sig = base_sig & keep
            if sig.sum() < 30:
                continue
            r = B.stats(B.sim(df, sig, z, sl, tp, mh, asset), asset)
            variants.append(dict(mode=f'asym_lb{lb}_thr{thr}', lb=lb, thr=thr, **r))
    # معیارِ پذیرش (قانونِ #۱): net↑ نسبت به base و WR≥40 و WR≥base (WR نباید افت کند)
    def ok(v):
        return (v['n'] >= 30 and v['wr'] >= WR_FLOOR and v['net'] > base['net'] and v['wr'] >= base['wr'])
    acc = [v for v in variants if ok(v)]
    acc.sort(key=lambda v: -v['net'])
    best = acc[0] if acc else None
    # walk-forward برای موردِ برنده
    wf_ok = False
    if best:
        keep = recent_asym_ok(df, best['lb'], best['thr'])
        wh = wf_halves(df, base_sig & keep, sl, tp, mh, asset)
        if wh:
            wf_ok = (wh['h1'] > 0 and wh['h2'] > 0 and all(w > 0 for w in wh['wf']))
            best['h1'] = wh['h1']; best['h2'] = wh['h2']; best['wf'] = wh['wf']; best['wf_ok'] = wf_ok
    return dict(name=name, asset=asset, base=base, variants=variants, best=best,
                delta_net=(best['net'] - base['net']) if (best and wf_ok) else 0.0,
                accepted=bool(best and wf_ok))


def main():
    print("=" * 100)
    print("S212c — فیلترِ عدم‌تقارنِ دیدِ معکوس (فصلِ ۹) روی لایه‌های زمان-محورِ مرزی")
    print("گیت: net↑ (>base) + WR≥40 + WR≥base + walk-forward ۴/۴. هدف = سودِ خالصِ بیشتر.")
    print("=" * 100, flush=True)

    layers = []
    dfx = B.cal(B.lastn(B.cal(B.load('XAUUSD_M15'))))
    sc_g = B.confirms(dfx, B.KEYS)
    b140 = ((dfx['dow'].values == 0) & np.isin(dfx['hour'].values, [18, 19, 20, 21])) & (sc_g >= 3)
    layers.append(evaluate_layer('S140 Monday+', dfx, b140, 100, 300, 96, 'XAUUSD'))
    b142 = np.isin(dfx['dom'].values, [10, 13, 20]) & np.isin(dfx['hour'].values, list(range(1, 13)))
    layers.append(evaluate_layer('S142 Mid-Month', dfx, b142, 100, 500, 96, 'XAUUSD'))

    dfe = B.cal(B.lastn(B.cal(B.load('EURUSD_M15'))))
    sc_e = B.confirms(dfe, B.KEYS)
    b143 = (np.isin(dfe['dom'].values, [3, 9, 20]) &
            np.isin(dfe['hour'].values, [1, 2, 3, 4, 5, 11, 12, 13, 14, 15]) & (sc_e >= 2))
    layers.append(evaluate_layer('S143 EURUSD Mid-Month+', dfe, b143, 20, 40, 96, 'EURUSD'))

    total_delta = 0.0
    out = []
    for L in layers:
        b = L['base']; bf = L['best']
        print(f"\n▶ {L['name']}  ({L['asset']})")
        print(f"   baseline: WR={b['wr']:.1f}%  net=${b['net']:+,.0f}  n={b['n']}  PF={b['pf']:.2f}")
        for v in L['variants']:
            mark = '  ✅' if (v['n'] >= 30 and v['wr'] >= WR_FLOOR and v['net'] > b['net'] and v['wr'] >= b['wr']) else ''
            print(f"     {v['mode']:18s} WR={v['wr']:5.1f}%  net=${v['net']:+9,.0f}  n={v['n']:4d}  PF={v['pf']:.2f}{mark}")
        if bf and L['accepted']:
            d = bf['net'] - b['net']; total_delta += d
            print(f"   🏅 برنده: {bf['mode']}  ⇒ WR {b['wr']:.1f}%→{bf['wr']:.1f}%  "
                  f"net ${b['net']:+,.0f}→${bf['net']:+,.0f} (Δ{d:+,.0f})  WF={bf.get('wf')} ✅پایدار")
        elif bf and not L['accepted']:
            print(f"   ⚠️ بهترین گرید ({bf['mode']}) net↑ داد اما walk-forward ناپایدار ⇒ رد.")
        else:
            print(f"   ⛔ هیچ فیلتری هم‌زمان net↑ و WR≥base نداد ⇒ بی‌بهبود.")
        out.append(dict(name=L['name'], base_net=b['net'], base_wr=b['wr'],
                        best=(bf['mode'] if bf else None), delta=L['delta_net'], accepted=L['accepted']))

    print("\n" + "=" * 100)
    print(f"جمعِ Δ سودِ خالصِ فیلترِ عدم‌تقارنِ دیدِ معکوس = {total_delta:+,.0f}$")
    with open(os.path.join(ROOT, 'results', '_s212c_filter.json'), 'w') as f:
        json.dump(dict(layers=out, total_delta=total_delta), f, indent=1)
    print("saved: results/_s212c_filter.json")


if __name__ == '__main__':
    main()
