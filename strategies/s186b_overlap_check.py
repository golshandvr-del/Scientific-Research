# -*- coding: utf-8 -*-
"""
S186b — همپوشانیِ *کاملِ* لبهٔ close-strength (S186، فصلِ ۸) با کلِ اجتماعِ پرتفویِ XAUUSD long
=================================================================================================
درسِ S182/S185c: سهمِ مستقلِ هر لبهٔ نو باید نسبت به «Union-All» سنجیده شود، نه فقط یک
زیرمجموعه. اجتماع = پنجره‌های زمان-محورِ طلا ∪ ساختارِ Brooks High-2/Low-2 (بار-به-بار).
هر معاملهٔ close-strength که واردِ اجتماع نشود «سهمِ مستقلِ اصیل» است.

کاندیدِ برندهٔ خام (از _s186_close_strength.json): XAUUSD long، ema10/30، br0.6، cp0.6،
lb20، SL150/TP225، mh48 ⇒ net=+$8,510، WR=47.7٪، n=1387، PF=1.10، WF ۴/۴ مثبت.

خروجی: درصدِ همپوشانی + net/WR/گیتِ walk-forward روی سهمِ مستقلِ نهایی (سیب‌به‌سیبِ S185c).
"""
import os, sys
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import s172_brooks_two_legs as S
import s186_brooks_close_strength as M
from strategies.s168_brooks_high2_low2 import count_high2_low2

# پارامترهای کاندیدِ برنده
PARAMS = dict(side='long', br=0.6, cp=0.6, lb=20, ef=10, es=30, sl=150, tp=225, mh=48)


def build_union_mask(df):
    """ماسکِ بار-به-بارِ اجتماعِ کاملِ پرتفویِ طلا: زمان-محورها ∪ Brooks High-2/Low-2.
    عیناً مطابقِ S185c برای سازگاریِ سیب‌به‌سیب."""
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


def sub_stats_from_trades(df, tr_sub, asset):
    """net/WR سهمِ مستقل با همان موتورِ capital-per-trade (سیب‌به‌سیب S.stats)."""
    if tr_sub is None or len(tr_sub) == 0:
        return dict(net=0.0, n=0, wr=0.0, pf=0.0)
    return S.stats(tr_sub, asset)


def main():
    print("=" * 84)
    print("S186b — همپوشانیِ کاملِ close-strength (فصلِ ۸) با Union-All طلا (زمان ∪ Brooks H2/L2)")
    print("=" * 84)

    df = S.lastn(S.load('XAUUSD_M15'))
    p = PARAMS
    sig = M.close_strength_signals(df, p['side'], p['br'], p['cp'], p['lb'], p['ef'], p['es'])
    z = np.zeros(len(df), bool)
    tr = S.sim(df, sig, z, p['sl'], p['tp'], p['mh'], 'XAUUSD')
    print(f"کاندیدِ برنده: XAUUSD long ema{p['ef']}/{p['es']} br{p['br']} cp{p['cp']} "
          f"lb{p['lb']} SL{p['sl']}/TP{p['tp']}/mh{p['mh']}  (n={len(tr)})")

    union_mask, time_mask, brooks_mask = build_union_mask(df)

    total = len(tr)
    ct = cb = cu = 0
    indep_idx = []
    for _, t in tr.iterrows():
        i = int(t['entry_bar'])
        if i >= len(union_mask):
            i = len(union_mask) - 1
        ct += bool(time_mask[i]); cb += bool(brooks_mask[i]); cu += bool(union_mask[i])
        if not bool(union_mask[i]):
            indep_idx.append(True)
        else:
            indep_idx.append(False)
    indep_idx = np.array(indep_idx, bool)
    tr_ind = tr[indep_idx].reset_index(drop=True)

    print(f"\nکلِ معاملات: {total}")
    print(f"  همپوشانی با زمان-محورها : {ct} ({ct/total*100:.1f}%)")
    print(f"  همپوشانی با Brooks H2/L2 : {cb} ({cb/total*100:.1f}%)")
    print(f"  همپوشانی با Union-All    : {cu} ({cu/total*100:.1f}%)")
    print(f"  سهمِ مستقلِ اصیل         : {len(tr_ind)} ({len(tr_ind)/total*100:.1f}%)")

    s_all = S.stats(tr, 'XAUUSD')
    s_ind = sub_stats_from_trades(df, tr_ind, 'XAUUSD')
    print(f"\n  کل    : net={s_all['net']:+,.2f} WR={s_all['wr']:.2f}% n={s_all['n']} PF={s_all['pf']:.3f}")
    print(f"  مستقل : net={s_ind['net']:+,.2f} WR={s_ind['wr']:.2f}% n={s_ind['n']} PF={s_ind['pf']:.3f}")

    # halves + walk-forward روی سهمِ مستقل (به‌ترتیبِ entry_bar)
    tr_ind = tr_ind.sort_values('entry_bar').reset_index(drop=True)
    # استفاده از capital-per-trade برای pnl هر معامله (مطابق stats)
    from engine import scalp_engine as se
    if len(tr_ind) >= 8:
        _, _, ptbl = se.run_capital_pertrade(tr_ind, 'XAUUSD', initial_capital=S.CAP,
                                             risk_pct=S.RISK, compounding=False)
        nu = ptbl['net_usd'].to_numpy()
        h = len(nu) // 2
        h1 = float(nu[:h].sum()); h2 = float(nu[h:].sum())
        q = len(nu) // 4
        wf = [round(float(nu[i*q:(i+1)*q].sum())) for i in range(4)]
        print(f"  مستقل halves: h1={h1:+.0f} h2={h2:+.0f} | WF={wf}")
        passes = (s_ind['net'] > 0 and s_ind['wr'] >= 40 and h1 > 0 and h2 > 0
                  and all(w > 0 for w in wf) and s_ind['n'] >= 30)
    else:
        passes = False; h1 = h2 = 0; wf = []

    print(f"\n  سهمِ مستقلِ نهایی گیتِ سخت را: "
          f"{'✅ پاس می‌کند ⇒ ثبتِ لبهٔ مستقل' if passes else '❌ رد می‌کند'}")
    print(f"  ➜ سودِ خالصِ قابلِ ثبت (سهمِ مستقلِ محافظه‌کارانه): "
          f"{s_ind['net'] if passes else 0:+,.2f}$")


if __name__ == '__main__':
    main()
