# -*- coding: utf-8 -*-
"""
S831 — کاوشِ ۶: فیلتر سشن روی sweep-short — XAUUSD-H1 (فقط ۶۰٪ اکتشاف)
=========================================================================
هندسه‌ی ثابت از کاوش ۵ (بهترین پایداری): G=50, slm=1.4, rr=3.4, hold=21
فرضیه‌ی اقتصادی: جاروی نقدینگی واقعی کار نهادهاست (لندن/NY)؛ سشن آسیا نویز.
سلول‌ها: all / London(7-16 UTC) / NY(12-21) / LDN+NY(7-21) / Asia(0-7, کنترل منفی)
گزارش: PF کل + E1/E2 + lift.
"""
import sys, os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

SPLIT_IDX = 54798
WARMUP = 600
HALF = SPLIT_IDX // 2
G, SLM, RR, HOLD = 50.0, 1.4, 3.4, 21

d = fd.load_fast('XAUUSD', 'H1')
df = fd.as_dataframe(d).iloc[:SPLIT_IDX].reset_index(drop=True)
c = df['close'].values.astype(np.float64)
h = df['high'].values.astype(np.float64)
l = df['low'].values.astype(np.float64)
t = df['time'].values.astype(np.int64)
hour = (t // 3600) % 24
prev_c = np.concatenate([[c[0]], c[:-1]])
tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
atr = np.empty_like(tr); atr[0] = tr[0]
a = 1.0 / 34
for i in range(1, len(tr)):
    atr[i] = atr[i-1] + a * (tr[i] - atr[i-1])
atr_pip = atr / se.ASSETS['XAUUSD']['pip']

lev = np.round(prev_c / G) * G
base = (prev_c < lev) & (h >= lev) & (c < lev)
base[:WARMUP] = False
slp = np.clip(atr_pip * SLM, 8, 5000)
tpp = slp * RR

def pf_of(pnl):
    w = pnl[pnl > 0].sum(); lo = -pnl[pnl < 0].sum()
    return w / lo if lo > 0 else np.inf

SESSIONS = {
    'all':      np.ones(len(df), bool),
    'LDN_7_16': (hour >= 7) & (hour < 16),
    'NY_12_21': (hour >= 12) & (hour < 21),
    'LDNNY_7_21': (hour >= 7) & (hour < 21),
    'ASIA_0_7': (hour < 7),
}
print(f'explore bars={len(df):,}  src={d["src"]}', flush=True)
for name, m in SESSIONS.items():
    ev = base & m
    z0 = np.zeros(len(df), bool)
    tdf = se.simulate_trades(df, z0, ev, sl_pip=slp, tp_pip=tpp,
                             asset='XAUUSD', max_hold=HOLD, allow_overlap=False)
    if len(tdf) < 40:
        print(f'{name:11s}: n={len(tdf)} — کم', flush=True)
        continue
    pnl = tdf['pnl_pip'].values
    eb = tdf['entry_bar'].values
    wr = float((pnl > 0).mean() * 100)
    exp = float(pnl.mean())
    med_sl = float(np.median(tdf['sl_pip']))
    be = (med_sl + 3.3) / (med_sl + med_sl * RR) * 100
    pf = pf_of(pnl); pf1 = pf_of(pnl[eb < HALF]); pf2 = pf_of(pnl[eb >= HALF])
    print(f'{name:11s}: n={len(tdf):5,} WR={wr:5.2f}% lift={wr-be:+6.2f}pp '
          f'exp={exp:+7.2f}pip PF={pf:.3f} [E1={pf1:.3f} E2={pf2:.3f}]', flush=True)
print('\n[S831 explore-6 complete]', flush=True)
