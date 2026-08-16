# -*- coding: utf-8 -*-
"""
S831 — کاوشِ ۳: جاروی «تازه» + عمق نفوذ — XAUUSD-H1 (فقط ۶۰٪ اکتشاف)
======================================================================
پالایش کاوش ۲: رویدادهای sweep_up_fail شامل سایش‌های تکراری روی سطح‌اند
که سیگنال را رقیق می‌کنند. جاروی «کتاب درسیِ» ICT:
  (۱) تازگی: در F کندل گذشته سطح لمس نشده باشد (اولین برخورد)
  (۲) نفوذ معنادار: (high - L) >= pen × ATR (استاپ‌ها واقعاً فعال شده باشند)
  (۳) بسته‌شدن رد: close < L
شبکه: G ∈ {25, 50} × F ∈ {8, 21} × pen ∈ {0.0, 0.15, 0.30}
هندسه‌ی ثابت از کاوش ۲: slm=2.1, rr=1.6, hold=13 (بهترین تعادل exp×lift)
+ یک ستون کنترل: همان فیلترها با هندسه slm=2.6.
جمع: 2×2×3×2 = 24 سلول.
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

HOLD = 13
for G in (25.0, 50.0):
    lev = np.round(prev_c / G) * G
    base = (prev_c < lev) & (h >= lev) & (c < lev)
    touched = (l <= lev) & (lev <= h)   # هر لمس سطحِ جاری
    for F in (8, 21):
        fresh = np.ones(len(df), bool)
        for j in range(1, F + 1):
            # آیا در j کندل قبل، «همان سطح» لمس شده بود؟ سطح با prev_c جابه‌جا
            # می‌شود؛ تقریب صادقانه: لمس هر سطح G-شبکه در j کندل قبل
            sh = np.concatenate([np.zeros(j, bool), touched[:-j]])
            fresh &= ~sh
        for pen in (0.0, 0.15, 0.30):
            ev = base & fresh & ((h - lev) >= pen * atr)
            ev[:WARMUP] = False
            n_ev = int(ev.sum())
            if n_ev < 80:
                print(f'G={G:.0f} F={F} pen={pen}: only {n_ev} events — skip', flush=True)
                continue
            for slm in (2.1, 2.6):
                slp = np.clip(atr_pip * slm, 8, 5000)
                tpp = slp * 1.6
                z0 = np.zeros(len(df), bool)
                tdf = se.simulate_trades(df, z0, ev, sl_pip=slp, tp_pip=tpp,
                                         asset='XAUUSD', max_hold=HOLD,
                                         allow_overlap=False)
                if len(tdf) < 30:
                    continue
                pnl = tdf['pnl_pip'].values
                wr = float((pnl > 0).mean() * 100)
                exp = float(pnl.mean())
                med_sl = float(np.median(tdf['sl_pip']))
                be = (med_sl + 3.3) / (med_sl + med_sl * 1.6) * 100
                print(f'G={G:.0f} F={F} pen={pen} slm={slm}: n={len(tdf):5,} '
                      f'WR={wr:5.2f}% be_cost={be:5.2f}% lift={wr-be:+6.2f}pp '
                      f'exp={exp:+7.2f}pip', flush=True)

print('\n[S831 explore-3 complete]', flush=True)
