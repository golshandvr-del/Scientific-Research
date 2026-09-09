# -*- coding: utf-8 -*-
"""
S835 — کاوشِ ۱: کشمکشِ شبانه/درون‌روزی (Overnight–Intraday Tug-of-War) — فقط ۶۰٪ اکتشاف
========================================================================================
منبع: Lou, Polk & Skouras (2019) — بازدهِ شبانه و درون‌روزی حاملِ اطلاعاتِ دو جمعیتِ متفاوت‌اند؛
هر مؤلفه در خودش ماندگار است و با مؤلفه‌ی دیگر مخالف.
ساخت (از H1، سطحِ روزِ UTC):
  ON_d = open(اولین کندلِ روز d) − close(آخرین کندلِ روز d−1)   (شبانه)
  ID_d = close(آخرین کندلِ روز d) − open(اولین کندلِ روز d)     (درون‌روزی)
  S_ON, S_ID = جمعِ N روزه ؛ z = S / (σ_d·√N) ، σ_d = میانه‌ی rangeِ روزانه‌ی ۲۰ روز
  رخداد: |z_lead| > k [و اختیاری: sign(z_ON) ≠ sign(z_ID) = کشمکش]
  جهت: lead=ON ⇒ جهتِ S_ON ؛ lead=ID ⇒ جهتِ S_ID  (هر دو آینه‌ای/درون‌زاد)
  سیگنال روی آخرین کندلِ روز d ⇒ ورود در openِ اولین کندلِ روز d+1 (موتور).
هندسه: SL=1.0×σ_d، TP=1.3×SL، hold∈{24,72} کندل، بدون trail/BE.
سنجه: INFO-lift نسبت به نالِ جای‌گشتیِ جهت با همان هندسه K=80؛ pw؛ سه رژیمِ واقعی R1/R2/R3.
"""
import sys, os
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

K_NULL = 80
SEED = 835001
R1_END = 1356998400; R2_END = 1451606400
PIP = se.ASSETS['XAUUSD']['pip']


def pf_of(p):
    w = p[p > 0].sum(); lo_ = -p[p < 0].sum()
    return w / lo_ if lo_ > 0 else np.inf


def info_null(df, sig_bars, slp, tpp, hold, rng):
    wrs = []
    for _ in range(K_NULL):
        dirs = rng.integers(0, 2, size=len(sig_bars)).astype(bool)
        lm = np.zeros(len(df), bool); lm[sig_bars[dirs]] = True
        sm = np.zeros(len(df), bool); sm[sig_bars[~dirs]] = True
        t = se.simulate_trades(df, lm, sm, sl_pip=slp, tp_pip=tpp, asset='XAUUSD',
                               max_hold=hold, allow_overlap=False)
        if len(t):
            wrs.append((t['pnl_pip'].values > 0).mean() * 100)
    return float(np.mean(wrs)), float(np.std(wrs))


d = fd.load_fast('XAUUSD', 'H1')
assert 'mt5_full' in d['src'], f'E-16 trap: {d["src"]}'
df_full = fd.as_dataframe(d)
split = int(len(df_full) * 0.6)
df = df_full.iloc[:split].reset_index(drop=True)
t = df['time'].values.astype(np.int64)
o = df['open'].values.astype(np.float64); c = df['close'].values.astype(np.float64)
h = df['high'].values.astype(np.float64); l = df['low'].values.astype(np.float64)
n = len(df)
day = t // 86400
first = np.concatenate([[True], day[1:] != day[:-1]])
last = np.concatenate([day[1:] != day[:-1], [True]])
fidx = np.where(first)[0]; lidx = np.where(last)[0]
D = len(fidx)
d_open = o[fidx]; d_close = c[lidx]
d_hi = np.array([h[a:b+1].max() for a, b in zip(fidx, lidx)])
d_lo = np.array([l[a:b+1].min() for a, b in zip(fidx, lidx)])
ON = np.full(D, np.nan); ON[1:] = d_open[1:] - d_close[:-1]
ID = d_close - d_open
sigma = pd.Series(d_hi - d_lo).rolling(20).median().values
print(f'explore bars={n:,} days={D:,} src={d["src"]}', flush=True)
print(f'  sanity: mean ON={np.nanmean(ON):+.3f}$ mean ID={np.nanmean(ID):+.3f}$ ; '
      f'ac1(ON)={pd.Series(ON).autocorr():+.3f} ac1(ID)={pd.Series(ID).autocorr():+.3f} '
      f'corr(ON,ID)={np.corrcoef(ON[1:], ID[1:])[0,1]:+.3f}', flush=True)

