# -*- coding: utf-8 -*-
"""
S172-C — «Two-Legged» به‌عنوان فیلترِ تأیید (راهِ اولِ پروژه = بهبود)
================================================================================
> قانونِ #۱: هدف = سودِ خالصِ بیشتر (XAUUSD+EURUSD)؛ WR≥۴۰٪ فقط کفِ هر لایه.

منشأ و ضرورت:
  در S172 دیدیم که لایهٔ مستقلِ double-bottom→Long روی طلا:
    • walk-forward ✅ و beats-baseline-p95 ✅ (لبهٔ آماریِ +$13,881 فراتر از long-bias)،
    • اما همپوشانیِ ۹۰٪ با S168 High-2 و سهمِ مستقل با نیمهٔ اولِ منفی (h1<0) ⇒
      ثبت به‌عنوان «لبهٔ مستقلِ جدید» نادرست است.
  طبقِ **قانونِ صریحِ همپوشانیِ پرامپت** (قانونِ سوم: از بخشِ همپوشان می‌توان به‌عنوان
  راهِ اولِ بهبود/فیلتر استفاده کرد؛ و این را به مراحلِ بعد موکول نکن) پیش از رفتن به
  فصلِ بعدیِ کتاب، کاربردِ فیلتری را می‌آزماییم.

روش:
  فیلترِ `recent-DoubleBottom(w)` = «آیا در w کندلِ اخیر یک سیگنالِ two-leg
  double-bottom (bull) رخ داده؟» (shift-safe) روی لایه‌های زمان-محورِ مرزیِ پروژه
  AND می‌شود. گیتِ بهبود (سیب‌به‌سیب با S170/S171):
    WR جدید ≥ WR baseline و ≥۴۰   و   net جدید ≥ net baseline   و   n≥۳۰.
  اعتبارسنجیِ نهایی: هر دو نیمه مثبت + walk-forward هر ۴ پنجره مثبت.

نکته: چون لبهٔ مستقلِ double-bottom روی *طلا* بود، مثلِ S170 احتمالِ ارزش‌افزودهٔ
      واقعی روی *EURUSD* بیشتر است (که ساختارِ two-leg مستقل ندارد).
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from engine import indicators as ind
import s172_brooks_two_legs as S
from s171_brooks_signs_of_strength_filter import confirms, KEYS, cal

RESULTS = os.path.join(ROOT, 'results')
WR_FLOOR = 40.0


def recent_double_bottom(df, k, tol, lb, w):
    """فیلتر: در w کندلِ اخیر حداقل یک double-bottom(long) رخ داده؟ (shift-safe)."""
    sig = S.two_leg_reversal_signals(df, k, tol, lb, 'long')  # از قبل shift(1) دارد
    return pd.Series(sig).rolling(w, min_periods=1).max().fillna(0).to_numpy() > 0


def walk_forward_ok(df, sig, asset, sl, tp, mh, nwin=4):
    n = len(df); bnds = [int(n * i / nwin) for i in range(nwin + 1)]
    for wi in range(nwin):
        lo, hi = bnds[wi], bnds[wi + 1]
        sub = df.iloc[lo:hi].reset_index(drop=True)
        r = S.stats(S.sim(sub, sig[lo:hi], np.zeros(hi - lo, bool), sl, tp, mh, asset), asset)
        if not (r['net'] > 0 and r['wr'] >= WR_FLOOR):
            return False, wi + 1
    return True, None


def eval_layer(name, df, base_sig, sl, tp, mh, asset):
    z = np.zeros(len(df), bool)
    base = S.stats(S.sim(df, base_sig, z, sl, tp, mh, asset), asset)
    variants = []
    for k in (5, 3):
        for tol in (0.0015, 0.003):
            for lb in (30, 60):
                for w in (48, 96, 192):
                    filt = recent_double_bottom(df, k, tol, lb, w)
                    sig = base_sig & filt
                    r = S.stats(S.sim(df, sig, z, sl, tp, mh, asset), asset)
                    ok = (r['n'] >= 30 and r['wr'] >= WR_FLOOR and r['wr'] >= base['wr']
                          and r['net'] >= base['net'])
                    variants.append(dict(k=k, tol=tol, lb=lb, w=w, **r, improve=bool(ok)))
    good = [v for v in variants if v['improve']]
    good.sort(key=lambda v: v['net'], reverse=True)
    best = None
    for cand in good:
        filt = recent_double_bottom(df, cand['k'], cand['tol'], cand['lb'], cand['w'])
        sig = base_sig & filt
        hv = S.halves(df, sig, np.zeros(len(df), bool), sl, tp, mh, asset)
        wf_ok, badw = walk_forward_ok(df, sig, asset, sl, tp, mh)
        if hv and hv['h1'] > 0 and hv['h2'] > 0 and wf_ok:
            best = dict(cand, h1=hv['h1'], h2=hv['h2'], wf_ok=True)
            break
    return dict(name=name, asset=asset, base=base, variants=variants, best=best,
                delta=(best['net'] - base['net']) if best else 0.0)


def main():
    print("=" * 100)
    print("S172-C — فیلترِ two-leg double-bottom روی لایه‌های زمان-محورِ مرزی (راهِ اولِ بهبود)")
    print("=" * 100, flush=True)
    layers = []

    # طلا M15
    dfx = cal(S.lastn(S.load('XAUUSD_M15')))
    sc_g = confirms(dfx, KEYS)
    b140 = ((dfx['dow'].values == 0) & np.isin(dfx['hour'].values, [18, 19, 20, 21])) & (sc_g >= 3)
    layers.append(eval_layer('S140 Monday+ (طلا)', dfx, b140, 100, 300, 96, 'XAUUSD'))
    b142 = np.isin(dfx['dom'].values, [10, 13, 20]) & np.isin(dfx['hour'].values, list(range(1, 13)))
    layers.append(eval_layer('S142 Mid-Month (طلا)', dfx, b142, 100, 500, 96, 'XAUUSD'))

    # یورو M15
    dfe = cal(S.lastn(S.load('EURUSD_M15')))
    sc_e = confirms(dfe, KEYS)
    b143 = (np.isin(dfe['dom'].values, [3, 9, 20]) &
            np.isin(dfe['hour'].values, [1, 2, 3, 4, 5, 11, 12, 13, 14, 15]) & (sc_e >= 2))
    layers.append(eval_layer('S143 EURUSD Mid-Month+', dfe, b143, 20, 40, 96, 'EURUSD'))

    total = 0.0; out = []
    for L in layers:
        b = L['base']; bf = L['best']
        print(f"\n▶ {L['name']}  baseline: WR={b['wr']:.1f}% net=${b['net']:+,.0f} n={b['n']} PF={b['pf'] if b['pf']!=float('inf') else 999:.2f}")
        imp = [v for v in L['variants'] if v['improve']]
        for v in sorted(imp, key=lambda x: -x['net'])[:4]:
            print(f"     k{v['k']} tol{v['tol']} lb{v['lb']} w{v['w']}: WR={v['wr']:.1f}% net=${v['net']:+,.0f} n={v['n']} ✅بهبودِ خام")
        if bf:
            total += L['delta']
            print(f"   🏅 پذیرفته (هر دو نیمه + WF): k{bf['k']} tol{bf['tol']} lb{bf['lb']} w{bf['w']} "
                  f"⇒ WR {b['wr']:.1f}%→{bf['wr']:.1f}% net ${b['net']:+,.0f}→${bf['net']:+,.0f} (Δ{L['delta']:+,.0f}) "
                  f"h1={bf['h1']:+.0f} h2={bf['h2']:+.0f}")
        else:
            print("   ⛔ هیچ فیلتری هم‌زمان WR↑ و net↑ + هر دو نیمه + WF نداد.")
        out.append(dict(name=L['name'], asset=L['asset'], base=b, best=bf, delta=L['delta']))

    print("\n" + "=" * 100)
    print(f"اثرِ خالصِ کلِ فیلترِ Two-Leg (جمعِ بهبودها) = ${total:+,.0f}")
    rb = 233260
    print(f"رکوردِ قبل = +${rb:,.0f}  ⇒  رکوردِ پس از فیلتر = +${rb + total:,.0f}")
    with open(os.path.join(RESULTS, '_s172c_two_leg_filter.json'), 'w') as f:
        json.dump(dict(layers=out, total_delta=float(total), record_before=rb,
                       record_after=float(rb + total)), f, ensure_ascii=False, indent=2, default=float)
    print("✅ ذخیره شد: results/_s172c_two_leg_filter.json")


if __name__ == '__main__':
    main()
