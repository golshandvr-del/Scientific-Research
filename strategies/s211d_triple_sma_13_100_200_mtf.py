# -*- coding: utf-8 -*-
"""
S211d — تثبیتِ کاندیدِ برنده 13/100/200 + آزمونِ مولتی‌تایم‌فریم (قانونِ #۱)
================================================================================
یافتهٔ S211c: با «دستکاریِ مقادیرِ SMA» (پیشنهادِ صریحِ User Note) ست
13/100/200 روی XAUUSD M15 گیتِ سختِ ضدِ overfit را پاس کرد:
    n=1749, net=+$10,559, WR=47.7%, h1=+1726, h2=+7286, WF=[1673,54,1557,4985] ✅
درسِ منفیِ مهم: فیلترهای رژیم (ADX/slope/RSI/ATR) net را *کاهش* دادند ⇒ مشکلِ
نیمهٔ اول «رنج» نبود؛ صرفاً fast=8 پُر-نویز بود. fast=13 + mid=100 خودش فیلترِ
کافیِ کیفیت است.

این فایل:
  ۱) کاندیدِ 13/100/200 را روی *همهٔ تایم‌فریم‌های XAUUSD* (شروع از M5) با گیتِ
     سخت می‌آزماید — طبقِ قانونِ مولتی‌تایم‌فریم هر TF مجزا گزارش می‌شود.
  ۲) همان را روی EURUSD (همه TF) می‌آزماید (تعریفِ سودِ خالص = XAU+EUR).
  ۳) TP/SL مخصوصِ هر TF (قانونِ بهبود: هر TF می‌تواند تنظیمِ خود را بخواهد).
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.indicators import sma
from engine.scalp_engine import simulate_trades, run_capital, ASSETS


def load(path):
    df = pd.read_csv(path)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df.reset_index(drop=True)


def _net(t, asset):
    if t is None or len(t) == 0:
        return 0.0
    stats, _ = run_capital(t, asset)
    return stats['net_profit']


def hard_gate(trades, df, asset):
    if trades is None or len(trades) == 0:
        return dict(n=0, net=0, wr=0, pass_gate=False)
    net = _net(trades, asset)
    wr = 100.0 * (trades['outcome'] == 'win').mean()
    half = len(df) // 2
    net_h1 = _net(trades[trades['signal_bar'] < half], asset)
    net_h2 = _net(trades[trades['signal_bar'] >= half], asset)
    wf = []
    bounds = np.linspace(0, len(df), 5).astype(int)
    for k in range(4):
        tw = trades[(trades['signal_bar'] >= bounds[k]) & (trades['signal_bar'] < bounds[k + 1])]
        wf.append(_net(tw, asset))
    pg = (net > 0 and net_h1 > 0 and net_h2 > 0 and all(w > 0 for w in wf) and wr >= 40.0)
    return dict(n=len(trades), net=round(net), wr=round(wr, 1),
                net_h1=round(net_h1), net_h2=round(net_h2),
                wf=[round(w) for w in wf], pass_gate=bool(pg))


def build_long(df, pf, pm, ps):
    c = df['close'].values.astype(float)
    l = df['low'].values.astype(float)
    sf = sma(df['close'], pf).values
    sm = sma(df['close'], pm).values
    ss = sma(df['close'], ps).values
    n = len(df)
    sig = np.zeros(n, dtype=bool)
    for i in range(ps + 1, n):
        if np.isnan(ss[i]) or np.isnan(sm[i]) or np.isnan(sf[i]):
            continue
        if sf[i] > sm[i] > ss[i] and l[i - 1] <= sf[i - 1] and c[i] > sf[i]:
            sig[i] = True
    return sig


def build_short(df, pf, pm, ps):
    c = df['close'].values.astype(float)
    h = df['high'].values.astype(float)
    sf = sma(df['close'], pf).values
    sm = sma(df['close'], pm).values
    ss = sma(df['close'], ps).values
    n = len(df)
    sig = np.zeros(n, dtype=bool)
    for i in range(ps + 1, n):
        if np.isnan(ss[i]) or np.isnan(sm[i]) or np.isnan(sf[i]):
            continue
        if sf[i] < sm[i] < ss[i] and h[i - 1] >= sf[i - 1] and c[i] < sf[i]:
            sig[i] = True
    return sig


# TP/SL مخصوصِ هر TF (ATR در TFهای بزرگ‌تر بزرگ‌تر است)
TPSL = {
    'M5':  dict(sl=100, tp=200, mh=48),
    'M15': dict(sl=150, tp=300, mh=32),
    'M30': dict(sl=200, tp=400, mh=24),
    'H1':  dict(sl=250, tp=500, mh=16),
    'H4':  dict(sl=400, tp=800, mh=12),
    'M1':  dict(sl=60,  tp=120, mh=60),
}

PF, PM, PS = 13, 100, 200


def run_asset(asset, tfs):
    print(f"\n{'='*100}\n{asset} — ست SMA {PF}/{PM}/{PS} (stack-pullback) — همه تایم‌فریم‌ها\n{'='*100}")
    print(f"{'TF':>4} {'dir':>6} {'n':>5} {'net':>9} {'wr':>5} {'h1':>7} {'h2':>7} {'walk-forward':>26} gate")
    print("-" * 100)
    rows = []
    for tf in tfs:
        path = f'data/{asset}_{tf}.csv'
        if not os.path.exists(path):
            continue
        ASSETS[asset]['file'] = path
        df = load(path)
        cfg = TPSL[tf]
        zeros = np.zeros(len(df), dtype=bool)
        ls = build_long(df, PF, PM, PS)
        ss = build_short(df, PF, PM, PS)
        for label, a, b in [('LONG', ls, zeros), ('SHORT', zeros, ss)]:
            tr = simulate_trades(df, a, b, cfg['sl'], cfg['tp'], asset, max_hold=cfg['mh'])
            g = hard_gate(tr, df, asset); g['tf'] = tf; g['dir'] = label; g['asset'] = asset
            rows.append(g)
            mark = "✅PASS" if g['pass_gate'] else ""
            print(f"{tf:>4} {label:>6} {g['n']:>5} {g['net']:>9} {g['wr']:>5} "
                  f"{g.get('net_h1',0):>7} {g.get('net_h2',0):>7} {str(g.get('wf',[])):>26} {mark}")
        print("-" * 100)
    return rows


def main():
    all_rows = []
    all_rows += run_asset('XAUUSD', ['M5', 'M15', 'M30', 'H1', 'H4'])
    all_rows += run_asset('EURUSD', ['M1', 'M5', 'M15', 'M30'])

    passed = [r for r in all_rows if r['pass_gate']]
    print(f"\n{'#'*100}")
    print(f"لایه‌هایی که گیتِ سخت را پاس کردند ({len(passed)}):")
    total = 0
    for r in passed:
        print(f"  {r['asset']} {r['tf']} {r['dir']}: net=+${r['net']} WR={r['wr']}% WF={r['wf']}")
        total += r['net']
    print(f"جمعِ خامِ net لایه‌های پاس‌شده = +${total}")
    print("(توجه: پیش از افزودن به رکورد باید همپوشانی با پرتفوی بررسی شود — گام بعد)")

    os.makedirs('results', exist_ok=True)
    with open('results/_s211d_triple_sma_mtf.json', 'w') as f:
        json.dump(all_rows, f, indent=2, default=str)
    print("\nsaved: results/_s211d_triple_sma_mtf.json")


if __name__ == '__main__':
    main()
