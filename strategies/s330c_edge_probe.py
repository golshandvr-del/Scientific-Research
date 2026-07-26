# -*- coding: utf-8 -*-
"""
s330c_edge_probe.py — کاوشِ عمیقِ لبه: آیا هیچ زیرمجموعه‌ای از ORB لبهٔ واقعی دارد؟
بررسیِ WR بر حسبِ:
  • قدرتِ شکست (breakout_depth = (close - or_high)/ATR در کندلِ شکست)
  • فیلترِ HTF-trend (close > EMA(بلند))
  • ساعتِ دقیقِ ورود
  • فاصله تا EMA (momentum)
با RRِ متقارن ۱:۱ (بدونِ تلهٔ RR).
"""
import os, sys
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import trade_simulator as TS
from engine import indicators as ind


def probe(tf='XAUUSD_M5', start_h=7, or_bars=12, window=48, hold=48):
    df = TS.load_data(tf)
    dt = df['dt']
    hour = dt.dt.hour.to_numpy(); dow = dt.dt.dayofweek.to_numpy(); date = dt.dt.date.to_numpy()
    h = df['high'].to_numpy(); l = df['low'].to_numpy(); c = df['close'].to_numpy(); o = df['open'].to_numpy()
    atr = ind.atr(df, 14).to_numpy()
    ema200 = ind.ema(df['close'], 200).to_numpy()
    ema800 = ind.ema(df['close'], 800).to_numpy()   # HTF proxy روی M5 (~ کندلِ روزانه)
    n = len(df)

    rows = []
    i = 0
    while i < n:
        if hour[i] != start_h:
            i += 1; continue
        j0 = i; j1 = min(i + or_bars, n)
        if (j1 - j0) < or_bars or not all(date[k] == date[j0] for k in range(j0, j1)):
            i = j1; continue
        or_hi = float(np.max(h[j0:j1])); or_lo = float(np.min(l[j0:j1])); or_rng = or_hi - or_lo
        w0, w1 = j1, min(j1 + window, n)
        for k in range(w0, w1):
            if date[k] != date[j0]:
                break
            if c[k] > or_hi and or_rng > 0:  # شکستِ سقف
                kk = k + 1
                if kk >= n:
                    break
                entry = o[kk]
                sl = entry - or_rng; tp = entry + or_rng
                depth = (c[k] - or_hi) / atr[k] if atr[k] > 0 else 0.0
                up200 = c[k] > ema200[k]
                up800 = c[k] > ema800[k]
                res = None
                for m in range(kk, min(kk + hold, n)):
                    if l[m] <= sl:
                        res = 0; break
                    if h[m] >= tp:
                        res = 1; break
                rows.append(dict(hour=hour[kk], dow=int(dow[kk]), depth=depth,
                                 up200=up200, up800=up800, res=res))
                break
        i = w1

    d = pd.DataFrame(rows).dropna(subset=['res'])
    print(f"\n=== {tf} h={start_h} or_bars={or_bars} : n={len(d)} WR={d['res'].mean()*100:.1f}% ===")
    # فیلترِ EMA200
    for col in ('up200', 'up800'):
        for v in (True, False):
            s = d[d[col] == v]
            if len(s) >= 30:
                print(f"  {col}={v}: n={len(s):4d} WR={s['res'].mean()*100:.1f}%")
    # قدرتِ شکست
    if len(d) > 40:
        d = d.copy()
        d['dq'] = pd.qcut(d['depth'].clip(lower=0), 4, labels=['D1','D2','D3','D4_strong'], duplicates='drop')
        print("  WR by breakout depth:")
        print(d.groupby('dq', observed=True)['res'].agg(['mean','count']).round(3).to_string().replace('\n','\n    '))
    # ترکیب: up800 & depth بالا
    strong = d[(d['up800'] == True)]
    if len(strong) > 40:
        strong = strong.copy()
        med = strong['depth'].median()
        hi = strong[strong['depth'] >= med]
        print(f"  up800 & depth>=median: n={len(hi)} WR={hi['res'].mean()*100:.1f}%")


if __name__ == '__main__':
    for sh in (7, 8, 13):
        probe('XAUUSD_M5', start_h=sh, or_bars=12)
