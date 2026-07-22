# -*- coding: utf-8 -*-
"""
S176-FINALIZE — سنجشِ لبهٔ واقعیِ «Signal-Bar Stop-Entry» (فصلِ ۴) و ارزشِ مکانیزمِ
                تأیید (CONF) در برابرِ ورودِ ساده (BASE)، و سهمِ مستقل vs پرتفویِ LONG.

قانونِ شمارهٔ ۱: هدف فقط سودِ خالصِ بیشتر (XAUUSD+EURUSD)؛ WR کفِ ۴۰٪ هر لایه.

سه آزمون (هم‌سو با روش‌شناسیِ S173/S175):
  ۱) baseline long-bias: آیا سیگنالِ signal-bar فراتر از «صرفاً خرید در روند صعودی» است؟
  ۲) ارزشِ مکانیزمِ تأیید فصل ۴: CONF در برابرِ BASE روی همان پیکربندی (تزِ اصلیِ فصل).
  ۳) سهمِ مستقل: پس از حذفِ همپوشانی با پرتفویِ LONGِ طلا (High-2 + time-drift + SoS)،
     آیا چیزی پایدار (گیتِ سختِ کامل) باقی می‌ماند؟

پیکربندیِ متعادلِ منتخب (بالاترین WR+PF در میانِ گیت‌پاس‌ها):
   XAUUSD long · ema20/50 · body_frac 0.6 · SL250/TP375 · mh96
"""
import os, sys, json
import numpy as np
import pandas as pd
import warnings; warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import s172_brooks_two_legs as S
import s176_brooks_signal_bar_stopentry as SB
import s175_finalize as FN          # high2_signal, time_drift_union, sos_signal,
                                     # independent_share, bar_overlap_pct, full_gate
from engine import indicators as ind

WR_FLOOR = 40.0
OVERLAP_BARS = 12

# پیکربندیِ منتخب
CFG = dict(asset='XAUUSD', side='long', ef=20, es=50, bf=0.6, sl=250, tp=375, mh=96)


def sig_of(df, confirm):
    setup, h, l = SB.setup_signal(df, CFG['side'], CFG['ef'], CFG['es'], CFG['bf'])
    return SB.to_entry_signal(setup, h, l, CFG['side'], CFG['asset'], confirm)


def simple_trend_long(df, ef, es):
    """baseline: صرفاً «روندِ صعودی» (ema_f>ema_s) بدونِ شرطِ trend-bar/تأیید.
    هر کندلی که در روندِ صعودی است سیگنالِ خرید می‌دهد (پس از shift)."""
    c = df['close']
    up = (ind.ema(c, ef).to_numpy() > ind.ema(c, es).to_numpy())
    return pd.Series(up).shift(1).fillna(False).to_numpy()


def net_wr(df, sig, asset, side, sl, tp, mh):
    z = np.zeros(len(df), bool)
    tr = S.sim(df, sig if side == 'long' else z, z if side == 'long' else sig,
               sl, tp, mh, asset)
    r = S.stats(tr, asset)
    return r


