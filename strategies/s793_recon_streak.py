#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S793 RECON-B — Drift-Aligned Streak Pullback (DASP) — XAUUSD
فرضیه: رگهٔ K کندلِ متوالیِ خلافِ درفتِ ۸۹کندله = پولبکِ تدریجی (نه پرش —
پرش‌ها طبق recon-A نویزند) ⇒ ورود در جهتِ درفت («خرید در افت» نهادی).
تمایز از S326 (REJECT): آن‌جا رگهٔ خام بی‌شرطِ رژیم بود؛ این‌جا رگه فقط
خلافِ درفت معنا دارد و ورود هم‌جهتِ درفت است (درسِ S950/S790/S792).
اکتشاف فقط نیمهٔ اول (Path C). usage: python3 s793_recon_streak.py [TF]
"""
import sys, numpy as np, pandas as pd
sys.path.insert(0, '/home/user/webapp')
from tools import s434_fast_data as fd
from engine import scalp_engine as se

TF = sys.argv[1] if len(sys.argv) > 1 else 'H3'
PIP = 0.10

d = fd.load_fast('XAUUSD', TF)
df = fd.as_dataframe(d)
o = df['open'].values; h = df['high'].values; l = df['low'].values
c = df['close'].values
n = len(c); split = n // 2
print(f"src={d['src']} | TF={TF} | bars={n} | discovery=first {split}", flush=True)

# ATR89 EMA(alpha=2/90) shifted 1 (causal)
pc = np.r_[c[0], c[:-1]]
tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
atr = np.empty(n); a = tr[0]; kk = 2.0 / 90.0
for i in range(n):
    a = a + kk * (tr[i] - a); atr[i] = a
atr = np.r_[np.nan, atr[:-1]]

# 89-bar drift, causal
drift = np.full(n, np.nan)
drift[90:] = c[89:-1] - c[:n-90]

# consecutive down/up closes ending at bar t (bar t is closed => usable for entry t+1)
dn = (c < pc).astype(int); up = (c > pc).astype(int)
run_dn = np.zeros(n, int); run_up = np.zeros(n, int)
for i in range(1, n):
    run_dn[i] = run_dn[i-1] + 1 if dn[i] else 0
    run_up[i] = run_up[i-1] + 1 if up[i] else 0

valid = ~np.isnan(atr) & ~np.isnan(drift)

def run_cfg(K, a_geom, mh):
    long_sig  = valid & (drift > 0) & (run_dn == K)   # exactly K to avoid overlap pyramids
    short_sig = valid & (drift < 0) & (run_up == K)
    long_sig[split:] = False; short_sig[split:] = False
    sl_arr = np.where(valid, a_geom * atr / PIP, 0.0)
    tr_ = se.simulate_trades(df, long_sig, short_sig, sl_arr, sl_arr, 'XAUUSD',
                             max_hold=mh, allow_overlap=False)
    if tr_ is None or len(tr_) == 0:
        return dict(n=0, wr=np.nan, exp=np.nan, net=0.0)
    nn = len(tr_); w = (tr_['pnl_pip'] > 0).sum(); net = tr_['pnl_pip'].sum()
    return dict(n=nn, wr=100.0*w/nn, exp=net/nn, net=net)

print(f'{"K":>3} {"a":>6} {"mh":>4} | {"n":>6} {"WR%":>6} {"exp":>8} {"net":>9}')
best = None
for K in (2, 3, 5):
    for a_geom in (1.618, 2.058, 2.618):
        for mh in (21, 34):
            m = run_cfg(K, a_geom, mh)
            tag = ''
            if m['n'] >= 100 and (best is None or m['exp'] > best[0]['exp']):
                best = (m, K, a_geom, mh); tag = ' *'
            print(f'{K:>3} {a_geom:>6} {mh:>4} | {m["n"]:>6} {m["wr"]:>6.2f} '
                  f'{m["exp"]:>8.2f} {m["net"]:>9.1f}{tag}', flush=True)
if best:
    m, K, a_geom, mh = best
    print(f'\nBEST(n>=100): K={K} a={a_geom} mh={mh} -> n={m["n"]} '
          f'WR={m["wr"]:.2f}% exp={m["exp"]:.2f}p net={m["net"]:.1f}p')
