# -*- coding: utf-8 -*-
"""
S219_finalize — قانونِ همپوشانیِ اجباری + سهمِ مستقلِ کاندیدهای برندهٔ S219 (Channels، فصلِ ۱۵)
================================================================================================
> قانونِ شمارهٔ ۱ پروژه: هدف فقط سودِ خالصِ بیشتر (XAUUSD + EURUSD)؛ WR فقط کفِ ۴۰٪.

کشفِ کلیدیِ پروژه: انتخابِ کاندید بر پایهٔ «پایداریِ سهمِ مستقل» (نه net خام). S219 یک لبهٔ
LONGِ روند-صعودیِ طلاست ⇒ انتظارِ همپوشانیِ قابل‌توجه با اجتماعِ لایه‌های LONG طلا
(زمان-محورها ∪ Brooks High-2/Low-2 — عیناً build_union_mask ِ S186b/S214).

برای هر کاندیدِ برندهٔ هر تایم‌فریم:
  ۱) درصدِ همپوشانیِ بار-به-بارِ سیگنال با Union-All.
  ۲) سهمِ مستقل (سیگنال‌هایی که بارشان در union نیست) ⇒ گیتِ سختِ ۴-گانه (net>0، WR≥40،
     هر دو نیمه مثبت، walk-forward ۴/۴).
  ۳) قانونِ همپوشانیِ #۳: بخشِ همپوشان به‌عنوان «فیلترِ تأیید» روی لایه‌های ضعیف ارزش دارد؟
     (اینجا به‌شکلِ گزارشِ کیفیت سنجیده می‌شود؛ اگر سهمِ مستقل قوی بماند، لبه اصیل است.)
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import s172_brooks_two_legs as S
import s219_brooks_channels as X
from s168_brooks_high2_low2 import count_high2_low2
from engine import scalp_engine as se

RESULTS = os.path.join(ROOT, 'results')

# کاندیدهای برندهٔ هر تایم‌فریمِ XAUUSD (از _s219_channels_xau.json، best net با WFmin>0)
CANDS = [
    dict(tf='XAUUSD_M5',  asset='XAUUSD', side='long', ef=10, es=30, k=5, pos=0.6, gap=40, sl=150, tp=300, mh=96),
    dict(tf='XAUUSD_M15', asset='XAUUSD', side='long', ef=20, es=50, k=3, pos=0.4, gap=80, sl=200, tp=400, mh=48),
    dict(tf='XAUUSD_M30', asset='XAUUSD', side='long', ef=10, es=30, k=3, pos=0.4, gap=80, sl=150, tp=300, mh=32),
    dict(tf='XAUUSD_H1',  asset='XAUUSD', side='long', ef=20, es=50, k=3, pos=0.6, gap=40, sl=250, tp=500, mh=24),
    dict(tf='XAUUSD_H4',  asset='XAUUSD', side='long', ef=10, es=30, k=5, pos=0.6, gap=40, sl=200, tp=400, mh=16),
]


def build_union_mask(df):
    """ماسکِ بار-به-بارِ اجتماعِ کاملِ پرتفویِ طلا: زمان-محورها ∪ Brooks High-2/Low-2.
    عیناً مطابقِ S186b/S214 (سازگاریِ سیب‌به‌سیب)."""
    d = df.copy()
    d['hour'] = d['dt'].dt.hour
    d['dow'] = d['dt'].dt.dayofweek
    d['dom'] = d['dt'].dt.day
    d['ym'] = d['dt'].dt.year * 100 + d['dt'].dt.month
    days = d[['dt', 'ym']].copy()
    days['date'] = d['dt'].dt.normalize()
    dd = days.drop_duplicates('date').reset_index(drop=True)
    dd['rank'] = dd.groupby('ym').cumcount() + 1
    dd['cnt'] = dd.groupby('ym')['date'].transform('count')
    dd['from_end'] = dd['rank'] - dd['cnt'] - 1
    mp = dict(zip(dd['date'], dd['from_end']))
    d['from_end'] = d['dt'].dt.normalize().map(mp)
    time_mask = (
        d['hour'].isin([22, 23]) |
        (d['dom'] <= 3) |
        d['dom'].between(13, 17) |
        d['from_end'].between(-8, -6) |
        (d['dow'] == 0)
    ).to_numpy()
    long_evt, short_evt = count_high2_low2(d, 20, 50)
    brooks_mask = np.asarray(long_evt, dtype=bool) | np.asarray(short_evt, dtype=bool)
    return time_mask | brooks_mask


def wf_halves(tr, asset):
    if tr is None or len(tr) < 8:
        return None
    tr = tr.sort_values('entry_bar').reset_index(drop=True)
    _, _, ptbl = se.run_capital_pertrade(tr, asset, initial_capital=S.CAP,
                                         risk_pct=S.RISK, compounding=False)
    nu = ptbl['net_usd'].to_numpy()
    h = len(nu) // 2
    q = len(nu) // 4
    return dict(h1=float(nu[:h].sum()), h2=float(nu[h:].sum()),
                wf=[round(float(nu[i * q:(i + 1) * q].sum())) for i in range(4)])


def main():
    print("=" * 96)
    print("S219_finalize — همپوشانیِ اجباری + سهمِ مستقلِ کاندیدهای Channels (فصلِ ۱۵) با Union-All طلا")
    print("=" * 96, flush=True)

    out = []
    for P in CANDS:
        df = S.lastn(S.load(P['tf']), y=4)
        sig = X.channel_signals(df, P['side'], P['ef'], P['es'], P['k'], P['pos'], P['gap'])
        z = np.zeros(len(df), bool)

        # لبهٔ خام
        r = X.evaluate(df, P['asset'], sig, P['side'], P['sl'], P['tp'], P['mh'])
        raw_net, raw_wr, raw_n = r['net'], r['wr'], r['n']

        # ماسکِ union و همپوشانیِ بار-به-بارِ سیگنال
        union = build_union_mask(df)
        sig_idx = np.where(sig)[0]
        in_union = union[sig_idx]
        ov_pct = 100.0 * in_union.sum() / max(1, len(sig_idx))

        # سهمِ مستقل = سیگنال‌هایی که بارشان در union نیست
        indep = sig & (~union)
        ri = X.evaluate(df, P['asset'], indep, P['side'], P['sl'], P['tp'], P['mh'])

        # walk-forward سهمِ مستقل
        wf = None
        if ri is not None and ri['n'] >= 8:
            tr = S.sim(df, indep, z, P['sl'], P['tp'], P['mh'], P['asset'])
            wf = wf_halves(tr, P['asset'])

        indep_ok = False
        if ri is not None and wf is not None:
            wfmin = min(wf['wf'])
            indep_ok = bool(ri['net'] > 0 and ri['wr'] >= 40 and
                            wf['h1'] > 0 and wf['h2'] > 0 and wfmin > 0 and ri['n'] >= 30)

        rec = dict(tf=P['tf'], raw_net=round(raw_net), raw_wr=raw_wr, raw_n=raw_n,
                   overlap_pct=round(ov_pct, 1),
                   indep_n=(ri['n'] if ri else 0),
                   indep_net=(round(ri['net']) if ri else None),
                   indep_wr=(ri['wr'] if ri else None),
                   indep_wf=(wf['wf'] if wf else None),
                   indep_wfmin=(min(wf['wf']) if wf else None),
                   indep_h1h2=([round(wf['h1']), round(wf['h2'])] if wf else None),
                   indep_ok=indep_ok)
        out.append(rec)
        print(f"\n### {P['tf']}  خام: net=${raw_net:+,.0f} WR{raw_wr} n{raw_n}")
        print(f"    همپوشانیِ سیگنال با Union-All = {ov_pct:.1f}%")
        if ri:
            print(f"    سهمِ مستقل: n={ri['n']} net=${ri['net']:+,.0f} WR{ri['wr']} "
                  f"WF={wf['wf'] if wf else None} ⇒ {'✅ گیت‌پاس' if indep_ok else '❌ رد'}")
        else:
            print("    سهمِ مستقل: n<آستانه ⇒ ❌")

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, '_s219_finalize.json'), 'w') as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print("\n" + "=" * 96)
    passed = [o for o in out if o['indep_ok']]
    print(f"کاندیدهای گیت‌پاسِ سهمِ مستقل: {len(passed)}/{len(out)}")
    for o in passed:
        print(f"  ✅ {o['tf']}: indep net=${o['indep_net']:+,} WR{o['indep_wr']} "
              f"n{o['indep_n']} overlap{o['overlap_pct']}% WFmin={o['indep_wfmin']}")
    print("saved: results/_s219_finalize.json")


if __name__ == '__main__':
    main()
