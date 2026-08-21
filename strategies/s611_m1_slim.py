# -*- coding: utf-8 -*-
"""S611 — ردیف M1 جدول MTF با رژیم حافظه (درس S580: سندباکس ~1GB).
تفاوت با مسیر اصلی: day از time//86400 ساخته می‌شود (هم‌ارز UTC date؛
بدون آرایهٔ آبجکتِ سنگین dt.date). سایر منطق بیت‌به‌بیت همان s153 است."""
import os, sys, json, time, gc
import numpy as np
import pandas as pd

ROOT = '/home/user/webapp'
sys.path.insert(0, ROOT)
from engine import scalp_engine as SE

CFG = dict(z_entry=1.5, ema_trend=200, atr_mult=0.5, cooldown=48,
           sl=80.0, tp=700.0, be=6.0, trail=6.0, mh=48)
OUT = os.path.join(ROOT, 'results', '_s611_vwap', 'mtf')

t0 = time.time()
src = os.path.join(ROOT, 'data', 'mt5_full', 'XAUUSD_M1.csv')
# بارگذاری قطعه‌قطعه (ضد OOM — read_csv یکجا روی 5.4M ردیف اسپایک >800MB دارد)
chunks = {k: [] for k in ['time', 'open', 'high', 'low', 'close', 'volume']}
for ch in pd.read_csv(src, chunksize=400_000,
                      dtype={'time': np.int64, 'open': np.float64, 'high': np.float64,
                             'low': np.float64, 'close': np.float64, 'volume': np.float64}):
    for k in chunks:
        chunks[k].append(ch[k].values)
tsec = np.concatenate(chunks['time']); o = np.concatenate(chunks['open'])
h = np.concatenate(chunks['high']); l = np.concatenate(chunks['low'])
c = np.concatenate(chunks['close']); v = np.concatenate(chunks['volume'])
del chunks; gc.collect()
N = len(tsec)
print('bars', N, f'{time.time()-t0:.0f}s', flush=True)

# --- daily_vwap_z (هم‌ارز s153؛ day = time//86400) ---
tp_ = (h + l + c) / 3.0
day = tsec // 86400
z = np.zeros(N)
cum_pv = 0.0; cum_v = 0.0
devs = []
cur = -1
dev_window = 60
for i in range(N):
    if day[i] != cur:
        cur = day[i]; cum_pv = 0.0; cum_v = 0.0; devs = []
    cum_pv += tp_[i] * v[i]; cum_v += v[i]
    vw = cum_pv / cum_v if cum_v > 0 else tp_[i]
    d_ = c[i] - vw
    devs.append(d_)
    if len(devs) >= 10:
        sd = np.std(devs[-dev_window:]) if len(devs) >= dev_window else np.std(devs)
        z[i] = d_ / sd if sd > 0 else 0.0
del tp_, day; gc.collect()
print('vwap-z done', f'{time.time()-t0:.0f}s', flush=True)

# --- gen_signal (بیت‌به‌بیت s153) ---
et = pd.Series(c).ewm(span=CFG['ema_trend'], adjust=False).mean().values
pc = np.roll(c, 1); pc[0] = c[0]
tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
a = pd.Series(tr).rolling(14).mean().bfill().values
del pc, tr; gc.collect()
rng_ = h - l
ls = np.zeros(N, dtype=bool)
last = -10**9
for i in range(2, N - 1):
    if i - last < CFG['cooldown']:
        continue
    if (z[i] > CFG['z_entry'] and c[i] > et[i] and c[i] > o[i]
            and rng_[i] >= CFG['atr_mult'] * a[i]):
        ls[i] = True
        last = i
del z, et, a, rng_; gc.collect()
nsig = int(ls.sum())
print('signals', nsig, f'{time.time()-t0:.0f}s', flush=True)

asset = 'XAUUSD_S611_M1'
SE.ASSETS[asset] = dict(file='', pip=0.10, contract=100.0, pip_value=10.0,
                        spread_pip=3.3, comm=0.0, slip_pip=0.0)
df = pd.DataFrame({'open': o, 'high': h, 'low': l, 'close': c}, copy=False)
trd = SE.simulate_trades(df, ls, np.zeros(N, dtype=bool), CFG['sl'], CFG['tp'],
                         asset, max_hold=CFG['mh'], be_trigger_pip=CFG['be'],
                         trail_pip=CFG['trail'])
w = (trd['outcome'] == 'win').values
sb = trd['signal_bar'].values
mid = N // 2
row = dict(tf='M1', src=src, n_bars=N, span_years=round((tsec[-1]-tsec[0])/86400/365.25, 2),
           n_signals=nsig, n_trades=int(len(trd)),
           wr=round(float(w.mean()*100), 2),
           net_pip=round(float(trd['pnl_pip'].sum()), 1),
           wr_h1=round(float(w[sb < mid].mean()*100), 2),
           wr_h2=round(float(w[sb >= mid].mean()*100), 2),
           net_h1=round(float(trd['pnl_pip'].values[sb < mid].sum()), 1),
           net_h2=round(float(trd['pnl_pip'].values[sb >= mid].sum()), 1),
           note='day built from time//86400 (UTC-equivalent); rest bit-identical to s153')
json.dump(row, open(os.path.join(OUT, 'M1.json'), 'w'), indent=1)
print(row, flush=True)
print(f'total {time.time()-t0:.0f}s')
