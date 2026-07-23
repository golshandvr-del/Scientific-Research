# -*- coding: utf-8 -*-
"""
S212d — فیلترِ «عدم‌تقارنِ دیدِ معکوس» (Brooks فصلِ ۹) روی **لایهٔ فعالِ رکورد**: S140⁺⁺ (M5)
=================================================================================================
چرا این تستِ درست است (تصحیحِ روش‌شناختیِ S212c):
  S212c فیلتر را روی «S140 پایه روی M15 (h18-21, TP300)» آزمود — اما این نسخه **در رکورد فعال
  نیست**. رکوردِ +$258,809 از **S140⁺⁺ روی M5** استفاده می‌کند: دوشنبه (dow==0)، ساعتِ
  h[18,19,20] (حذفِ ساعتِ ۲۱)، LONG، SL100/TP200، mh288، compounding=True (سندِ S190_S195).
  بنابراین برای اینکه Δ واقعاً به رکورد بیفزاید، فیلتر باید روی **همین نسخهٔ دقیق** آزموده شود.

تزِ فصلِ ۹ (inverse-chart cross-check): ستاپی که در منظرِ معکوس یک "rounding bottom" (اصلاحِ
  محدب/کم‌شتاب) دیده می‌شود تله است ⇒ رد. معیار = S212.inverse_view_asym روی همان دیتافریمِ M5.
  فیلتر: ورودِ دوشنبه تنها وقتی مجاز که asym_recent(shift1) ≤ thr (یا اصلاً اصلاحی نبوده ⇒ خنثی).

گیت (قانونِ #۱ = هدف سودِ خالص): net↑ نسبت به مبنا + WR≥40 + WR≥مبنا + WF4/4 مثبت + دو نیمه مثبت.
موتور: عیناً همان s194 (build_trades/net_of/wf_ok/two_halves_ok، compounding=True) برای سازگاریِ
دقیق با محاسبهٔ رکورد.
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import s194_s140_m5_double_filter as R   # load/confirms/net_of/wf_ok/two_halves_ok/build_trades
import s212_brooks_inverse_view as M      # inverse_view_asym
from engine import indicators as ind

ASSET = 'XAUUSD_M5'
SL, TP, MH = 100.0, 200.0, 288
ENTRY_HOURS = [18, 19, 20]   # ★ S140⁺⁺ فعالِ رکورد = حذفِ ساعتِ ۲۱


def asym_keep(df, lb, thr):
    """ماسکِ bool: asymِ اصلاحِ اخیر (shift1) ≤ thr یا اصلاحی نبوده (nan ⇒ خنثی/مجاز)."""
    asym = M.inverse_view_asym(df, lb)
    asym_s = pd.Series(asym).shift(1).to_numpy()
    return (asym_s <= thr) | np.isnan(asym_s)


def main():
    print("=" * 100)
    print("S212d — فیلترِ عدم‌تقارنِ دیدِ معکوس (فصلِ ۹) روی لایهٔ فعالِ رکورد S140⁺⁺ (XAUUSD_M5)")
    print("مبنا: دوشنبه, h[18,19,20], LONG, SL100/TP200, mh288, compounding=True (نسخهٔ رکورد)")
    print("گیت: net↑ + WR≥40 + WR≥مبنا + WF4/4 + دو نیمه مثبت. هدف = سودِ خالصِ بیشتر.")
    print("=" * 100, flush=True)

    df = R.load(ASSET)
    base_mask = (df['dow'].values == 0) & np.isin(df['hour'].values, ENTRY_HOURS)

    base_tr = R.build_trades(df, base_mask, SL, TP, MH, ASSET)
    base = R.net_of(base_tr, ASSET)
    bwf_ok, bwf = R.wf_ok(base_tr, ASSET, 4)
    bh = R.two_halves_ok(base_tr, ASSET)
    print(f"\n[مبنا] S140⁺⁺ رکورد: net=${base['net']:+,.0f}  WR={base['wr']:.2f}%  n={base['n']}  "
          f"PF={base['pf']:.2f}  WF={bwf}  دونیمه={bh}")

    # کشِ asym به‌ازای lb (مستقل از thr)
    asym_cache = {}
    def keep_of(lb, thr):
        if lb not in asym_cache:
            a = M.inverse_view_asym(df, lb)
            asym_cache[lb] = pd.Series(a).shift(1).to_numpy()
        s = asym_cache[lb]
        return (s <= thr) | np.isnan(s)

    print(f"\n{'فیلتر':22s}{'net':>12}{'Δمبنا':>10}{'WR':>8}{'n':>6}{'PF':>7}  {'WF4/4':>7}  {'2نیمه':>6}  تصمیم")
    print("-" * 100)

    variants = []
    best = None
    for lb in (12, 20, 32):
        for thr in (0.3, 0.5, 1.0, 2.0):
            keep = keep_of(lb, thr)
            mask = base_mask & keep
            if mask.sum() < 20:
                continue
            tr = R.build_trades(df, mask, SL, TP, MH, ASSET)
            if tr is None or len(tr) < 20:
                continue
            st = R.net_of(tr, ASSET)
            wfok, nets = R.wf_ok(tr, ASSET, 4)
            hok = R.two_halves_ok(tr, ASSET)
            d = st['net'] - base['net']
            accept = (st['n'] >= 20 and st['wr'] >= 40.0 and st['wr'] >= base['wr']
                      and st['net'] > base['net'] and wfok and hok)
            mark = '✅پذیرش' if accept else 'رد'
            print(f"asym_lb{lb}_thr{thr:<4}    {st['net']:>+11,.0f}{d:>+10,.0f}{st['wr']:>7.1f}%"
                  f"{st['n']:>6}{st['pf']:>7.2f}  {str(wfok):>7}  {str(hok):>6}  {mark}")
            rec = dict(mode=f'asym_lb{lb}_thr{thr}', lb=lb, thr=thr, net=round(st['net'], 1),
                       wr=round(st['wr'], 2), n=st['n'], wf=nets, wf_ok=wfok, halves_ok=hok,
                       dnet=round(d, 1), accepted=accept)
            variants.append(rec)
            if accept and (best is None or st['net'] > best['net']):
                best = rec

    print("\n" + "=" * 100)
    if best:
        print(f"🏅 برندهٔ گیت-پاس: {best['mode']}  ⇒ net ${base['net']:+,.0f}→${best['net']:+,.0f} "
              f"(Δ{best['dnet']:+,.0f})  WR {base['wr']:.1f}%→{best['wr']:.1f}%  WF={best['wf']}")
        print(f"➜ اگر پایدار: رکوردِ کل +${best['dnet']:,.0f} افزایش می‌یابد (جایگزینِ S140⁺⁺).")
    else:
        print("⛔ هیچ آستانه/پنجره‌ای هم‌زمان net↑ و WR≥مبنا و WF4/4 و دو نیمه نداد ⇒ فیلتر روی")
        print("   لایهٔ فعالِ رکورد بی‌بهبود است. (Δ رکورد = +$0)")

    out = dict(base=dict(net=round(base['net'], 1), wr=round(base['wr'], 2), n=base['n'],
                         wf=bwf, wf_ok=bwf_ok, halves_ok=bh),
               variants=variants, best=best)
    with open(os.path.join(ROOT, 'results', '_s212d_record_filter.json'), 'w') as f:
        json.dump(out, f, indent=1)
    print("saved: results/_s212d_record_filter.json")


if __name__ == '__main__':
    main()
