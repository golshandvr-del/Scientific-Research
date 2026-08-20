#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S793 RECON — Counter-Drift Jump Fade (CDJF) — XAUUSD
فرضیه: پرشِ بزرگ (سنجیده با Bipower Variation جهش-مقاوم، Barndorff-Nielsen &
Shephard 2004) که *خلافِ* درفتِ رژیم رخ دهد = آبشار استاپ/لیکوییدیشن اجباری
(Grossman–Miller 1988) ⇒ بازجذب؛ ورود در جهتِ درفت (fade پرش).
درس S950 (ACCEPT): مقیاسِ BV + هم‌راستایی با درفت. درس S790/S792 (REJECT):
خلاف‌درفت روی طلا می‌بازد ⇒ این‌بار جهتِ معامله = جهتِ درفت.

اکتشاف فقط روی نیمهٔ اول (Path C). usage: python3 s793_recon_cdjf.py [TF]
"""
import sys, numpy as np, pandas as pd
sys.path.insert(0, '/home/user/webapp')
from tools import s434_fast_data as fd
from engine import scalp_engine as se

TF = sys.argv[1] if len(sys.argv) > 1 else 'H3'
PIP = 0.10; SPREAD = 3.3

d = fd.load_fast('XAUUSD', TF)
df = d['df'] if isinstance(d, dict) and 'df' in d else d
src = d['src'] if isinstance(d, dict) else 'unknown'
o = df['open'].values; h = df['high'].values; l = df['low'].values
c = df['close'].values; t = pd.to_datetime(df['time']).values
n = len(c); split = n // 2
print(f'src={src} | TF={TF} | bars={n} | discovery=first {split} bars '
      f'({str(t[0])[:10]} → {str(t[split-1])[:10]})', flush=True)

# --- causal building blocks ---
r = np.r_[np.nan, np.diff(np.log(c))]                      # log return of bar t
# Bipower variation scale, window 89, causal to t-1
absr = np.abs(r)
bp = absr * np.r_[np.nan, absr[:-1]]
bv = pd.Series(bp).rolling(89).mean().values * (np.pi / 2.0)
sigma = np.sqrt(bv)
sigma = np.r_[np.nan, sigma[:-1]]                          # shift 1 -> causal
# ATR89 (EMA of TR, alpha=2/90), shifted 1 (same as S79x layers)
tr = np.maximum(h - l, np.maximum(np.abs(h - np.r_[c[0], c[:-1]]),
                                  np.abs(l - np.r_[c[0], c[:-1]])))
atr = np.empty(n); atr[0] = tr[0]; al = 2.0 / 90.0
for i in range(1, n): atr[i] = al * tr[i] + (1 - al) * atr[i-1]
atr = np.r_[np.nan, atr[:-1]]
# regime drift, 89-bar, causal (uses close up to t-1)
drift = np.r_[np.nan, c[:-1]] - np.r_[[np.nan]*90, c[:-90]][:n]

def run(k_jump, a_geom, mh):
    long_sig  = (r < -k_jump * sigma) & (drift > 0)   # down-jump in uptrend -> fade long
    short_sig = (r > +k_jump * sigma) & (drift < 0)   # up-jump in downtrend -> fade short
    valid = ~np.isnan(sigma) & ~np.isnan(atr) & ~np.isnan(drift)
    long_sig &= valid; short_sig &= valid
    long_sig[split:] = False; short_sig[split:] = False   # discovery half only
    sl_arr = np.where(valid, a_geom * atr / PIP, 0.0)
    trades = se.simulate_trades(
        o, h, l, c, long_sig, short_sig,
        sl_pip=sl_arr, tp_pip=sl_arr, max_hold=mh,
        spread_pip=SPREAD, pip=PIP, allow_overlap=False)
    if trades is None or len(trades) == 0:
        return dict(n=0, wr=np.nan, net=0.0, exp=np.nan)
    nn = len(trades); w = (trades['pnl_pip'] > 0).sum()
    net = trades['pnl_pip'].sum()
    return dict(n=nn, wr=100.0*w/nn, net=net, exp=net/nn)

print(f'{"k":>6} {"a":>6} {"mh":>4} | {"n":>5} {"WR%":>6} {"exp":>8} {"net":>9}')
best = None
for k_jump in (1.618, 2.058, 2.6):
    for a_geom in (1.618, 2.058, 2.618):
        for mh in (21, 34):
            m = run(k_jump, a_geom, mh)
            tag = ''
            if m['n'] >= 60 and best is not None and m['exp'] > best[0]['exp']: tag = ' <'
            if m['n'] >= 60 and (best is None or m['exp'] > best[0]['exp']):
                best = (m, k_jump, a_geom, mh); tag = ' *'
            print(f'{k_jump:>6} {a_geom:>6} {mh:>4} | {m["n"]:>5} '
                  f'{m["wr"]:>6.2f} {m["exp"]:>8.2f} {m["net"]:>9.1f}{tag}', flush=True)
if best:
    m, k_jump, a_geom, mh = best
    print(f'\nBEST (n>=60): k={k_jump} a={a_geom} mh={mh} -> n={m["n"]} '
          f'WR={m["wr"]:.2f}% exp={m["exp"]:.2f}p net={m["net"]:.1f}p')
