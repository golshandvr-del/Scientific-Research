# -*- coding: utf-8 -*-
"""
S174-FINALIZE — سنجشِ لبهٔ واقعیِ «Sell-Climax Exhaustion Reversal» (LONG طلا)
================================================================================
هدفِ پروژه: بیشینه‌سازیِ سودِ خالص (XAUUSD+EURUSD)؛ WR فقط کفِ ۴۰٪.

کاندیدِ برندهٔ گریدِ S174 (فصلِ ۲، «sell-climax exhaustion»):
    XAUUSD  ema10/30  dur20  k_body2.0  SL250/TP375/mh96
    خام: net=$+2,630  WR=46.9%  n=778  PF=1.07  (گیتِ کامل پاس)

⚠️ هشدارِ روش‌شناختی (درسِ S172): PF=1.07 و n=778 خیلی بالاست ⇒ خطرِ اینکه این
   صرفاً بازتولیدِ **long-bias ساختاریِ طلا** باشد (نه لبهٔ کلایمکسِ واقعی). طبقِ درسِ
   S172 (کاندیدِ خامِ +$20k عمدتاً long-bias بود و رد شد)، این اسکریپت دو آزمونِ
   سخت‌گیرانه اجرا می‌کند:

   (۱) BASELINE long-bias: خریدِ **بدونِ شرطِ کلایمکس** با همان رژیمِ نزولی + همان
       SL/TP/mh (یعنی «هر کندل در روندِ نزولی LONG بزن»). اگر net کلایمکس از توزیعِ
       baseline متمایز نباشد ⇒ لبه توهمی است.

   (۲) سهمِ مستقل: حذفِ سیگنال‌هایی که در بازهٔ recent-۱۲ کندلِ *اجتماعِ* لایه‌های
       LONGِ طلا (High-2, Signs-of-Strength, time-drifts) هستند ⇒ گیتِ کامل روی باقی.

خروجی: چاپِ کنسول + results/_s174_finalize.json
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(__file__))
import s172_brooks_two_legs as S           # load, lastn, sim, stats, halves
import s174_brooks_sell_climax_reversal as SC
from engine import indicators as ind

OVERLAP_BARS = 12
WR_FLOOR = 40.0

# کاندیدِ برندهٔ S174 (تثبیت‌شده در گرید)
CFG = dict(asset='XAUUSD', ema_fast=10, ema_slow=30, dur=20, k_body=2.0,
           accel=False, body_win=5, sl=250, tp=375, mh=96, side='long')


# ---------------------------------------------------------------------------
#  BASELINE long-bias: LONG در هر کندلِ روندِ نزولی (بدونِ شرطِ کلایمکس)
#  با همان EMA regime؛ برای تعیینِ اینکه لبهٔ کلایمکس واقعی است یا long-bias.
# ---------------------------------------------------------------------------
def baseline_regime_long(df, ema_fast, ema_slow, dur, sample_every):
    c = df['close']; cl = c.to_numpy()
    ef = ind.ema(c, ema_fast).to_numpy(); es = ind.ema(c, ema_slow).to_numpy()
    below = (cl < es).astype(float)
    dur_below = pd.Series(below).rolling(dur).sum().to_numpy()
    regime_down = (ef < es) & (dur_below >= max(1, int(dur * 0.6)))
    # نمونه‌گیریِ تُنُک (هر sample_every کندلِ رژیمِ نزولی) تا تعدادِ معامله مشابهِ کلایمکس شود
    raw = np.zeros(len(df), bool)
    cnt = 0
    idxs = np.where(regime_down)[0]
    for i in idxs:
        if cnt % sample_every == 0:
            raw[i] = True
        cnt += 1
    return pd.Series(raw).shift(1).fillna(False).to_numpy()


# ---------------------------------------------------------------------------
#  بازسازیِ لایه‌های LONGِ طلا برای بررسیِ همپوشانی
# ---------------------------------------------------------------------------
def brooks_high2_long(df, ef=20, es=50):
    """S168 High-2: در روندِ صعودی، دومین high>high[1] پس از یک pullback ⇒ Long."""
    c = df['close']; h = df['high'].to_numpy()
    emaF = ind.ema(c, ef).to_numpy(); emaS = ind.ema(c, es).to_numpy()
    up = emaF > emaS
    hh = h > np.r_[np.nan, h[:-1]]                       # high>high[1]
    n = len(df); sig = np.zeros(n, bool)
    count = 0
    for i in range(1, n):
        if not up[i]:
            count = 0; continue
        if hh[i]:
            count += 1
            if count == 2:                               # High-2
                sig[i] = True; count = 0
        # pullback ریست را ساده نگه می‌داریم
    return pd.Series(sig).shift(1).fillna(False).to_numpy()


def time_drift_long(df):
    """اجتماعِ ساده‌شدهٔ لایه‌های زمان-محورِ LONGِ طلا (Monday/Mid-Month/Turn-of-Month/
    Overnight/Pre-End) — تقریبِ رویدادِ ورود برای سنجشِ همپوشانی."""
    dt = df['dt'].dt
    hour = dt.hour.to_numpy(); dow = dt.dayofweek.to_numpy(); dom = dt.day.to_numpy()
    overnight = (hour >= 22) & (hour <= 23)
    monday = (dow == 0) & (hour >= 8) & (hour <= 12)
    mid_month = (dom >= 10) & (dom <= 20) & (hour >= 8) & (hour <= 12)
    turn_month = (dom <= 3) & (hour >= 8) & (hour <= 12)
    raw = overnight | monday | mid_month | turn_month
    return pd.Series(raw).shift(1).fillna(False).to_numpy()


def independent_share(sig, union, n_bars=OVERLAP_BARS):
    recent = pd.Series(union.astype(float)).rolling(n_bars, min_periods=1).max().to_numpy() > 0
    return sig & (~recent)


def bar_overlap_pct(a, b, n_bars=OVERLAP_BARS):
    if a.sum() == 0:
        return 0.0
    recent = pd.Series(b.astype(float)).rolling(n_bars, min_periods=1).max().to_numpy() > 0
    return float((a & recent).sum()) / float(a.sum()) * 100


def full_gate(df, sig, asset, sl, tp, mh, label):
    z = np.zeros(len(df), bool)
    tr = S.sim(df, sig, z, sl, tp, mh, asset)
    r = S.stats(tr, asset)
    if not r or r['n'] < 30:
        return dict(label=label, n=r['n'] if r else 0, ok=False, reason='n<30')
    hv = S.halves(df, sig, z, sl, tp, mh, asset)
    wf = SC.walk_forward(df, sig, sl, tp, mh, asset)
    wf_ok = all(x[0] > 0 and x[1] >= WR_FLOOR for x in wf)
    both_ok = bool(hv and hv['h1'] > 0 and hv['h2'] > 0)
    ok = bool(r['net'] > 0 and r['wr'] >= WR_FLOOR and both_ok and wf_ok)
    return dict(label=label, net=round(r['net'], 1), wr=round(r['wr'], 2),
                n=r['n'], pf=round(r['pf'], 3) if r['pf'] != float('inf') else 999.0,
                h1=round(hv['h1'], 1) if hv else None,
                h2=round(hv['h2'], 1) if hv else None,
                wf=[(round(x[0], 1), round(x[1], 1), x[2]) for x in wf],
                wf_ok=wf_ok, both_ok=both_ok, ok=ok)


def main():
    print("=" * 100)
    print("S174-FINALIZE — لبهٔ کلایمکسِ فروش در برابرِ baseline long-bias + سهمِ مستقل")
    print("=" * 100)

    asset = CFG['asset']
    df = S.lastn(S.load(asset + '_M15'))
    print(f"{asset}: rows={len(df)}  ({df['dt'].iloc[0]} → {df['dt'].iloc[-1]})")

    # 1) سیگنالِ خامِ کلایمکس
    sig = SC.sell_climax_signals(df, CFG['ema_fast'], CFG['ema_slow'], CFG['dur'],
                                 CFG['k_body'], CFG['accel'], CFG['body_win'])
    print(f"\nS174 climax خام: n_signals={int(sig.sum())}")
    raw = full_gate(df, sig, asset, CFG['sl'], CFG['tp'], CFG['mh'], 'S174 climax raw')
    print(f"  خام: net={raw.get('net'):+.0f} WR={raw.get('wr')} n={raw['n']} PF={raw.get('pf')} "
          f"h1={raw.get('h1')} h2={raw.get('h2')} WF_ok={raw.get('wf_ok')} => {'OK' if raw['ok'] else 'X'}")

    # 2) BASELINE long-bias با تعدادِ معاملهٔ مشابه (تنظیمِ sample_every)
    n_climax = int(sig.sum())
    # تخمینِ نرخِ رژیمِ نزولی برای هم‌ترازیِ تعداد
    c = df['close']
    ef = ind.ema(c, CFG['ema_fast']).to_numpy(); es = ind.ema(c, CFG['ema_slow']).to_numpy()
    below = (c.to_numpy() < es).astype(float)
    dur_below = pd.Series(below).rolling(CFG['dur']).sum().to_numpy()
    regime_n = int(((ef < es) & (dur_below >= max(1, int(CFG['dur']*0.6)))).sum())
    sample_every = max(1, regime_n // max(1, n_climax))
    print(f"\nBASELINE long-bias: رژیمِ نزولی={regime_n} کندل، هدفِ ~{n_climax} معامله "
          f"⇒ sample_every={sample_every}")
    base_sig = baseline_regime_long(df, CFG['ema_fast'], CFG['ema_slow'], CFG['dur'], sample_every)
    base = full_gate(df, base_sig, asset, CFG['sl'], CFG['tp'], CFG['mh'], 'baseline regime-long')
    print(f"  baseline: net={base.get('net'):+.0f} WR={base.get('wr')} n={base['n']} PF={base.get('pf')}")

    # قضاوت: آیا کلایمکس از baseline برتر است؟
    edge_vs_baseline = None
    if base.get('net') is not None:
        edge_vs_baseline = round(raw['net'] - base['net'], 1)
        print(f"\n  ⇒ Δ(climax − baseline) = ${edge_vs_baseline:+,.0f}  "
              f"({'لبهٔ کلایمکس فراتر از long-bias' if edge_vs_baseline > 0 else 'صرفاً long-bias — مشکوک'})")

    # 3) همپوشانی با لایه‌های LONGِ طلا + سهمِ مستقل
    h2 = brooks_high2_long(df)
    td = time_drift_long(df)
    union = h2 | td
    ov_h2 = bar_overlap_pct(sig, h2)
    ov_td = bar_overlap_pct(sig, td)
    ov_all = bar_overlap_pct(sig, union)
    print(f"\nهمپوشانیِ بار-به-بار (recent-{OVERLAP_BARS}):")
    print(f"  climax ∩ High-2(S168)       = {ov_h2:.0f}%")
    print(f"  climax ∩ time-drifts        = {ov_td:.0f}%")
    print(f"  climax ∩ اجتماعِ LONGِ طلا   = {ov_all:.0f}%")

    indep = independent_share(sig, union)
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
              f"n={r_indep['n']} PF={r_indep['pf']} (فراتر از baseline long-bias، گیتِ کامل پاس)")
    else:
        reason = []
        if not r_indep.get('ok'): reason.append('سهمِ مستقل گیت را پاس نکرد')
        if edge_vs_baseline is not None and edge_vs_baseline <= 0: reason.append('از long-bias متمایز نیست')
        print(f"⛔ رد ⇒ {' / '.join(reason)}. لایه ثبت نمی‌شود (بررسیِ کاربردِ فیلتر در گامِ بعد).")
    print("=" * 100)

    out = dict(strategy='S174_finalize', cfg=CFG, raw=raw, baseline=base,
               edge_vs_baseline=edge_vs_baseline,
               overlap_high2_pct=round(ov_h2, 1), overlap_timedrift_pct=round(ov_td, 1),
               overlap_all_pct=round(ov_all, 1), independent=r_indep, accepted=accept)
    with open('results/_s174_finalize.json', 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=float)
    print("✅ ذخیره شد: results/_s174_finalize.json")


if __name__ == '__main__':
    main()
