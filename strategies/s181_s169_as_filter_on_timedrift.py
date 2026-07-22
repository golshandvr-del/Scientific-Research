# -*- coding: utf-8 -*-
"""
S181 — استفاده از ساختارِ Spike-and-Channel (S169) به‌عنوان «فیلترِ تأیید» روی
لایه‌های زمان-محورِ مرزیِ موجود (راهِ اولِ پروژه: بهبودِ WR/سودِ لایه‌های موجود).
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه: هدف = بیشینه‌سازیِ سودِ خالص (XAUUSD+EURUSD)؛ WR تابعِ
> هدف نیست اما هر لایهٔ فعال باید WR≥۴۰٪ داشته باشد.

منشأ (قانونِ همپوشانیِ پرامپت — تکمیلِ همان‌جا، نه موکول به بعد):
  در S180 معلوم شد سیگنالِ S169 (Spike-and-Channel LONG طلا) با اجتماعِ کلِ پرتفویِ
  LONGِ طلا **۱۰۰٪ همپوشان** است (به‌ویژه Signs-of-Strength S171 = ۹۹.۶٪ و High-2 = ۹۱٪)
  ⇒ سهمِ کاملاً مستقلی ندارد (n=1) ⇒ به‌عنوان لایهٔ نوِ مستقل رد شد.

  اما طبقِ «قانونِ همپوشانیِ» صریحِ پرامپت (قانونِ سوم): از بخشِ همپوشانِ لایه می‌توان
  به‌عنوان **فیلترِ تأیید** برای بالا بردنِ WR لایه‌های مرزی استفاده کرد — و این باید
  «همان‌جا» بررسی شود نه موکول به مرحلهٔ بعد.

  فرضیه: «به‌تازگی یک ساختارِ Spike-and-Channelِ صعودی رخ داده باشد» یک تأییدِ ساختاریِ
  مومنتومِ روند است. اگر ورودِ لایه‌های زمان-محورِ مرزی (S140⁺ WR≈۴۲٪، S142⁺ WR≈۴۲٪،
  S143⁺ EURUSD WR≈۴۵.۵٪) را مشروط به این تأیید کنیم، انتظار می‌رود WR بالا رود.

روش (عیناً هم‌ترازِ S170 — همان baselineها، همان گیت):
  فیلتر = `recent-spike-channel(window)`: آیا در `window` کندلِ اخیر یک رویدادِ
  spike-channelِ LONG (خروجیِ S169) رخ داده؟ سپس `shift(1)` (ضدِ look-ahead) و AND با
  سیگنالِ baseline. گریدِ پنجره: {8,16,32,64,96}.

  گیتِ پذیرشِ فیلتر: n≥30 و WR_new ≥ WR_base و WR_new ≥ 40 و net_new ≥ net_base.
  اگر هر دو برقرار ⇒ فیلتر به‌عنوان بهبود پذیرفته و Δnet به رکورد افزوده می‌شود.

خروجی: چاپِ کنسول + results/_s181_s169_filter.json
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
from engine import scalp_engine as se
from engine import indicators as ind
import s169_brooks_spike_channel as SP
# استفاده از همان baseline/confirms/cal/stats/sim که S170 استفاده کرد (سیب‌به‌سیب)
import s170_brooks_high2_filter_on_timedrift as H

RESULTS = os.path.join(ROOT, 'results')
WR_FLOOR = 40.0
se.ASSETS['XAUUSD'].update(spread_pip=3.3, comm=0.0, slip_pip=0.0)
se.ASSETS['EURUSD'].update(spread_pip=1.0, comm=0.0, slip_pip=0.3)


def recent_spike_channel(df, ema_fast, ema_slow, spike_len, spike_atr_mult,
                         channel_window, window):
    """آیا در `window` کندلِ اخیر یک رویدادِ spike-channelِ LONG رخ داده؟ causal."""
    long_evt, _ = SP.detect_spike_channel_events(df, ema_fast, ema_slow, spike_len,
                                                 spike_atr_mult, channel_window)
    s = pd.Series(np.asarray(long_evt, float))
    rolled = s.rolling(window, min_periods=1).sum().to_numpy()
    return rolled > 0


def evaluate_layer(name, df, base_sig, sl, tp, mh, asset,
                   ema_fast=10, ema_slow=30, spike_len=3, spike_atr_mult=1.5, channel_window=20):
    z = np.zeros(len(df), bool)
    base = H.stats(H.sim(df, base_sig, z, sl, tp, mh, asset), asset)
    variants = []
    for w in (8, 16, 32, 64, 96):
        filt = recent_spike_channel(df, ema_fast, ema_slow, spike_len, spike_atr_mult,
                                    channel_window, w)
        filt = pd.Series(filt).shift(1).fillna(False).to_numpy()   # ضدِ look-ahead
        sig = base_sig & filt
        r = H.stats(H.sim(df, sig, z, sl, tp, mh, asset), asset)
        variants.append(dict(mode=f'recentSpikeChannel_w{w}', **r))

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
    print("S181 — فیلترِ تأییدِ ساختاریِ Spike-and-Channel (S169) روی لایه‌های زمان-محورِ مرزی")
    print("گیت: WR↑ (≥base و ≥40) و net↑ (≥base). هدفِ نهایی = سودِ خالصِ بیشتر.")
    print("=" * 100, flush=True)

    layers = []

    # ---------- طلا M15 (همان baselineهای S170) ----------
    dfx = H.cal(H.lastn(H.cal(H.load('XAUUSD_M15'))))
    sc_g = H.confirms(dfx, H.KEYS)

    # S140 Monday⁺
    b140 = ((dfx['dow'].values == 0) & np.isin(dfx['hour'].values, [18, 19, 20, 21])) & (sc_g >= 3)
    layers.append(evaluate_layer('S140 Monday+', dfx, b140, 100, 300, 96, 'XAUUSD'))

    # S142 Mid-Month⁺
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
    print(f"جمعِ Δnet از فیلترِ S169: ${total_delta:+,.0f}")
    print("=" * 100)

    with open(os.path.join(RESULTS, '_s181_s169_filter.json'), 'w') as f:
        json.dump(dict(strategy='S181_s169_as_filter', total_delta=total_delta,
                       layers=out), f, ensure_ascii=False, indent=1, default=float)
    print("✅ ذخیره شد: results/_s181_s169_filter.json")


if __name__ == '__main__':
    main()
