# -*- coding: utf-8 -*-
"""
s330e_mtf_scan.py — اسکنِ سریعِ برداری روی همهٔ TFها (XAU+EUR) برای یافتنِ رژیمی که
ORB لبه دارد. برای هر (TF, start_h, or_bars, logic, rr) نرخِ برد و لبهٔ خام (پس از
هزینه) را می‌سنجد. logic ∈ {cont(ادامه), fade}. هدف: کشفِ محلِ زندهٔ لبه پیش از grid.

نکته: این اسکن فقط جهت‌یابی است؛ تأییدِ نهایی با شبیه‌سازِ رویداد-محور + RQS+ انجام می‌شود.
"""
import os, sys
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import trade_simulator as TS
from engine import indicators as ind

SPREAD = {'XAUUSD': 0.33, 'EURUSD': 0.00013}  # price units (EUR: 1.0pip+0.3slip)


def scan(tf, asset, start_h, or_bars, window, hold, logic, rr):
    df = TS.load_data(tf)
    dt = df['dt']
    hour = dt.dt.hour.to_numpy(); date = dt.dt.date.to_numpy()
    h = df['high'].to_numpy(); l = df['low'].to_numpy(); c = df['close'].to_numpy(); o = df['open'].to_numpy()
    n = len(df)
    cost = SPREAD[asset]
    wins = 0; tot = 0; net = 0.0
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
            if date[k] != date[j0] or done or or_rng <= 0:
                break
            kk = k + 1
            if kk >= n:
                break
            side = None
            if logic == 'cont':
                if c[k] > or_hi:
                    side = 'L'
                elif c[k] < or_lo:
                    side = 'S'
            else:  # fade
                if h[k] > or_hi and c[k] < or_hi:
                    side = 'S'
                elif l[k] < or_lo and c[k] > or_lo:
                    side = 'L'
            if side is None:
                continue
            entry = o[kk]
            if side == 'L':
                sl = entry - or_rng; tp = entry + rr * or_rng
            else:
                sl = entry + or_rng; tp = entry - rr * or_rng
            res = None; exitp = None
            for m in range(kk, min(kk + hold, n)):
                if side == 'L':
                    if l[m] <= sl: res, exitp = 0, sl; break
                    if h[m] >= tp: res, exitp = 1, tp; break
                else:
                    if h[m] >= sl: res, exitp = 0, sl; break
                    if l[m] <= tp: res, exitp = 1, tp; break
            if res is not None:
                move = (exitp - entry) if side == 'L' else (entry - exitp)
                net += move - cost
                wins += res; tot += 1
            done = True
        i = w1
    if tot < 30:
        return None
    wr = wins / tot * 100
    return dict(tf=tf, h=start_h, ob=or_bars, logic=logic, rr=rr, n=tot, wr=wr, net=net)


if __name__ == '__main__':
    configs = [
        ('XAUUSD_M5', 'XAUUSD', 12), ('XAUUSD_M15', 'XAUUSD', 4),
        ('XAUUSD_M30', 'XAUUSD', 2), ('XAUUSD_H1', 'XAUUSD', 1),
        ('XAUUSD_H4', 'XAUUSD', 1),
        ('EURUSD_M15', 'EURUSD', 4), ('EURUSD_M30', 'EURUSD', 2),
    ]
    results = []
    for tf, asset, ob in configs:
        for sh in (0, 7, 8, 13):
            for logic in ('cont', 'fade'):
                for rr in (1.0, 1.5):
                    r = scan(tf, asset, sh, ob, window=48, hold=48, logic=logic, rr=rr)
                    if r:
                        results.append(r)
    # مرتب‌سازی بر پایهٔ WR (برای cont) و net
    results.sort(key=lambda x: (x['wr'], x['net']), reverse=True)
    print(f"{'TF':12s} {'h':>2s} {'ob':>2s} {'logic':5s} {'rr':>4s} {'n':>4s} {'WR%':>5s} {'net':>10s}")
    for r in results[:30]:
        print(f"{r['tf']:12s} {r['h']:2d} {r['ob']:2d} {r['logic']:5s} {r['rr']:4.1f} {r['n']:4d} {r['wr']:5.1f} {r['net']:10.2f}")
