# -*- coding: utf-8 -*-
"""
داور مشترک دههٔ S1780–S1789 — ابن هیثم.
هر لایه یک تابع signals(df, ctx) -> (long_sig, short_sig, sl_arr, tp_arr, MH, arm_name)
در ماژول strategies/s17xx_rules.py ثبت می‌کند. این داور:
  - دادهٔ کامل mt5_full (assert)، split_bar = int(0.60·n)
  - نول متعارف: ۴۰×بی‌قید هم‌حجم + K=500 جایگشت، seed = شمارهٔ لایه (قانون S78x/S79x)
  - یک فراخوان compute_rqs2 برای هر (کارت، بازو)؛ حکم موتور دست‌نخورده
usage: python3 strategies/s178x_runner.py <layer> <tf> <arm>
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from engine import rqs2
from strategies import s17xx_rules as rules

LAYER = int(sys.argv[1]); TF = sys.argv[2]; ARM = sys.argv[3]
SEED = LAYER; N_PERM = 500; PIP = 0.10
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTD = os.path.join(ROOT, 'results', f'_s{LAYER}'); os.makedirs(OUTD, exist_ok=True)

d = fd.load_fast('XAUUSD', TF)
assert 'mt5_full' in d['src'], f"E-16! src={d['src']}"
df = fd.as_dataframe(d)
n = len(df); t = df['time'].values.astype(np.int64)
split = int(0.60 * n)
print(f'LAYER=S{LAYER} TF={TF} ARM={ARM} | src={d["src"]} | n={n} split_bar={split} '
      f'({np.datetime64(int(t[split]), "s")})', flush=True)

spec = rules.build(LAYER, ARM, df, split)
long_sig, short_sig, sl_arr, tp_arr, MH, n_trials = (spec['long'], spec['short'], spec['sl'],
                                                    spec['tp'], spec['max_hold'], spec['n_trials'])
warm = spec.get('warm', 300)
valid_m = np.zeros(n, bool); valid_m[warm:n - MH - 2] = True
if np.ndim(sl_arr):
    valid_m &= np.isfinite(sl_arr) & (sl_arr > 0)
    sl_arr = np.where(valid_m, sl_arr, 1.0); tp_arr = np.where(valid_m, tp_arr, 1.0)
long_sig = long_sig & valid_m; short_sig = short_sig & valid_m
sl_med = float(np.nanmedian(np.asarray(sl_arr)[long_sig | short_sig])) if np.ndim(sl_arr) else float(sl_arr)
tp_med = float(np.nanmedian(np.asarray(tp_arr)[long_sig | short_sig])) if np.ndim(tp_arr) else float(tp_arr)
print(f'signals: long={long_sig.sum()} short={short_sig.sum()} MH={MH} sl_med={sl_med:.1f} tp_med={tp_med:.1f}', flush=True)

trades = se.simulate_trades(df, long_sig, short_sig, sl_pip=sl_arr, tp_pip=tp_arr,
                            asset='XAUUSD', max_hold=MH, allow_overlap=False)
p = trades['pnl_pip'].values
print(f'TRADES n={len(trades)} WR={np.mean(p > 0)*100:.2f}% net={np.sum(p):+.0f}pip', flush=True)

valid = np.where(valid_m)[0]
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


def draw():
    pick = rng_.choice(valid, size=nL + nS, replace=False)
    ls = np.zeros(n, bool); ss = np.zeros(n, bool)
    ls[pick[:nL]] = True; ss[pick[nL:]] = True
    return wr_of(ls, ss)


uw_l, uw_s = [], []
for _ in range(40):
    wl, ws = draw()
    if not np.isnan(wl): uw_l.append(wl)
    if not np.isnan(ws): uw_s.append(ws)
uncond_l = float(np.mean(uw_l)) * 100 if uw_l else 50.0
uncond_s = float(np.mean(uw_s)) * 100 if uw_s else 50.0
print(f'uncond null: long={uncond_l:.2f}% short={uncond_s:.2f}%', flush=True)

perm_l, perm_s = [], []; t0 = time.time()
for k in range(N_PERM):
    wl, ws = draw()
    if not np.isnan(wl): perm_l.append(wl * 100)
    if not np.isnan(ws): perm_s.append(ws * 100)
    if (k + 1) % 100 == 0:
        print(f'  perm {k+1}/{N_PERM} ({time.time()-t0:.0f}s)', flush=True)


def side_null(vals, fallback):
    if len(vals) < 10:
        return {'uncond_wr': fallback, 'perm_mean': fallback, 'perm_sd': 5.0,
                'perm_max': fallback, 'perm_k': max(len(vals), 1)}
    return {'uncond_wr': fallback, 'perm_mean': float(np.mean(vals)),
            'perm_sd': float(np.std(vals, ddof=1)), 'perm_max': float(np.max(vals)),
            'perm_k': len(vals)}


null = {'long': side_null(perm_l, uncond_l), 'short': side_null(perm_s, uncond_s)}
res = rqs2.compute_rqs2(trades, 'XAUUSD', sl_pip=sl_med, tp_pip=tp_med, bar_time=t,
                        null=null, n_trials=n_trials, split_bar=split,
                        close=df['close'].values.astype(float))
out = {'layer': LAYER, 'tf': TF, 'arm': ARM, 'null': null, 'verdict': res['verdict'],
       'rqs2_score': res['rqs2_score'],
       'gates': {k: (bool(vv) if vv is not None else None) for k, vv in res['gates'].items()},
       'metrics': {k: (float(vv) if isinstance(vv, (int, float, np.floating)) else vv)
                   for k, vv in res['metrics'].items()},
       'notes': res['notes'], 'n_trades': int(len(trades)), 'src': d['src'],
       'split_bar': int(split), 'n_trials': n_trials, 'sl_med': sl_med, 'tp_med': tp_med}
trades.to_csv(os.path.join(OUTD, f's{LAYER}_{TF}_{ARM}_trades.csv'), index=False)
json.dump(out, open(os.path.join(OUTD, f's{LAYER}_{TF}_{ARM}_result.json'), 'w'), indent=1, default=str)
m = res['metrics']
print('\n================= VERDICT =================', flush=True)
print(f"S{LAYER}-{TF}-{ARM} | {res['verdict']} RQS2={res['rqs2_score']} | n={len(trades)} "
      f"WR={m.get('win_rate')} lift={m.get('skill_lift_pp')} z={m.get('skill_z')} "
      f"p={m.get('skill_p_perm')} PF={m.get('profit_factor')} net=${m.get('net_profit')}", flush=True)
print('  gates: ' + ' '.join(f"H{i}{'✓' if res['gates'][f'H{i}'] else '✗'}" for i in range(11)), flush=True)
print('  oos:', m.get('oos'), flush=True)
for nt in res['notes']:
    print('  note:', nt, flush=True)
