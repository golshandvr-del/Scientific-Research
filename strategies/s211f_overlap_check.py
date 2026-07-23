# -*- coding: utf-8 -*-
"""
S211f — قانونِ همپوشانیِ اجباری: لایهٔ Triple-SMA(13/100/200)+Vortex+ER
        در برابرِ پرتفویِ LONGِ طلای رکورد (M15)
================================================================================
> قانونِ همپوشانیِ اجباری (هر سه بند پیش از ثبت):
>   (۱) با کدام لایه/لایه‌ها و چند درصد همپوشانی دارد؟
>   (۲) حتی ۱٪ ناهمپوشان ارزش دارد (بخشِ مستقل سودده است؟).
>   (۳) امکانِ استفاده از بخشِ همپوشان به‌عنوان فیلتر بررسی شود.

کاندید (S211e): XAUUSD M15 LONG، SMA 13/100/200 stack-pullback + Vortex(VI+>VI-)
    + Kaufman-ER>0.2، SL150/TP300/mh32 ⇒ net=+$13,686, WR=49.6%, WF=[439,605,2636,7139].

پرتفویِ LONGِ طلای رکورد که روی M15 معامله می‌کند (تقریبِ محورهای زمانی + PA):
  S139 Overnight, S140 Monday, S141 TurnOfMonth, S142 MidMonth, S144 EndOfMonth,
  + Squeeze-Breakout (فشردگی) به‌عنوانِ نمایندهٔ لایهٔ PA/روند.
روش (مثلِ S209): همپوشانیِ روز-معاملاتی + همبستگیِ روزانه ⇒ سهمِ مستقل.
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se
from engine.indicators import sma, atr, ema
se.ASSETS['XAUUSD'].update(spread_pip=3.3, comm=0.0, slip_pip=0.0)

DATA = 'data/XAUUSD_M15.csv'
CAP, RISK = 10000.0, 1.0


def load(path):
    df = pd.read_csv(path)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df['hour'] = df['dt'].dt.hour
    df['dow'] = df['dt'].dt.dayofweek
    df['dom'] = df['dt'].dt.day
    df['dim'] = df['dt'].dt.days_in_month
    return df.reset_index(drop=True)


def vortex(df, period=14):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    n = len(df); tr = np.zeros(n); vmp = np.zeros(n); vmm = np.zeros(n)
    for i in range(1, n):
        tr[i] = max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1]))
        vmp[i] = abs(h[i]-l[i-1]); vmm[i] = abs(l[i]-h[i-1])
    s = lambda x: pd.Series(x).rolling(period).sum().values
    str_ = s(tr); str_[str_ == 0] = np.nan
    return s(vmp)/str_, s(vmm)/str_


def kaufman_er(df, period=10):
    c = df['close'].values; n = len(df); er = np.full(n, np.nan)
    for i in range(period, n):
        ch = abs(c[i]-c[i-period]); vol = np.sum(np.abs(np.diff(c[i-period:i+1])))
        er[i] = ch/vol if vol > 0 else 0.0
    return er


def candidate_long(df):
    c = df['close'].values.astype(float); l = df['low'].values.astype(float)
    sf = sma(df['close'], 13).values; sm = sma(df['close'], 100).values; ss = sma(df['close'], 200).values
    vip, vim = vortex(df, 14); er = kaufman_er(df, 10)
    n = len(df); sig = np.zeros(n, dtype=bool)
    for i in range(201, n):
        if np.isnan(ss[i]) or np.isnan(sm[i]) or np.isnan(sf[i]) or np.isnan(vip[i]) or np.isnan(er[i]):
            continue
        if (sf[i] > sm[i] > ss[i] and l[i-1] <= sf[i-1] and c[i] > sf[i]
                and vip[i] > vim[i] and er[i] > 0.2):
            sig[i] = True
    return sig


def run(df, sig, sl, tp, mh):
    short = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, sig, short, sl, tp, 'XAUUSD', max_hold=mh)
    if tr is None or len(tr) == 0:
        return None, None
    tr = tr.copy(); tr['sl_pip'] = float(sl)
    st, _ = se.run_capital(tr, 'XAUUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)
    return st, tr


def daily_net(df, tr):
    if tr is None or len(tr) == 0:
        return pd.Series(dtype=float)
    st, eq, pt = se.run_capital_pertrade(tr, 'XAUUSD', df=df, initial_capital=CAP, risk_pct=RISK, compounding=True)
    if len(pt) == 0:
        return pd.Series(dtype=float)
    pt['day'] = pd.to_datetime(pt['dt']).dt.date
    return pt.groupby('day')['net_usd'].sum()


def trade_days(df, tr):
    if tr is None or len(tr) == 0:
        return set()
    eb = np.clip(tr['entry_bar'].values.astype(int), 0, len(df)-1)
    dt = pd.to_datetime(df['time'].values[eb], unit='s', utc=True)
    return set(pd.to_datetime(dt).date)


# لایه‌های رکورد (تقریبِ زمان-محور روی M15) + squeeze به‌عنوان نمایندهٔ روند
def m15_overnight(df):   return np.isin(df['hour'].values, [21, 22, 23])
def m15_monday(df):      return (df['dow'].values == 0) & np.isin(df['hour'].values, [18, 19, 20])
def m15_turnofmonth(df): return np.isin(df['dom'].values, [1, 2, 3]) & np.isin(df['hour'].values, range(7, 13))
def m15_midmonth(df):    return np.isin(df['dom'].values, [10, 13, 20]) & np.isin(df['hour'].values, range(1, 13))
def m15_endofmonth(df):
    dom = df['dom'].values; dim = df['dim'].values; m = np.zeros(len(df), bool)
    for rel in [-6, -7, -8]:
        m |= (dom == (dim + rel + 1))
    return m & np.isin(df['hour'].values, [19, 20, 21, 22, 23])
def m15_trend_proxy(df):
    # نمایندهٔ لایه‌های روند/PA رکورد: روندِ ساده EMA20>EMA50 + pullback به EMA20
    e20 = ema(df['close'], 20).values; e50 = ema(df['close'], 50).values
    c = df['close'].values; l = df['low'].values; n = len(df); m = np.zeros(n, bool)
    for i in range(51, n):
        if e20[i] > e50[i] and l[i-1] <= e20[i-1] and c[i] > e20[i]:
            m[i] = True
    return m


def main():
    print("=" * 96)
    print("S211f — قانونِ همپوشانیِ اجباری: Triple-SMA(13/100/200)+Vortex+ER در برابرِ LONGِ طلای رکورد")
    print("=" * 96, flush=True)
    df = load(DATA)

    st_c, tr_c = run(df, candidate_long(df), 150, 300, 32)
    print(f"کاندید: net=${st_c['net_profit']:+,.0f}  WR={st_c['win_rate']:.1f}%  n={st_c['n_trades']}")
    dn_c = daily_net(df, tr_c); td_c = trade_days(df, tr_c)
    print(f"روزهای معاملهٔ کاندید: {len(td_c)}\n")

    layers = {
        'S139_Overnight': m15_overnight, 'S140_Monday': m15_monday,
        'S141_TurnOfMonth': m15_turnofmonth, 'S142_MidMonth': m15_midmonth,
        'S144_EndOfMonth': m15_endofmonth, 'Trend_PA_proxy': m15_trend_proxy,
    }
    print("بند ۱ — همپوشانیِ روز-معاملاتی + همبستگیِ روزانه:")
    print(f"  {'لایه':<20}{'n_days':>8}{'اشتراک':>9}{'٪ازکاندید':>11}{'corr':>9}")
    union = set(); results = {}
    for name, fn in layers.items():
        sl_, tp_, mh_ = (150, 300, 32)
        stx, trx = run(df, fn(df), sl_, tp_, mh_)
        tdx = trade_days(df, trx); union |= tdx
        inter = td_c & tdx
        pct = 100.0 * len(inter) / max(len(td_c), 1)
        dnx = daily_net(df, trx)
        idx = dn_c.index.intersection(dnx.index)
        corr = float(np.corrcoef(dn_c.reindex(idx).fillna(0), dnx.reindex(idx).fillna(0))[0,1]) if len(idx) >= 5 else 0.0
        print(f"  {name:<20}{len(tdx):>8}{len(inter):>9}{pct:>10.1f}%{corr:>+9.3f}")
        results[name] = dict(n_days=len(tdx), inter=len(inter), pct=pct, corr=corr)

    inter_u = td_c & union
    pct_u = 100.0 * len(inter_u) / max(len(td_c), 1)
    print(f"\n  ⇒ اجتماعِ همهٔ لایه‌ها: {len(union)} روز؛ اشتراک با کاندید = {len(inter_u)} = {pct_u:.1f}٪")

    indep = td_c - union
    indep_net = dn_c[dn_c.index.isin(indep)].sum()
    overlap_net = dn_c[dn_c.index.isin(inter_u)].sum()
    print(f"\nبند ۲ — سهمِ مستقلِ کاندید (روزهای غیرِهمپوشان): {len(indep)} روز "
          f"({100.0*len(indep)/max(len(td_c),1):.1f}٪)")
    print(f"  net روی روزهای مستقل   = ${indep_net:+,.0f}")
    print(f"  net روی روزهای همپوشان = ${overlap_net:+,.0f}")
    print(f"  کلِ کاندید            = ${dn_c.sum():+,.0f}")

    out = dict(candidate=dict(net=st_c['net_profit'], wr=st_c['win_rate'], n=st_c['n_trades'],
                              trade_days=len(td_c)),
               per_layer=results, union_days=len(union), inter_union=len(inter_u),
               pct_union=pct_u, indep_days=len(indep),
               indep_net=float(indep_net), overlap_net=float(overlap_net))
    os.makedirs('results', exist_ok=True)
    with open('results/_s211f_overlap.json', 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print("\nsaved: results/_s211f_overlap.json")


if __name__ == '__main__':
    main()
