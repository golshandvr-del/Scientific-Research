# -*- coding: utf-8 -*-
"""
S177-FINALIZE — سنجشِ لبهٔ واقعیِ «Reversal Bar» (فصلِ ۵، LONG طلا)
================================================================================
هدفِ پروژه: بیشینه‌سازیِ سودِ خالص (XAUUSD+EURUSD)؛ WR فقط کفِ ۴۰٪.

کاندیدِ برندهٔ گریدِ S177 (پایدارترین با walk-forward 4/4):
    XAUUSD long  ema20/50  tf0.33  uf0.25  cc4  hh3  lb40  SL200/TP300/mh48
    خام: net=$+1,679  WR=53.16%  n=79  PF=1.50  (گیتِ کاملِ ۴-گانه پاس)

⚠️ درسِ تکراریِ پروژه (S172/S174/S175): مفاهیمِ برگشتیِ Brooks روی طلا اغلب *واقعی*
   اما همپوشانِ سنگین با long-bias/High-2 هستند. بنابراین دو آزمونِ سخت:

   (۱) BASELINE long-bias: خریدِ بدونِ شرطِ reversal-bar در همان رژیم/SL/TP/mh
       با تعدادِ معاملهٔ هم‌تراز ⇒ Δ(reversal − baseline) باید مثبتِ معنادار باشد.
   (۲) سهمِ مستقل (anti-double-counting): حذفِ سیگنال‌های داخلِ recent-۱۲ کندلِ
       *اجتماعِ* لایه‌های LONGِ طلا (High-2 + time-drifts) ⇒ گیتِ کامل روی باقی.

خروجی: چاپِ کنسول + results/_s177_finalize.json
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(__file__))
import s172_brooks_two_legs as S            # load, lastn, sim, stats, halves
import s174_brooks_sell_climax_reversal as SC   # walk_forward
import s174_finalize as F                    # brooks_high2_long, time_drift_long, overlap helpers
import s177_brooks_reversal_bar as R
from engine import indicators as ind

OVERLAP_BARS = 12
WR_FLOOR = 40.0

# کاندیدِ برندهٔ S177 (تثبیت‌شده در گرید — پایدارترین با walk-forward 4/4)
CFG = dict(asset='XAUUSD', side='long', ema_fast=10, ema_slow=30,
           tail_frac=0.5, up_frac=0.35, cc=4, hh=3, lb=20,
           sl=150, tp=225, mh=96)


def baseline_regime_long(df, ema_fast, ema_slow, lb, sample_every):
    """LONG در کندل‌های نزدیکِ کفِ lb اخیر در رژیمِ نزولی/خنثی (همان context، بدونِ
    شرطِ هندسهٔ reversal-bar) ⇒ برای تفکیکِ لبهٔ شکلِ کندل از long-bias ساختاری."""
    c = df['close']; cl = c.to_numpy()
    l = df['low']; h = df['high']
    ef = ind.ema(c, ema_fast).to_numpy(); es = ind.ema(c, ema_slow).to_numpy()
    ctx_low = l.shift(1).rolling(lb).min().to_numpy()
    ctx_high = h.shift(1).rolling(lb).max().to_numpy()
    near_low = l.to_numpy() <= np.nan_to_num(ctx_low, nan=-1e18) + \
        (np.nan_to_num(ctx_high, nan=0) - np.nan_to_num(ctx_low, nan=0)) * 0.15
    regime = ef <= es
    elig = near_low & regime
    raw = np.zeros(len(df), bool)
    cnt = 0
    for i in np.where(elig)[0]:
        if cnt % sample_every == 0:
            raw[i] = True
        cnt += 1
    return pd.Series(raw).shift(1).fillna(False).to_numpy()


def full_gate(df, sig, asset, sl, tp, mh, label):
    z = np.zeros(len(df), bool)
    tr = S.sim(df, sig, z, sl, tp, mh, asset)
    r = S.stats(tr, asset)
    if not r or r['n'] < 30:
        return dict(label=label, n=(r['n'] if r else 0), ok=False, reason='n<30')
    hv = S.halves(df, sig, z, sl, tp, mh, asset)
    wf = SC.walk_forward(df, sig, sl, tp, mh, asset)
    wf_ok = all(x[0] > 0 and x[1] >= WR_FLOOR for x in wf)
    both_ok = bool(hv and hv['h1'] > 0 and hv['h2'] > 0)
    ok = bool(r['net'] > 0 and r['wr'] >= WR_FLOOR and both_ok and wf_ok)
    return dict(label=label, net=round(r['net'], 1), wr=round(r['wr'], 2), n=r['n'],
                pf=round(r['pf'], 3) if r['pf'] != float('inf') else 999.0,
                h1=round(hv['h1'], 1) if hv else None,
                h2=round(hv['h2'], 1) if hv else None,
                wf=[(round(x[0], 1), round(x[1], 1), x[2]) for x in wf],
                wf_ok=wf_ok, both_ok=both_ok, ok=ok)


def main():
    print("=" * 100)
    print("S177-FINALIZE — لبهٔ «Reversal Bar» (فصلِ ۵) در برابرِ baseline long-bias + سهمِ مستقل")
    print("=" * 100)

    asset = CFG['asset']
    df = S.lastn(S.load(asset + '_M15'))
    print(f"{asset}: rows={len(df)}  ({df['dt'].iloc[0]} → {df['dt'].iloc[-1]})")

    # 1) سیگنالِ خامِ reversal-bar
    sig = R.reversal_bar_signals(df, CFG['side'], CFG['tail_frac'], CFG['up_frac'],
                                 CFG['cc'], CFG['hh'], CFG['lb'], CFG['ema_fast'], CFG['ema_slow'])
    print(f"\nS177 reversal-bar خام: n_signals={int(sig.sum())}")
    raw = full_gate(df, sig, asset, CFG['sl'], CFG['tp'], CFG['mh'], 'S177 reversal raw')
    print(f"  خام: net={raw.get('net'):+.0f} WR={raw.get('wr')} n={raw['n']} PF={raw.get('pf')} "
          f"h1={raw.get('h1')} h2={raw.get('h2')} WF_ok={raw.get('wf_ok')} => {'OK' if raw['ok'] else 'X'}")

    # 2) BASELINE long-bias هم‌تراز
    n_rev = int(sig.sum())
    l = df['low']; h = df['high']; c = df['close']
    ef = ind.ema(c, CFG['ema_fast']).to_numpy(); es = ind.ema(c, CFG['ema_slow']).to_numpy()
    ctx_low = l.shift(1).rolling(CFG['lb']).min().to_numpy()
    ctx_high = h.shift(1).rolling(CFG['lb']).max().to_numpy()
    near_low = l.to_numpy() <= np.nan_to_num(ctx_low, nan=-1e18) + \
        (np.nan_to_num(ctx_high, nan=0) - np.nan_to_num(ctx_low, nan=0)) * 0.15
    elig_n = int((near_low & (ef <= es)).sum())
    sample_every = max(1, elig_n // max(1, n_rev))
    print(f"\nBASELINE long-bias: کندل‌های واجدِ context={elig_n}، هدفِ ~{n_rev} معامله "
          f"⇒ sample_every={sample_every}")
    base_sig = baseline_regime_long(df, CFG['ema_fast'], CFG['ema_slow'], CFG['lb'], sample_every)
    base = full_gate(df, base_sig, asset, CFG['sl'], CFG['tp'], CFG['mh'], 'baseline context-long')
    print(f"  baseline: net={base.get('net'):+.0f} WR={base.get('wr')} n={base['n']} PF={base.get('pf')}")

    edge_vs_baseline = None
    if base.get('net') is not None:
        edge_vs_baseline = round(raw['net'] - base['net'], 1)
        print(f"\n  ⇒ Δ(reversal − baseline) = ${edge_vs_baseline:+,.0f}  "
              f"({'لبهٔ شکلِ کندل فراتر از long-bias' if edge_vs_baseline > 0 else 'صرفاً long-bias — مشکوک'})")

    # 3) همپوشانی با لایه‌های LONGِ طلا + سهمِ مستقل
    h2 = F.brooks_high2_long(df)
    td = F.time_drift_long(df)
    union = h2 | td
    ov_h2 = F.bar_overlap_pct(sig, h2)
    ov_td = F.bar_overlap_pct(sig, td)
    ov_all = F.bar_overlap_pct(sig, union)
    print(f"\nهمپوشانیِ بار-به-بار (recent-{OVERLAP_BARS}):")
    print(f"  reversal ∩ High-2(S168)       = {ov_h2:.0f}%")
    print(f"  reversal ∩ time-drifts        = {ov_td:.0f}%")
    print(f"  reversal ∩ اجتماعِ LONGِ طلا   = {ov_all:.0f}%")

    indep = F.independent_share(sig, union)
    r_indep = full_gate(df, indep, asset, CFG['sl'], CFG['tp'], CFG['mh'], 'indep-of-gold-LONG')
    if r_indep.get('net') is not None:
        print(f"\nسهمِ مستقل (پس از حذفِ همپوشانی): net={r_indep['net']:+.0f} WR={r_indep['wr']} "
              f"n={r_indep['n']} PF={r_indep['pf']} h1={r_indep.get('h1')} h2={r_indep.get('h2')} "
              f"WF={'/'.join(f'{x[0]:+.0f}' for x in r_indep.get('wf', []))} "
              f"=> {'OK ✅' if r_indep['ok'] else 'X'}")
    else:
        print(f"\nسهمِ مستقل: n={r_indep['n']} reason={r_indep.get('reason')}")

    # 4) تصمیمِ نهایی
    print("\n" + "=" * 100)
    accept = bool(r_indep.get('ok') and (edge_vs_baseline is None or edge_vs_baseline > 0))
    if accept:
        print(f"✅ لبهٔ مستقلِ ثبت‌پذیر: net=${r_indep['net']:+,.0f} WR={r_indep['wr']}% "
              f"n={r_indep['n']} PF={r_indep['pf']} (فراتر از baseline، گیتِ کامل پاس)")
    else:
        reason = []
        if not r_indep.get('ok'): reason.append('سهمِ مستقل گیت را پاس نکرد')
        if edge_vs_baseline is not None and edge_vs_baseline <= 0: reason.append('از long-bias متمایز نیست')
        print(f"⛔ رد ⇒ {' / '.join(reason)}. (بررسیِ کاربردِ فیلتر در گامِ بعد.)")
    print("=" * 100)

    out = dict(strategy='S177_finalize', cfg=CFG, raw=raw, baseline=base,
               edge_vs_baseline=edge_vs_baseline,
               overlap_high2_pct=round(ov_h2, 1), overlap_timedrift_pct=round(ov_td, 1),
               overlap_all_pct=round(ov_all, 1), independent=r_indep, accepted=accept)
    with open('results/_s177_finalize.json', 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=float)
    print("✅ ذخیره شد: results/_s177_finalize.json")


if __name__ == '__main__':
    main()
