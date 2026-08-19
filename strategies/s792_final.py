# -*- coding: utf-8 -*-
"""
S792 — داوریِ نهایی: Shock-Candle Continuation — XAUUSD-H3 (مسیر C)
================================================================================
طبق strategies/S792_PREREG.md (commit 2bb25319 — پیش از هر نگاه به نیمهٔ دوم):
  رخداد: range>=2.618·ATR89 و clv<=0.236 (SHORT) یا clv>=0.764 (LONG)
  ورود openِ بعد · SL=TP=1.618·ATR89 · mh=21 · overlap ممنوع.
null: بی‌قید ۴۰× + جایگشتِ زمانی K=500 (seed=792) · یک فراخوانِ compute_rqs2
با split_bar=n//2. حکم = خروجیِ موتور.
اجرای دیگر TFها (گزارشی/pooling) با آرگومان TF؛ داوریِ رسمی فقط H3.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from engine import rqs2

TF = sys.argv[1] if len(sys.argv) > 1 else 'H3'
SEED = 792
N_PERM = 500
N_TRIALS = 100
R_TH, Q, K_GEOM, MH = 2.618, 0.236, 1.618, 21
HERE = os.path.dirname(os.path.abspath(__file__))

d = fd.load_fast('XAUUSD', TF)
df = fd.as_dataframe(d)
print('src =', d['src'], '| TF =', TF, flush=True)
t = df['time'].values.astype(np.int64)
h = df['high'].values; l = df['low'].values; c = df['close'].values
n = len(df)
split = n // 2
print(f'FULL DATA: {np.datetime64(int(t[0]),"s")} → {np.datetime64(int(t[-1]),"s")} '
      f'({n} bars, split_bar={split})', flush=True)

tr_ = np.maximum(h - l, np.maximum(np.abs(h - np.r_[c[0], c[:-1]]),
                                   np.abs(l - np.r_[c[0], c[:-1]])))
atr = np.empty(n); a = tr_[0]; kk = 2.0 / 90.0
for i in range(n):
    a = a + kk * (tr_[i] - a); atr[i] = a
atr = np.r_[np.nan, atr[:-1]]

rng_ = h - l
clv = np.where(rng_ > 0, (c - l) / np.where(rng_ > 0, rng_, 1.0), 0.5)
big = rng_ >= R_TH * atr
long_sig = big & (clv >= 1 - Q)
short_sig = big & (clv <= Q)
pip = 0.10
sl_arr = np.where(np.isnan(atr), 0.0, K_GEOM * atr / pip)
print(f'signals: long={long_sig.sum()} short={short_sig.sum()}', flush=True)

trades = se.simulate_trades(df, long_sig, short_sig, sl_pip=sl_arr, tp_pip=sl_arr,
                            asset='XAUUSD', max_hold=MH, allow_overlap=False)
p = trades['pnl_pip'].values
print(f'TRADES n={len(trades)}  WR={np.mean(p>0)*100:.2f}%  net={np.sum(p):+.0f}pip', flush=True)

# ذخیرهٔ معاملات برای pooling/هم‌پوشانیِ احتمالی
trades.to_json(os.path.join(HERE, f's792_trades_{TF}.json'), orient='records')

valid = np.where(~np.isnan(atr))[0]
valid = valid[(valid > 90) & (valid < n - MH - 2)]
rng = np.random.default_rng(SEED)
nL, nS = int(long_sig.sum()), int(short_sig.sum())

def wr_of(ls, ss):
    tr2 = se.simulate_trades(df, ls, ss, sl_pip=sl_arr, tp_pip=sl_arr,
                             asset='XAUUSD', max_hold=MH, allow_overlap=False)
    if len(tr2) == 0:
        return np.nan, np.nan
    isl = tr2['direction'].values == 'long'
    wl = float(np.mean(tr2.loc[isl, 'pnl_pip'] > 0)) if isl.sum() else np.nan
    ws = float(np.mean(tr2.loc[~isl, 'pnl_pip'] > 0)) if (~isl).sum() else np.nan
    return wl, ws

uw_l, uw_s = [], []
for _ in range(40):
    pick = rng.choice(valid, size=nL + nS, replace=False)
    ls = np.zeros(n, bool); ss = np.zeros(n, bool)
    ls[pick[:nL]] = True; ss[pick[nL:]] = True
    wl, ws = wr_of(ls, ss)
    if not np.isnan(wl): uw_l.append(wl)
    if not np.isnan(ws): uw_s.append(ws)
uncond_l = float(np.mean(uw_l)) * 100
uncond_s = float(np.mean(uw_s)) * 100
print(f'uncond null: long={uncond_l:.2f}%  short={uncond_s:.2f}%', flush=True)

perm_l, perm_s = [], []
t0 = time.time()
for kperm in range(N_PERM):
    pick = rng.choice(valid, size=nL + nS, replace=False)
    ls = np.zeros(n, bool); ss = np.zeros(n, bool)
    ls[pick[:nL]] = True; ss[pick[nL:]] = True
    wl, ws = wr_of(ls, ss)
    if not np.isnan(wl): perm_l.append(wl * 100)
    if not np.isnan(ws): perm_s.append(ws * 100)
    if (kperm + 1) % 100 == 0:
        print(f'  perm {kperm+1}/{N_PERM} ({time.time()-t0:.0f}s)', flush=True)

null = {
    'long': {'uncond_wr': uncond_l, 'perm_mean': float(np.mean(perm_l)),
             'perm_sd': float(np.std(perm_l, ddof=1)), 'perm_max': float(np.max(perm_l)),
             'perm_k': len(perm_l)},
    'short': {'uncond_wr': uncond_s, 'perm_mean': float(np.mean(perm_s)),
              'perm_sd': float(np.std(perm_s, ddof=1)), 'perm_max': float(np.max(perm_s)),
              'perm_k': len(perm_s)},
}
print('NULL =', json.dumps(null, indent=1), flush=True)

res = rqs2.compute_rqs2(
    trades, 'XAUUSD',
    sl_pip=float(np.median(trades['sl_pip'].values)),
    tp_pip=float(np.median(trades['sl_pip'].values)),
    bar_time=t, null=null, n_trials=N_TRIALS,
    split_bar=split, close=c,
)
out = {'tf': TF, 'null': null, 'verdict': res['verdict'], 'rqs2_score': res['rqs2_score'],
       'gates': {k: (bool(v) if v is not None else None) for k, v in res['gates'].items()},
       'metrics': {k: (float(v) if isinstance(v, (int, float, np.floating)) else v)
                   for k, v in res['metrics'].items()},
       'notes': res['notes'], 'n_trades': int(len(trades)),
       'src': d['src'], 'split_bar': int(split)}
json.dump(out, open(os.path.join(HERE, f's792_final_result_{TF}.json'), 'w'),
          indent=1, default=str)
print('\n================= VERDICT =================', flush=True)
print('verdict:', res['verdict'], ' score:', res['rqs2_score'], flush=True)
for g, v in res['gates'].items():
    print(f'  {g}: {v}', flush=True)
for nt in res['notes']:
    print('  note:', nt, flush=True)
