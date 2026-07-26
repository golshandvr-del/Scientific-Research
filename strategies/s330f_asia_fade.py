# -*- coding: utf-8 -*-
"""
s330f_asia_fade.py — بزرگ‌نماییِ تنها روزنهٔ امید از اسکنِ S330e:
XAUUSD سشنِ آسیا (h=0 UTC) + منطقِ FADE.
هدف: آیا با or_bars/window/rr مختلف می‌توان n را بالا برد بی‌آنکه WR سقوط کند؟
اگر همه‌جا n کوچک بماند یا WR به ۵۰ برگردد ⇒ شواهدِ قویِ DEAD.
تستِ روی چند TF (M5, M15, M30) برای سشنِ آسیا.
"""
import os, sys
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import trade_simulator as TS

SPREAD = {'XAUUSD': 0.33, 'EURUSD': 0.00013}


def scan(tf, asset, start_h, or_bars, window, hold, rr):
    df = TS.load_data(tf)
    dt = df['dt']
    hour = dt.dt.hour.to_numpy(); date = dt.dt.date.to_numpy()
    h = df['high'].to_numpy(); l = df['low'].to_numpy(); c = df['close'].to_numpy(); o = df['open'].to_numpy()
    n = len(df); cost = SPREAD[asset]
    trades = []
    i = 0
    while i < n:
        if hour[i] != start_h:
            i += 1; continue
        j0 = i; j1 = min(i + or_bars, n)
        if (j1 - j0) < or_bars or not all(date[k] == date[j0] for k in range(j0, j1)):
            i = j1; continue
        or_hi = float(np.max(h[j0:j1])); or_lo = float(np.min(l[j0:j1])); or_rng = or_hi - or_lo
        w0, w1 = j1, min(j1 + window, n); done = False
        for k in range(w0, w1):
            if date[k] != date[j0] or done or or_rng <= 0:
                break
            kk = k + 1
            if kk >= n: break
            side = None
            if h[k] > or_hi and c[k] < or_hi: side = 'S'
            elif l[k] < or_lo and c[k] > or_lo: side = 'L'
            if side is None: continue
            entry = o[kk]
            if side == 'L': sl = entry - or_rng; tp = entry + rr * or_rng
            else: sl = entry + or_rng; tp = entry - rr * or_rng
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
                trades.append((res, move - cost, dt.dt.year.to_numpy()[kk]))
            done = True
        i = w1
    if len(trades) < 30:
        return None
    res = np.array([t[0] for t in trades]); nets = np.array([t[1] for t in trades])
    yrs = np.array([t[2] for t in trades])
    # WF: چهار پنجرهٔ مساوی
    q = len(nets) // 4
    wf = [nets[a*q:(a+1)*q].sum() for a in range(4)] if q > 0 else [0,0,0,0]
    wf_ok = all(x > 0 for x in wf)
    return dict(tf=tf, ob=or_bars, win=window, rr=rr, n=len(trades),
                wr=res.mean()*100, net=nets.sum(), wf_ok=wf_ok, wf=[round(x,1) for x in wf])


if __name__ == '__main__':
    print("XAUUSD Asia-session (h=0) FADE — n vs WR sweep")
    print(f"{'TF':12s} {'ob':>2s} {'win':>3s} {'rr':>4s} {'n':>4s} {'WR%':>5s} {'net':>9s} {'WF_ok':>6s} {'wf'}")
    for tf in ('XAUUSD_M5', 'XAUUSD_M15', 'XAUUSD_M30'):
        for ob in (4, 6, 8, 12, 18, 24):
            for win in (36, 48, 72):
                for rr in (1.0, 1.3, 1.5):
                    r = scan(tf, 'XAUUSD', 0, ob, win, 48, rr)
                    if r and r['n'] >= 40 and r['wr'] >= 55:
                        print(f"{r['tf']:12s} {r['ob']:2d} {r['win']:3d} {r['rr']:4.1f} {r['n']:4d} "
                              f"{r['wr']:5.1f} {r['net']:9.2f} {str(r['wf_ok']):>6s} {r['wf']}")
