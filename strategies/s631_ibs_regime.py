# -*- coding: utf-8 -*-
"""
S631 — IBS رژیم‌گیت‌شده — آزمون hold-out پیش‌ثبت‌شده (research/S631_PREREG.md)
================================================================================
XAUUSD H1 | نیمهٔ دوم داده | یک اجرا، بدون تکرار.
لانگ: عبور mean(IBS,5) زیر 0.235 فقط اگر close>SMA144
شورت: عبور mean(IBS,5) بالای 0.765 فقط اگر close<SMA144
SL=TP=1.5×median(ATR100) | max_hold=64 | بدون همپوشانی | n_trials=2
نول: ① بی‌قیدِ گیت‌خورده هر سمت مستقل (stride 3/7/13 → بیشینه) ② جایگشت K=1000 seed=631631
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from engine import rqs2 as R

ASSET, TF = 'XAUUSD', 'H1'
K_IBS, THR = 5, 0.235
SMA_P, MAX_HOLD = 144, 64
PERM_K, SEED, N_TRIALS = 1000, 631631, 2

OUTD = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results', '_s631')
os.makedirs(OUTD, exist_ok=True)

# ---------- داده: فقط نیمهٔ دوم ----------
d = fd.load_fast(ASSET, TF)
df_full = fd.as_dataframe(d)
half = len(df_full)//2
df = df_full.iloc[half:].reset_index(drop=True)
print(f"src={d.get('src','?')} full_bars={len(df_full)} holdout_bars={len(df)}", flush=True)

h, l, c = df['high'].values, df['low'].values, df['close'].values
rng = h - l
ibs = np.where(rng > 0, (c - l)/np.where(rng > 0, rng, 1.0), 0.5)
ibs_k = pd.Series(ibs).rolling(K_IBS).mean()
lo_raw = ((ibs_k.shift(1) >= THR) & (ibs_k < THR)).fillna(False)
hi_raw = ((ibs_k.shift(1) <= 1-THR) & (ibs_k > 1-THR)).fillna(False)

cs = pd.Series(c)
sma = cs.rolling(SMA_P).mean()
up = (cs > sma).fillna(False)
dn = (cs < sma).fillna(False)
lo_sig = (lo_raw & up).fillna(False)
hi_sig = (hi_raw & dn).fillna(False)

tr_ = np.maximum(h-l, np.maximum(abs(h-np.roll(c,1)), abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
atr = pd.Series(tr_).rolling(100).mean().values
sl_pip = float(np.nanmedian(atr))*1.5/0.1
tp_pip = sl_pip
print(f"signals: long={int(lo_sig.sum())} short={int(hi_sig.sum())} | SL=TP={sl_pip:.1f} pip", flush=True)

# ---------- شبیه‌سازی لایه ----------
empty = pd.Series(False, index=df.index)
tr = se.simulate_trades(df, lo_sig, hi_sig, sl_pip=sl_pip, tp_pip=tp_pip,
                        asset=ASSET, max_hold=MAX_HOLD, allow_overlap=False)
n = len(tr)
wr = 100*float((tr['outcome']=='win').mean()) if n else 0.0
nl = int((tr['direction']=='long').sum()); ns = int((tr['direction']=='short').sum())
print(f"trades n={n} (L={nl}/S={ns}) WR={wr:.2f}%", flush=True)

# ---------- نول ① : بی‌قیدِ گیت‌خورده، هر سمت مستقل، سخت‌ترین stride ----------
def uncond_side(gate, side, stride):
    base = pd.Series(False, index=df.index); base.iloc[::stride] = True
    sig = (base & gate).fillna(False)
    lo_, hi_ = (sig, empty) if side == 'long' else (empty, sig)
    t = se.simulate_trades(df, lo_, hi_, sl_pip=sl_pip, tp_pip=tp_pip,
                           asset=ASSET, max_hold=MAX_HOLD, allow_overlap=False)
    t = t[t['direction'] == side]
    if len(t) == 0: return None
    return 100*float((t['outcome']=='win').mean())

uncond = {}
for side, gate in [('long', up), ('short', dn)]:
    vals = [v for v in (uncond_side(gate, side, s) for s in (3,7,13)) if v is not None]
    uncond[side] = max(vals) if vals else None
print(f"uncond (hardest): long={uncond['long']:.2f} short={uncond['short']:.2f}", flush=True)

# ---------- نول ② : جایگشت زمانی درون گیت، همان تعداد سیگنال هر سمت ----------
rs = np.random.RandomState(SEED)
up_idx = np.where(up.values)[0]
dn_idx = np.where(dn.values)[0]
n_lo, n_hi = int(lo_sig.sum()), int(hi_sig.sum())

def perm_stats(side):
    idx_pool = up_idx if side == 'long' else dn_idx
    n_sig = n_lo if side == 'long' else n_hi
    wrs = []
    for _ in range(PERM_K):
        pick = rs.choice(idx_pool, size=min(n_sig, len(idx_pool)), replace=False)
        sig = pd.Series(False, index=df.index); sig.iloc[pick] = True
        lo_, hi_ = (sig, empty) if side == 'long' else (empty, sig)
        t = se.simulate_trades(df, lo_, hi_, sl_pip=sl_pip, tp_pip=tp_pip,
                               asset=ASSET, max_hold=MAX_HOLD, allow_overlap=False)
        t = t[t['direction'] == side]
        if len(t): wrs.append(100*float((t['outcome']=='win').mean()))
    a = np.array(wrs)
    return dict(perm_mean=float(a.mean()), perm_sd=float(a.std(ddof=1)),
                perm_max=float(a.max()), perm_k=len(a))

null = {}
for side in ('long', 'short'):
    st = perm_stats(side)
    null[side] = dict(uncond_wr=uncond[side], **st)
    print(f"perm {side}: mean={st['perm_mean']:.2f} sd={st['perm_sd']:.2f} max={st['perm_max']:.2f} k={st['perm_k']}", flush=True)

with open(os.path.join(OUTD, 'null_model.json'), 'w') as f:
    json.dump(null, f, indent=1)

# ---------- RQS2 ----------
split_bar = int(0.70*len(df))
res = R.compute_rqs2(tr, ASSET, sl_pip=sl_pip, tp_pip=tp_pip,
                     bar_time=df['time'], close=df['close'],
                     null=null, n_trials=N_TRIALS, split_bar=split_bar)

with open(os.path.join(OUTD, 'H1_rqs2.json'), 'w') as f:
    json.dump(res, f, indent=1, default=str)
tr.to_csv(os.path.join(OUTD, 'H1_trades.csv'), index=False)

g = res.get('gates', {})
gs = ' '.join(f"H{i}:{'✓' if g.get(f'H{i}',{}).get('pass') else '✗'}" for i in range(11))
print(f"\nS631_IbsRegime_H1_holdout | {res.get('verdict')} RQS2={res.get('score')} | n={n} WR={wr:.2f}% | {gs}", flush=True)
print(json.dumps({k: res[k] for k in res if k != 'gates'}, indent=1, default=str), flush=True)
