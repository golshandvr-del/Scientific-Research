# -*- coding: utf-8 -*-
"""
s330d_fade_probe.py — فرضیهٔ معکوس: ORB False-Breakout FADE.
کشفِ S330c: شکستِ ادامه‌دار روی طلای M5 ≈ پرتابِ سکه (WR~۵۰٪). تزِ معکوس:
شکستِ بازهٔ افتتاحیه اغلب یک «liquidity grab / false break» است ⇒ باید آن را fade کرد.

منطق: قیمت سقفِ بازه را می‌شکند (high>or_hi) ولی کندل *داخلِ* بازه می‌بندد
(close<or_hi) ⇒ شکستِ ناموفق ⇒ SHORT (fade). قرینه برای کف ⇒ LONG.
RR متقارن ۱:۱ بر حسبِ range؛ بدونِ تلهٔ RR.
"""
import os, sys
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import trade_simulator as TS
from engine import indicators as ind


def probe(tf='XAUUSD_M5', start_h=7, or_bars=12, window=48, hold=48, rr=1.0):
    df = TS.load_data(tf)
    dt = df['dt']
    hour = dt.dt.hour.to_numpy(); dow = dt.dt.dayofweek.to_numpy(); date = dt.dt.date.to_numpy()
    h = df['high'].to_numpy(); l = df['low'].to_numpy(); c = df['close'].to_numpy(); o = df['open'].to_numpy()
    atr = ind.atr(df, 14).to_numpy()
    ema200 = ind.ema(df['close'], 200).to_numpy()
    n = len(df)

    long_rows = []  # fade کفِ شکسته ⇒ LONG
    short_rows = [] # fade سقفِ شکسته ⇒ SHORT
    i = 0
    while i < n:
        if hour[i] != start_h:
            i += 1; continue
        j0 = i; j1 = min(i + or_bars, n)
        if (j1 - j0) < or_bars or not all(date[k] == date[j0] for k in range(j0, j1)):
            i = j1; continue
        or_hi = float(np.max(h[j0:j1])); or_lo = float(np.min(l[j0:j1])); or_rng = or_hi - or_lo
        w0, w1 = j1, min(j1 + window, n)
        done = False
        for k in range(w0, w1):
            if date[k] != date[j0] or done:
                break
            if or_rng <= 0:
                continue
            kk = k + 1
            if kk >= n:
                break
            # false-break سقف: high شکست ولی close برگشت داخل بازه ⇒ SHORT
            if h[k] > or_hi and c[k] < or_hi:
                entry = o[kk]; sl = entry + or_rng; tp = entry - rr * or_rng
                res = None
                for m in range(kk, min(kk + hold, n)):
                    if h[m] >= sl:
                        res = 0; break
                    if l[m] <= tp:
                        res = 1; break
                short_rows.append(dict(dow=int(dow[kk]), res=res, up200=c[k] > ema200[k]))
                done = True
            # false-break کف: low شکست ولی close برگشت داخل بازه ⇒ LONG
            elif l[k] < or_lo and c[k] > or_lo:
                entry = o[kk]; sl = entry - or_rng; tp = entry + rr * or_rng
                res = None
                for m in range(kk, min(kk + hold, n)):
                    if l[m] <= sl:
                        res = 0; break
                    if h[m] >= tp:
                        res = 1; break
                long_rows.append(dict(dow=int(dow[kk]), res=res, up200=c[k] > ema200[k]))
                done = True
        i = w1

    for tag, rows in (('SHORT-fade-top', short_rows), ('LONG-fade-bottom', long_rows)):
        d = pd.DataFrame(rows).dropna(subset=['res'])
        if len(d) == 0:
            print(f"  {tag}: no trades"); continue
        print(f"  {tag}: n={len(d):4d} WR={d['res'].mean()*100:.1f}%")


if __name__ == '__main__':
    for sh in (7, 8, 13):
        print(f"\n=== XAUUSD_M5 start_h={sh} RR=1:1 ===")
        probe('XAUUSD_M5', start_h=sh, or_bars=12, rr=1.0)
