"""
explore_gold_eom_wf_stability.py — جاروبِ پایداریِ Walk-Forward برای End-of-Month drift
================================================================================
> قانونِ شمارهٔ ۱: تنها معیار «سودِ خالصِ بیشتر = XAUUSD + EURUSD» است.

هدف: S144 با خوشهٔ {-6,-7,-3} × ساعاتِ ۱۶–۲۱ گیتِ WF را رد کرد (دو پنجرهٔ میانی
منفی). اما corr با همهٔ لایه‌ها متعامد بود و both-halves ✓. این اسکریپت فضای
(روزهای خوشه × پنجرهٔ ساعتی × خروج) را می‌گردد تا ببیند آیا *هیچ* پیکربندیِ
معقولِ از-پیش-تعیین‌شده‌ای هست که **هر ۴ پنجرهٔ WF** را مثبت کند بدون over-fit.

فقط اکتشاف. انتخابِ نهایی باید هم both-halves و هم all-WF باشد.
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from engine import scalp_engine as se

DATA = os.path.join(ROOT, 'data', 'XAUUSD_M15.csv')
RESULTS = os.path.join(ROOT, 'results')
CAP, RISK = 10000.0, 1.0


def load():
    df = pd.read_csv(DATA)
    dt = pd.to_datetime(df['time'], unit='s', utc=True)
    df['hour'] = dt.dt.hour; df['dom'] = dt.dt.day
    df['date'] = dt.dt.normalize(); df['ym'] = dt.dt.year*100 + dt.dt.month
    days = df[['date','ym']].drop_duplicates('date').reset_index(drop=True)
    days['r'] = days.groupby('ym').cumcount()+1
    days['c'] = days.groupby('ym')['date'].transform('count')
    days['from_end'] = days['r'] - days['c'] - 1
    m = dict(zip(days['date'], days['from_end']))
    df['from_end'] = df['date'].map(m).astype(int)
    return df.reset_index(drop=True)


def run(df, days, hours, sl, tp, mh):
    ls = np.isin(df['from_end'].values, days) & np.isin(df['hour'].values, hours)
    ss = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, ls, ss, sl, tp, 'XAUUSD', max_hold=mh)
    if len(tr) == 0:
        return None, None
    tr = tr.copy(); tr['sl_pip'] = float(sl)
    st, _ = se.run_capital(tr, 'XAUUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)
    return st, tr


def net(st):
    return float(st['net_profit']) if st else 0.0


def wf(df, days, hours, sl, tp, mh, nwin=4):
    n = len(df); e = np.linspace(0, n, nwin+1, dtype=int); outs = []
    for k in range(nwin):
        sub = df.iloc[e[k]:e[k+1]].reset_index(drop=True)
        st, _ = run(sub, days, hours, sl, tp, mh)
        outs.append(round(net(st), 0))
    return outs


def main():
    df = load(); n = len(df); half = n//2
    print(f"داده: {n} کندل | جاروبِ پایداریِ WF برای End-of-Month drift\n")

    # کاندیدهای از-پیش-تعیین‌شدهٔ روزها (بر اساس اکتشاف، نه بهینه‌سازیِ کور)
    day_sets = {
        '{-6,-7}': [-6, -7],
        '{-6,-7,-3}': [-6, -7, -3],
        '{-5,-6,-7,-8}': [-5, -6, -7, -8],
        '{-6,-7,-8}': [-6, -7, -8],
    }
    hour_sets = {
        '16-21': [16,17,18,19,20,21],
        '16-23': [16,17,18,19,20,21,22,23],
        '19-23': [19,20,21,22,23],
        '16-19': [16,17,18,19],
    }
    exits = [(150,500,48),(150,700,96),(200,700,96),(150,300,96),(200,300,96),
             (100,300,96),(120,400,96),(150,400,48),(180,600,96)]

    best_rows = []
    print(f"{'days':>14}{'hours':>8}{'SL/TP/mh':>14}{'net$':>10}{'both':>6}{'allWF':>7}  WF")
    for dname, days in day_sets.items():
        for hname, hours in hour_sets.items():
            for (sl,tp,mh) in exits:
                st, tr = run(df, days, hours, sl, tp, mh)
                if st is None or st['n_trades'] < 100:
                    continue
                trh1 = tr[tr['exit_bar']<half]; trh2 = tr[tr['exit_bar']>=half]
                s1 = se.run_capital(trh1,'XAUUSD',initial_capital=CAP,risk_pct=RISK,compounding=True)[0] if len(trh1) else None
                s2 = se.run_capital(trh2,'XAUUSD',initial_capital=CAP,risk_pct=RISK,compounding=True)[0] if len(trh2) else None
                both = net(s1)>0 and net(s2)>0
                w = wf(df, days, hours, sl, tp, mh)
                allwf = all(x>0 for x in w)
                if both and allwf:
                    print(f"{dname:>14}{hname:>8}{f'{sl}/{tp}/{mh}':>14}{net(st):>10,.0f}{'✓':>6}{'✅':>7}  {w}")
                    best_rows.append({'days':days,'hours':hours,'sl':sl,'tp':tp,'mh':mh,
                                      'net':round(net(st),0),'wf':w,
                                      'wr':round(st['win_rate'],1),'pf':round(st['profit_factor'],2),
                                      'n':int(st['n_trades'])})

    print(f"\n✅ تعداد پیکربندیِ both✓ و allWF✅: {len(best_rows)}")
    if best_rows:
        # کف محافظه‌کارانه = میانگینِ همهٔ پیکربندی‌های واجدِ شرایط
        avg = float(np.mean([r['net'] for r in best_rows]))
        print(f"📉 میانگینِ net همهٔ واجدینِ شرایط (کف محافظه‌کارانه): ${avg:,.0f}")
        best = max(best_rows, key=lambda r: r['net'])
        print(f"🏅 بهترین: days={best['days']} hours={best['hours']} "
              f"SL{best['sl']}/TP{best['tp']}/mh{best['mh']} ⇒ ${best['net']:,.0f}  WF={best['wf']}")

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, '_s144_wf_stability.json'),'w') as f:
        json.dump({'qualified': best_rows,
                   'avg_net': (float(np.mean([r['net'] for r in best_rows])) if best_rows else 0.0),
                   'n_qualified': len(best_rows)}, f, indent=2, ensure_ascii=False)
    print(f"\nذخیره شد: results/_s144_wf_stability.json")


if __name__ == '__main__':
    main()
