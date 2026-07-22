# -*- coding: utf-8 -*-
"""
S182 — تأییدِ مستقلِ S178 (Two-Bar Reversal LONG طلا) با سنجشِ همپوشانیِ *کامل*
================================================================================
هدفِ پروژه: بیشینه‌سازیِ سودِ خالص (XAUUSD+EURUSD)؛ WR فقط کفِ ۴۰٪.

انگیزه (درسِ تازهٔ S180): فایلِ `s178_finalize.py` که S178 را «پذیرفته» اعلام کرد،
سهمِ مستقل را فقط نسبت به **High-2 + time-drift** سنجیده بود (`union = h2 | td`) — دقیقاً
همان نقصی که در S169 باعثِ توهمِ «+$4,817 مستقل» شد. چون S169 با Signs-of-Strength (S171)
۹۹.۶٪ همپوشان بود، لازم است S178 هم نسبت به **اجتماعِ کاملِ پرتفوی** بازسنجی شود:
   High-2(S168) + Signs-of-Strength(S171) + Two-Legs(S172) + Sell-Climax(S174) + time-drifts.

اگر سهمِ کاملاً مستقلِ S178 هنوز گیت را پاس کند ⇒ پذیرشِ +$1,533 معتبر است و رکورد
واقعاً +$238,714 است. اگر نه ⇒ باید عددِ رکورد تصحیح شود.

خروجی: چاپ + results/_s182_verify_s178_full_overlap.json
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(__file__))
import s172_brooks_two_legs as S
import s174_brooks_sell_climax_reversal as SC
import s174_finalize as F
import s178_brooks_two_bar_reversal as T
import s180_revive_s169_standalone as R180   # signs_of_strength_long, two_legs_long, sell_climax_long

WR_FLOOR = 40.0

CFG = dict(asset='XAUUSD', side='long', ema_fast=10, ema_slow=30,
           body_frac=0.6, size_tol=1.0, lb=40, sl=300, tp=450, mh=96)


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
    print("S182 — تأییدِ S178 (Two-Bar Reversal LONG طلا) با همپوشانیِ کاملِ پرتفوی")
    print("=" * 100)

    asset = CFG['asset']
    df = S.lastn(S.load(asset + '_M15'))
    print(f"{asset}: rows={len(df)}  ({df['dt'].iloc[0]} → {df['dt'].iloc[-1]})\n")

    sig = T.two_bar_reversal_signals(df, CFG['side'], CFG['body_frac'], CFG['size_tol'],
                                     CFG['lb'], CFG['ema_fast'], CFG['ema_slow'])
    print(f"سیگنالِ خامِ S178: n={int(sig.sum())}")
    raw = gate(df, sig, asset, CFG['sl'], CFG['tp'], CFG['mh'], 'S178 raw')
    print(f"S178 خام        : net={raw.get('net'):+.0f} WR={raw.get('wr')}% n={raw['n']} "
          f"PF={raw.get('pf')} WF_ok={raw.get('wf_ok')} => {'OK' if raw.get('ok') else 'X'}")
    print(f"                  WF: {['%+.0f(WR%.0f)' % (x[0], x[1]) for x in raw['wf']]}\n")

    # همپوشانی با کلِ پرتفویِ LONG طلا
    print("-" * 100)
    print("همپوشانیِ بار-به-بار (recent-12) با کلِ پرتفویِ LONGِ طلا:")
    h2 = F.brooks_high2_long(df)
    sos = R180.signs_of_strength_long(df)
    tl = R180.two_legs_long(df)
    scx = R180.sell_climax_long(df)
    td = F.time_drift_long(df)
    layers = dict(High2_S168=h2, SignsOfStrength_S171=sos, TwoLegs_S172=tl,
                  SellClimax_S174=scx, TimeDrifts=td)
    overlaps = {}
    for name, lyr in layers.items():
        ov = F.bar_overlap_pct(sig, lyr)
        overlaps[name] = round(ov, 1)
        print(f"  S178 ∩ {name:22s} = {ov:5.1f}%")

    # اجتماعِ finalize قدیمی (فقط High-2 + time-drift)
    union_old = h2 | td
    ov_old = F.bar_overlap_pct(sig, union_old)
    overlaps['UNION_OLD_h2_td'] = round(ov_old, 1)
    # اجتماعِ کامل
    union_full = h2 | sos | tl | scx | td
    ov_full = F.bar_overlap_pct(sig, union_full)
    overlaps['UNION_FULL'] = round(ov_full, 1)
    print(f"\n  اجتماعِ قدیمِ finalize (High-2+time) = {ov_old:5.1f}%  (این را finalize استفاده کرد)")
    print(f"  اجتماعِ کاملِ پرتفوی (+S171/S172/S174) = {ov_full:5.1f}%  ← معیارِ درست")

    # سهمِ مستقل با هر دو تعریف
    print("\n" + "-" * 100)
    indep_old = F.independent_share(sig, union_old)
    r_old = gate(df, indep_old, asset, CFG['sl'], CFG['tp'], CFG['mh'], 'indep vs OLD union')
    print(f"سهمِ مستقل (تعریفِ قدیمِ finalize): net={_g(r_old,'net')} WR={_g(r_old,'wr')}% "
          f"n={r_old.get('n')} WF_ok={r_old.get('wf_ok')} => {'OK' if r_old.get('ok') else 'رد'}")

    indep_full = F.independent_share(sig, union_full)
    r_full = gate(df, indep_full, asset, CFG['sl'], CFG['tp'], CFG['mh'], 'indep vs FULL union')
    print(f"سهمِ مستقل (اجتماعِ کاملِ درست): ", end='')
    if r_full.get('n', 0) >= 30:
        print(f"net={r_full['net']:+.0f} WR={r_full['wr']}% n={r_full['n']} "
              f"PF={r_full['pf']} h1={r_full['h1']} h2={r_full['h2']}")
        print(f"   WF: {['%+.0f(WR%.0f)' % (x[0], x[1]) for x in r_full['wf']]}")
        print(f"   گیتِ کامل: {'✅ پاس' if r_full['ok'] else '⛔ رد'}")
    else:
        print(f"n={r_full.get('n')} < 30 ⇒ سهمِ مستقلِ کافی وجود ندارد ⇒ ⛔ رد")

    # حکم
    print("\n" + "=" * 100)
    if r_full.get('ok'):
        verdict = 'CONFIRMED'
        print(f"✅ تأیید شد: سهمِ کاملاً مستقلِ S178 گیت را پاس می‌کند (net=+${r_full['net']:,.0f}).")
        print(f"   پذیرشِ S178 و رکوردِ +$238,714 معتبر است.")
    else:
        verdict = 'INVALIDATED'
        print(f"⚠️ ابطال: سهمِ کاملاً مستقلِ S178 گیت را پاس نمی‌کند.")
        print(f"   عددِ رکوردِ +$238,714 باید بازبینی/تصحیح شود.")
    print("=" * 100)

    out = dict(strategy='S182_verify_s178', cfg=CFG, raw=raw, overlaps=overlaps,
               indep_old=r_old, indep_full=r_full, verdict=verdict)
    with open('results/_s182_verify_s178_full_overlap.json', 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=float)
    print("✅ ذخیره شد: results/_s182_verify_s178_full_overlap.json")


def _g(r, k):
    v = r.get(k)
    return f"{v:+.0f}" if isinstance(v, (int, float)) else str(v)


if __name__ == '__main__':
    main()
