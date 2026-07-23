# -*- coding: utf-8 -*-
"""
S211g — همپوشانیِ *معامله-محور* (bar-level) + آزمونِ افزایشیِ واقعی
================================================================================
S211f نشان داد همپوشانیِ *روز-محور* ۱۰۰٪ است (هر روزی که کاندید معامله می‌کند،
لایه‌ای دیگر هم فعال است) اما همبستگیِ *روزانه* با اکثرِ لایه‌ها پایین است
(Overnight +0.26، Monday +0.15). روز-محور برای طلای M15 مقیاسِ درشتی است
(هر روز چند ساعت). این فایل دو سنجهٔ دقیق‌تر:

  (الف) همپوشانیِ bar-level: چند درصد از *کندل‌های ورودِ* کاندید دقیقاً با
        کندل‌های ورودِ هر لایهٔ دیگر یکی است (±۱ کندل).
  (ب) آزمونِ افزایشی: net کاندید روی *کندل‌های ورودی که هیچ لایهٔ دیگری در
        همان کندل (±۱) وارد نشده* — سهمِ واقعیِ ناهمپوشان بر حسبِ معامله.

اگر سهمِ معامله-محورِ مستقل سودده و گیت-پاس باشد ⇒ لبهٔ افزایشی.
اگر نه ⇒ طبقِ بند ۳ به‌عنوانِ فیلتر روی لایهٔ ضعیف بررسی می‌شود (S211h).
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se
from engine.indicators import sma, ema
se.ASSETS['XAUUSD'].update(spread_pip=3.3, comm=0.0, slip_pip=0.0)

DATA = 'data/XAUUSD_M15.csv'
CAP, RISK = 10000.0, 1.0


def load(path):
    df = pd.read_csv(path)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df['hour'] = df['dt'].dt.hour; df['dow'] = df['dt'].dt.dayofweek
    df['dom'] = df['dt'].dt.day; df['dim'] = df['dt'].dt.days_in_month
    return df.reset_index(drop=True)


def vortex(df, p=14):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    n = len(df); tr = np.zeros(n); vmp = np.zeros(n); vmm = np.zeros(n)
    for i in range(1, n):
        tr[i] = max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1]))
        vmp[i] = abs(h[i]-l[i-1]); vmm[i] = abs(l[i]-h[i-1])
    s = lambda x: pd.Series(x).rolling(p).sum().values
    st = s(tr); st[st == 0] = np.nan
    return s(vmp)/st, s(vmm)/st


def er_kauf(df, p=10):
    c = df['close'].values; n = len(df); er = np.full(n, np.nan)
    for i in range(p, n):
        ch = abs(c[i]-c[i-p]); vol = np.sum(np.abs(np.diff(c[i-p:i+1])))
        er[i] = ch/vol if vol > 0 else 0.0
    return er


def candidate(df):
    c = df['close'].values.astype(float); l = df['low'].values.astype(float)
    sf = sma(df['close'], 13).values; sm = sma(df['close'], 100).values; ss = sma(df['close'], 200).values
    vip, vim = vortex(df); er = er_kauf(df)
    n = len(df); sig = np.zeros(n, bool)
    for i in range(201, n):
        if np.isnan(ss[i]) or np.isnan(vip[i]) or np.isnan(er[i]):
            continue
        if sf[i] > sm[i] > ss[i] and l[i-1] <= sf[i-1] and c[i] > sf[i] and vip[i] > vim[i] and er[i] > 0.2:
            sig[i] = True
    return sig


def m15_overnight(df):   return np.isin(df['hour'].values, [21, 22, 23])
def m15_monday(df):      return (df['dow'].values == 0) & np.isin(df['hour'].values, [18, 19, 20])
def m15_turnofmonth(df): return np.isin(df['dom'].values, [1, 2, 3]) & np.isin(df['hour'].values, range(7, 13))
def m15_midmonth(df):    return np.isin(df['dom'].values, [10, 13, 20]) & np.isin(df['hour'].values, range(1, 13))
def m15_endofmonth(df):
    dom = df['dom'].values; dim = df['dim'].values; m = np.zeros(len(df), bool)
    for rel in [-6, -7, -8]:
        m |= (dom == (dim+rel+1))
    return m & np.isin(df['hour'].values, [19, 20, 21, 22, 23])
def m15_trend(df):
    e20 = ema(df['close'], 20).values; e50 = ema(df['close'], 50).values
    c = df['close'].values; l = df['low'].values; n = len(df); m = np.zeros(n, bool)
    for i in range(51, n):
        if e20[i] > e50[i] and l[i-1] <= e20[i-1] and c[i] > e20[i]:
            m[i] = True
    return m


def _net(tr):
    if tr is None or len(tr) == 0:
        return 0.0
    tr = tr.copy(); tr['sl_pip'] = 150.0
    return se.run_capital(tr, 'XAUUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)[0]['net_profit']


def gate_from_sig(df, sig):
    short = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, sig, short, 150, 300, 'XAUUSD', max_hold=32)
    if tr is None or len(tr) == 0:
        return dict(n=0, net=0, wr=0, pass_gate=False, wf=[])
    net = _net(tr); wr = 100.0*(tr['outcome'] == 'win').mean()
    half = len(df)//2
    h1 = _net(tr[tr['signal_bar'] < half]); h2 = _net(tr[tr['signal_bar'] >= half])
    b = np.linspace(0, len(df), 5).astype(int); wf = []
    for k in range(4):
        wf.append(_net(tr[(tr['signal_bar'] >= b[k]) & (tr['signal_bar'] < b[k+1])]))
    pg = net > 0 and h1 > 0 and h2 > 0 and all(w > 0 for w in wf) and wr >= 40
    return dict(n=len(tr), net=round(net), wr=round(wr, 1), h1=round(h1), h2=round(h2),
                wf=[round(w) for w in wf], pass_gate=bool(pg))


def main():
    print("=" * 92)
    print("S211g — همپوشانیِ معامله-محور (bar-level ±1) + آزمونِ افزایشی")
    print("=" * 92, flush=True)
    df = load(DATA); n = len(df)
    cand = candidate(df)
    cand_bars = np.where(cand)[0]
    print(f"کاندید: {len(cand_bars)} سیگنالِ ورود، net={gate_from_sig(df, cand)['net']}\n")

    layers = {'S139_Overnight': m15_overnight, 'S140_Monday': m15_monday,
              'S141_TurnOfMonth': m15_turnofmonth, 'S142_MidMonth': m15_midmonth,
              'S144_EndOfMonth': m15_endofmonth, 'Trend_PA_proxy': m15_trend}

    # ماسکِ اجتماعِ همهٔ لایه‌ها با پنجرهٔ ±1 کندل
    union_mask = np.zeros(n, bool)
    print("بند ۱ — همپوشانیِ bar-level (±۱ کندل):")
    print(f"  {'لایه':<20}{'سیگنال':>9}{'اشتراک':>9}{'٪ازکاندید':>11}")
    for name, fn in layers.items():
        m = fn(df)
        m_bars = set(np.where(m)[0])
        # اشتراکِ ±1
        inter = sum(1 for bi in cand_bars if (bi in m_bars or bi-1 in m_bars or bi+1 in m_bars))
        pct = 100.0*inter/max(len(cand_bars), 1)
        print(f"  {name:<20}{int(m.sum()):>9}{inter:>9}{pct:>10.1f}%")
        # افزودن به union با ±1
        mm = m.copy()
        mm[1:] |= m[:-1]; mm[:-1] |= m[1:]
        union_mask |= mm

    # بند ۲ — سهمِ معامله-محورِ مستقل: کندل‌های ورودِ کاندید که در union نیستند
    indep_sig = cand & ~union_mask
    overlap_sig = cand & union_mask
    print(f"\nبند ۲ — تفکیکِ سیگنال‌های کاندید:")
    print(f"  کلِ سیگنال          = {int(cand.sum())}")
    print(f"  همپوشان (±۱ با union) = {int(overlap_sig.sum())} ({100.0*overlap_sig.sum()/max(cand.sum(),1):.1f}٪)")
    print(f"  مستقل (ناهمپوشان)    = {int(indep_sig.sum())} ({100.0*indep_sig.sum()/max(cand.sum(),1):.1f}٪)")

    g_indep = gate_from_sig(df, indep_sig)
    g_overlap = gate_from_sig(df, overlap_sig)
    print(f"\n  سهمِ مستقل (معامله-محور): n={g_indep['n']} net=${g_indep['net']:+} "
          f"WR={g_indep['wr']}% WF={g_indep['wf']} pass={g_indep['pass_gate']}")
    print(f"  سهمِ همپوشان:            n={g_overlap['n']} net=${g_overlap['net']:+} "
          f"WR={g_overlap['wr']}% pass={g_overlap['pass_gate']}")

    out = dict(cand_signals=int(cand.sum()),
               indep_signals=int(indep_sig.sum()), overlap_signals=int(overlap_sig.sum()),
               indep_gate=g_indep, overlap_gate=g_overlap)
    os.makedirs('results', exist_ok=True)
    with open('results/_s211g_bar_overlap.json', 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print("\nsaved: results/_s211g_bar_overlap.json")


if __name__ == '__main__':
    main()
