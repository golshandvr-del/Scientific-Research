# -*- coding: utf-8 -*-
"""
S831 — کاوشِ ۲: هندسه‌ی معامله برای «جاروی ناکام سطح رند» — XAUUSD-H1
========================================================================
فقط پنجره‌ی اکتشاف (۶۰٪ اول، تا کندل 54798). کاوش ۱ نشان داد:
  sweep_up_fail G=25: fwd21 = -0.23 ATR (z=-2.9, n=1834) → کاندید short خلاف‌رانش
  sweep_dn_fail: هیچ سیگنال long معناداری ندارد (رد شد)

این کاوش: شبکه‌ی کوچک هندسه برای short پس از جاروی ناکام صعودی.
  رخداد: prev_close < L ، high >= L ، close < L  (L = نزدیک‌ترین مضرب G به prev_close)
  ورود: کندل بعد (open) از طریق شبیه‌ساز
شبکه: G ∈ {25, 50} × slm ∈ {1.3, 2.1, 2.6} × rr ∈ {1.0, 1.6} × hold ∈ {13, 21}
جمع: 2×3×2×2 = 24 سلول. اسپرد کامل 3.3 پیپ در شبیه‌ساز.
"""
import sys, os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

SPLIT_IDX = 54798
WARMUP = 600

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

print(f'explore bars={len(df):,}  src={d["src"]}', flush=True)

for G in (25.0, 50.0):
    lev = np.round(prev_c / G) * G
    sweep = (prev_c < lev) & (h >= lev) & (c < lev)
    sweep[:WARMUP] = False
    n_ev = int(sweep.sum())
    print(f'\n===== G={G:.0f}  events={n_ev:,} =====', flush=True)
    for slm in (1.3, 2.1, 2.6):
        for rr in (1.0, 1.6):
            for hold in (13, 21):
                slp = np.clip(atr_pip * slm, 8, 5000)
                tpp = slp * rr
                z0 = np.zeros(len(df), bool)
                tdf = se.simulate_trades(df, z0, sweep, sl_pip=slp, tp_pip=tpp,
                                         asset='XAUUSD', max_hold=hold,
                                         allow_overlap=False)
                if len(tdf) < 30:
                    continue
                pnl = tdf['pnl_pip'].values
                wr = float((pnl > 0).mean() * 100)
                exp = float(pnl.mean())
                med_sl = float(np.median(tdf['sl_pip']))
                be = (med_sl + 3.3) / (med_sl + med_sl * rr) * 100
                print(f'  slm={slm} rr={rr} hold={hold}: n={len(tdf):5,} '
                      f'WR={wr:5.2f}% be_cost={be:5.2f}% lift={wr-be:+6.2f}pp '
                      f'exp={exp:+7.2f}pip medSL={med_sl:.0f}', flush=True)

print('\n[S831 explore-2 complete]', flush=True)
