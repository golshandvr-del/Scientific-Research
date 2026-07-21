"""
explore_eurusd_mm_wf_stability.py — کدام ترکیبِ خروجِ EURUSD Mid-Month در walk-forward پایدار است؟
================================================================================
> قانونِ #۱: تنها معیار «سودِ خالص = XAUUSD + EURUSD» است، نه Win-Rate.

S143 نشان داد لبهٔ «روزهای {3,9,20} × ساعاتِ لندن/آسیا» روی EURUSD both-halves
مثبت و با S73 متعامد است، اما برندهٔ net (SL15/TP80/mh96) در پنجرهٔ WF دوم منفی
بود ([5377, -811, 2043, 1488]). پنجرهٔ دوم = دورهٔ رنجِ ۲۰۲۱–۲۰۲۲.

این اسکریپت WF را برای **همهٔ** ترکیب‌های both محاسبه می‌کند تا ترکیبی بیابیم که
هم both-halves مثبت باشد هم هر ۴ پنجرهٔ WF مثبت — انتخابِ علمی به‌جای صرفاً بیشترین net.
================================================================================
"""
import os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from engine import scalp_engine as se

DATA = os.path.join(ROOT, 'data', 'EURUSD_M15.csv')
CAP, RISK = 10000.0, 1.0
MM_DAYS = [3, 9, 20]
MM_HOURS = [1, 2, 3, 4, 5, 11, 12, 13, 14, 15]


def load():
    df = pd.read_csv(DATA)
    dt = pd.to_datetime(df['time'], unit='s', utc=True)
    df['hour'] = dt.dt.hour; df['dom'] = dt.dt.day
    return df.reset_index(drop=True)


def sig(df):
    n = len(df)
    return (np.isin(df['dom'].values, MM_DAYS) & np.isin(df['hour'].values, MM_HOURS),
            np.zeros(n, bool))


def run(df, sl, tp, mh):
    ls, ss = sig(df)
    tr = se.simulate_trades(df, ls, ss, sl, tp, 'EURUSD', max_hold=mh)
    if len(tr) == 0:
        return 0.0, None
    tr = tr.copy(); tr['sl_pip'] = float(sl)
    st, _ = se.run_capital(tr, 'EURUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)
    return float(st['net_profit']), tr


def wf(df, sl, tp, mh, nwin=4):
    n = len(df); e = np.linspace(0, n, nwin+1, dtype=int); out = []
    for k in range(nwin):
        sub = df.iloc[e[k]:e[k+1]].reset_index(drop=True)
        net, _ = run(sub, sl, tp, mh)
        out.append(round(net, 0))
    return out


def main():
    df = load(); n = len(df); half = n // 2
    print(f"داده: {n} کندلِ EURUSD | روزها {MM_DAYS} ساعات {MM_HOURS}\n")
    print(f"{'SL':>4}{'TP':>5}{'mh':>4}{'net$':>10}  {'both':>5}  {'WF (4 پنجره)':>32}  همه‌WF")
    winners = []
    for sl in [15, 20, 30]:
        for tp in [30, 50, 80, 120]:
            for mh in [48, 96, 144]:
                net, tr = run(df, sl, tp, mh)
                if tr is None:
                    continue
                trh1 = tr[tr['exit_bar'] < half]; trh2 = tr[tr['exit_bar'] >= half]
                s1 = se.run_capital(trh1, 'EURUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)[0] if len(trh1) else {'net_profit': 0}
                s2 = se.run_capital(trh2, 'EURUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)[0] if len(trh2) else {'net_profit': 0}
                both = (s1['net_profit'] > 0 and s2['net_profit'] > 0)
                w = wf(df, sl, tp, mh)
                allwf = all(x > 0 for x in w)
                mark = '✅' if (both and allwf) else ('both' if both else '')
                if both:
                    print(f"{sl:>4}{tp:>5}{mh:>4}{net:>10,.0f}  {'✓':>5}  {str(w):>32}  {'✅' if allwf else '❌'}")
                if both and allwf:
                    winners.append((net, sl, tp, mh, w))

    print(f"\n{'='*74}")
    if winners:
        winners.sort(reverse=True)
        print(f"✅ {len(winners)} ترکیبِ both+هرWF مثبت یافت شد.")
        cons = float(np.mean([w[0] for w in winners]))
        print(f"برندهٔ net: SL{winners[0][1]}/TP{winners[0][2]}/mh{winners[0][3]} = ${winners[0][0]:,.0f}")
        print(f"سودِ محافظه‌کارانه (میانگینِ همهٔ برنده‌ها) = ${cons:,.0f}")
    else:
        print("❌ هیچ ترکیبی هم both هم هرWF مثبت نبود.")
        print("   ⇒ پنجرهٔ رنجِ ۲۰۲۱–۲۰۲۲ لبه را در WF منفی می‌کند.")
        print("   طبقِ PARADIGM (بی‌خیالِ رنج)، گزینهٔ جایگزین: گیتِ WF نرم‌تر (۳ از ۴).")


if __name__ == '__main__':
    main()
