#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S897 — حافظهٔ بازتابیِ شوک (Reflexive Shock Memory) · مسیر C · نالِ کانونی.

قرارداد: results/S897_PREREG_ReflexiveShockMemory_Xauusd_MTF.md (کامیت 7c6b8f16)
  - پایهٔ منجمد S965: range >= 2.618*ATR21[t-1] و rho >= 0.618 ؛ جهت follow (body)
    ورود open t+1 · SL=1.272*ATR21[t-1] · TP=2.058*ATR21[t-1] · hold=16 · no overlap
  - حافظه: آخرین شوکِ پایهٔ *رسیده* p (p+H <= t-1) در W=200 کندل قبل؛
    موفق <=> sign(close[p+H]-close[p]) == sign(body_p) و |d| >= 0.5*ATR21[p-1]
  - H in {8,16} · بازو A_win / A_loss · 4 config/کارت · n_trials=76
  - اهلیت n_IS>=60 و exp@2xcost_IS>0 · قفل t_pnl · بدون اهل => UNPROVEN
  - نال کانونی uncond {897,1897,2897} + perm K=500 seed=897 (long/short جدا)
  - P1: lift قفل‌شده vs پایهٔ بی‌گیت (IS) · P2: A_loss برنده => ابطال فرضیه

اجرا: python3 strategies/s897_shock_memory.py H8
"""
import sys, os, json, gc, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from tools import s434_fast_data as fd
from engine import rqs2
from engine import scalp_engine as se

ASSET = 'XAUUSD'; PIP = 0.1; COST_PIP = 3.3
N_TRIALS = 76; PERM_K = 500; PERM_SEED = 897; UNC_SEEDS = (897, 1897, 2897)
OUT = 'results/_s897'; PREREG = '7c6b8f16'
TH = 2.618; RHO = 0.618; K_SL = 1.272; K_TP = 2.058; HOLD = 16
W_LOOK = 200; DELTA = 0.5
HS = (8, 16); ARMS = ('A_win', 'A_loss')
MIN_IS = 60

TF_MIN = {'M1':1,'M3':3,'M4':4,'M5':5,'M6':6,'M10':10,'M12':12,'M15':15,
          'M20':20,'M30':30,'H1':60,'H2':120,'H3':180,'H6':360,'H8':480,
          'H12':720,'D1':1440,'W1':10080,'MN1':43200}


def atr_prev(df, n=21):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).rolling(n).mean().shift(1).values   # ATR21[t-1]


def base_shocks(df, atr):
    o, h, l, c = (df[k].values for k in ('open', 'high', 'low', 'close'))
    rng = h - l
    body = c - o
    with np.errstate(divide='ignore', invalid='ignore'):
        rho = np.where(rng > 0, np.abs(body) / rng, 0.0)
    shock = (rng >= TH * atr) & (rho >= RHO) & (body != 0) & ~np.isnan(atr)
    shock[:25] = False
    sgn = np.sign(body).astype(int)
    return shock, sgn


def memory_masks(shock, sgn, close, atr, H):
    """برای هر شوک t، وضعیت آخرین شوکِ رسیدهٔ p در W کندل قبل: 1=موفق، -1=ناموفق، 0=هیچ."""
    N = len(close)
    idx = np.flatnonzero(shock)
    outcome = np.zeros(N, dtype=int)          # نتیجهٔ هر شوک (پس از رسیدن)
    for p in idx:
        if p + H < N:
            d = close[p + H] - close[p]
            ok = (np.sign(d) == sgn[p]) and (abs(d) >= DELTA * atr[p - 1])
            outcome[p] = 1 if ok else -1
    mem = np.zeros(N, dtype=int)
    for j, t in enumerate(idx):
        k = j - 1
        while k >= 0:
            p = idx[k]
            if t - p > W_LOOK:
                break
            if p + H <= t - 1 and outcome[p] != 0:
                mem[t] = outcome[p]; break
            k -= 1
    return mem


def simulate(df, ls, ss, sl_arr, tp_arr):
    return se.simulate_trades(df, ls, ss, sl_arr, tp_arr, asset=ASSET,
                              max_hold=HOLD, allow_overlap=False)


def stats(tr):
    pnl = tr['pnl_pip'].values
    n = len(pnl); exp = float(pnl.mean()); sd = float(pnl.std(ddof=1))
    t = exp / sd * math.sqrt(n) if sd > 0 else 0.0
    wr = 100.0 * float((tr['outcome'] == 'win').mean())
    return n, exp, exp - COST_PIP, t, wr


def canonical_null(df, sl_arr, tp_arr, n_long, n_short):
    """نال هندسه‌همتا، هر جهت جدا با همان تعداد سیگنال."""
    N = len(df); lo, hi = 30, N - HOLD - 2
    z = np.zeros(N, dtype=bool)
    out = {}; unc_all = {}; perm_all = {}
    for side, n_sig in (('long', n_long), ('short', n_short)):
        if n_sig < 5:
            out[side] = dict(uncond_wr=50.0, perm_mean=50.0, perm_sd=0.0, perm_max=50.0, perm_k=0)
            continue
        unc_rows = []
        size = min(20000, N // HOLD)
        for seed in UNC_SEEDS:
            rng = np.random.default_rng(seed)
            pos = rng.choice(np.arange(lo, hi), size=min(size, hi - lo), replace=False)
            sig = np.zeros(N, dtype=bool); sig[np.sort(pos)] = True
            tr = simulate(df, sig if side == 'long' else z, sig if side == 'short' else z, sl_arr, tp_arr)
            unc_rows.append((seed, 100.0 * float((tr['outcome'] == 'win').mean()), len(tr)))
            del tr; gc.collect()
        rng = np.random.default_rng(PERM_SEED)
        wrs = []
        for i in range(PERM_K):
            pos = rng.choice(np.arange(lo, hi), size=n_sig, replace=False)
            sig = np.zeros(N, dtype=bool); sig[np.sort(pos)] = True
            tr = simulate(df, sig if side == 'long' else z, sig if side == 'short' else z, sl_arr, tp_arr)
            if tr is not None and len(tr) >= 5:
                wrs.append(100.0 * float((tr['outcome'] == 'win').mean()))
            del tr
            if (i + 1) % 100 == 0:
                gc.collect(); print(f"  perm[{side}] {i+1}/{PERM_K} …", flush=True)
        a = np.asarray(wrs, float)
        perm = dict(mean=float(a.mean()), sd=float(a.std(ddof=1)), max=float(a.max()), k=int(len(a)))
        out[side] = dict(uncond_wr=max(r[1] for r in unc_rows), perm_mean=perm['mean'],
                         perm_sd=perm['sd'], perm_max=perm['max'], perm_k=perm['k'])
        unc_all[side] = unc_rows; perm_all[side] = perm
    return out, unc_all, perm_all


def _save(tf, obj):
    os.makedirs(OUT, exist_ok=True)
    with open(f'{OUT}/rqs2_XAUUSD-{tf}.json', 'w') as f:
        json.dump(obj, f, indent=1, default=str)


def run_tf(tf):
    print('=' * 72); print(f"S897 Reflexive Shock Memory · XAUUSD-{tf} (prereg {PREREG})"); print('=' * 72, flush=True)
    if TF_MIN[tf] >= 10080:
        _save(tf, dict(card=f'XAUUSD-{tf}', prereg=PREREG, verdict='INCOMPLETE',
                       reason='pre-declared: W=200 lookback + hold 16 at >=W1 leaves n structurally < 60'))
        print("pre-declared INCOMPLETE"); return
    d = fd.load_fast(ASSET, tf); df = fd.as_dataframe(d)
    if 'volume' in df.columns: df = df.drop(columns=['volume'])
    src = d.get('src', '?'); del d; gc.collect()
    N = len(df); split = int(N * 0.70); times = df['time'].values; close = df['close'].values
    atr = atr_prev(df, 21)
    atr_f = np.nan_to_num(atr, nan=np.nanmedian(atr))
    sl_arr = K_SL * atr_f / PIP; tp_arr = K_TP * atr_f / PIP
    shock, sgn = base_shocks(df, atr)
    print(f"src={src} bars={N} split={split} base shocks={shock.sum()} (IS {shock[:split].sum()})", flush=True)
    z = np.zeros(N, dtype=bool)
    ls0 = shock & (sgn > 0); ss0 = shock & (sgn < 0)
    dfe = df.iloc[:split]

    # P1 base (IS): ungated S965
    tr0 = simulate(dfe, ls0[:split], ss0[:split], sl_arr[:split], tp_arr[:split])
    base = {}
    if tr0 is not None and len(tr0) >= 10:
        n0, e0, _, _, w0 = stats(tr0); base = dict(n=n0, wr=round(w0, 2), exp=round(e0, 2))
    del tr0
    print(f"P1 base (IS, ungated S965): {base}", flush=True)

    best = None; table = []; n_ev = {}
    for H in HS:
        mem = memory_masks(shock, sgn, close, atr_f, H)
        for arm in ARMS:
            sel = shock & (mem == (1 if arm == 'A_win' else -1))
            key = f'H{H}/{arm}'; n_ev[key] = int(sel.sum())
            ls = (sel & (sgn > 0))[:split]; ss = (sel & (sgn < 0))[:split]
            if sel[:split].sum() < 20:
                table.append(dict(cfg=key, n_is=int(sel[:split].sum()), note='too few')); continue
            tr = simulate(dfe, ls, ss, sl_arr[:split], tp_arr[:split])
            if tr is None or len(tr) < MIN_IS:
                table.append(dict(cfg=key, n_is=0 if tr is None else len(tr), note='n_IS<60')); del tr; continue
            n, exp, exp2x, t, wr = stats(tr)
            elig = exp2x > 0
            table.append(dict(cfg=key, n_is=n, wr=round(wr, 2), exp=round(exp, 2), exp2x=round(exp2x, 2), t=round(t, 3), eligible=elig))
            print(f"  {'ELIGIBLE' if elig else '        '} {key:<11} n={n:>4} WR={wr:5.2f} exp={exp:+8.2f} exp2x={exp2x:+8.2f} t={t:+.2f}", flush=True)
            if elig and (best is None or t > best['t_pnl']):
                best = dict(H=H, arm=arm, t_pnl=round(t, 3), is_n=n, is_wr=round(wr, 2), is_exp=round(exp, 3), is_exp2x=round(exp2x, 3))
            del tr; gc.collect()

    # P2 diagnostic: did A_loss beat A_win in IS (by WR) for any H?
    p2 = {}
    for H in HS:
        w = next((r for r in table if r['cfg'] == f'H{H}/A_win' and 'wr' in r), None)
        l = next((r for r in table if r['cfg'] == f'H{H}/A_loss' and 'wr' in r), None)
        if w and l: p2[f'H{H}'] = dict(win_wr=w['wr'], loss_wr=l['wr'], reflexive_direction_ok=w['wr'] > l['wr'])

    if best is None:
        _save(tf, dict(card=f'XAUUSD-{tf}', prereg=PREREG, verdict='UNPROVEN',
                       reason='no eligible config in discovery (n_IS>=60 & exp@2x>0) - holdout untouched',
                       src=src, bars=N, split=split, events=n_ev, discovery=table, p1_base_is=base, p2=p2))
        print("NO ELIGIBLE CONFIG → UNPROVEN"); return

    p1 = dict(base_is=base, locked_is_wr=best['is_wr'], passes=bool(base and best['is_wr'] > base['wr']))
    print(f"\nLOCKED: H{best['H']}/{best['arm']} t={best['t_pnl']} IS n={best['is_n']} WR={best['is_wr']}  P1={p1['passes']}  P2={p2}", flush=True)

    mem = memory_masks(shock, sgn, close, atr_f, best['H'])
    sel = shock & (mem == (1 if best['arm'] == 'A_win' else -1))
    ls = sel & (sgn > 0); ss = sel & (sgn < 0)
    tr = simulate(df, ls, ss, sl_arr, tp_arr)
    sl_med = float(np.median(tr['sl_pip'].values)); tp_med = sl_med * K_TP / K_SL
    null, unc, perm = canonical_null(df, sl_arr, tp_arr, int(ls.sum()), int(ss.sum()))
    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med, bar_time=times, null=null,
                          n_trials=N_TRIALS, split_bar=split, close=close)
    n_all, _, _, _, wr_all = stats(tr)
    hm = tr['entry_bar'].values >= split; oos_n = int(hm.sum())
    oos_wr = 100.0 * float((tr.loc[hm, 'outcome'] == 'win').mean()) if oos_n else None
    print(f"\nFULL: n={n_all} WR={wr_all:.2f} OOS: n={oos_n} WR={oos_wr}")
    print(f"VERDICT: {r.get('verdict')} score={r.get('rqs2_score')}  gates: {r.get('gates')}  notes={r.get('notes')}", flush=True)
    _save(tf, dict(card=f'XAUUSD-{tf}', prereg=PREREG, src=src, bars=N, split=split, events=n_ev,
                   discovery=table, locked=best, p1=p1, p2=p2, sl_pip_med=round(sl_med, 2), tp_pip_med=round(tp_med, 2),
                   n=n_all, wr=round(wr_all, 2), n_long=int(ls.sum()), n_short=int(ss.sum()),
                   net_pip=round(float(tr['pnl_pip'].sum()), 1), oos_n=oos_n, oos_wr=round(oos_wr, 2) if oos_wr else None,
                   uncond_draws=unc, perm=perm, null=null, rqs2=r))
    tr.to_csv(f'{OUT}/trades_XAUUSD-{tf}.csv', index=False)


if __name__ == '__main__':
    run_tf(sys.argv[1])
