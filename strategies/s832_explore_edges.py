# -*- coding: utf-8 -*-
"""
S832 — کاوشِ ۶ (لبه‌سنجی پیش از انجماد): EMA بلندتر و trail کوتاه‌تر
======================================================================
دو کاندیدِ برتر کاوش ۵ روی لبه‌ی شبکه بودند. پرسش: آیا پشت لبه پرتگاه است؟
شبکه: EMA ∈ {200, 300, 400, 500} × trail ∈ {0.5, 0.7, 1.0} — slm=2.1 ثابت،
rr=6, hold=55. اگر روند بهبود ادامه‌دار و هموار باشد ⇒ فلات واقعی؛ انجمادِ
سلولِ میانیِ ناحیه‌ی امن. فقط ۶۰٪ اکتشاف.
"""
import sys, os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

SPLIT_IDX = 54798
WARMUP = 600
HALF = SPLIT_IDX // 2

d = fd.load_fast('XAUUSD', 'H1')
df = fd.as_dataframe(d).iloc[:SPLIT_IDX].reset_index(drop=True)
t = df['time'].values.astype(np.int64)
c = df['close'].values.astype(np.float64)
h = df['high'].values.astype(np.float64)
l = df['low'].values.astype(np.float64)
hour = (t // 3600) % 24
day = t // 86400
prev_c = np.concatenate([[c[0]], c[:-1]])
tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
atr = np.empty_like(tr); atr[0] = tr[0]
a = 1.0 / 34
for i in range(1, len(tr)):
    atr[i] = atr[i-1] + a * (tr[i] - atr[i-1])
atr_pip = atr / se.ASSETS['XAUUSD']['pip']
n = len(df)

rhi = np.full(n, np.nan); rlo = np.full(n, np.nan)
for dd in np.unique(day):
    m = (day == dd) & (hour <= 6)
    if m.sum() < 5:
        continue
    md = (day == dd) & (hour >= 7)
    rhi[md] = h[m].max(); rlo[md] = l[m].min()
in_win = (hour >= 7) & (hour <= 16)
brk_up = in_win & np.isfinite(rhi) & (c > rhi)
brk_dn = in_win & np.isfinite(rlo) & (c < rlo)
first = np.zeros(n, bool)
seen = set()
for i in range(n):
    if (brk_up[i] or brk_dn[i]) and day[i] not in seen:
        first[i] = True
        seen.add(day[i])
base_ls = first & brk_up
base_ss = first & brk_dn & ~base_ls
base_ls[:WARMUP] = False; base_ss[:WARMUP] = False

MED_ATR = float(np.median(atr_pip[WARMUP:]))
SLM = 2.1; RR = 6.0; HOLD = 55
slp = np.clip(atr_pip * SLM, 8, 5000)
tpp = slp * RR

def pf_of(pnl):
    w = pnl[pnl > 0].sum(); lo_ = -pnl[pnl < 0].sum()
    return w / lo_ if lo_ > 0 else np.inf

print(f'explore bars={n:,}  src={d["src"]}', flush=True)

for span in (200, 300, 400, 500):
    e = np.empty_like(c); e[0] = c[0]
    kk = 2.0 / (span + 1)
    for i in range(1, n):
        e[i] = e[i-1] + kk * (c[i] - e[i-1])
    above = c > e
    ls = base_ls & above
    ss = base_ss & ~above
    print(f'\n===== EMA{span}  (L={int(ls.sum())} S={int(ss.sum())}) =====', flush=True)
    for tf_ in (0.5, 0.7, 1.0):
        trail = float(MED_ATR * tf_)
        tdf = se.simulate_trades(df, ls, ss, sl_pip=slp, tp_pip=tpp,
                                 asset='XAUUSD', max_hold=HOLD,
                                 allow_overlap=False, trail_pip=trail)
        if len(tdf) < 60:
            continue
        pnl = tdf['pnl_pip'].values
        eb = tdf['entry_bar'].values
        wr = float((pnl > 0).mean() * 100)
        med_sl = float(np.median(tdf['sl_pip']))
        be_cost = (med_sl + 3.3) / (med_sl + med_sl * RR) * 100
        pf = pf_of(pnl); pf1 = pf_of(pnl[eb < HALF]); pf2 = pf_of(pnl[eb >= HALF])
        print(f'  trail={tf_}: n={len(tdf):5,} WR={wr:5.2f}% lift={wr-be_cost:+6.2f}pp '
              f'exp={float(pnl.mean()):+7.2f}pip PF={pf:.3f} [E1={pf1:.3f} E2={pf2:.3f}]', flush=True)

print('\n[S832 explore-6 complete]', flush=True)
