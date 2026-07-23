# -*- coding: utf-8 -*-
"""
S212b — همپوشانیِ کاملِ کاندیدِ برندهٔ S212 (inverse-view pullback، فصلِ ۹) با اجتماعِ پرتفویِ طلا
=================================================================================================
درسِ S182/S185c/S186b: سهمِ مستقلِ هر لبهٔ نو باید نسبت به «Union-All» سنجیده شود.
کاندیدِ برنده (از _s212_inverse_view.json): **XAUUSD_H1، pullback-long + inverse-view filter،
lb20، thr0.5، SL200/TP300، mh24** ⇒ filt net=+$15,925، WR 49.2٪، n=817، WF ۴/۴.

نکته: پرتفویِ رکورد هیچ لایهٔ H1 فعالی ندارد (لایه‌ها روی M5/M15/M30 هستند)؛ پس انتظار
می‌رود همپوشانیِ *معامله-محور* روی H1 کم باشد. اجتماع = time-drift ∪ Brooks High-2/Low-2
(هم‌سو با S186b؛ محافظه‌کارانه — اگر همپوشانیِ کمی هم بود، سهمِ مستقل هنوز بزرگ می‌ماند).

خروجی: درصدِ همپوشانی + net/WR/گیتِ walk-forward روی سهمِ مستقلِ نهایی (سیب‌به‌سیب S186b).
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import s172_brooks_two_legs as S
import s212_brooks_inverse_view as M
from s168_brooks_high2_low2 import count_high2_low2
from engine import scalp_engine as se

# کاندیدِ برندهٔ S212
P = dict(tf='XAUUSD_H1', asset='XAUUSD', lb=20, thr=0.5, sl=200, tp=300, mh=24, ef=20, es=50)


def build_union_mask(df):
    """اجتماعِ کاملِ پرتفویِ طلا: زمان-محورها ∪ Brooks High-2/Low-2 (هم‌سو با S186b)."""
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
    return time_mask | brooks_mask, time_mask, brooks_mask


def main():
    print("=" * 88)
    print("S212b — همپوشانیِ کاندیدِ inverse-view pullback (فصلِ ۹) با Union-All طلا (زمان ∪ Brooks H2/L2)")
    print("=" * 88)

    df = S.lastn(S.load(P['tf']), y=4)
    asym = M.inverse_view_asym(df, P['lb'])
    asym_s = pd.Series(asym).shift(1).to_numpy()
    base_sig = M.pullback_long_signals(df, P['ef'], P['es'], P['lb'])
    keep = (asym_s <= P['thr']) | np.isnan(asym_s)
    sig = base_sig & keep

    z = np.zeros(len(df), bool)
    tr = S.sim(df, sig, z, P['sl'], P['tp'], P['mh'], P['asset'])
    print(f"کاندید: {P['tf']} pullback-long+inverse-filter lb{P['lb']} thr{P['thr']} "
          f"SL{P['sl']}/TP{P['tp']}/mh{P['mh']}  (n={len(tr)})")

    union_mask, time_mask, brooks_mask = build_union_mask(df)
    total = len(tr)
    ct = cb = cu = 0
    indep = []
    for _, t in tr.iterrows():
        i = int(t['entry_bar'])
        i = min(i, len(union_mask) - 1)
        ct += bool(time_mask[i]); cb += bool(brooks_mask[i]); cu += bool(union_mask[i])
        indep.append(not bool(union_mask[i]))
    indep = np.array(indep, bool)
    tr_ind = tr[indep].reset_index(drop=True)

    print(f"\nکلِ معاملات: {total}")
    print(f"  همپوشانی با زمان-محورها : {ct} ({ct/total*100:.1f}%)")
    print(f"  همپوشانی با Brooks H2/L2 : {cb} ({cb/total*100:.1f}%)")
    print(f"  همپوشانی با Union-All    : {cu} ({cu/total*100:.1f}%)")
    print(f"  سهمِ مستقلِ اصیل         : {len(tr_ind)} ({len(tr_ind)/total*100:.1f}%)")

    s_all = S.stats(tr, P['asset'])
    s_ind = S.stats(tr_ind, P['asset']) if len(tr_ind) else dict(net=0, wr=0, n=0, pf=0)
    print(f"\n  کل    : net={s_all['net']:+,.2f} WR={s_all['wr']:.2f}% n={s_all['n']} PF={s_all['pf']:.3f}")
    print(f"  مستقل : net={s_ind['net']:+,.2f} WR={s_ind['wr']:.2f}% n={s_ind['n']} PF={s_ind['pf']:.3f}")

    passes = False; h1 = h2 = 0; wf = []
    if len(tr_ind) >= 8:
        tr_ind = tr_ind.sort_values('entry_bar').reset_index(drop=True)
        _, _, ptbl = se.run_capital_pertrade(tr_ind, P['asset'], initial_capital=S.CAP,
                                             risk_pct=S.RISK, compounding=False)
        nu = ptbl['net_usd'].to_numpy()
        h = len(nu) // 2
        h1 = float(nu[:h].sum()); h2 = float(nu[h:].sum())
        q = len(nu) // 4
        wf = [round(float(nu[i*q:(i+1)*q].sum())) for i in range(4)]
        print(f"  مستقل halves: h1={h1:+.0f} h2={h2:+.0f} | WF={wf}")
        passes = (s_ind['net'] > 0 and s_ind['wr'] >= 40 and h1 > 0 and h2 > 0
                  and all(w > 0 for w in wf) and s_ind['n'] >= 30)

    print(f"\n  سهمِ مستقلِ نهایی گیتِ سخت را: "
          f"{'✅ پاس می‌کند ⇒ ثبتِ لبهٔ مستقل' if passes else '❌ رد می‌کند'}")
    print(f"  ➜ سودِ خالصِ قابلِ ثبت (سهمِ مستقلِ محافظه‌کارانه): {s_ind['net'] if passes else 0:+,.2f}$")

    out = dict(candidate=P, total=total, ov_time=ct, ov_brooks=cb, ov_union=cu,
               indep_n=len(tr_ind), net_all=s_all['net'], wr_all=s_all['wr'],
               net_indep=s_ind['net'], wr_indep=s_ind['wr'], h1=h1, h2=h2, wf=wf, passes=bool(passes))
    with open(os.path.join(ROOT, 'results', '_s212b_overlap.json'), 'w') as f:
        json.dump(out, f, indent=1)
    print("saved: results/_s212b_overlap.json")


if __name__ == '__main__':
    main()
