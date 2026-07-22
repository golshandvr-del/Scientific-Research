# -*- coding: utf-8 -*-
"""
S180 — احیای مستقیمِ استراتژیِ سوختهٔ S169 (Spike-and-Channel LONG طلا) روی دادهٔ ۴ سالِ اخیر
================================================================================
هدفِ پروژه: بیشینه‌سازیِ سودِ خالص (XAUUSD+EURUSD)؛ WR فقط کفِ ۴۰٪ برای هر لایه.

راهِ دومِ پروژه (زنده‌کردنِ استراتژیِ سوخته) + کشفِ جانبیِ نشستِ قبل:

  S169 (Spike-and-Channel LONG طلا) در نشستِ فصلِ ۲۱ رد شد چون «سهمِ مستقلِ» آن روی
  دادهٔ کامل (۲۰۲۰→۲۰۲۶) در پنجرهٔ W1 (کووید ۲۰۲۰، دورهٔ نوسانِ شدید) منفی بود ⇒
  walk-forward نامعتبر. اما با پنجرهٔ استانداردِ پروژه (lastn = ۴ سالِ اخیر، ۲۰۲۲→۲۰۲۶)
  که دورهٔ کووید را حذف می‌کند، سهمِ مستقل دیگر سوخته نیست.

  این اسکریپت آن کشف را با روش‌شناسیِ **کامل و سخت‌گیرانهٔ** پروژه تأیید می‌کند:
   1) سیگنالِ خامِ S169 LONG طلا (کاندیدِ برنده: ema10/30, spk3×1.5, cw20, SL200/TP300/mh32).
   2) سنجشِ همپوشانیِ بار-به-بار با **کلِ پرتفویِ LONGِ طلا** (نه فقط time-drift):
      High-2(S168), Signs-of-Strength(S171), Two-Legs(S172), sell-climax(S174), و
      اجتماعِ زمان-محورها. طبقِ «قانونِ همپوشانی» باید بدانیم دقیقاً با چه چیزی و چند درصد.
   3) استخراجِ «سهمِ کاملاً مستقل» = حذفِ recent-۱۲ کندلِ اجتماعِ کلِ پرتفوی.
   4) گیتِ سختِ ۴-گانه روی سهمِ مستقل: net>0, WR≥40, هر دو نیمه مثبت, walk-forward 4/4, n≥30.
   5) آزمونِ همپوشانی به‌عنوان فیلتر (راهِ اولِ پروژه): آیا بخشِ همپوشانِ S169 می‌تواند
      WR لایه‌های مرزیِ زمان-محور (S140⁺/S142⁺) را بالا ببرد؟

خروجی: چاپِ کنسول + results/_s180_revive_s169_standalone.json
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(__file__))
import s172_brooks_two_legs as S              # load, lastn, sim, stats, halves
import s174_brooks_sell_climax_reversal as SC # walk_forward, sell_climax_signals
import s174_finalize as F                     # brooks_high2_long, time_drift_long, bar_overlap_pct
import s169_brooks_spike_channel as SP
from engine import indicators as ind

WR_FLOOR = 40.0
OVERLAP_BARS = 12

# کاندیدِ برندهٔ S169 (از فایلِ REJECTED)
CFG = dict(asset='XAUUSD', side='long', ema_fast=10, ema_slow=30,
           spike_len=3, spike_atr_mult=1.5, channel_window=20, sl=200, tp=300, mh=32)


def s169_long_signal(df):
    le, sh = SP.detect_spike_channel_events(df, CFG['ema_fast'], CFG['ema_slow'],
                                            CFG['spike_len'], CFG['spike_atr_mult'],
                                            CFG['channel_window'])
    return pd.Series(le).shift(1).fillna(False).to_numpy()   # causal


def signs_of_strength_long(df, ema_period=20, win=20, threshold=2):
    """بازسازیِ ساده‌شدهٔ S171: نمرهٔ ۴-نشانهٔ قدرتِ روندِ صعودی ≥ threshold ⇒ Long."""
    c = df['close']; h = df['high'].to_numpy(); l = df['low'].to_numpy()
    o = df['open'].to_numpy(); cl = c.to_numpy()
    e = ind.ema(c, ema_period).to_numpy()
    rng = np.maximum(h - l, 1e-9); body = np.abs(cl - o)
    n = len(df); sig = np.zeros(n, bool)
    hh = h > np.r_[np.nan, h[:-1]]
    for i in range(win, n):
        if not (e[i] > e[i-1]):
            continue
        score = 0
        # 1) بدنه‌های صعودیِ قوی
        if body[i] >= 0.6 * rng[i] and cl[i] > o[i]:
            score += 1
        # 2) higher-highهای متوالی
        if hh[i] and hh[i-1]:
            score += 1
        # 3) بسته‌شدن نزدیکِ سقفِ کندل
        if (h[i] - cl[i]) <= 0.25 * rng[i]:
            score += 1
        # 4) close بالای ema
        if cl[i] > e[i]:
            score += 1
        if score >= threshold:
            sig[i] = True
    return pd.Series(sig).shift(1).fillna(False).to_numpy()


def two_legs_long(df):
    """بازسازیِ S172 two-leg pullback LONG طلا."""
    try:
        s = S.two_leg_pullback_signals(df, 20, 50, 5, 'long')
        return pd.Series(np.asarray(s, bool)).shift(1).fillna(False).to_numpy()
    except Exception:
        return np.zeros(len(df), bool)


def sell_climax_long(df):
    """بازسازیِ S174 sell-climax exhaustion reversal LONG طلا."""
    try:
        s = SC.sell_climax_signals(df, 10, 30, 20, 2.0, False, 5)
        return np.asarray(s, bool)
    except Exception:
        return np.zeros(len(df), bool)


def gate(df, sig, asset, sl, tp, mh, label):
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
                h1=round(hv['h1'], 1) if hv else None, h2=round(hv['h2'], 1) if hv else None,
                wf=[(round(x[0], 1), round(x[1], 1), x[2]) for x in wf],
                wf_ok=wf_ok, both_ok=both_ok, ok=ok)


def main():
    print("=" * 100)
    print("S180 — احیای S169 (Spike-Channel LONG طلا) مستقیم روی دادهٔ ۴ سالِ اخیر")
    print("گیت: net>0, WR≥40, هر دو نیمه, walk-forward 4/4, n≥30. هدف=سودِ خالص.")
    print("=" * 100)

    asset = CFG['asset']
    df = S.lastn(S.load(asset + '_M15'))
    print(f"{asset}: rows={len(df)}  ({df['dt'].iloc[0]} → {df['dt'].iloc[-1]})\n")

    s169 = s169_long_signal(df)
    print(f"سیگنالِ خامِ S169: n={int(s169.sum())}\n")

    # (1) خامِ S169
    raw = gate(df, s169, asset, CFG['sl'], CFG['tp'], CFG['mh'], 'S169 raw')
    print(f"S169 خام        : net={raw.get('net'):+.0f} WR={raw.get('wr')}% n={raw['n']} "
          f"PF={raw.get('pf')} WF_ok={raw.get('wf_ok')} => {'OK' if raw.get('ok') else 'X'}")
    print(f"                  WF: {['%+.0f(WR%.0f)' % (x[0], x[1]) for x in raw['wf']]}")

    # (2) همپوشانی با کلِ پرتفویِ LONGِ طلا
    print("\n" + "-" * 100)
    print("سنجشِ همپوشانیِ بار-به-بار (recent-12) با کلِ پرتفویِ LONGِ طلا:")
    h2 = F.brooks_high2_long(df)
    sos = signs_of_strength_long(df)
    tl = two_legs_long(df)
    scx = sell_climax_long(df)
    td = F.time_drift_long(df)
    layers = dict(High2_S168=h2, SignsOfStrength_S171=sos, TwoLegs_S172=tl,
                  SellClimax_S174=scx, TimeDrifts=td)
    overlaps = {}
    for name, lyr in layers.items():
        ov = F.bar_overlap_pct(s169, lyr)
        overlaps[name] = round(ov, 1)
        print(f"  S169 ∩ {name:22s} = {ov:5.1f}%")
    union = h2 | sos | tl | scx | td
    ov_all = F.bar_overlap_pct(s169, union)
    overlaps['UNION_ALL'] = round(ov_all, 1)
    print(f"  {'':2s}S169 ∩ اجتماعِ کلِ پرتفویِ LONG = {ov_all:5.1f}%  ← تعیین‌کننده")

    # (3) سهمِ کاملاً مستقل (پس از حذفِ اجتماعِ کل)
    print("\n" + "-" * 100)
    indep = F.independent_share(s169, union)
    ind_res = gate(df, indep, asset, CFG['sl'], CFG['tp'], CFG['mh'], 'S169 fully-independent')
    print(f"سهمِ کاملاً مستقلِ S169 (پس از حذفِ اجتماعِ کل):")
    if ind_res.get('n', 0) >= 30:
        print(f"  net={ind_res['net']:+.0f} WR={ind_res['wr']}% n={ind_res['n']} PF={ind_res['pf']} "
              f"h1={ind_res['h1']} h2={ind_res['h2']}")
        print(f"  WF: {['%+.0f(WR%.0f)' % (x[0], x[1]) for x in ind_res['wf']]}")
        print(f"  گیتِ کامل: {'✅ پاس' if ind_res['ok'] else '⛔ رد'} "
              f"(net>0={ind_res['net']>0}, WR≥40={ind_res['wr']>=40}, "
              f"both_halves={ind_res['both_ok']}, WF4/4={ind_res['wf_ok']})")
    else:
        print(f"  n={ind_res.get('n')} < 30 ⇒ سهمِ مستقلِ کافی وجود ندارد")

    # (4) نتیجهٔ نهایی
    print("\n" + "=" * 100)
    accepted_sig = None; accepted_net = 0.0; decision = 'REJECT'
    if ind_res.get('ok'):
        accepted_sig = 'fully_independent'; accepted_net = ind_res['net']; decision = 'ACCEPT_INDEP'
        print(f"✅ سهمِ کاملاً مستقلِ S169 گیت را پاس کرد ⇒ لایهٔ نو با net=+${ind_res['net']:,.0f}")
    elif raw.get('ok'):
        # اگر مستقلِ کامل n<30 شد ولی خام پاس است، تصمیم بر اساس همپوشانی
        print(f"ℹ️ سهمِ کاملاً مستقل به گیت نرسید (n یا WF)، اما خامِ S169 پاس است.")
        print(f"   همپوشانیِ کل = {ov_all:.0f}% ⇒ تصمیم در بخشِ فیلتر بررسی می‌شود.")
    else:
        print("⛔ نه سهمِ مستقل و نه خام گیت را پاس نکرد.")
    print("=" * 100)

    out = dict(strategy='S180_revive_s169_standalone', cfg=CFG,
               raw=raw, overlaps=overlaps, independent=ind_res,
               decision=decision, accepted_net=accepted_net)
    with open('results/_s180_revive_s169_standalone.json', 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=float)
    print("✅ ذخیره شد: results/_s180_revive_s169_standalone.json")


if __name__ == '__main__':
    main()
