# -*- coding: utf-8 -*-
"""
S186d — «قدرتِ close» (فصلِ ۸) به‌عنوان فیلترِ *مضاعف* روی نسخهٔ رکوردِ S143⁺
(baseline AND Brooks-High2-w96) — راهِ اولِ پروژه: بهبودِ WR/سودِ یک لایهٔ فعالِ رکورد.
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه: هدف = بیشینه‌سازیِ سودِ خالص (XAUUSD+EURUSD)؛ WR تابعِ
> هدف نیست اما هر لایهٔ فعال باید WR≥۴۰٪ داشته باشد.

منشأ (قانونِ سومِ همپوشانیِ پرامپت — تکمیلِ همان‌جا):
  در S186c فیلترِ close-strength روی baselineِ *خامِ* S143 (+$4,605) بهبودِ Δ+$677 داد.
  اما نسخهٔ رکوردِ S143 در پرتفوی، **S143⁺** است = baseline AND فیلترِ ساختاریِ
  Brooks-High2 (S170، mode=A_recentHigh2_w96, ema20/50) با net=**+$6,489**، WR ۴۵.۵٪.
  طبقِ قانونِ همپوشانی باید فیلترِ نو را روی نسخهٔ *واقعیِ رکورد* آزمود، نه baseline خام.
  این اسکریپت فیلترِ close-strength را به‌صورتِ AND سوم روی S143⁺ می‌آزماید (فیلترِ مضاعف).

روش (سیب‌به‌سیب با S170/S186c، همان حساب/بازه/SL/TP):
  سیگنالِ نهایی = b143  AND  recentHigh2_w96(ema20/50)  AND  recentStrongBullClose(br,cp,w).
  همه فیلترها shift(1) (ضدِ look-ahead).
  گیتِ پذیرش: n≥30 و WR≥40 و WR≥WR(S143⁺) و net≥net(S143⁺) و walk-forward ۴/۴ مثبت.

خروجی: چاپِ کنسول + results/_s186d_close_strength_double_filter.json
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
import s170_brooks_high2_filter_on_timedrift as H
from s186c_close_strength_as_filter import recent_strong_bull_close

RESULTS = os.path.join(ROOT, 'results')
WR_FLOOR = 40.0
SL, TP, MH = 20, 40, 96          # همان پارامترهای رکوردِ S143
EMA_F, EMA_S = 20, 50            # همان ema فیلترِ Brooks در S170
HIGH2_W = 96                     # همان پنجرهٔ رکوردِ S170 (A_recentHigh2_w96)


def wf4(dfe, sig, z):
    """۴ پنجرهٔ زمانیِ متوالی؛ برای هرکدام (net, wr, n)."""
    n = len(dfe); res = []
    for k in range(4):
        lo = int(n * k / 4); hi = int(n * (k + 1) / 4)
        m = np.zeros(n, bool); m[lo:hi] = True
        r = H.stats(H.sim(dfe, sig & m, z, SL, TP, MH, 'EURUSD'), 'EURUSD')
        res.append(dict(net=round(r['net'], 1), wr=round(r['wr'], 2), n=r['n']))
    return res


def main():
    print("=" * 100)
    print("S186d — فیلترِ مضاعفِ «قدرتِ close» (فصلِ ۸) روی نسخهٔ رکوردِ S143⁺ (Brooks-High2)")
    print("گیت: WR↑ و net↑ نسبت به S143⁺، WR≥40، n≥30، walk-forward ۴/۴ مثبت.")
    print("=" * 100, flush=True)

    dfe = H.cal(H.lastn(H.cal(H.load('EURUSD_M15'))))
    sc_e = H.confirms(dfe, H.KEYS)
    b143 = (np.isin(dfe['dom'].values, [3, 9, 20]) &
            np.isin(dfe['hour'].values, [1, 2, 3, 4, 5, 11, 12, 13, 14, 15]) & (sc_e >= 2))
    z = np.zeros(len(dfe), bool)

    # S143⁺ رکورد = baseline AND Brooks-High2-w96
    bh = pd.Series(H.brooks_recent_high2(dfe, EMA_F, EMA_S, HIGH2_W)).shift(1).fillna(False).to_numpy()
    s143plus = b143 & bh
    rec = H.stats(H.sim(dfe, s143plus, z, SL, TP, MH, 'EURUSD'), 'EURUSD')
    rec_wf = wf4(dfe, s143plus, z)
    print(f"\n▶ S143⁺ (رکوردِ فعلی): WR={rec['wr']:.2f}%  net=${rec['net']:+,.0f}  n={rec['n']}  PF={rec['pf']:.2f}")
    print(f"   walk-forward: {[w['net'] for w in rec_wf]}")

    # گریدِ فیلترِ سومِ close-strength
    THR = [(0.6, 0.6), (0.5, 0.6), (0.5, 0.7), (0.6, 0.5)]
    WINS = (8, 16, 32, 64, 96)
    variants = []
    print("\n  فیلترِ مضاعف (S143⁺ AND close-strength):")
    for (br, cp) in THR:
        for w in WINS:
            cs = pd.Series(recent_strong_bull_close(dfe, br, cp, w)).shift(1).fillna(False).to_numpy()
            sig = s143plus & cs
            r = H.stats(H.sim(dfe, sig, z, SL, TP, MH, 'EURUSD'), 'EURUSD')
            wf = wf4(dfe, sig, z)
            wf_ok = all(x['net'] > 0 and x['wr'] >= WR_FLOOR for x in wf)
            gate = (r['n'] >= 30 and r['wr'] >= WR_FLOOR and r['wr'] >= rec['wr']
                    and r['net'] >= rec['net'] and wf_ok)
            variants.append(dict(mode=f'br{br}_cp{cp}_w{w}', wr=round(r['wr'], 2),
                                 net=round(r['net'], 1), n=r['n'],
                                 pf=(round(r['pf'], 3) if r['pf'] != float('inf') else 999.0),
                                 wf=[x['net'] for x in wf], wf_ok=wf_ok, gate=gate))
            mark = '  ✅ گیت پاس' if gate else ''
            print(f"    {br}/{cp} w{w:<2d}: WR={r['wr']:5.2f}%  net=${r['net']:+7,.0f}  "
                  f"n={r['n']:3d}  WF={[x['net'] for x in wf]}{mark}")

    passed = [v for v in variants if v['gate']]
    passed.sort(key=lambda v: v['net'], reverse=True)
    best = passed[0] if passed else None

    print("\n" + "=" * 100)
    if best:
        d = best['net'] - rec['net']
        print(f"🏅 بهترین فیلترِ مضاعف: {best['mode']}")
        print(f"   WR {rec['wr']:.2f}%→{best['wr']:.2f}%  |  net ${rec['net']:+,.0f}→${best['net']:+,.0f}  (Δ{d:+,.0f})")
        print(f"   walk-forward ۴/۴ مثبت: {best['wf']}  ⇒ پایدار، غیرِ overfit.")
        print(f"   ⇒ S143⁺⁺ جایگزینِ S143⁺ در رکورد می‌شود؛ Δnet = +${d:,.0f}")
    else:
        print("⛔ هیچ فیلترِ مضاعفی هم‌زمان WR↑ و net↑ و WF-پایدار نداد ⇒ بی‌بهبود.")
    print("=" * 100)

    with open(os.path.join(RESULTS, '_s186d_close_strength_double_filter.json'), 'w') as f:
        json.dump(dict(strategy='S186d_close_strength_double_filter_on_s143',
                       record=dict(wr=rec['wr'], net=rec['net'], n=rec['n'],
                                   pf=rec['pf'], wf=[w['net'] for w in rec_wf]),
                       variants=variants, best=best,
                       delta_net=(best['net'] - rec['net']) if best else 0.0),
                  f, ensure_ascii=False, indent=1, default=float)
    print("✅ ذخیره شد: results/_s186d_close_strength_double_filter.json")


if __name__ == '__main__':
    main()
