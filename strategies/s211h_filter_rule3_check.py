# -*- coding: utf-8 -*-
"""
S211h — بند ۳ قانونِ همپوشانی: آیا Vortex+ER (بخشِ همپوشان) به‌عنوانِ فیلتر
        یک لایهٔ ضعیفِ موجود را بهبود می‌دهد؟
================================================================================
S211g: سهمِ مستقلِ معامله-محورِ کاندید گیت-پاس است (net +$6,338). طبقِ بند ۳
باید *پیش از رفتن به مرحلهٔ بعد* بررسی شود آیا بخشِ همپوشان (فیلترِ Vortex+ER
که کیفیتِ روند را می‌سنجد) می‌تواند لایهٔ ضعیفِ موجود را هم تقویت کند.

ضعیف‌ترین‌های ممیزیِ ۴ساله (README): S144 EndOfMonth (+$1,097)، Squeeze (+$1,210).
اینجا فیلترِ «Vortex(VI+>VI-) AND Kaufman-ER>0.2» را روی نسخهٔ M15 این لایه‌ها
اعمال می‌کنیم و Δ net را می‌سنجیم (فیلترِ جهت/کیفیتِ روند باید ورودهای بد را حذف کند).
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


def m15_overnight(df):   return np.isin(df['hour'].values, [21, 22, 23])
def m15_midmonth(df):    return np.isin(df['dom'].values, [10, 13, 20]) & np.isin(df['hour'].values, range(1, 13))
def m15_endofmonth(df):
    dom = df['dom'].values; dim = df['dim'].values; m = np.zeros(len(df), bool)
    for rel in [-6, -7, -8]:
        m |= (dom == (dim+rel+1))
    return m & np.isin(df['hour'].values, [19, 20, 21, 22, 23])


def _net(tr, sl=150):
    if tr is None or len(tr) == 0:
        return 0.0
    tr = tr.copy(); tr['sl_pip'] = float(sl)
    return se.run_capital(tr, 'XAUUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)[0]['net_profit']


def gate(df, sig, sl=150, tp=300, mh=32):
    short = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, sig, short, sl, tp, 'XAUUSD', max_hold=mh)
    if tr is None or len(tr) == 0:
        return dict(n=0, net=0, wr=0, pass_gate=False, wf=[])
    net = _net(tr, sl); wr = 100.0*(tr['outcome'] == 'win').mean()
    half = len(df)//2
    h1 = _net(tr[tr['signal_bar'] < half], sl); h2 = _net(tr[tr['signal_bar'] >= half], sl)
    b = np.linspace(0, len(df), 5).astype(int); wf = []
    for k in range(4):
        wf.append(_net(tr[(tr['signal_bar'] >= b[k]) & (tr['signal_bar'] < b[k+1])], sl))
    pg = net > 0 and h1 > 0 and h2 > 0 and all(w > 0 for w in wf) and wr >= 40
    return dict(n=len(tr), net=round(net), wr=round(wr, 1), wf=[round(w) for w in wf], pass_gate=bool(pg))


def main():
    print("=" * 88)
    print("S211h — بند ۳: Vortex+ER به‌عنوانِ فیلترِ کیفیتِ روند روی لایه‌های ضعیفِ موجود")
    print("=" * 88, flush=True)
    df = load(DATA)
    vip, vim = vortex(df); er = er_kauf(df)
    filt = (vip > vim) & (er > 0.2)
    filt = np.nan_to_num(filt.astype(float), nan=0.0).astype(bool)

    layers = {'S144_EndOfMonth': m15_endofmonth,
              'S142_MidMonth': m15_midmonth,
              'S139_Overnight': m15_overnight}
    out = {}
    for name, fn in layers.items():
        base = fn(df)
        g0 = gate(df, base)
        g1 = gate(df, base & filt)
        delta = g1['net'] - g0['net']
        print(f"\n{name}:")
        print(f"  پایه:        n={g0['n']} net={g0['net']} wr={g0['wr']} wf={g0['wf']} pass={g0['pass_gate']}")
        print(f"  +Vortex+ER:  n={g1['n']} net={g1['net']} wr={g1['wr']} wf={g1['wf']} pass={g1['pass_gate']}")
        print(f"  Δnet = {delta:+}   {'✅ بهبود' if delta > 0 and g1['pass_gate'] else '✗ بهبود نداد/گیت رد'}")
        out[name] = dict(base=g0, filtered=g1, delta=delta)

    os.makedirs('results', exist_ok=True)
    with open('results/_s211h_rule3_filter.json', 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print("\nsaved: results/_s211h_rule3_filter.json")
    print("\nنتیجه: اگر هیچ Δ مثبتِ گیت-پاسی نبود ⇒ بخشِ همپوشان فیلترِ مفیدی نیست؛")
    print("        تصمیمِ نهایی = افزودنِ سهمِ مستقلِ کاندید (S211g: +$6,338).")


if __name__ == '__main__':
    main()
