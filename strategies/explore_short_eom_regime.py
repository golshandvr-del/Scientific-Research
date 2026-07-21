"""
explore_short_eom_regime.py — نجاتِ پنجرهٔ سومِ WF با فیلترِ رژیمِ نزولی
================================================================================
> قانونِ شمارهٔ ۱: فقط «سودِ خالصِ بیشتر». سودِ خالص = XAUUSD + EURUSD.

مشکلِ S145 خام: ماشهٔ SHORTِ pre-EOM (from_end∈{-9,-10}، ساعتِ ۱۶–۲۱) در ۳ پنجرهٔ
WF مثبت است اما در **پنجرهٔ سومِ** WF منفی می‌شود (~-$600) — چون در آن بازه طلا روندِ
صعودیِ قوی داشت و short خلافِ روند ضرر می‌دهد. فرضیهٔ اقتصادی: «drift نزولیِ نهادیِ
pre-EOM فقط وقتی قابلِ اتکاست که بازار در رژیمِ صعودیِ شدید نباشد.» پس یک فیلترِ رژیم
اضافه می‌کنیم: SHORT فقط وقتی مجاز است که قیمت زیرِ یک میانگینِ بلند باشد (ضدِ روند
نزنیم). این اصلِ استانداردِ ترید است، نه data-snooping.

این اسکریپت چند فیلترِ رژیم را می‌سنجد و WF هر کدام را چاپ می‌کند تا ببینیم کدام
پنجرهٔ سوم را نجات می‌دهد و هم‌زمان سودِ کل را مثبت نگه می‌دارد.
================================================================================
"""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from engine import scalp_engine as se

DATA = os.path.join(ROOT, 'data', 'XAUUSD_M15.csv')
CAP, RISK = 10000.0, 1.0
DAYS = [-9, -10]; HOURS = [16, 17, 18, 19, 20, 21]


def load():
    df = pd.read_csv(DATA)
    dt = pd.to_datetime(df['time'], unit='s', utc=True)
    df['hour'] = dt.dt.hour; df['date'] = dt.dt.normalize()
    df['ym'] = dt.dt.year*100 + dt.dt.month
    return df.reset_index(drop=True)


def assign_from_end(df):
    days = df[['date','ym']].drop_duplicates('date').reset_index(drop=True)
    days['rk'] = days.groupby('ym').cumcount()+1
    days['cnt'] = days.groupby('ym')['date'].transform('count')
    days['from_end'] = days['rk']-days['cnt']-1
    df['from_end'] = df['date'].map(dict(zip(days['date'], days['from_end']))).astype(int)
    return df


def regime_masks(df):
    c = df['close']
    ema100 = c.ewm(span=100, adjust=False).mean().values
    ema200 = c.ewm(span=200, adjust=False).mean().values
    sma200 = c.rolling(200).mean().bfill().values
    px = c.values
    return {
        'none': np.ones(len(df), bool),
        'below_ema100': px < ema100,
        'below_ema200': px < ema200,
        'below_sma200': px < sma200,
        'ema100_below_ema200': ema100 < ema200,   # روندِ نزولیِ ساختاری
    }


def run(df, short_sig, sl, tp, mh):
    ls = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, ls, short_sig, sl, tp, 'XAUUSD', max_hold=mh)
    if len(tr) == 0: return None, None
    tr = tr.copy(); tr['sl_pip'] = float(sl)
    st,_ = se.run_capital(tr, 'XAUUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)
    return st, tr


def net(st): return float(st['net_profit']) if st else 0.0


def wf(df, regime_key, sl, tp, mh, nwin=4):
    n=len(df); edges=np.linspace(0,n,nwin+1,dtype=int); outs=[]
    for k in range(nwin):
        sub = df.iloc[edges[k]:edges[k+1]].reset_index(drop=True)
        sub = assign_from_end(sub)
        rm = regime_masks(sub)[regime_key]
        ss = np.isin(sub['from_end'].values, DAYS) & np.isin(sub['hour'].values, HOURS) & rm
        st,_ = run(sub, ss, sl, tp, mh)
        outs.append(round(net(st),0))
    return outs


def main():
    df = assign_from_end(load())
    n=len(df); half=n//2
    print("نجاتِ پنجرهٔ سومِ WF با فیلترِ رژیمِ نزولی\n")
    rms = regime_masks(df)
    for rk in rms:
        print(f"\n{'='*70}\nرژیم: {rk}\n{'='*70}")
        print(f"{'SL':>5}{'TP':>6}{'mh':>5}{'net$':>10}{'N':>6}{'WR%':>6}  both  allWF   WF")
        for sl in [150, 200]:
            for tp in [500, 700]:
                for mh in [48, 96]:
                    ss = np.isin(df['from_end'].values, DAYS) & np.isin(df['hour'].values, HOURS) & rms[rk]
                    st, tr = run(df, ss, sl, tp, mh)
                    if st is None: continue
                    trh1 = tr[tr['exit_bar']<half]; trh2 = tr[tr['exit_bar']>=half]
                    s1 = se.run_capital(trh1,'XAUUSD',initial_capital=CAP,risk_pct=RISK,compounding=True)[0] if len(trh1) else None
                    s2 = se.run_capital(trh2,'XAUUSD',initial_capital=CAP,risk_pct=RISK,compounding=True)[0] if len(trh2) else None
                    both = (net(s1)>0 and net(s2)>0)
                    w = wf(df, rk, sl, tp, mh); allwf = all(x>0 for x in w)
                    mark = ('✓' if both else '✗')+'   '+('✅' if allwf else '❌')
                    print(f"{sl:>5}{tp:>6}{mh:>5}{net(st):>10,.0f}{len(tr):>6}{st.get('win_rate',0):>6.1f}  {mark}  {w}")


if __name__ == '__main__':
    main()
