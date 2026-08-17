# -*- coding: utf-8 -*-
"""
S632 — IBS لانگ‌تنهای رژیم‌گیت‌شده — آزمون hold-out پیش‌ثبت‌شده (research/S632_PREREG.md)
==========================================================================================
XAUUSD H1 | نیمهٔ دوم | یک اجرا.
لانگ: state mean(IBS,5)<0.28 فقط اگر close>SMA144 | SL=TP=1.5×medATR100 | max_hold=64
n_trials=3 | نول: ① بی‌قید گیت‌خورده stride 3/7/13 بیشینه ② جایگشت K=1000 seed=632632
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from engine import rqs2 as R

ASSET, TF = 'XAUUSD', 'H1'
K_IBS, THR, SMA_P, MAX_HOLD = 5, 0.28, 144, 64
PERM_K, SEED, N_TRIALS = 1000, 632632, 3

OUTD = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results', '_s632')
os.makedirs(OUTD, exist_ok=True)

d = fd.load_fast(ASSET, TF)
df_full = fd.as_dataframe(d)
half = len(df_full)//2
df = df_full.iloc[half:].reset_index(drop=True)
print(f"src={d.get('src','?')} holdout_bars={len(df)}", flush=True)

h, l, c = df['high'].values, df['low'].values, df['close'].values
rng = h - l
ibs = np.where(rng > 0, (c - l)/np.where(rng > 0, rng, 1.0), 0.5)
ibs_k = pd.Series(ibs).rolling(K_IBS).mean()
cs = pd.Series(c)
up = (cs > cs.rolling(SMA_P).mean()).fillna(False)
lo_sig = ((ibs_k < THR) & up).fillna(False)
empty = pd.Series(False, index=df.index)

tr_ = np.maximum(h-l, np.maximum(abs(h-np.roll(c,1)), abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
atr = pd.Series(tr_).rolling(100).mean().values
sl_pip = float(np.nanmedian(atr))*1.5/0.1
tp_pip = sl_pip
print(f"state-bars={int(lo_sig.sum())} | SL=TP={sl_pip:.1f} pip", flush=True)

tr = se.simulate_trades(df, lo_sig, empty, sl_pip=sl_pip, tp_pip=tp_pip,
                        asset=ASSET, max_hold=MAX_HOLD, allow_overlap=False)
tr = tr[tr['direction']=='long'].reset_index(drop=True)
n = len(tr)
wr = 100*float((tr['outcome']=='win').mean()) if n else 0.0
print(f"trades n={n} WR={wr:.2f}% pnl_mean={float(tr['pnl_pip'].mean()):.3f}", flush=True)

# ---------- نول ① ----------
def uncond(stride):
    b = pd.Series(False, index=df.index); b.iloc[::stride]=True
    sig = (b & up).fillna(False)
    t = se.simulate_trades(df, sig, empty, sl_pip=sl_pip, tp_pip=tp_pip,
                           asset=ASSET, max_hold=MAX_HOLD, allow_overlap=False)
    t = t[t['direction']=='long']
    return 100*float((t['outcome']=='win').mean()) if len(t) else None

uvals = [v for v in (uncond(s) for s in (3,7,13)) if v is not None]
uncond_wr = max(uvals)
print(f"uncond hardest={uncond_wr:.2f}", flush=True)

# ---------- نول ② : جایگشت — همان تعداد «معامله» درون گیت ----------
rs = np.random.RandomState(SEED)
up_idx = np.where(up.values)[0]
wrs = []
for _ in range(PERM_K):
    pick = rs.choice(up_idx, size=min(int(lo_sig.sum()), len(up_idx)), replace=False)
    sig = pd.Series(False, index=df.index); sig.iloc[pick] = True
    t = se.simulate_trades(df, sig, empty, sl_pip=sl_pip, tp_pip=tp_pip,
                           asset=ASSET, max_hold=MAX_HOLD, allow_overlap=False)
    t = t[t['direction']=='long']
    if len(t): wrs.append(100*float((t['outcome']=='win').mean()))
a = np.array(wrs)
null = {'long': dict(uncond_wr=uncond_wr, perm_mean=float(a.mean()), perm_sd=float(a.std(ddof=1)),
                     perm_max=float(a.max()), perm_k=len(a))}
print(f"perm: mean={a.mean():.2f} sd={a.std(ddof=1):.2f} max={a.max():.2f} k={len(a)}", flush=True)
with open(os.path.join(OUTD,'null_model.json'),'w') as f: json.dump(null,f,indent=1)

# ---------- RQS2 ----------
split_bar = int(0.70*len(df))
res = R.compute_rqs2(tr, ASSET, sl_pip=sl_pip, tp_pip=tp_pip,
                     bar_time=df['time'], close=df['close'],
                     null=null, n_trials=N_TRIALS, split_bar=split_bar)
with open(os.path.join(OUTD,'H1_rqs2.json'),'w') as f: json.dump(res,f,indent=1,default=str)
tr.to_csv(os.path.join(OUTD,'H1_trades.csv'), index=False)

g = res.get('gates', {})
gs = ' '.join(f"H{i}:{'✓' if g.get(f'H{i}') else '✗'}" for i in range(11))
m = res.get('metrics', {})
print(f"\nS632_IbsLongRegime_H1_holdout | {res.get('verdict')} RQS2={res.get('rqs2_score')} | n={n} WR={wr:.2f}% PF={m.get('profit_factor')} lift={m.get('skill_lift_pp')}pp z={m.get('skill_z')} p_perm={m.get('skill_p_perm')} | {gs}", flush=True)
