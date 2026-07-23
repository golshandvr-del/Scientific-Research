# -*- coding: utf-8 -*-
"""
S186c — استفاده از «قدرتِ close» (فصلِ ۸، S186) به‌عنوان «فیلترِ تأیید» روی
لایه‌های زمان-محورِ مرزیِ موجود (راهِ اولِ پروژه: بهبودِ WR/سودِ لایه‌های موجود).
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه: هدف = بیشینه‌سازیِ سودِ خالص (XAUUSD+EURUSD)؛ WR تابعِ
> هدف نیست اما هر لایهٔ فعال باید WR≥۴۰٪ داشته باشد.

منشأ (قانونِ همپوشانیِ پرامپت — تکمیلِ همان‌جا، نه موکول به بعد):
  در S186 معلوم شد لبهٔ خامِ close-strength (XAUUSD long) گیتِ ۴-گانه را پاس می‌کند
  (net=+$8,510) اما ۶۳.۲٪ آن با اجتماعِ LONGِ طلا (زمان‌محور + Brooks H2/L2) هم‌پوشان است.
  سهمِ مستقلِ ۳۶.۸٪ به‌تنهایی گیت را پاس می‌کند (net=+$2,672) و به‌عنوان لبهٔ مستقل ثبت
  خواهد شد. اما طبقِ «قانونِ سومِ همپوشانی» صریحِ پرامپت، پیش از رفتن به فصلِ بعد باید
  بررسی شود آیا همان مفهومِ close-strength می‌تواند به‌عنوان فیلترِ تأییدِ مومنتوم روی
  لایه‌های زمان-محورِ مرزی WR را بالا ببرد بی‌آنکه net افت کند (بهبودِ هم‌زمانِ دو لایه).

روش (عیناً هم‌ترازِ S184 — همان baselineها، همان گیت):
  فیلتر = `recent-strong-bull-close(window)`: آیا در `window` کندلِ اخیر یک کندلِ صعودیِ
  «قوی» (body_ratio≥br و close_pos≥cp) رخ داده؟ سپس shift(1) (ضدِ look-ahead) و AND با
  سیگنالِ baseline. گریدِ پنجره: {8,16,32,64,96} × آستانه‌های (br,cp)∈{(0.6,0.6),(0.5,0.7)}.

  گیتِ پذیرشِ فیلتر: n≥30 و WR_new ≥ WR_base و WR_new ≥ 40 و net_new ≥ net_base.

خروجی: چاپِ کنسول + results/_s186c_close_strength_filter.json
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
from engine import indicators as ind
import s170_brooks_high2_filter_on_timedrift as H

RESULTS = os.path.join(ROOT, 'results')
WR_FLOOR = 40.0


def recent_strong_bull_close(df, br_thr, cp_thr, window):
    """آیا در `window` کندلِ اخیر یک کندلِ صعودیِ «قوی» رخ داده؟ causal.
    body_ratio = |close-open|/(high-low) ≥ br_thr ؛ close_pos = (close-low)/(high-low) ≥ cp_thr
    ؛ bull: close>open."""
    o = df['open'].to_numpy(); c = df['close'].to_numpy()
    h = df['high'].to_numpy(); l = df['low'].to_numpy()
    rng = np.maximum(h - l, 1e-9)
    body_ratio = np.abs(c - o) / rng
    close_pos = (c - l) / rng
    bull = c > o
    evt = bull & (body_ratio >= br_thr) & (close_pos >= cp_thr)
    s = pd.Series(np.asarray(evt, float))
    rolled = s.rolling(window, min_periods=1).sum().to_numpy()
    return rolled > 0


# آستانه‌های (br,cp) که در S186 لبهٔ برنده دادند
THR = [(0.6, 0.6), (0.5, 0.7)]


def evaluate_layer(name, df, base_sig, sl, tp, mh, asset):
    z = np.zeros(len(df), bool)
    base = H.stats(H.sim(df, base_sig, z, sl, tp, mh, asset), asset)
    variants = []
    for (br, cp) in THR:
        for w in (8, 16, 32, 64, 96):
            filt = recent_strong_bull_close(df, br, cp, w)
            filt = pd.Series(filt).shift(1).fillna(False).to_numpy()   # ضدِ look-ahead
            sig = base_sig & filt
            r = H.stats(H.sim(df, sig, z, sl, tp, mh, asset), asset)
            variants.append(dict(mode=f'strongBullClose_br{br}_cp{cp}_w{w}', **r))

    def ok(v):
        return (v['n'] >= 30 and v['wr'] >= WR_FLOOR and v['wr'] >= base['wr']
                and v['net'] >= base['net'])
    accepted = [v for v in variants if ok(v)]
    accepted.sort(key=lambda v: v['net'], reverse=True)
    best = accepted[0] if accepted else None
    return dict(name=name, asset=asset, base=base, variants=variants,
                best_filter=best, delta_net=(best['net'] - base['net']) if best else 0.0)


def main():
    print("=" * 100)
    print("S186c — فیلترِ تأییدِ «قدرتِ close» (فصلِ ۸) روی لایه‌های زمان-محورِ مرزی")
    print("گیت: WR↑ (≥base و ≥40) و net↑ (≥base). هدفِ نهایی = سودِ خالصِ بیشتر.")
    print("=" * 100, flush=True)

    layers = []

    # ---------- طلا M15 (همان baselineهای S170/S181/S184) ----------
    dfx = H.cal(H.lastn(H.cal(H.load('XAUUSD_M15'))))
    sc_g = H.confirms(dfx, H.KEYS)

    b140 = ((dfx['dow'].values == 0) & np.isin(dfx['hour'].values, [18, 19, 20, 21])) & (sc_g >= 3)
    layers.append(evaluate_layer('S140 Monday+', dfx, b140, 100, 300, 96, 'XAUUSD'))

    b142 = np.isin(dfx['dom'].values, [10, 13, 20]) & np.isin(dfx['hour'].values, list(range(1, 13)))
    layers.append(evaluate_layer('S142 Mid-Month', dfx, b142, 100, 500, 96, 'XAUUSD'))

    # ---------- یورو M15 ----------
    dfe = H.cal(H.lastn(H.cal(H.load('EURUSD_M15'))))
    sc_e = H.confirms(dfe, H.KEYS)
    b143 = (np.isin(dfe['dom'].values, [3, 9, 20]) &
            np.isin(dfe['hour'].values, [1, 2, 3, 4, 5, 11, 12, 13, 14, 15]) & (sc_e >= 2))
    layers.append(evaluate_layer('S143 EURUSD Mid-Month+', dfe, b143, 20, 40, 96, 'EURUSD'))

    # ---------- گزارش ----------
    print("\n" + "=" * 100)
    total_delta = 0.0
    out = []
    for L in layers:
        b = L['base']; bf = L['best_filter']
        print(f"\n▶ {L['name']}  ({L['asset']})")
        print(f"   baseline: WR={b['wr']:.1f}%  net=${b['net']:+,.0f}  n={b['n']}  PF={b['pf']:.2f}")
        for v in L['variants']:
            mark = ''
            if v['n'] >= 30 and v['wr'] >= WR_FLOOR and v['wr'] >= b['wr'] and v['net'] >= b['net']:
                mark = '  ✅ بهبود'
            print(f"     {v['mode']:32s} WR={v['wr']:5.1f}%  net=${v['net']:+9,.0f}  "
                  f"n={v['n']:4d}  PF={v['pf']:.2f}{mark}")
        if bf:
            d = bf['net'] - b['net']
            total_delta += d
            print(f"   🏅 بهترین: {bf['mode']}  ⇒ WR {b['wr']:.1f}%→{bf['wr']:.1f}%  "
                  f"net ${b['net']:+,.0f}→${bf['net']:+,.0f}  (Δ{d:+,.0f})")
        else:
            print(f"   ⛔ هیچ فیلتری هم‌زمان WR↑ و net↑ نداد ⇒ این لایه بی‌بهبود.")
        out.append(dict(name=L['name'], asset=L['asset'], base=b,
                        best_filter=bf, delta_net=L['delta_net'],
                        variants=L['variants']))

    print("\n" + "=" * 100)
    print(f"جمعِ Δnet از فیلترِ close-strength: ${total_delta:+,.0f}")
    print("=" * 100)

    with open(os.path.join(RESULTS, '_s186c_close_strength_filter.json'), 'w') as f:
        json.dump(dict(strategy='S186c_close_strength_as_filter', total_delta=total_delta,
                       layers=out), f, ensure_ascii=False, indent=1, default=float)
    print("✅ ذخیره شد: results/_s186c_close_strength_filter.json")


if __name__ == '__main__':
    main()
