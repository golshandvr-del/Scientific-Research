#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S673 — حکمِ نهایی (یک compute_rqs2، مطابق PREREG-2 — کامیت‌شده قبل از لمس holdout)

کاندیدای منجمد: H8 both: N=200, θ=1.0×ATR100, k_sl=1.0, RR=1.5, mh=32
سیگنال LONG: (سقفِ high رولینگِ ۲۰۰ بارِ قبل − close) ≤ θ·ATR100 ∧ close ≤ سقف ∧ close<open
سیگنال SHORT: آینه با کفِ low رولینگ ∧ close>open
مدل صفر: کانونیکالِ بی‌قید per side (ورودهای تصادفی از همهٔ بارهای valid)، K=1000
n_trials=12 (بدهی انباشتهٔ بلوک S670-S679)
"""
import gc
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se     # noqa: E402
from engine import indicator_bank as ib   # noqa: E402
from engine import rqs2 as R              # noqa: E402
from tools import s434_fast_data as fd    # noqa: E402

SEED = 20260824
K_PERM = 1000
N_TRIALS = 12
ATR_P = 100

FROZEN = {
    'H8': dict(N=200, theta=1.0, side='both', k_sl=1.0, rr=1.5, max_hold=32),
}

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_final_S673')


def build_signals(df, cfg):
    n = len(df)
    o = df['open'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    lo = df['low'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    pip = se.ASSETS['XAUUSD']['pip']

    atr_raw = ib.atr_s(df, ATR_P).values
    atr_pip = atr_raw / pip
    valid = np.isfinite(atr_pip) & (atr_pip > 0)
    valid[:ATR_P + 1] = False

    N = cfg['N']
    hi_prev = pd.Series(h).rolling(N, min_periods=N).max().shift(1).values
    lo_prev = pd.Series(lo).rolling(N, min_periods=N).min().shift(1).values
    okN = valid & np.isfinite(hi_prev) & np.isfinite(lo_prev)
    th = cfg['theta']
    near_hi = okN & ((hi_prev - c) <= th * atr_raw) & (c <= hi_prev)
    near_lo = okN & ((c - lo_prev) <= th * atr_raw) & (c >= lo_prev)
    long_raw = near_hi & (c < o)
    short_raw = near_lo & (c > o)

    side = cfg['side']
    ls = long_raw if side in ('long', 'both') else np.zeros(n, bool)
    ss = short_raw if side in ('short', 'both') else np.zeros(n, bool)
    return ls, ss, atr_pip, valid


def _wrpct(tr):
    if tr is None or len(tr) == 0:
        return None
    return 100.0 * float((tr['pnl_pip'] > 0).mean())


def build_null(df, cfg, atr_pip, valid, n_sig_long, n_sig_short):
    """مدل صفر کانونیکال بی‌قید: K پرمیوتیشن با ورودهای تصادفی از همهٔ بارهای valid."""
    rng = np.random.default_rng(SEED)
    n = len(df)
    mh = cfg['max_hold']
    sl_arr = cfg['k_sl'] * atr_pip
    tp_arr = cfg['rr'] * sl_arr
    pool = np.where(valid)[0]
    null = {}
    for side, n_sig in (('long', n_sig_long), ('short', n_sig_short)):
        if n_sig == 0:
            null[side] = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                              perm_max=None, perm_k=None)
            continue
        n_samp = min(20000, len(pool))
        pick = np.sort(rng.choice(len(pool), size=n_samp, replace=False))
        sig = np.zeros(n, bool); sig[pool[pick]] = True
        ls = sig if side == 'long' else np.zeros(n, bool)
        ss = sig if side == 'short' else np.zeros(n, bool)
        tr = se.simulate_trades(df, ls, ss, sl_arr, tp_arr, 'XAUUSD',
                                max_hold=mh, allow_overlap=False)
        uncond_wr = _wrpct(tr)
        del tr
        wrs = []
        for k in range(K_PERM):
            pick = np.sort(rng.choice(len(pool), size=min(n_sig, len(pool)),
                                      replace=False))
            sig = np.zeros(n, bool); sig[pool[pick]] = True
            ls = sig if side == 'long' else np.zeros(n, bool)
            ss = sig if side == 'short' else np.zeros(n, bool)
            tr = se.simulate_trades(df, ls, ss, sl_arr, tp_arr, 'XAUUSD',
                                    max_hold=mh, allow_overlap=False)
            w = _wrpct(tr)
            if w is not None:
                wrs.append(w)
            del tr
            if (k + 1) % 200 == 0:
                print(f"    perm {side} {k+1}/{K_PERM}", flush=True)
        wrs = np.array(wrs, float)
        null[side] = dict(uncond_wr=uncond_wr,
                          perm_mean=float(wrs.mean()),
                          perm_sd=float(wrs.std(ddof=1)),
                          perm_max=float(wrs.max()),
                          perm_k=int(len(wrs)))
    return null


def run_tf(tf):
    t0 = time.time()
    cfg = FROZEN[tf]
    d = fd.load_fast('XAUUSD', tf)
    df = fd.as_dataframe(d)
    n_full = len(df)
    src = d['src']
    d.clear(); gc.collect()
    assert 'mt5_full' in src, f"E-16: src={src}"
    split_bar = n_full // 2
    print(f"[S673-FINAL/{tf}] src={src} n_full={n_full} split_bar={split_bar} "
          f"cfg={cfg}", flush=True)

    ls, ss, atr_pip, valid = build_signals(df, cfg)
    sl_arr = cfg['k_sl'] * atr_pip
    tp_arr = cfg['rr'] * sl_arr
    tr = se.simulate_trades(df, ls, ss, sl_arr, tp_arr, 'XAUUSD',
                            max_hold=cfg['max_hold'], allow_overlap=False)
    nL = int((tr['direction'] == 'long').sum())
    nS = int(len(tr)) - nL
    print(f"[S673-FINAL/{tf}] trades={len(tr)} (L={nL}/S={nS}) wr={_wrpct(tr)}",
          flush=True)

    null = build_null(df, cfg, atr_pip, valid, nL, nS)
    for side in ('long', 'short'):
        z = null[side]
        print(f"    null {side} uncond={z['uncond_wr']} perm_mean={z['perm_mean']} "
              f"sd={z['perm_sd']} k={z['perm_k']}", flush=True)

    med_sl = float(np.median(tr['sl_pip'].values))
    res = R.compute_rqs2(
        tr, 'XAUUSD', sl_pip=med_sl, tp_pip=cfg['rr'] * med_sl,
        bar_time=df['time'].values, close=df['close'].values,
        null=null, n_trials=N_TRIALS, split_bar=split_bar)

    os.makedirs(OUT_DIR, exist_ok=True)
    tr.to_csv(os.path.join(OUT_DIR, f'{tf}_trades.csv'), index=False)
    out = dict(tf=tf, src=src, n_full=n_full, split_bar=split_bar, cfg=cfg,
               seed=SEED, k_perm=K_PERM, n_trials=N_TRIALS,
               n_trades=int(len(tr)), n_long=nL, n_short=nS,
               null=null, rqs2=res, elapsed_s=round(time.time() - t0, 1))
    with open(os.path.join(OUT_DIR, f'{tf}.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"[S673-FINAL/{tf}] verdict={res['verdict']} score={res['rqs2_score']} "
          f"({time.time()-t0:.0f}s)", flush=True)
    return out


if __name__ == '__main__':
    tfs = sys.argv[1:] or list(FROZEN)
    for tf in tfs:
        run_tf(tf)
