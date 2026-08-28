# -*- coding: utf-8 -*-
"""
S833 — کاوشِ ۴ (آخرین پیش از تصمیم): تعادلِ n×lift در ER-cont — فقط ۶۰٪ اکتشاف H1
====================================================================================
یافته‌ها: θ=0.6 ⇒ n≈1300 ولی lift≈3.8pp (زیر گیت)؛ θ=0.7 ⇒ lift≈9pp ولی n≈160
(توان مرزی). پرسش: آیا θ میانی نقطه‌ی تعادلِ (lift≥5pp و n≥400) دارد؟
شبکه: W ∈ {17, 21, 26} × θ ∈ {0.62, 0.65, 0.68} — هندسه‌ی منجمدِ برداشت:
RR=1.3, hold=55, SLM=2.0 (بهترین برداشتِ کاوش ۳ با پایداری E1/E2).
K=200 برای دقت بهتر sd نال. cont فقط.
"""
import sys, os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

WARMUP = 200
K_NULL = 200
SEED = 833004
SLM, RR, HOLD = 2.0, 1.3, 55

def pf_of(p):
    w = p[p > 0].sum(); lo_ = -p[p < 0].sum()
    return w / lo_ if lo_ > 0 else np.inf

d = fd.load_fast('XAUUSD', 'H1')
assert 'mt5_full' in d['src'], f'E-16 trap: {d["src"]}'
df_full = fd.as_dataframe(d)
split = int(len(df_full) * 0.6)
df = df_full.iloc[:split].reset_index(drop=True)
c = df['close'].values.astype(np.float64)
h = df['high'].values.astype(np.float64)
l = df['low'].values.astype(np.float64)
n = len(df)
HALF = n // 2
prev_c = np.concatenate([[c[0]], c[:-1]])
tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
atr = np.empty_like(tr); atr[0] = tr[0]
a = 1.0 / 34
for i in range(1, n):
    atr[i] = atr[i-1] + a * (tr[i] - atr[i-1])
atr_pip = atr / se.ASSETS['XAUUSD']['pip']
slp = np.clip(atr_pip * SLM, 8, 5000)
tpp = slp * RR

dc = np.abs(np.diff(c, prepend=c[0]))
cs_abs = np.cumsum(np.concatenate([[0.0], dc]))
print(f'explore bars={n:,}  src={d["src"]}  geometry: SL=2xATR34 RR={RR} hold={HOLD}', flush=True)

for W in (17, 21, 26):
    net = np.full(n, np.nan)
    net[W:] = c[W:] - c[:-W]
    noise = cs_abs[W+1:] - cs_abs[1:-W]
    er = np.full(n, np.nan)
    ok = noise > 0
    er[W:][ok] = np.abs(net[W:])[ok] / noise[ok]
    prev_er = np.concatenate([[np.nan], er[:-1]])
    for theta in (0.62, 0.65, 0.68):
        x = (er > theta) & ~(prev_er > theta)
        x[:WARMUP] = False
        ls = x & (net > 0); ss = x & (net < 0)
        if int(ls.sum() + ss.sum()) < 100:
            print(f'  W={W} th={theta}: events={int(ls.sum()+ss.sum())} — کم', flush=True)
            continue
        tdf = se.simulate_trades(df, ls, ss, sl_pip=slp, tp_pip=tpp,
                                 asset='XAUUSD', max_hold=HOLD, allow_overlap=False)
        pnl = tdf['pnl_pip'].values
        eb = tdf['entry_bar'].values
        wr = float((pnl > 0).mean() * 100)
        pf = pf_of(pnl); pf1 = pf_of(pnl[eb < HALF]); pf2 = pf_of(pnl[eb >= HALF])
        sig_bars = tdf['signal_bar'].values.astype(int)
        rng = np.random.default_rng(SEED + W * 100 + int(theta * 1000))
        wrs = []
        for _ in range(K_NULL):
            dirs = rng.integers(0, 2, size=len(sig_bars)).astype(bool)
            lm = np.zeros(n, bool); lm[sig_bars[dirs]] = True
            sm = np.zeros(n, bool); sm[sig_bars[~dirs]] = True
            ptr = se.simulate_trades(df, lm, sm, sl_pip=slp, tp_pip=tpp,
                                     asset='XAUUSD', max_hold=HOLD, allow_overlap=False)
            if len(ptr):
                wrs.append(float((ptr['pnl_pip'].values > 0).mean() * 100))
        nm = float(np.mean(wrs)); nsd = float(np.std(wrs))
        lift = wr - nm
        z = lift / nsd if nsd > 0 else 0.0
        pw = lift * np.sqrt(len(tdf))
        flag = ' <<<' if (lift >= 5 and z >= 2.8 and len(tdf) >= 350 and pf >= 1.1) else ''
        print(f'  W={W} th={theta}: n={len(tdf):5,} WR={wr:5.2f}% null={nm:5.2f}%±{nsd:.2f} '
              f'INFOlift={lift:+6.2f}pp z={z:+4.1f} pw={pw:5.0f} PF={pf:.3f} '
              f'[E1={pf1:.3f} E2={pf2:.3f}]{flag}', flush=True)

print('\n[S833 explore-4 complete]', flush=True)
