# -*- coding: utf-8 -*-
"""
داور رسمی معوقه‌های دههٔ S780–S789 — طبق strategies/S78x_PREREG_ADJUDICATIONS.md
(کامیت a14c73b9، پیش از لمس هر دادهٔ داوری). یک فراخوان compute_rqs2 برای هر
لایه روی دادهٔ کامل mt5_full؛ split_bar = مرز اکتشاف همان لایه؛ نول متعارف =
۴۰×بی‌قید + K=500 جایگشت (seed=شمارهٔ لایه). حکم موتور هر چه بود همان است.
usage: python3 s78x_final_adjudicator.py {782|785|786|787|788|789}
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from engine import rqs2

LAYER = int(sys.argv[1])
CFG = {
    782: dict(tf='H1',  n_trials=32),
    785: dict(tf='H6',  n_trials=80),
    786: dict(tf='H2',  n_trials=128),
    787: dict(tf='H12', n_trials=112),
    788: dict(tf='H2',  n_trials=240),
    789: dict(tf='H12', n_trials=145),
}[LAYER]
TF = CFG['tf']
SEED = LAYER; N_PERM = 500; PIP = 0.10
HERE = os.path.dirname(os.path.abspath(__file__))
HOLDOUT_EPOCH_782 = 1_661_990_400

d = fd.load_fast('XAUUSD', TF)
assert 'mt5_full' in d['src'], f"E-16! src={d['src']}"
df = fd.as_dataframe(d)
t = df['time'].values.astype(np.int64)
o = df['open'].values.astype(float); h = df['high'].values.astype(float)
l = df['low'].values.astype(float);  c = df['close'].values.astype(float)
v = df['volume'].values.astype(float)
n = len(df)
print(f'LAYER=S{LAYER} | src={d["src"]} | TF={TF} | n={n}', flush=True)


def causal_atr(period=89):
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).rolling(period).mean().shift(1).values


long_sig = np.zeros(n, bool); short_sig = np.zeros(n, bool)

if LAYER == 782:
    from engine import indicator_bank as ib
    split = int(np.searchsorted(t, HOLDOUT_EPOCH_782))
    atr34 = causal_atr(34)
    disc_med = float(np.nanmedian(atr34[:split])) / PIP
    SL = round(2.23 * disc_med, 1); TP = round(2.68 * disc_med, 1)
    MH = fd.hold_bars_for(TF, 72)
    up = np.nan_to_num(np.asarray(ib.compute('cdl_3whitesoldiers', df), float)) != 0
    dn = np.nan_to_num(np.asarray(ib.compute('cdl_3blackcrows', df), float)) != 0
    long_sig, short_sig = up, dn
    sl_arr = SL; tp_arr = TP
    sl_med, tp_med = SL, TP

elif LAYER == 785:
    split = int(0.60 * n)
    atr89 = causal_atr(89)
    disc_med = float(np.nanmedian(atr89[:split])) / PIP
    SL = round(2.058 * disc_med, 1); TP = round(1.0 * SL, 1)
    MH = 34
    thr = pd.Series(v).rolling(233).quantile(0.943).shift(1).values
    shock = np.isfinite(thr) & (v >= thr)
    body = c - o
    pc1 = np.roll(c, 1); pc1[0] = np.nan
    drift = pc1 - np.roll(c, 56); drift[:57] = np.nan
    long_sig = shock & (body > 0) & (drift > 0)
    short_sig = shock & (body < 0) & (drift < 0)
    sl_arr = SL; tp_arr = TP; sl_med, tp_med = SL, TP

elif LAYER == 786:
    split = int(0.60 * n)
    atr89 = causal_atr(89)
    disc_med = float(np.nanmedian(atr89[:split])) / PIP
    SL = round(2.058 * disc_med, 1); TP = round(1.272 * SL, 1)
    MH = 34
    rng = h - l
    rng_safe = np.where(rng > 0, rng, np.nan)
    lo_share = (np.minimum(o, c) - l) / rng_safe
    up_share = (h - np.maximum(o, c)) / rng_safe
    pc1 = np.roll(c, 1); pc1[0] = np.nan
    drift89 = pc1 - np.roll(c, 90); drift89[:91] = np.nan
    big = np.isfinite(atr89) & (rng >= 1.272 * atr89)
    long_sig = big & (lo_share >= 0.618) & (drift89 > 0)
    short_sig = big & (up_share >= 0.618) & (drift89 < 0)
    sl_arr = SL; tp_arr = TP; sl_med, tp_med = SL, TP

elif LAYER == 787:
    split = int(0.60 * n)
    atr89 = causal_atr(89)
    disc_med = float(np.nanmedian(atr89[:split])) / PIP
    SL = round(2.058 * disc_med, 1); TP = round(1.0 * SL, 1)
    MH = 21
    r = np.sign(np.diff(c, prepend=c[0]))
    cnt = np.zeros(n)
    for i in range(1, n):
        if r[i] > 0:   cnt[i] = cnt[i-1] + 1 if cnt[i-1] > 0 else 1
        elif r[i] < 0: cnt[i] = cnt[i-1] - 1 if cnt[i-1] < 0 else -1
        else:          cnt[i] = 0
    long_sig = (cnt == 5)
    short_sig = (cnt == -5)
    sl_arr = SL; tp_arr = TP; sl_med, tp_med = SL, TP

elif LAYER == 788:
    split = int(0.60 * n)
    atr89 = causal_atr(89)
    peak = pd.Series(c).rolling(89).max().shift(1).values
    dd = peak - c
    thr = 2.618 * atr89
    armed = True
    for i in range(n):
        if not (np.isfinite(dd[i]) and np.isfinite(thr[i])):
            continue
        if dd[i] <= 0:
            armed = True
        elif armed and dd[i] >= thr[i]:
            short_sig[i] = True
            armed = False
    MH = 21
    sl_dyn = np.where(np.isfinite(atr89), 2.058 * atr89 / PIP, 0.0)
    sl_arr = sl_dyn; tp_arr = sl_dyn
    valid_m = np.isfinite(atr89)
    long_sig &= valid_m; short_sig &= valid_m
    sl_med = float(np.nanmedian(sl_dyn[sl_dyn > 0])); tp_med = sl_med

elif LAYER == 789:
    split = int(0.60 * n)
    atr89 = causal_atr(89)
    roll_hi = pd.Series(h).rolling(144).max().shift(1).values
    roll_lo = pd.Series(l).rolling(144).min().shift(1).values
    last_hi = -10**9; last_lo = -10**9
    for i in range(n):
        if np.isfinite(roll_hi[i]) and h[i] > roll_hi[i]:
            if i - last_hi >= 21: long_sig[i] = True
            last_hi = i
        if np.isfinite(roll_lo[i]) and l[i] < roll_lo[i]:
            if i - last_lo >= 21: short_sig[i] = True
            last_lo = i
    MH = 21
    sl_dyn = np.where(np.isfinite(atr89), 1.618 * atr89 / PIP, 0.0)
    sl_arr = sl_dyn; tp_arr = np.round(1.272 * sl_dyn, 2)
    valid_m = np.isfinite(atr89)
    long_sig &= valid_m; short_sig &= valid_m
    sl_med = float(np.nanmedian(sl_dyn[sl_dyn > 0])); tp_med = round(1.272 * sl_med, 1)

print(f'split_bar={split} ({np.datetime64(int(t[split]), "s")})', flush=True)
print(f'signals: long={long_sig.sum()} short={short_sig.sum()}  MH={MH}', flush=True)

trades = se.simulate_trades(df, long_sig, short_sig, sl_pip=sl_arr, tp_pip=tp_arr,
                            asset='XAUUSD', max_hold=MH, allow_overlap=False)
p = trades['pnl_pip'].values
print(f'TRADES n={len(trades)}  WR={np.mean(p > 0)*100:.2f}%  net={np.sum(p):+.0f}pip', flush=True)
trades.to_json(os.path.join(HERE, f's{LAYER}_trades_{TF}.json'), orient='records')

valid = np.arange(n)
valid = valid[(valid > 300) & (valid < n - MH - 2)]
if LAYER in (788, 789):
    valid = valid[np.isfinite(causal_atr(89))[valid]]
rng_ = np.random.default_rng(SEED)
nL, nS = int(long_sig.sum()), int(short_sig.sum())


def wr_of(ls, ss):
    tr2 = se.simulate_trades(df, ls, ss, sl_pip=sl_arr, tp_pip=tp_arr,
                             asset='XAUUSD', max_hold=MH, allow_overlap=False)
    if len(tr2) == 0:
        return np.nan, np.nan
    isl = tr2['direction'].values == 'long'
    wl = float(np.mean(tr2.loc[isl, 'pnl_pip'] > 0)) if isl.sum() else np.nan
    ws = float(np.mean(tr2.loc[~isl, 'pnl_pip'] > 0)) if (~isl).sum() else np.nan
    return wl, ws


uw_l, uw_s = [], []
for _ in range(40):
    pick = rng_.choice(valid, size=nL + nS, replace=False)
    ls = np.zeros(n, bool); ss = np.zeros(n, bool)
    ls[pick[:nL]] = True; ss[pick[nL:]] = True
    wl, ws = wr_of(ls, ss)
    if not np.isnan(wl): uw_l.append(wl)
    if not np.isnan(ws): uw_s.append(ws)
uncond_l = float(np.mean(uw_l)) * 100 if uw_l else 50.0
uncond_s = float(np.mean(uw_s)) * 100 if uw_s else 50.0
print(f'uncond null: long={uncond_l:.2f}%  short={uncond_s:.2f}%', flush=True)

perm_l, perm_s = [], []
t0 = time.time()
for kperm in range(N_PERM):
    pick = rng_.choice(valid, size=nL + nS, replace=False)
    ls = np.zeros(n, bool); ss = np.zeros(n, bool)
    ls[pick[:nL]] = True; ss[pick[nL:]] = True
    wl, ws = wr_of(ls, ss)
    if not np.isnan(wl): perm_l.append(wl * 100)
    if not np.isnan(ws): perm_s.append(ws * 100)
    if (kperm + 1) % 100 == 0:
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
    trades, 'XAUUSD', sl_pip=sl_med, tp_pip=tp_med,
    bar_time=t, null=null, n_trials=CFG['n_trials'],
    split_bar=split, close=c,
)
out = {'layer': LAYER, 'tf': TF, 'null': null, 'verdict': res['verdict'],
       'rqs2_score': res['rqs2_score'],
       'gates': {k: (bool(vv) if vv is not None else None) for k, vv in res['gates'].items()},
       'metrics': {k: (float(vv) if isinstance(vv, (int, float, np.floating)) else vv)
                   for k, vv in res['metrics'].items()},
       'notes': res['notes'], 'n_trades': int(len(trades)),
       'src': d['src'], 'split_bar': int(split), 'n_trials': CFG['n_trials']}
json.dump(out, open(os.path.join(HERE, f's{LAYER}_final_result_{TF}.json'), 'w'),
          indent=1, default=str)
print('\n================= VERDICT =================', flush=True)
print(f'S{LAYER} verdict:', res['verdict'], ' score:', res['rqs2_score'], flush=True)
for g, vv in res['gates'].items():
    print(f'  {g}: {vv}', flush=True)
for nt in res['notes']:
    print('  note:', nt, flush=True)
