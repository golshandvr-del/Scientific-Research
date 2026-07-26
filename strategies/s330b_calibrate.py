# -*- coding: utf-8 -*-
"""
s330b_calibrate.py — کالیبراسیونِ توزیعِ range/ATR و WRِ خامِ ORB بر حسبِ سشن/ساعت/روز.
هدف: فهمِ ساختارِ داده پیش از grid — اجتناب از اعدادِ رند (اشتباهِ رایجِ #۷).
"""
import os, sys
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import trade_simulator as TS
from engine import indicators as ind


def analyze(tf='XAUUSD_M5', start_h=7, or_bars=12):
    df = TS.load_data(tf)
    dt = df['dt']
    hour = dt.dt.hour.to_numpy()
    dow = dt.dt.dayofweek.to_numpy()
    date = dt.dt.date.to_numpy()
    h = df['high'].to_numpy(); l = df['low'].to_numpy(); c = df['close'].to_numpy(); o = df['open'].to_numpy()
    atr = ind.atr(df, 14).to_numpy()
    n = len(df)

    rows = []
    i = 0
    while i < n:
        if hour[i] != start_h:
            i += 1; continue
        j0 = i; j1 = min(i + or_bars, n)
        if (j1 - j0) < or_bars or not all(date[k] == date[j0] for k in range(j0, j1)):
            i = j1; continue
        or_hi = float(np.max(h[j0:j1])); or_lo = float(np.min(l[j0:j1]))
        or_rng = or_hi - or_lo
        a = atr[j1 - 1]
        # نتیجهٔ ساده: آیا در ۴۸ کندلِ بعد از بازه، اول سقف شکست یا کف؟ و LONG با RR 1:1 برد؟
        w0, w1 = j1, min(j1 + 48, n)
        # روزِ همان تاریخ
        long_hit = None
        entry = None
        for k in range(w0, w1):
            if date[k] != date[j0]:
                break
            if entry is None and c[k] > or_hi:  # شکستِ سقف روی close
                entry = o[k + 1] if k + 1 < n else c[k]
                sl = entry - or_rng; tp = entry + or_rng
                for m in range(k + 1, min(w1 + 20, n)):
                    if date[m] != date[j0] and (m - (k + 1)) > 48:
                        break
                    if l[m] <= sl:
                        long_hit = 0; break
                    if h[m] >= tp:
                        long_hit = 1; break
                break
        rows.append(dict(hour=start_h, dow=int(dow[j0]), rng=or_rng, atr=a,
                         ratio=or_rng / a if a > 0 else np.nan,
                         long_hit=long_hit))
        i = w1

    d = pd.DataFrame(rows)
    d = d.dropna(subset=['ratio'])
    print(f"\n=== {tf} start_h={start_h} or_bars={or_bars} : n_sessions={len(d)} ===")
    print("ratio(range/ATR) quantiles:", np.round(d['ratio'].quantile([.1,.25,.5,.75,.9]).values, 2))
    dd = d.dropna(subset=['long_hit'])
    print(f"LONG breakouts with resolution: {len(dd)}  overall WR={dd['long_hit'].mean()*100:.1f}%")
    # WR بر حسبِ چارکِ ratio (coiled-spring: ratio پایین باید WR بهتری بدهد؟)
    if len(dd) > 40:
        dd = dd.copy()
        dd['q'] = pd.qcut(dd['ratio'], 4, labels=['Q1_tight','Q2','Q3','Q4_wide'])
        print("WR by range/ATR quartile:")
        print(dd.groupby('q', observed=True)['long_hit'].agg(['mean','count']).round(3))
    # WR بر حسبِ روزِ هفته
    print("WR by dow:")
    print(dd.groupby('dow')['long_hit'].agg(['mean','count']).round(3))


if __name__ == '__main__':
    for sh in (7, 8, 13):
        analyze('XAUUSD_M5', start_h=sh, or_bars=12)
