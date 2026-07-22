# -*- coding: utf-8 -*-
"""
S176-RECORD-IMPACT — آیا «بهبودِ stop-entry روی High-2» (فصلِ ۴) سهمِ مستقلِ ثبت‌پذیرِ
                     تازه‌ای می‌سازد که رکوردِ رسمی را بالا ببرد؟

منطق (هم‌سو با ثبتِ رسمیِ S168 = سهمِ مستقلِ OUT = +$1,351):
  • رکوردِ فعلی سهمِ مستقلِ High-2 را «گروهِ OUT» (خارج از پنجره‌های همپوشانِ پرتفویِ
    LONGِ دیگر) با +$1,351 ثبت کرده است.
  • حالا مکانیزمِ ورود را از next-open (BASE) به stop-entry (CONF, فصل ۴) تغییر می‌دهیم
    و **سهمِ مستقلِ OUT** را در هر دو حالت با گیتِ سختِ کامل می‌سنجیم.
  • اگر CONF سهمِ مستقلِ OUT را افزایش دهد و گیت را پاس کند:
        Δ_record = net_indep(CONF) − 1351   (فقط اگر Δ>0 و گیت پاس)
    رکوردِ جدید = 237,181 + Δ_record.

union (برای تعیینِ OUT) = time-drift ∪ SoS  (پروکسیِ سایرِ لایه‌های LONG؛ **بدونِ**
خودِ High-2). محافظه‌کارانه؛ همان اسکلتِ finalizeهای قبلی.
"""
import os, sys, json
import numpy as np
import pandas as pd
import warnings; warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import s172_brooks_two_legs as S
import s168_brooks_high2_low2 as H2
import s175_finalize as FN
import s176_high2_stopentry as HS
from engine import indicators as ind

WR_FLOOR = 40.0
OVERLAP_BARS = 12
RECORD_NOW = 237181.0
S168_REGISTERED = 1351.0

# config رسمیِ S168
EF, ES, SL, TP, MH = 20, 50, 300, 450, 32
ASSET = 'XAUUSD'


def walk_forward_indep(df, confirm, union_fn_cache):
    """walk-forward روی سهمِ مستقلِ OUT."""
    wf = []
    n = len(df)
    for k in range(4):
        a = int(n * k / 4); b = int(n * (k + 1) / 4)
        sub = df.iloc[a:b].reset_index(drop=True)
        sig = HS.high2_entry(sub, ASSET, EF, ES, confirm)
        td = FN.time_drift_union(sub); sos = FN.sos_signal(sub)
        union = td | sos
        indep = FN.independent_share(sig, union)
        z = np.zeros(len(sub), bool)
        if indep.sum() < 8:
            wf.append((0.0, 0.0, 0)); continue
        t = S.sim(sub, indep, z, SL, TP, MH, ASSET)
        st = S.stats(t, ASSET)
        wf.append((round(st['net'], 1), round(st['wr'], 1), int(st['n'])))
    return wf


def indep_gate(df, confirm):
    sig = HS.high2_entry(df, ASSET, EF, ES, confirm)
    td = FN.time_drift_union(df); sos = FN.sos_signal(df)
    union = td | sos
    ov = FN.bar_overlap_pct(sig, union)
    indep = FN.independent_share(sig, union)
    z = np.zeros(len(df), bool)
    tr = S.sim(df, indep, z, SL, TP, MH, ASSET)
    r = S.stats(tr, ASSET)
    if not r or r['n'] < 30:
        return dict(ok=False, reason='n<30', n=(r['n'] if r else 0), overlap=round(ov, 1))
    hv = S.halves(df, indep, z, SL, TP, MH, ASSET)
    wf = walk_forward_indep(df, confirm, None)
    wf_ok = all(x[0] > 0 and x[1] >= WR_FLOOR for x in wf)
    both_ok = bool(hv and hv['h1'] > 0 and hv['h2'] > 0)
    ok = bool(r['net'] > 0 and r['wr'] >= WR_FLOOR and both_ok and wf_ok)
    return dict(net=round(r['net'], 1), wr=round(r['wr'], 2), n=int(r['n']),
                pf=round(r['pf'], 3) if r['pf'] != float('inf') else 999.0,
                h1=round(hv['h1'], 1) if hv else None,
                h2=round(hv['h2'], 1) if hv else None,
                wf=wf, wf_ok=wf_ok, both_ok=both_ok, overlap=round(ov, 1), ok=ok)


def main():
    print("=" * 100)
    print("S176-RECORD-IMPACT — سهمِ مستقلِ OUTِ High-2: BASE در برابرِ CONF (stop-entry فصل ۴)")
    print(f"config رسمیِ S168: ema{EF}/{ES} SL{SL}/TP{TP} mh{MH} · رکوردِ فعلی=${RECORD_NOW:,.0f}")
    print("=" * 100)
    df = S.lastn(S.load(f'{ASSET}_M15'))

    base = indep_gate(df, confirm=False)
    conf = indep_gate(df, confirm=True)

    print(f"\n[سهمِ مستقلِ OUT — BASE (next-open)]")
    print(f"  {json.dumps({k:base.get(k) for k in ('net','wr','n','pf','h1','h2','overlap','wf_ok','both_ok','ok')}, ensure_ascii=False)}")
    print(f"  wf={base.get('wf')}")
    print(f"\n[سهمِ مستقلِ OUT — CONF (stop-entry)]")
    print(f"  {json.dumps({k:conf.get(k) for k in ('net','wr','n','pf','h1','h2','overlap','wf_ok','both_ok','ok')}, ensure_ascii=False)}")
    print(f"  wf={conf.get('wf')}")

    print("\n" + "=" * 100)
    # تصمیمِ رکورد
    delta = 0.0
    decision = "بدونِ تغییرِ رکورد"
    new_record = RECORD_NOW
    if conf.get('ok') and conf['net'] > S168_REGISTERED:
        delta = conf['net'] - S168_REGISTERED
        new_record = RECORD_NOW + delta
        decision = (f"✅ بهبودِ ثبت‌پذیر: سهمِ مستقلِ OUT از ${S168_REGISTERED:,.0f} به "
                    f"${conf['net']:,.0f} رسید ⇒ Δ=+${delta:,.0f}")
    elif conf.get('ok'):
        decision = (f"CONF گیت را پاس کرد ولی سهمِ مستقل (${conf['net']:,.0f}) از عددِ "
                    f"ثبت‌شدهٔ S168 (${S168_REGISTERED:,.0f}) بیشتر نیست ⇒ رکورد بدون تغییر")
    else:
        decision = "⛔ سهمِ مستقلِ CONF گیتِ کامل را پاس نکرد ⇒ رکورد بدون تغییر"

    print(decision)
    print(f"رکوردِ نهایی: ${new_record:,.0f}")
    print("=" * 100)

    out = dict(config=dict(ef=EF, es=ES, sl=SL, tp=TP, mh=MH, asset=ASSET),
               record_now=RECORD_NOW, s168_registered=S168_REGISTERED,
               base_independent=base, conf_independent=conf,
               delta_record=round(delta, 1), new_record=round(new_record, 1),
               decision=decision)
    with open('results/_s176_record_impact.json', 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("✅ ذخیره شد: results/_s176_record_impact.json")


if __name__ == '__main__':
    main()