sig_sigma = np.full(n, np.nan); sig_sigma[lidx] = sigma
slp_full = np.clip(np.nan_to_num(sig_sigma, nan=1.0) / PIP, 8, 5000)
tpp_full = slp_full * 1.3
rng = np.random.default_rng(SEED)
WARM_D = 60
for N in (5, 10, 20):
    zon = pd.Series(ON).rolling(N).sum().values / (sigma * np.sqrt(N))
    zid = pd.Series(ID).rolling(N).sum().values / (sigma * np.sqrt(N))
    for k in (0.5, 1.0, 1.5):
        for mode in ('ON', 'ID'):
            z_lead = zon if mode == 'ON' else zid
            z_other = zid if mode == 'ON' else zon
            for conflict in (1, 0):
                ev = (np.abs(z_lead) > k) & np.isfinite(z_lead) & np.isfinite(z_other)
                if conflict:
                    ev &= (np.sign(z_lead) != np.sign(z_other))
                ev[:WARM_D] = False
                ls = np.zeros(n, bool); ss = np.zeros(n, bool)
                dl = np.where(ev & (z_lead > 0))[0]; ds = np.where(ev & (z_lead < 0))[0]
                dl = dl[dl < D - 1]; ds = ds[ds < D - 1]
                ls[lidx[dl]] = True; ss[lidx[ds]] = True
                if ls.sum() + ss.sum() < 80:
                    continue
                for HOLD in (24, 72):
                    tdf = se.simulate_trades(df, ls, ss, sl_pip=slp_full, tp_pip=tpp_full,
                                             asset='XAUUSD', max_hold=HOLD, allow_overlap=False)
                    if len(tdf) < 80:
                        continue
                    pnl = tdf['pnl_pip'].values; eb = tdf['entry_bar'].values
                    sb = tdf['signal_bar'].values.astype(int)
                    wr = (pnl > 0).mean() * 100
                    nm, nsd = info_null(df, sb, slp_full, tpp_full, HOLD, rng)
                    lift = wr - nm; z = lift / nsd if nsd > 0 else 0; pw = lift * np.sqrt(len(pnl))
                    te = t[eb]
                    def lo(m):
                        return (pnl[m] > 0).mean() * 100 - nm if m.sum() >= 15 else np.nan
                    l1, l2, l3 = lo(te < R1_END), lo((te >= R1_END) & (te < R2_END)), lo(te >= R2_END)
                    flag = ' <<<' if (lift >= 4 and z >= 2.5 and np.nanmin([l1, l2, l3]) > 0) else ''
                    print(f'  N={N:2d} k={k} lead={mode} conf={conflict} hold={HOLD}: '
                          f'n={len(pnl):5,} WR={wr:5.2f}% null={nm:5.2f}%±{nsd:.2f} INFOlift={lift:+6.2f}pp '
                          f'z={z:+4.1f} pw={pw:5.0f} PF={pf_of(pnl):.3f} exp={pnl.mean():+7.2f} '
                          f'[R1={l1:+5.1f} R2={l2:+5.1f} R3={l3:+5.1f}]{flag}', flush=True)

print('\n[S835 explore-1 complete]', flush=True)
