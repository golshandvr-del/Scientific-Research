# -*- coding: utf-8 -*-
"""
S833 — کاوشِ ۳: هندسه‌سنجیِ سیگنالِ ER-cont — فقط ۶۰٪ اکتشاف H1
====================================================================
یافته‌ی کاوش ۲: جهتِ cont واقعی است (پادتقارنِ کاملِ cont+/rev− در ۱۵ سلول)
اما lift پایدار ≈ +3pp < گیتِ 4pp. پرسش: آیا هندسه‌ی براکت (RR/hold) می‌تواند
سهمِ اطلاعاتی را بهتر برداشت کند؟ (سنجه همچنان INFO-lift هم‌هندسه — منصفانه،
چون null هم با همان هندسه اجرا می‌شود؛ این بهینه‌سازیِ برداشتِ سیگنال است نه توهم.)
شبکه: (W,θ) ∈ {(13,0.6), (21,0.7)} × RR ∈ {1.3, 2.0, 3.4} × hold ∈ {13, 34, 55}
ثابت: TF=H1، SLM=2.0، cont only، K=120.
"""
import sys, os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

WARMUP = 200
K_NULL = 120
SEED = 833003
SLM = 2.0

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

dc = np.abs(np.diff(c, prepend=c[0]))
cs_abs = np.cumsum(np.concatenate([[0.0], dc]))
print(f'explore bars={n:,}  src={d["src"]}', flush=True)

def signals(W, theta):
    net = np.full(n, np.nan)
    net[W:] = c[W:] - c[:-W]
    noise = cs_abs[W+1:] - cs_abs[1:-W]
    er = np.full(n, np.nan)
    ok = noise > 0
    er[W:][ok] = np.abs(net[W:])[ok] / noise[ok]
    prev_er = np.concatenate([[np.nan], er[:-1]])
    x = (er > theta) & ~(prev_er > theta)
    x[:WARMUP] = False
    return x & (net > 0), x & (net < 0)

for (W, theta) in ((13, 0.6), (21, 0.7)):
    ls, ss = signals(W, theta)
    print(f'\n===== W={W} th={theta} cont (L={int(ls.sum())} S={int(ss.sum())}) =====', flush=True)
    for RR in (1.3, 2.0, 3.4):
        tpp = slp * RR
        for HOLD in (13, 34, 55):
            tdf = se.simulate_trades(df, ls, ss, sl_pip=slp, tp_pip=tpp,
                                     asset='XAUUSD', max_hold=HOLD,
                                     allow_overlap=False)
            if len(tdf) < 60:
                continue
            pnl = tdf['pnl_pip'].values
            eb = tdf['entry_bar'].values
            wr = float((pnl > 0).mean() * 100)
            pf = pf_of(pnl); pf1 = pf_of(pnl[eb < HALF]); pf2 = pf_of(pnl[eb >= HALF])
            sig_bars = tdf['signal_bar'].values.astype(int)
            rng = np.random.default_rng(SEED + W * 1000 + int(RR * 10) + HOLD)
            wrs = []
            for _ in range(K_NULL):
                dirs = rng.integers(0, 2, size=len(sig_bars)).astype(bool)
                lm = np.zeros(n, bool); lm[sig_bars[dirs]] = True
                sm = np.zeros(n, bool); sm[sig_bars[~dirs]] = True
                ptr = se.simulate_trades(df, lm, sm, sl_pip=slp, tp_pip=tpp,
                                         asset='XAUUSD', max_hold=HOLD,
                                         allow_overlap=False)
                if len(ptr):
                    wrs.append(float((ptr['pnl_pip'].values > 0).mean() * 100))
            nm = float(np.mean(wrs)); nsd = float(np.std(wrs))
            lift = wr - nm
            z = lift / nsd if nsd > 0 else 0.0
            pw = lift * np.sqrt(len(tdf))
            flag = ' <<<' if (lift >= 4 and z >= 2.5 and pf >= 1.15 and pw >= 78) else ''
            print(f'  RR={RR} hold={HOLD}: n={len(tdf):5,} WR={wr:5.2f}% '
                  f'null={nm:5.2f}%±{nsd:.2f} INFOlift={lift:+6.2f}pp z={z:+4.1f} '
                  f'pw={pw:5.0f} PF={pf:.3f} [E1={pf1:.3f} E2={pf2:.3f}]{flag}', flush=True)

print('\n[S833 explore-3 complete]', flush=True)
