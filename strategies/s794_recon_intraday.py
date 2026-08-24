#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S794 RECON — Market Intraday Momentum (Gao, Han, Li & Zhou 2018) — XAUUSD H1
فرضیه: بازدهِ نخستین کندلِ H1 روزِ معاملاتی، جهتِ ادامهٔ روز را پیش‌بینی می‌کند
(سرمایه‌گذاریِ تدریجیِ نهادی + hedging گاما). دو واریانت:
  A: ورود در openِ کندلِ دوم روز، نگه‌داشت mh کندل (ادامهٔ روز)
  B: ورود دیرهنگام (کندل ساعت h_e)، نگه‌داشت کوتاه (پایان روز)
آستانه: |r_first| >= θ·ADR21 (بی‌بعد، درس S770). اکتشاف فقط نیمهٔ اول (Path C).
usage: python3 s794_recon_intraday.py [TF]
"""
import sys, numpy as np, pandas as pd
sys.path.insert(0, '/home/user/webapp')
from tools import s434_fast_data as fd
from engine import scalp_engine as se

TF = sys.argv[1] if len(sys.argv) > 1 else 'H1'
PIP = 0.10

d = fd.load_fast('XAUUSD', TF)
df = fd.as_dataframe(d)
o = df['open'].values; h = df['high'].values; l = df['low'].values
c = df['close'].values
ts = df['time'].values.astype(np.int64)
n = len(c); split = n // 2
print(f"src={d['src']} | TF={TF} | bars={n} | discovery=first {split}", flush=True)

# --- day segmentation via time gap (S560 lesson: not hour==0) ---
tf_sec = fd.TF_MINUTES[TF] * 60
gap = np.r_[10**9, np.diff(ts)]
day_start = gap > max(1800, int(1.5 * tf_sec))
day_id = np.cumsum(day_start) - 1
# first bar index of each day
first_idx = np.where(day_start)[0]
n_days = len(first_idx)
print(f'days detected: {n_days}', flush=True)

# ADR21: mean of daily (high-low) over prior 21 days, causal
day_hi = np.full(n_days, np.nan); day_lo = np.full(n_days, np.nan)
for k in range(n_days):
    a = first_idx[k]; b = first_idx[k+1] if k+1 < n_days else n
    day_hi[k] = h[a:b].max(); day_lo[k] = l[a:b].min()
dr = day_hi - day_lo
adr = pd.Series(dr).rolling(21).mean().shift(1).values   # causal: prior days only

# ATR89 (EMA alpha=2/90) shifted 1, for geometry
pc = np.r_[c[0], c[:-1]]
tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
atr = np.empty(n); a0 = tr[0]; kk = 2.0/90.0
for i in range(n):
    a0 = a0 + kk*(tr[i]-a0); atr[i] = a0
atr = np.r_[np.nan, atr[:-1]]

# first-bar return of each day, mapped to signal bar = first bar itself
r_first = np.full(n, np.nan)      # value at the FIRST bar of day (closed at its close)
adr_bar = np.full(n, np.nan)
for k in range(n_days):
    i = first_idx[k]
    r_first[i] = c[i] - o[i]
    adr_bar[i] = adr[k]

hour = ((ts // 3600) % 24).astype(int)
valid = ~np.isnan(atr)

def run(theta, mh, a_geom, variant, h_e=None):
    ls = np.zeros(n, bool); ss = np.zeros(n, bool)
    for k in range(n_days):
        i = first_idx[k]
        if np.isnan(r_first[i]) or np.isnan(adr_bar[i]) or adr_bar[i] <= 0: continue
        if abs(r_first[i]) < theta * adr_bar[i]: continue
        b_end = first_idx[k+1] if k+1 < n_days else n
        if variant == 'A':
            sig = i                    # signal at first bar close -> entry open of bar i+1
        else:                          # B: signal at the bar with hour == h_e-1 within same day
            cand = np.where((hour[i:b_end] == h_e))[0]
            if len(cand) == 0: continue
            sig = i + cand[0] - 1      # entry at open of the h_e bar
            if sig <= i: continue
        if sig + 1 >= n: continue
        if r_first[i] > 0: ls[sig] = True
        elif r_first[i] < 0: ss[sig] = True
    ls &= valid; ss &= valid
    ls[split:] = False; ss[split:] = False
    sl = np.where(valid, a_geom * atr / PIP, 0.0)
    trd = se.simulate_trades(df, ls, ss, sl, sl, 'XAUUSD',
                             max_hold=mh, allow_overlap=False)
    if trd is None or len(trd) == 0: return dict(n=0, wr=np.nan, exp=np.nan, net=0)
    nn = len(trd); net = trd['pnl_pip'].sum()
    return dict(n=nn, wr=100*(trd['pnl_pip']>0).mean(), exp=net/nn, net=net)

print('--- Variant A: enter 2nd bar of day, ride the day ---')
print(f'{"θ":>6} {"mh":>3} {"a":>6} | {"n":>5} {"WR%":>6} {"exp":>7} {"net":>9}')
for theta in (0.0, 0.146, 0.236, 0.382):
    for mh in (13, 21):
        for a_geom in (1.618, 2.618):
            m = run(theta, mh, a_geom, 'A')
            print(f'{theta:>6} {mh:>3} {a_geom:>6} | {m["n"]:>5} {m["wr"]:>6.2f} '
                  f'{m["exp"]:>7.2f} {m["net"]:>9.1f}', flush=True)

print('--- Variant B: late-day entry (hour h_e), short hold ---')
print(f'{"θ":>6} {"h_e":>4} {"mh":>3} | {"n":>5} {"WR%":>6} {"exp":>7} {"net":>9}')
for theta in (0.146, 0.236, 0.382):
    for h_e in (19, 21):
        for mh in (2, 3):
            m = run(theta, mh, 2.618, 'B', h_e=h_e)
            print(f'{theta:>6} {h_e:>4} {mh:>3} | {m["n"]:>5} {m["wr"]:>6.2f} '
                  f'{m["exp"]:>7.2f} {m["net"]:>9.1f}', flush=True)
