# -*- coding: utf-8 -*-
"""
S174-FILTER — کاربردِ کلایمکسِ فروش به‌عنوان فیلتر (قانونِ همپوشانیِ پروژه)
================================================================================
هدفِ پروژه: بیشینه‌سازیِ سودِ خالص (XAUUSD+EURUSD)؛ WR فقط کفِ ۴۰٪.

منشأ: در S174-finalize دیدیم لبهٔ کلایمکس *واقعی* است (Δ+$1,977 فراتر از long-bias)
اما سهمِ مستقل (پس از حذفِ ۴۹٪ همپوشانی با LONGِ طلا) گیتِ walk-forward را رد کرد.
طبقِ **قانونِ همپوشانیِ پرامپت**: پیش از رفتن به فصلِ بعد، *حتماً* کاربردِ فیلتر بررسی
شود. دو فرضیهٔ فیلتری:

  (الف) فیلترِ ردِ SHORT: «اگر اخیراً sell-climax رخ داده ⇒ SHORT نزن» — چون کلایمکس
        نشانهٔ خستگیِ روندِ نزولی است. باید WR لایه‌های SHORT را بالا ببرد بی‌آنکه net
        را زیاد بخورد. لایهٔ هدف: S173 (Market Inertia SHORT، WR مرزیِ ۴۸.۹٪).
        این *منطقاً هم‌راستا* است: S173 در روندِ نزولی SHORT می‌زند؛ کلایمکس می‌گوید
        «این روندِ نزولی خسته است» ⇒ ردِ آن ورود.

  (ب) فیلترِ تأییدِ LONG: «فقط وقتی اخیراً sell-climax رخ داده LONG بزن» روی لایه‌های
        LONGِ مرزیِ طلا — سیگنالِ ورودِ باکیفیت‌تر (کفِ خستگی).

روش: برای هر لایهٔ هدف، سیگنالِ base و سیگنالِ base∧filter را با گیتِ کامل می‌سنجیم؛
فیلتر فقط وقتی پذیرفته می‌شود که (WR↑ یا net↑) و همهٔ گیت‌های سخت سبز بمانند.

خروجی: چاپِ کنسول + results/_s174_climax_filter.json
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(__file__))
import s172_brooks_two_legs as S
import s173_brooks_market_inertia as MI
import s174_brooks_sell_climax_reversal as SC
from engine import indicators as ind

WR_FLOOR = 40.0

# کاندیدِ کلایمکس (همان S174)
CLIMAX = dict(ema_fast=10, ema_slow=30, dur=20, k_body=2.0, accel=False, body_win=5)

# لایهٔ هدفِ SHORT: S173 (Market Inertia)
S173_CFG = dict(asset='XAUUSD', ef=20, es=50, adx_hi=28, lb=20, sl=250, tp=375, mh=48)


def full_gate_short(df, sig, asset, sl, tp, mh, label):
    z = np.zeros(len(df), bool)
    tr = S.sim(df, z, sig, sl, tp, mh, asset)
    r = S.stats(tr, asset)
    if not r or r['n'] < 30:
        return dict(label=label, n=r['n'] if r else 0, ok=False, reason='n<30')
    hv = S.halves(df, z, sig, sl, tp, mh, asset)
    wf = MI.walk_forward(df, sig, 'short', sl, tp, mh, asset)
    wf_ok = all(x[0] > 0 and x[1] >= WR_FLOOR for x in wf)
    both_ok = bool(hv and hv['h1'] > 0 and hv['h2'] > 0)
    ok = bool(r['net'] > 0 and r['wr'] >= WR_FLOOR and both_ok and wf_ok)
    return dict(label=label, net=round(r['net'], 1), wr=round(r['wr'], 2), n=r['n'],
                pf=round(r['pf'], 3) if r['pf'] != float('inf') else 999.0,
                h1=round(hv['h1'], 1) if hv else None, h2=round(hv['h2'], 1) if hv else None,
                wf=[(round(x[0], 1), round(x[1], 1), x[2]) for x in wf],
                wf_ok=wf_ok, both_ok=both_ok, ok=ok)


def climax_recent_mask(df, w):
    """آیا در w کندلِ اخیر یک sell-climax رخ داده؟ (shift-safe)"""
    sig = SC.sell_climax_signals(df, CLIMAX['ema_fast'], CLIMAX['ema_slow'],
                                 CLIMAX['dur'], CLIMAX['k_body'],
                                 CLIMAX['accel'], CLIMAX['body_win'])
    recent = pd.Series(sig.astype(float)).rolling(w, min_periods=1).max().to_numpy() > 0
    return recent


def main():
    print("=" * 100)
    print("S174-FILTER — کلایمکسِ فروش به‌عنوان فیلترِ ردِ SHORT روی S173 (قانونِ همپوشانی)")
    print("=" * 100)

    asset = S173_CFG['asset']
    df = S.lastn(S.load(asset + '_M15'))
    print(f"{asset}: rows={len(df)}")

    # base S173-SHORT
    base_sig = MI.inertia_signals(df, S173_CFG['ef'], S173_CFG['es'],
                                  S173_CFG['adx_hi'], S173_CFG['lb'], 'short')
    base = full_gate_short(df, base_sig, asset, S173_CFG['sl'], S173_CFG['tp'],
                           S173_CFG['mh'], 'S173-SHORT base')
    print(f"\nbase S173-SHORT: net={base.get('net'):+.0f} WR={base.get('wr')} n={base['n']} "
          f"PF={base.get('pf')} WF_ok={base.get('wf_ok')} both={base.get('both_ok')} "
          f"=> {'OK' if base['ok'] else 'X'}")

    # ---------- (الف) فیلترِ ردِ SHORT: NOT recent-climax ----------
    print("\n### (الف) فیلترِ ردِ SHORT: اگر اخیراً کلایمکس رخ داده، SHORT نزن ###")
    results_reject = []
    for w in (12, 24, 48, 96):
        rc = climax_recent_mask(df, w)
        filt_sig = base_sig & (~rc)                     # SHORT فقط وقتی اخیراً کلایمکس نبوده
        r = full_gate_short(df, filt_sig, asset, S173_CFG['sl'], S173_CFG['tp'],
                            S173_CFG['mh'], f'S173-SHORT ∧ ¬climax(w{w})')
        results_reject.append((w, r))
        if r.get('net') is not None:
            print(f"  w{w:3d}: net={r['net']:+.0f} WR={r['wr']} n={r['n']} PF={r['pf']} "
                  f"WF_ok={r['wf_ok']} both={r['both_ok']} "
                  f"[Δnet={r['net']-base['net']:+.0f} ΔWR={r['wr']-base['wr']:+.1f}] "
                  f"=> {'OK ✅' if r['ok'] else 'X'}")

    # ---------- ارزیابیِ برنده ----------
    # فیلتر ارزشمند است اگر: گیتِ کامل پاس + WR بالاتر از base (بهبود) + net افتِ فاجعه‌بار نکند
    best_reject = None
    for w, r in results_reject:
        if r.get('ok') and r['wr'] > base.get('wr', 0):
            if best_reject is None or r['net'] > best_reject[1]['net']:
                best_reject = (w, r)

    print("\n" + "=" * 100)
    verdict = {}
    if best_reject:
        w, r = best_reject
        print(f"✅ فیلترِ ردِ SHORT (w{w}) روی S173: WR {base['wr']}%→{r['wr']}% ، "
              f"net {base['net']:+.0f}→{r['net']:+.0f}  ⇒ Δnet={r['net']-base['net']:+.0f}")
        print("   (این «بهبودِ WR لایهٔ موجود» است — راهِ اولِ پروژه؛ Δnet مثبت/کوچک‌منفی قابلِ قبول اگر WR↑)")
        verdict = dict(kind='reject-short-filter', w=w, base=base, filtered=r,
                       delta_net=round(r['net']-base['net'], 1),
                       delta_wr=round(r['wr']-base['wr'], 2))
    else:
        print("⛔ فیلترِ ردِ SHORT روی S173 بهبودِ معنادار (WR↑ با گیتِ کامل) نداد.")
        verdict = dict(kind='reject-short-filter', accepted=False, base=base,
                       candidates=[(w, r) for w, r in results_reject])
    print("=" * 100)

    out = dict(strategy='S174_climax_filter', climax_cfg=CLIMAX, s173_cfg=S173_CFG,
               base=base, reject_short=[dict(w=w, **r) for w, r in results_reject],
               verdict=verdict)
    with open('results/_s174_climax_filter.json', 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=float)
    print("✅ ذخیره شد: results/_s174_climax_filter.json")


if __name__ == '__main__':
    main()
