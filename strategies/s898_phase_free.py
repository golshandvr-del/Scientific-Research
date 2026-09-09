#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S898 — حرکتِ مطلعِ بی‌فاز (Phase-Free Informed Move) · یک کانفیگ · نالِ کانونی.

قرارداد: results/S898_PREREG_PhaseFreeInformedMove_Xauusd_MTF.md (کامیت 2a88a426)
  - کندل مصنوعی L کندلی (L*TF ≈ 8h): O=open[t-L+1], C=close[t], H=max, Lo=min
  - ATR_syn[t] = میانگین R روی 21 پنجرهٔ ناهم‌پوشِ قبلی که تا t-L پایان یافته‌اند
  - شوک مطلع: R >= 2.618*ATR_syn و rho >= 0.618 ؛ follow ؛ ورود open t+1
  - SL=1.272*ATR_syn ، TP=2.058*ATR_syn ، hold=16*L ، no overlap ، spread 3.3
  - n_trials=19 ؛ نال کانونی uncond {898,1898,2898} + perm K=500 seed 898 هر جهت جدا
  - P1: کارت H8 (L=1) باید S965 را بازتولید کند

اجرا: python3 strategies/s898_phase_free.py H1
"""
import sys, os, json, gc, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from tools import s434_fast_data as fd
from engine import rqs2
from engine import scalp_engine as se

ASSET = 'XAUUSD'; PIP = 0.1; COST_PIP = 3.3
N_TRIALS = 19; PERM_K = 500; PERM_SEED = 898; UNC_SEEDS = (898, 1898, 2898)
OUT = 'results/_s898'; PREREG = '2a88a426'
TH = 2.618; RHO = 0.618; K_SL = 1.272; K_TP = 2.058; HOLD_MULT = 16; NWIN = 21

TF_MIN = {'M1':1,'M3':3,'M4':4,'M5':5,'M6':6,'M10':10,'M12':12,'M15':15,
          'M20':20,'M30':30,'H1':60,'H2':120,'H3':180,'H6':360,'H8':480,
          'H12':720,'D1':1440,'W1':10080,'MN1':43200}
L_OF = {'M1':480,'M3':160,'M4':120,'M5':96,'M6':80,'M10':48,'M12':40,'M15':32,
        'M20':24,'M30':16,'H1':8,'H2':4,'H3':3,'H6':2,'H8':1,'H12':1,'D1':1,'W1':1,'MN1':1}


def rolling_max(a, L):
    return pd.Series(a).rolling(L).max().values


def rolling_min(a, L):
    return pd.Series(a).rolling(L).min().values


def synthetic(df, L):
    o, h, l, c = (df[k].values for k in ('open', 'high', 'low', 'close'))
    N = len(c)
    O = np.full(N, np.nan); O[L - 1:] = o[:N - L + 1]
    H = rolling_max(h, L); Lo = rolling_min(l, L); C = c.copy()
    R = H - Lo
    body = C - O
    with np.errstate(divide='ignore', invalid='ignore'):
        rho = np.where(R > 0, np.abs(body) / R, 0.0)
    # ATR_syn: mean of R over 21 NON-overlapping prior windows ending at t-L, t-2L, ..., t-21L
    atr = np.full(N, np.nan)
    idx = np.arange(N)
    acc = np.zeros(N); cnt = np.zeros(N)
    for k in range(1, NWIN + 1):
        sh = k * L
        v = np.full(N, np.nan); v[sh:] = R[:N - sh]
        ok = ~np.isnan(v)
        acc[ok] += v[ok]; cnt[ok] += 1
    full = cnt == NWIN
    atr[full] = acc[full] / NWIN
    return O, C, H, Lo, R, body, rho, atr


def simulate(df, ls, ss, sl_arr, tp_arr, hold):
    return se.simulate_trades(df, ls, ss, sl_arr, tp_arr, asset=ASSET, max_hold=hold, allow_overlap=False)


def wr_of(tr):
    return 100.0 * float((tr['outcome'] == 'win').mean())


def canonical_null(df, sl_arr, tp_arr, hold, n_long, n_short, warm):
    N = len(df); lo, hi = warm, N - hold - 2
    z = np.zeros(N, dtype=bool); out = {}; unc_all = {}; perm_all = {}
    for side, n_sig in (('long', n_long), ('short', n_short)):
        if n_sig < 5:
            out[side] = dict(uncond_wr=50.0, perm_mean=50.0, perm_sd=0.0, perm_max=50.0, perm_k=0); continue
        unc_rows = []; size = min(20000, max(50, (hi - lo) // max(hold, 1)))
        for seed in UNC_SEEDS:
            rng = np.random.default_rng(seed)
            pos = rng.choice(np.arange(lo, hi), size=min(size, hi - lo), replace=False)
            sig = np.zeros(N, dtype=bool); sig[np.sort(pos)] = True
            tr = simulate(df, sig if side == 'long' else z, sig if side == 'short' else z, sl_arr, tp_arr, hold)
            unc_rows.append((seed, wr_of(tr), len(tr))); del tr; gc.collect()
        rng = np.random.default_rng(PERM_SEED); wrs = []
        for i in range(PERM_K):
            pos = rng.choice(np.arange(lo, hi), size=n_sig, replace=False)
            sig = np.zeros(N, dtype=bool); sig[np.sort(pos)] = True
            tr = simulate(df, sig if side == 'long' else z, sig if side == 'short' else z, sl_arr, tp_arr, hold)
            if tr is not None and len(tr) >= 5: wrs.append(wr_of(tr))
            del tr
            if (i + 1) % 100 == 0: gc.collect(); print(f"  perm[{side}] {i+1}/{PERM_K} …", flush=True)
        a = np.asarray(wrs, float)
        perm = dict(mean=float(a.mean()), sd=float(a.std(ddof=1)), max=float(a.max()), k=int(len(a)))
        out[side] = dict(uncond_wr=max(r[1] for r in unc_rows), perm_mean=perm['mean'], perm_sd=perm['sd'],
                         perm_max=perm['max'], perm_k=perm['k'])
        unc_all[side] = unc_rows; perm_all[side] = perm
    return out, unc_all, perm_all


def _save(tf, obj):
    os.makedirs(OUT, exist_ok=True)
    with open(f'{OUT}/rqs2_XAUUSD-{tf}.json', 'w') as f: json.dump(obj, f, indent=1, default=str)


def run_tf(tf):
    L = L_OF[tf]; hold = HOLD_MULT * L
    print('=' * 72); print(f"S898 Phase-Free Informed Move · XAUUSD-{tf}  L={L} hold={hold} (prereg {PREREG})"); print('=' * 72, flush=True)
    d = fd.load_fast(ASSET, tf); df = fd.as_dataframe(d)
    if 'volume' in df.columns: df = df.drop(columns=['volume'])
    src = d.get('src', '?'); del d; gc.collect()
    N = len(df); split = int(N * 0.70); times = df['time'].values; close = df['close'].values
    O, C, H, Lo, R, body, rho, atr = synthetic(df, L)
    warm = (NWIN + 1) * L + 5
    shock = (R >= TH * atr) & (rho >= RHO) & (body != 0) & ~np.isnan(atr)
    shock[:warm] = False
    sgn = np.sign(body)
    ls = shock & (sgn > 0); ss = shock & (sgn < 0)
    atr_f = np.nan_to_num(atr, nan=np.nanmedian(atr))
    sl_arr = K_SL * atr_f / PIP; tp_arr = K_TP * atr_f / PIP
    print(f"src={src} bars={N} split={split} raw shock phases: long={ls.sum()} short={ss.sum()}", flush=True)
    del O, C, H, Lo, R, body, rho; gc.collect()
    tr = simulate(df, ls, ss, sl_arr, tp_arr, hold)
    if tr is None or len(tr) < 30:
        _save(tf, dict(card=f'XAUUSD-{tf}', prereg=PREREG, verdict='INCOMPLETE', L=L, hold=hold,
                       reason=f'n={0 if tr is None else len(tr)} < 30', src=src, bars=N,
                       phases_long=int(ls.sum()), phases_short=int(ss.sum())))
        print("n<30 → INCOMPLETE"); return
    n_all = len(tr); wr_all = wr_of(tr)
    n_long = int((tr['side'] == 'long').sum()) if 'side' in tr.columns else int(ls.sum())
    n_short = n_all - n_long
    sl_med = float(np.median(tr['sl_pip'].values)); tp_med = sl_med * K_TP / K_SL
    print(f"trades n={n_all} (L{n_long}/S{n_short}) WR={wr_all:.2f} net={tr['pnl_pip'].sum():.0f}pip  SLmed={sl_med:.1f}", flush=True)
    null, unc, perm = canonical_null(df, sl_arr, tp_arr, hold, max(n_long, 5), max(n_short, 5), warm)
    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med, bar_time=times, null=null,
                          n_trials=N_TRIALS, split_bar=split, close=close)
    hm = tr['entry_bar'].values >= split; oos_n = int(hm.sum())
    oos_wr = wr_of(tr.loc[hm]) if oos_n else None
    is_wr = wr_of(tr.loc[~hm]) if (~hm).sum() else None
    m = r.get('metrics', {})
    print(f"IS WR={is_wr}  OOS n={oos_n} WR={oos_wr}")
    print(f"VERDICT: {r.get('verdict')} score={r.get('rqs2_score')} lift={m.get('skill_lift_pp')} z={m.get('skill_z')} p={m.get('skill_p_perm')} PF={m.get('profit_factor')}")
    print(f"gates: {r.get('gates')} notes={r.get('notes')}", flush=True)
    _save(tf, dict(card=f'XAUUSD-{tf}', prereg=PREREG, src=src, bars=N, split=split, L=L, hold=hold,
                   phases_long=int(ls.sum()), phases_short=int(ss.sum()), n=n_all, n_long=n_long, n_short=n_short,
                   wr=round(wr_all, 2), is_wr=round(is_wr, 2) if is_wr else None, oos_n=oos_n,
                   oos_wr=round(oos_wr, 2) if oos_wr else None, sl_pip_med=round(sl_med, 2), tp_pip_med=round(tp_med, 2),
                   net_pip=round(float(tr['pnl_pip'].sum()), 1), uncond_draws=unc, perm=perm, null=null, rqs2=r))
    tr.to_csv(f'{OUT}/trades_XAUUSD-{tf}.csv', index=False)


if __name__ == '__main__':
    run_tf(sys.argv[1])
