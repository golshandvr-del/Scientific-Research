# -*- coding: utf-8 -*-
"""
S213_finalize — همپوشانی + سهمِ مستقلِ کاندیدِ برندهٔ S213 (Second-Entry، فصلِ ۱۰)
=================================================================================
> قانونِ شمارهٔ ۱ پروژه: هدف فقط سودِ خالصِ بیشتر (XAUUSD + EURUSD)؛ WR فقط کفِ ۴۰٪.

کاندیدِ برنده (از گریدِ S213):
  **EURUSD_M15 SHORT، ema10/30، spk3، gap10، good_fill=True، SL150/TP225، mh48**
  ⇒ net=+$423، WR 57.1٪، n=63، PF 2.0، WF [131.8,110.1,120.9,60.6] (۴/۴)، هر دو نیمه مثبت.

چرا این نادر و ارزشمند است:
  - **اولین لبهٔ price-action SHORT روی EURUSD** (پرتفویِ EUR فقط S164 SHORTِ زمان-محور دارد).
  - Brooks معمولاً روی EURUSD شکست می‌خورد (S168/S169/…)؛ این استثناست.

قانونِ همپوشانیِ اجباری: سهمِ مستقلِ کاندید نسبت به **اجتماعِ کاملِ لایه‌های EURUSD**
(S164 SHORT ∪ S143 mid-month LONG ∪ S73 session-open LONG) سنجیده می‌شود. چون کاندید
SHORT و price-action محور است و لایه‌های موجود عمدتاً زمان-محور/LONG‌اند، انتظارِ
همپوشانیِ بسیار پایین می‌رود. سپس گیتِ سختِ ۴-گانه روی سهمِ مستقل.
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import s172_brooks_two_legs as S
import s213_brooks_second_entry as X
from engine import indicators as ind

RESULTS = os.path.join(ROOT, 'results')
P = dict(tf='EURUSD_M15', asset='EURUSD', ef=10, es=30, spk=3, gap=10,
         sl=150, tp=225, mh=48)


def build_eurusd_union_mask(df):
    """اجتماعِ کاملِ لایه‌های EURUSD (bar-level mask):
      S164 SHORT: from_end==-3 & hour==13
      S143 mid-month LONG: dom in {3,9,20} & hour in {11..15}
      S73 session-open LONG: hour==0
    """
    d = df.copy()
    d['hour'] = d['dt'].dt.hour
    d['dom'] = d['dt'].dt.day
    d['date'] = d['dt'].dt.normalize()
    d['ym'] = d['dt'].dt.year * 100 + d['dt'].dt.month
    dd = d[['date', 'ym']].drop_duplicates('date').reset_index(drop=True)
    dd['rank'] = dd.groupby('ym').cumcount() + 1
    dd['cnt'] = dd.groupby('ym')['date'].transform('count')
    dd['from_end'] = dd['rank'] - dd['cnt'] - 1
    mp = dict(zip(dd['date'], dd['from_end']))
    d['from_end'] = d['date'].map(mp)
    s164 = (d['from_end'] == -3) & (d['hour'] == 13)
    s143 = d['dom'].isin([3, 9, 20]) & d['hour'].between(11, 15)
    s73 = (d['hour'] == 0)
    union = (s164 | s143 | s73).to_numpy()
    return union, s164.to_numpy(), s143.to_numpy(), s73.to_numpy()


def trade_bar_mask(df, sig, side, sl, tp, mh, asset):
    """ماسکِ بار-به-بارِ کندل‌هایی که در طولِ عمرِ معاملاتِ این لایه «باز» بوده‌اند."""
    tr = S.sim(df, sig if side == 'long' else np.zeros(len(df), bool),
               np.zeros(len(df), bool) if side == 'long' else sig, sl, tp, mh, asset)
    mask = np.zeros(len(df), bool)
    if tr is None or len(tr) == 0:
        return mask, tr
    for _, row in tr.iterrows():
        a = int(row['entry_idx']) if 'entry_idx' in row else None
        b = int(row['exit_idx']) if 'exit_idx' in row else None
        if a is None or b is None:
            continue
        mask[a:b + 1] = True
    return mask, tr


def main():
    print("=" * 92)
    print("S213_finalize — همپوشانیِ کاندیدِ Second-Entry (EURUSD_M15 SHORT) با اجتماعِ لایه‌های EUR")
    print("=" * 92, flush=True)

    df = S.lastn(S.load(P['tf']), y=4)
    sig = X.second_entry_signals(df, 'short', P['ef'], P['es'], P['spk'], P['gap'], good_fill=True)

    # لبهٔ خام
    r = X.evaluate(df, P['asset'], sig, 'short', P['sl'], P['tp'], P['mh'])
    print(f"\n### لبهٔ خام (کاندید): net=${r['net']:+,.0f}  WR={r['wr']}  n={r['n']}  PF={r['pf']}")
    print(f"    WF={[w[0] for w in r['wf']]}  h1={r['h1']}  h2={r['h2']}  ACC={r['accepted']}")

    # ماسکِ معاملاتیِ کاندید + اجتماعِ لایه‌های EUR
    cand_mask, cand_tr = trade_bar_mask(df, sig, 'short', P['sl'], P['tp'], P['mh'], P['asset'])
    union, s164, s143, s73 = build_eurusd_union_mask(df)

    # همپوشانیِ بار-به-بار: چند درصد از بارهای معاملاتیِ کاندید در اجتماع هستند
    if cand_mask.sum() > 0:
        ov_all = (cand_mask & union).sum() / cand_mask.sum() * 100
        ov_164 = (cand_mask & s164).sum() / cand_mask.sum() * 100
        ov_143 = (cand_mask & s143).sum() / cand_mask.sum() * 100
        ov_73 = (cand_mask & s73).sum() / cand_mask.sum() * 100
    else:
        ov_all = ov_164 = ov_143 = ov_73 = 0.0
    print(f"\n### همپوشانیِ بار-به-بار با اجتماعِ لایه‌های EUR:")
    print(f"    Union-All={ov_all:.1f}٪  (S164={ov_164:.1f}٪  S143={ov_143:.1f}٪  S73={ov_73:.1f}٪)")

    # سهمِ مستقل: فقط سیگنال‌هایی که در لحظهٔ ورود در اجتماع نیستند
    sig_idx = np.where(sig)[0]
    indep = sig.copy()
    dropped = 0
    for i in sig_idx:
        if union[i]:
            indep[i] = False
            dropped += 1
    print(f"    سیگنال‌های کاندید: {int(sig.sum())} ⇒ حذفِ همپوشان: {dropped} ⇒ مستقل: {int(indep.sum())}")

    ri = X.evaluate(df, P['asset'], indep, 'short', P['sl'], P['tp'], P['mh'])
    print(f"\n### سهمِ مستقل (مبنای ثبت):")
    if ri is None:
        print("    n<30 ⇒ سهمِ مستقل کافی نیست.")
    else:
        print(f"    net=${ri['net']:+,.0f}  WR={ri['wr']}  n={ri['n']}  PF={ri['pf']}")
        print(f"    WF={[w[0] for w in ri['wf']]}  h1={ri['h1']}  h2={ri['h2']}")
        print(f"    گیتِ سختِ ۴-گانه: ACC={ri['accepted']}  (wf_ok={ri['wf_ok']} both={ri['both_ok']})")

    out = dict(param=P, raw=r, overlap=dict(all=ov_all, s164=ov_164, s143=ov_143, s73=ov_73),
               indep=ri, n_sig=int(sig.sum()), n_indep=int(indep.sum()), dropped=dropped)
    with open(os.path.join(RESULTS, '_s213_finalize.json'), 'w') as f:
        json.dump(out, f, indent=1, default=float)
    print("\nsaved: results/_s213_finalize.json")


if __name__ == '__main__':
    main()
