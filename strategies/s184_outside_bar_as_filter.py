# -*- coding: utf-8 -*-
"""
S184 — استفاده از هندسهٔ Outside-Bar (فصلِ ۷، S183) به‌عنوان «فیلترِ تأیید» روی
لایه‌های زمان-محورِ مرزیِ موجود (راهِ اولِ پروژه: بهبودِ WR/سودِ لایه‌های موجود).
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه: هدف = بیشینه‌سازیِ سودِ خالص (XAUUSD+EURUSD)؛ WR تابعِ
> هدف نیست اما هر لایهٔ فعال باید WR≥۴۰٪ داشته باشد.

منشأ (قانونِ همپوشانیِ پرامپت — تکمیلِ همان‌جا، نه موکول به بعد):
  در S183 معلوم شد هیچ کاندیدِ خامِ outside-bar گیتِ ۴-گانه را پاس نمی‌کند (بهترین
  XAUUSD long net=+$2,028 اما walk-forward ناپایدار؛ SHORT روی هر دو ارز منفی).
  اما سیگنالِ LONG ذاتاً سودده است ⇒ طبقِ «قانونِ همپوشانیِ» صریحِ پرامپت (قانونِ سوم)
  باید بررسی شود آیا «حضورِ اخیرِ bull outside-bar در جهتِ صعود» می‌تواند فیلترِ تأییدِ
  مومنتومِ روند برای لایه‌های زمان-محورِ مرزی باشد و WR را بالا ببرد بی‌آنکه net افت کند.

روش (عیناً هم‌ترازِ S170/S181 — همان baselineها، همان گیت):
  فیلتر = `recent-bull-outside-bar(window)`: آیا در `window` کندلِ اخیر یک bull outside bar
  (که روی بالای دامنه بسته) رخ داده؟ سپس shift(1) (ضدِ look-ahead) و AND با سیگنالِ baseline.
  گریدِ پنجره: {8,16,32,64,96}.

  گیتِ پذیرشِ فیلتر: n≥30 و WR_new ≥ WR_base و WR_new ≥ 40 و net_new ≥ net_base.

خروجی: چاپِ کنسول + results/_s184_outside_bar_filter.json
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


def recent_bull_outside_bar(df, close_frac, window):
    """آیا در `window` کندلِ اخیر یک bull outside bar (روی بالای دامنه بسته) رخ داده؟ causal.
    outside: high_i>high_{i-1} و low_i<low_{i-1}؛ bull: close>open؛ close نزدیکِ high."""
    o = df['open'].to_numpy(); c = df['close'].to_numpy()
    h = df['high'].to_numpy(); l = df['low'].to_numpy()
    rng = np.maximum(h - l, 1e-9)
    h1 = np.roll(h, 1); l1 = np.roll(l, 1)
    is_outside = (h > h1) & (l < l1)
    bull = c > o
    close_top = c >= h - close_frac * rng
    evt = is_outside & bull & close_top
    evt[0] = False
    s = pd.Series(np.asarray(evt, float))
    rolled = s.rolling(window, min_periods=1).sum().to_numpy()
    return rolled > 0


def evaluate_layer(name, df, base_sig, sl, tp, mh, asset, close_frac=0.2):
    z = np.zeros(len(df), bool)
    base = H.stats(H.sim(df, base_sig, z, sl, tp, mh, asset), asset)
    variants = []
    for w in (8, 16, 32, 64, 96):
        filt = recent_bull_outside_bar(df, close_frac, w)
        filt = pd.Series(filt).shift(1).fillna(False).to_numpy()   # ضدِ look-ahead
        sig = base_sig & filt
        r = H.stats(H.sim(df, sig, z, sl, tp, mh, asset), asset)
        variants.append(dict(mode=f'recentBullOutside_w{w}', **r))

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
    print("S184 — فیلترِ تأییدِ Outside-Bar (فصلِ ۷) روی لایه‌های زمان-محورِ مرزی")
    print("گیت: WR↑ (≥base و ≥40) و net↑ (≥base). هدفِ نهایی = سودِ خالصِ بیشتر.")
    print("=" * 100, flush=True)

    layers = []

    # ---------- طلا M15 (همان baselineهای S170/S181) ----------
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
            print(f"     {v['mode']:24s} WR={v['wr']:5.1f}%  net=${v['net']:+9,.0f}  "
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
    print(f"جمعِ Δnet از فیلترِ Outside-Bar: ${total_delta:+,.0f}")
    print("=" * 100)

    with open(os.path.join(RESULTS, '_s184_outside_bar_filter.json'), 'w') as f:
        json.dump(dict(strategy='S184_outside_bar_as_filter', total_delta=total_delta,
                       layers=out), f, ensure_ascii=False, indent=1, default=float)
    print("✅ ذخیره شد: results/_s184_outside_bar_filter.json")


if __name__ == '__main__':
    main()
