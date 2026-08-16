# -*- coding: utf-8 -*-
"""
S831 — کاوشِ ۷ (آخر): امتداد RR برای عبور PF از 1.3 — XAUUSD-H1 (۶۰٪ اکتشاف)
==============================================================================
سلول پایه: G=50, slm=1.4, hold∈{21,34}, rr∈{3.4, 4.2, 5.0, 6.0}
+ کنترل slm=1.0 (بازنده‌ی کوچک‌تر). گزارش PF کل + E1/E2 + lift + maxDD ساده.
"""
import sys, os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

SPLIT_IDX = 54798
WARMUP = 600
HALF = SPLIT_IDX // 2
G = 50.0

d = fd.load_fast('XAUUSD', 'H1')
df = fd.as_dataframe(d).iloc[:SPLIT_IDX].reset_index(drop=True)
c = df['close'].values.astype(np.float64)
h = df['high'].values.astype(np.float64)
l = df['low'].values.astype(np.float64)
prev_c = np.concatenate([[c[0]], c[:-1]])
tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
atr = np.empty_like(tr); atr[0] = tr[0]
a = 1.0 / 34
for i in range(1, len(tr)):
    atr[i] = atr[i-1] + a * (tr[i] - atr[i-1])
atr_pip = atr / se.ASSETS['XAUUSD']['pip']

lev = np.round(prev_c / G) * G
ev = (prev_c < lev) & (h >= lev) & (c < lev)
ev[:WARMUP] = False

def pf_of(pnl):
    w = pnl[pnl > 0].sum(); lo = -pnl[pnl < 0].sum()
    return w / lo if lo > 0 else np.inf

print(f'explore bars={len(df):,}  src={d["src"]}', flush=True)
for slm in (1.0, 1.4):
    slp = np.clip(atr_pip * slm, 8, 5000)
    for rr in (3.4, 4.2, 5.0, 6.0):
        tpp = slp * rr
        for hold in (21, 34):
            z0 = np.zeros(len(df), bool)
            tdf = se.simulate_trades(df, z0, ev, sl_pip=slp, tp_pip=tpp,
                                     asset='XAUUSD', max_hold=hold,
                                     allow_overlap=False)
            if len(tdf) < 60:
                continue
            pnl = tdf['pnl_pip'].values
            eb = tdf['entry_bar'].values
            wr = float((pnl > 0).mean() * 100)
            exp = float(pnl.mean())
            med_sl = float(np.median(tdf['sl_pip']))
            be = (med_sl + 3.3) / (med_sl + med_sl * rr) * 100
            pf = pf_of(pnl); pf1 = pf_of(pnl[eb < HALF]); pf2 = pf_of(pnl[eb >= HALF])
            eq = np.cumsum(pnl)
            dd = float((np.maximum.accumulate(eq) - eq).max())
            print(f'slm={slm} rr={rr} hold={hold}: n={len(tdf):5,} WR={wr:5.2f}% '
                  f'lift={wr-be:+6.2f}pp exp={exp:+7.2f}pip PF={pf:.3f} '
                  f'[E1={pf1:.3f} E2={pf2:.3f}] maxDD={dd:.0f}pip', flush=True)
print('\n[S831 explore-7 complete]', flush=True)