def main():
    print("=" * 100)
    print("S176-FINALIZE — لبهٔ واقعیِ Signal-Bar Stop-Entry + ارزشِ تأیید (فصلِ ۴)")
    print("=" * 100)
    df = S.lastn(S.load(f"{CFG['asset']}_M15"))
    asset, side = CFG['asset'], CFG['side']
    sl, tp, mh = CFG['sl'], CFG['tp'], CFG['mh']

    sig_base = sig_of(df, confirm=False)
    sig_conf = sig_of(df, confirm=True)

    rb = net_wr(df, sig_base, asset, side, sl, tp, mh)
    rc = net_wr(df, sig_conf, asset, side, sl, tp, mh)
    print(f"\n[پیکربندی] {asset} {side} ema{CFG['ef']}/{CFG['es']} bf{CFG['bf']} "
          f"SL{sl}/TP{tp}/mh{mh}")
    print(f"  BASE (next-open) : net=${rb['net']:+,.0f}  WR={rb['wr']:.2f}%  n={rb['n']}  PF={rb['pf']:.3f}")
    print(f"  CONF (stop-entry): net=${rc['net']:+,.0f}  WR={rc['wr']:.2f}%  n={rc['n']}  PF={rc['pf']:.3f}")

    # ---------- آزمونِ ۱: baseline long-bias ----------
    sig_trend = simple_trend_long(df, CFG['ef'], CFG['es'])
    rt = net_wr(df, sig_trend, asset, side, sl, tp, mh)
    delta_base = rb['net'] - rt['net']
    delta_conf = rc['net'] - rt['net']
    print(f"\n[آزمونِ ۱] baseline «روندِ صعودیِ خام»: net=${rt['net']:+,.0f} WR={rt['wr']:.2f}% n={rt['n']}")
    print(f"  Δ(BASE − trend) = ${delta_base:+,.0f}   Δ(CONF − trend) = ${delta_conf:+,.0f}")
    print(f"  ⇒ شرطِ signal-bar {'لبه می‌افزاید ✅' if delta_conf>0 else 'لبه‌ای فراتر از روند ندارد ⛔'}")

    # ---------- آزمونِ ۲: ارزشِ مکانیزمِ تأیید ----------
    d_cb = rc['net'] - rb['net']
    print(f"\n[آزمونِ ۲] ارزشِ مکانیزمِ تأییدِ فصل ۴ (CONF − BASE):")
    print(f"  Δnet = ${d_cb:+,.0f}   ΔWR = {rc['wr']-rb['wr']:+.2f}pp   ΔPF = {rc['pf']-rb['pf']:+.3f}")
    print(f"  حذفِ تله‌های یک‌کندلی: {rb['n']-rc['n']} معامله کمتر")
    conf_better = (rc['wr'] >= rb['wr'] and rc['pf'] >= rb['pf'])
    print(f"  ⇒ تأیید {'کیفیتِ ورود را بهتر می‌کند ✅ (WR↑ و PF↑)' if conf_better else 'کیفیت را بهتر نمی‌کند'}")

    # ---------- آزمونِ ۳: سهمِ مستقل (روی نسخهٔ برنده = CONF) ----------
    h2 = FN.high2_signal(df)
    td = FN.time_drift_union(df)
    sos = FN.sos_signal(df)
    union = h2 | td | sos
    print(f"\n[آزمونِ ۳] همپوشانی با پرتفویِ LONGِ طلا (High-2 + time-drift + SoS):")
    ov_h2 = FN.bar_overlap_pct(sig_conf, h2)
    ov_td = FN.bar_overlap_pct(sig_conf, td)
    ov_sos = FN.bar_overlap_pct(sig_conf, sos)
    ov_all = FN.bar_overlap_pct(sig_conf, union)
    print(f"  ∩ High-2      = {ov_h2:.0f}%")
    print(f"  ∩ time-drift  = {ov_td:.0f}%")
    print(f"  ∩ SoS         = {ov_sos:.0f}%")
    print(f"  ∩ اجتماع      = {ov_all:.0f}%")

    indep = FN.independent_share(sig_conf, union)
    gate = FN.full_gate(df, indep, asset, side, sl, tp, mh, 'S176-CONF-independent')
    print(f"\n[سهمِ مستقلِ CONF] پس از حذفِ {ov_all:.0f}% همپوشانی:")
    print(f"  {json.dumps({k:gate[k] for k in ('net','wr','n','pf','h1','h2','wf_ok','both_ok','ok')}, ensure_ascii=False)}")
    print(f"  walk-forward: {gate.get('wf')}")

    verdict = gate.get('ok', False)
    print("\n" + "=" * 100)
    if verdict:
        print("✅ سهمِ مستقل گیتِ کامل را پاس کرد ⇒ کاندیدِ ثبت به‌عنوان لایهٔ جدید.")
    else:
        print("⛔ سهمِ مستقل گیتِ کامل را پاس نکرد ⇒ عمدتاً long-bias/همپوشان با پرتفویِ موجود.")
    print("=" * 100)

    out = dict(cfg=CFG,
               base=dict(net=rb['net'], wr=rb['wr'], n=rb['n'], pf=rb['pf']),
               conf=dict(net=rc['net'], wr=rc['wr'], n=rc['n'], pf=rc['pf']),
               trend_baseline=dict(net=rt['net'], wr=rt['wr'], n=rt['n']),
               delta_conf_vs_trend=round(delta_conf, 1),
               delta_conf_vs_base=round(d_cb, 1),
               conf_better=conf_better,
               overlap=dict(high2=round(ov_h2, 1), time_drift=round(ov_td, 1),
                            sos=round(ov_sos, 1), union=round(ov_all, 1)),
               independent=gate,
               verdict_independent_ok=verdict)
    with open('results/_s176_finalize.json', 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("✅ ذخیره شد: results/_s176_finalize.json")


if __name__ == '__main__':
    main()
