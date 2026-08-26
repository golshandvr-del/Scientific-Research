# -*- coding: utf-8 -*-
"""
داور رسمی معوقه‌های بلوک S790–S799 — طبق strategies/S791_S793_S794_S795_PREREG_ADJUDICATIONS.md
(کامیت 97e21cfc، پیش از هر لمس نیمهٔ دوم). یک فراخوان compute_rqs2 برای هر لایه،
split_bar=n//2، null متعارف = ۴۰×بی‌قید + K=500 جایگشت (seed=شمارهٔ لایه).
usage: python3 s79x_final_adjudicator.py {791|793|794|795}
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from engine import rqs2

LAYER = int(sys.argv[1])
CFG = {
    791: dict(tf='M15', n_trials=64, mh=192, ksl=2.618),
    793: dict(tf='H3',  n_trials=55, mh=21,  ksl=2.618),
    794: dict(tf='H1',  n_trials=60, mh=13,  ksl=1.618),
    795: dict(tf='H3',  n_trials=45, mh=24,  ksl=4.236),
}[LAYER]
TF = CFG['tf']; MH = CFG['mh']; KSL = CFG['ksl']
SEED = LAYER; N_PERM = 500; PIP = 0.10
HERE = os.path.dirname(os.path.abspath(__file__))

d = fd.load_fast('XAUUSD', TF)
df = fd.as_dataframe(d)
print(f'LAYER=S{LAYER} | src={d["src"]} | TF={TF}', flush=True)
t = df['time'].values.astype(np.int64)
o = df['open'].values; h = df['high'].values; l = df['low'].values; c = df['close'].values
n = len(df); split = n // 2
print(f'FULL DATA: {np.datetime64(int(t[0]),"s")} → {np.datetime64(int(t[-1]),"s")} '
      f'({n} bars, split_bar={split})', flush=True)

# ATR89 (EMA alpha=2/90) shifted 1
tr_ = np.maximum(h - l, np.maximum(np.abs(h - np.r_[c[0], c[:-1]]),
                                   np.abs(l - np.r_[c[0], c[:-1]])))
atr = np.empty(n); a = tr_[0]; kk = 2.0 / 90.0
for i in range(n):
    a = a + kk * (tr_[i] - a); atr[i] = a
atr = np.r_[np.nan, atr[:-1]]
sl_arr = np.where(np.isnan(atr), 0.0, KSL * atr / PIP)

long_sig = np.zeros(n, bool); short_sig = np.zeros(n, bool)

if LAYER == 791:
    # Regime-Aligned ORB M15: 20-bar OR, close-break + thrust>=0.236*ATR89, drift L=144 days
    day = t // 86400
    day_id = np.cumsum(np.r_[True, np.diff(day) != 0]) - 1
    n_days = day_id[-1] + 1
    day_start = np.zeros(n_days, np.int64); seen = np.zeros(n_days, bool)
    for i in range(n):
        dd = day_id[i]
        if not seen[dd]: seen[dd] = True; day_start[dd] = i
    day_end = np.r_[day_start[1:], n]
    day_close = np.array([c[day_end[dd]-1] for dd in range(n_days)])
    L = 144; THR = 0.236; BARS_OR = 20
    drift = np.zeros(n_days)
    for dd in range(n_days):
        if dd - 1 - L >= 0: drift[dd] = day_close[dd-1] - day_close[dd-1-L]
    for dd in range(1, n_days):
        s0, e0 = day_start[dd], day_end[dd]
        if e0 - s0 < BARS_OR + 2: continue
        ds = np.sign(drift[dd])
        if ds == 0: continue
        orb_hi = np.max(h[s0:s0+BARS_OR]); orb_lo = np.min(l[s0:s0+BARS_OR])
        aref = atr[s0+BARS_OR]
        if not np.isfinite(aref) or aref <= 0: continue
        for j in range(s0+BARS_OR, e0-1):
            if c[j] > orb_hi:
                if ds > 0 and (c[j]-orb_hi)/aref >= THR: long_sig[j] = True
                break
            if c[j] < orb_lo:
                if ds < 0 and (orb_lo-c[j])/aref >= THR: short_sig[j] = True
                break

elif LAYER == 793:
    # Drift-Aligned Streak Pullback H3: run==2 counter-drift closes, enter with drift
    drift = np.full(n, np.nan); drift[90:] = c[89:-1] - c[:n-90]
    pc = np.r_[c[0], c[:-1]]
    dn = (c < pc).astype(int); up = (c > pc).astype(int)
    rd = np.zeros(n, int); ru = np.zeros(n, int)
    for i in range(1, n):
        rd[i] = rd[i-1] + 1 if dn[i] else 0
        ru[i] = ru[i-1] + 1 if up[i] else 0
    valid0 = ~np.isnan(atr) & ~np.isnan(drift)
    long_sig = valid0 & (drift > 0) & (rd == 2)
    short_sig = valid0 & (drift < 0) & (ru == 2)

elif LAYER == 794:
    # First-Bar Fade H1: |r_first|>=0.09*ADR21 (causal), fade
    import pandas as pd
    tf_sec = fd.TF_MINUTES[TF]*60
    gap = np.r_[10**9, np.diff(t)]
    day_start_m = gap > max(1800, int(1.5*tf_sec))
    first_idx = np.where(day_start_m)[0]; n_days = len(first_idx)
    day_hi = np.full(n_days, np.nan); day_lo = np.full(n_days, np.nan)
    for k in range(n_days):
        a0_, b0_ = first_idx[k], first_idx[k+1] if k+1 < n_days else n
        day_hi[k] = h[a0_:b0_].max(); day_lo[k] = l[a0_:b0_].min()
    adr = pd.Series(day_hi-day_lo).rolling(21).mean().shift(1).values
    for k in range(n_days):
        i = first_idx[k]
        if np.isnan(adr[k]) or adr[k] <= 0: continue
        r1 = c[i] - o[i]
        if abs(r1) < 0.09 * adr[k]: continue
        if r1 > 0: short_sig[i] = True
        elif r1 < 0: long_sig[i] = True

elif LAYER == 795:
    # Pre-EOM Short H3: last trading day of month, short at its open
    import pandas as pd
    tt = pd.to_datetime(t, unit='s')
    tf_sec = fd.TF_MINUTES[TF]*60
    gap = np.r_[10**9, np.diff(t)]
    day_start_m = gap > max(1800, int(1.5*tf_sec))
    first_idx = np.where(day_start_m)[0]; n_days = len(first_idx)
    day_month = np.array([tt[i].year*12 + tt[i].month for i in first_idx])
    mfd = np.r_[0, np.where(np.diff(day_month) != 0)[0] + 1]
    for mi, m0 in enumerate(mfd):
        m1 = mfd[mi+1] if mi+1 < len(mfd) else n_days
        k_last = m1 - 1                     # last trading day of this month
        if mi + 1 >= len(mfd): continue     # current month may be unfinished
        i = first_idx[k_last]
        if i - 1 >= 0: short_sig[i-1] = True

valid_atr = ~np.isnan(atr)
long_sig &= valid_atr; short_sig &= valid_atr
print(f'signals: long={long_sig.sum()} short={short_sig.sum()}', flush=True)

trades = se.simulate_trades(df, long_sig, short_sig, sl_pip=sl_arr, tp_pip=sl_arr,
                            asset='XAUUSD', max_hold=MH, allow_overlap=False)
p = trades['pnl_pip'].values
print(f'TRADES n={len(trades)}  WR={np.mean(p>0)*100:.2f}%  net={np.sum(p):+.0f}pip', flush=True)
trades.to_json(os.path.join(HERE, f's{LAYER}_trades_{TF}.json'), orient='records')

valid = np.where(valid_atr)[0]
valid = valid[(valid > 200) & (valid < n - MH - 2)]
rng = np.random.default_rng(SEED)
nL, nS = int(long_sig.sum()), int(short_sig.sum())

def wr_of(ls, ss):
    tr2 = se.simulate_trades(df, ls, ss, sl_pip=sl_arr, tp_pip=sl_arr,
                             asset='XAUUSD', max_hold=MH, allow_overlap=False)
    if len(tr2) == 0: return np.nan, np.nan
    isl = tr2['direction'].values == 'long'
    wl = float(np.mean(tr2.loc[isl, 'pnl_pip'] > 0)) if isl.sum() else np.nan
    ws = float(np.mean(tr2.loc[~isl, 'pnl_pip'] > 0)) if (~isl).sum() else np.nan
    return wl, ws

uw_l, uw_s = [], []
for _ in range(40):
    pick = rng.choice(valid, size=nL+nS, replace=False)
    ls = np.zeros(n, bool); ss = np.zeros(n, bool)
    ls[pick[:nL]] = True; ss[pick[nL:]] = True
    wl, ws = wr_of(ls, ss)
    if not np.isnan(wl): uw_l.append(wl)
    if not np.isnan(ws): uw_s.append(ws)
uncond_l = float(np.mean(uw_l))*100 if uw_l else 50.0
uncond_s = float(np.mean(uw_s))*100 if uw_s else 50.0
print(f'uncond null: long={uncond_l:.2f}%  short={uncond_s:.2f}%', flush=True)

perm_l, perm_s = [], []
t0 = time.time()
for kperm in range(N_PERM):
    pick = rng.choice(valid, size=nL+nS, replace=False)
    ls = np.zeros(n, bool); ss = np.zeros(n, bool)
    ls[pick[:nL]] = True; ss[pick[nL:]] = True
    wl, ws = wr_of(ls, ss)
    if not np.isnan(wl): perm_l.append(wl*100)
    if not np.isnan(ws): perm_s.append(ws*100)
    if (kperm+1) % 100 == 0:
        print(f'  perm {kperm+1}/{N_PERM} ({time.time()-t0:.0f}s)', flush=True)

def side_null(vals, fallback):
    if len(vals) < 10:
        return {'uncond_wr': fallback, 'perm_mean': fallback, 'perm_sd': 5.0,
                'perm_max': fallback, 'perm_k': max(len(vals), 1)}
    return {'uncond_wr': fallback, 'perm_mean': float(np.mean(vals)),
            'perm_sd': float(np.std(vals, ddof=1)), 'perm_max': float(np.max(vals)),
            'perm_k': len(vals)}

null = {'long': side_null(perm_l, uncond_l), 'short': side_null(perm_s, uncond_s)}
print('NULL =', json.dumps(null, indent=1), flush=True)

res = rqs2.compute_rqs2(
    trades, 'XAUUSD',
    sl_pip=float(np.median(trades['sl_pip'].values)),
    tp_pip=float(np.median(trades['sl_pip'].values)),
    bar_time=t, null=null, n_trials=CFG['n_trials'],
    split_bar=split, close=c,
)
out = {'layer': LAYER, 'tf': TF, 'null': null, 'verdict': res['verdict'],
       'rqs2_score': res['rqs2_score'],
       'gates': {k: (bool(v) if v is not None else None) for k, v in res['gates'].items()},
       'metrics': {k: (float(v) if isinstance(v, (int, float, np.floating)) else v)
                   for k, v in res['metrics'].items()},
       'notes': res['notes'], 'n_trades': int(len(trades)),
       'src': d['src'], 'split_bar': int(split), 'n_trials': CFG['n_trials']}
json.dump(out, open(os.path.join(HERE, f's{LAYER}_final_result_{TF}.json'), 'w'),
          indent=1, default=str)
print('\n================= VERDICT =================', flush=True)
print(f'S{LAYER} verdict:', res['verdict'], ' score:', res['rqs2_score'], flush=True)
for g, v in res['gates'].items():
    print(f'  {g}: {v}', flush=True)
for nt in res['notes']:
    print('  note:', nt, flush=True)
