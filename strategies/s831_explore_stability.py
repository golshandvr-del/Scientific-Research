# -*- coding: utf-8 -*-
"""
S831 — کاوشِ ۴: آزمون پایداری رژیمی درون پنجره‌ی اکتشاف (درس S830)
====================================================================
سلول کاندید: sweep_up_fail، G=50، slm=2.1، rr=1.6، hold=13 (short)
پنجره‌ی اکتشاف (تا 54798) به دو نیمه تقسیم می‌شود:
  E1: 2011 → ~2015 (کندل 0..27398)
  E2: ~2015 → 2020-05 (کندل 27399..54797)
اگر lift فقط در یکی زنده باشد ⇒ رژیمی ⇒ هولد‌اوت سوزانده نمی‌شود.
همچنین سلول‌های همسایه (G=25 و slm=2.6) برای دید فلات گزارش می‌شوند.
هنوز هیچ نگاهی به داده‌ی پس از 2020-05 نمی‌شود.
"""
import sys, os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

SPLIT_IDX = 54798
WARMUP = 600
HOLD = 13
RR = 1.6

d = fd.load_fast('XAUUSD', 'H1')
df_full = fd.as_dataframe(d).iloc[:SPLIT_IDX].reset_index(drop=True)
half = SPLIT_IDX // 2

def run_window(df, label):
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
    print(f'\n===== {label}  bars={len(df):,}  price {c.min():.0f}..{c.max():.0f} =====', flush=True)
    for G in (25.0, 50.0):
        lev = np.round(prev_c / G) * G
        ev = (prev_c < lev) & (h >= lev) & (c < lev)
        ev[:WARMUP] = False
        for slm in (2.1, 2.6):
            slp = np.clip(atr_pip * slm, 8, 5000)
            tpp = slp * RR
            z0 = np.zeros(len(df), bool)
            tdf = se.simulate_trades(df, z0, ev, sl_pip=slp, tp_pip=tpp,
                                     asset='XAUUSD', max_hold=HOLD,
                                     allow_overlap=False)
            if len(tdf) < 30:
                print(f'  G={G:.0f} slm={slm}: n={len(tdf)} — کم', flush=True)
                continue
            pnl = tdf['pnl_pip'].values
            wr = float((pnl > 0).mean() * 100)
            exp = float(pnl.mean())
            med_sl = float(np.median(tdf['sl_pip']))
            be = (med_sl + 3.3) / (med_sl + med_sl * RR) * 100
            print(f'  G={G:.0f} slm={slm}: n={len(tdf):5,} WR={wr:5.2f}% '
                  f'be_cost={be:5.2f}% lift={wr-be:+6.2f}pp exp={exp:+7.2f}pip', flush=True)

run_window(df_full.iloc[:half].reset_index(drop=True), 'E1 (2011→2015)')
run_window(df_full.iloc[half:].reset_index(drop=True), 'E2 (2015→2020-05)')
print('\n[S831 stability check complete]', flush=True)
