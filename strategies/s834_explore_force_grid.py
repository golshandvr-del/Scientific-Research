# -*- coding: utf-8 -*-
"""
S834 — کاوشِ ۳: شبکه‌ی پالایشِ Force Index (Elder) — فقط ۶۰٪ اکتشاف H1
======================================================================
سیگنالِ پایه (از کاوش ۲): fz = EMA_s(vol×Δc) / sd_rolling(win)؛ رخداد = عبورِ تازه‌ی |fz| از k،
جهت = علامتِ fz (follow؛ آینه‌ای — long روی +k و short روی −k در یک لایه).
شبکه: s∈{13,21} × win∈{144,377} × k∈{2.0,2.5} × RR∈{1.3,2.0} × hold∈{21,34}
سنجه: INFO-lift نسبت به نالِ هم‌هندسه K=80؛ pw=lift·√n؛ سه رژیمِ واقعی؛ PF کل و به تفکیکِ L/S.
"""
import sys, os
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

K_NULL = 80
SEED = 834003
SLM = 2.0
R1_END = 1356998400; R2_END = 1451606400
WARM = 400


def pf_of(p):
    w = p[p > 0].sum(); lo_ = -p[p < 0].sum()
    return w / lo_ if lo_ > 0 else np.inf


def ema(x, span):
    return pd.Series(x).ewm(span=span, adjust=False).mean().values


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
c = df['close'].values.astype(np.float64)
h = df['high'].values.astype(np.float64); l = df['low'].values.astype(np.float64)
v = df['volume'].values.astype(np.float64)
n = len(df)
prev_c = np.concatenate([[c[0]], c[:-1]])
tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
atr_pip = ema(tr, 67) / se.ASSETS['XAUUSD']['pip']
slp = np.clip(atr_pip * SLM, 8, 5000)
print(f'explore bars={n:,} src={d["src"]}', flush=True)
rng = np.random.default_rng(SEED)

for s in (13, 21):
    fi = ema(v * (c - prev_c), s)
    for win in (144, 377):
        sd = pd.Series(fi).rolling(win).std().values
        fz = fi / np.where(sd > 0, sd, np.nan)
        pfz = np.concatenate([[np.nan], fz[:-1]])
        for k in (2.0, 2.5):
            ls = (fz > k) & ~(pfz > k); ss = (fz < -k) & ~(pfz < -k)
            ls[:WARM] = False; ss[:WARM] = False
            print(f'\n===== s={s} win={win} k={k} (L={int(ls.sum())} S={int(ss.sum())}) =====', flush=True)
            for RR in (1.3, 2.0):
                tpp = slp * RR
                for HOLD in (21, 34):
                    tdf = se.simulate_trades(df, ls, ss, sl_pip=slp, tp_pip=tpp, asset='XAUUSD',
                                             max_hold=HOLD, allow_overlap=False)
                    if len(tdf) < 100:
                        continue
                    pnl = tdf['pnl_pip'].values; eb = tdf['entry_bar'].values
                    sb = tdf['signal_bar'].values.astype(int)
                    isl = tdf['direction'].values == 'long'
                    wr = (pnl > 0).mean() * 100
                    nm, nsd = info_null(df, sb, slp, tpp, HOLD, rng)
                    lift = wr - nm; z = lift / nsd if nsd > 0 else 0; pw = lift * np.sqrt(len(pnl))
                    te = t[eb]
                    def lo(m):
                        return (pnl[m] > 0).mean() * 100 - nm if m.sum() >= 15 else np.nan
                    l1, l2, l3 = lo(te < R1_END), lo((te >= R1_END) & (te < R2_END)), lo(te >= R2_END)
                    flag = ' <<<' if (lift >= 4 and z >= 2.5 and np.nanmin([l1, l2, l3]) > 0 and pf_of(pnl) >= 1.2) else ''
                    print(f'  RR={RR} hold={HOLD}: n={len(pnl):5,} WR={wr:5.2f}% null={nm:5.2f}%±{nsd:.2f} '
                          f'INFOlift={lift:+6.2f}pp z={z:+4.1f} pw={pw:5.0f} PF={pf_of(pnl):.3f} '
                          f'[PF_L={pf_of(pnl[isl]):.2f} PF_S={pf_of(pnl[~isl]):.2f}] exp={pnl.mean():+6.2f} '
                          f'[R1={l1:+5.1f} R2={l2:+5.1f} R3={l3:+5.1f}]{flag}', flush=True)

print('\n[S834 explore-3 complete]', flush=True)
