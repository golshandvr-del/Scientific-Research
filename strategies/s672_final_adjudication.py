#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S672 — حکمِ نهایی (یک compute_rqs2، مطابق PREREG-2 — کامیت‌شده قبل از لمس holdout)

کاندیدای منجمد: H8 short-only (No Demand): pt=50, α=0.7, k_sl=1.0, RR=1.5, mh=32
مدل صفر: روند-شرطی (ورودهای تصادفی short از بارهای valid ∧ close<SMA50)، K=1000
n_trials=11 (بدهی انباشتهٔ بلوک S670-S679)
"""
import gc
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se     # noqa: E402
from engine import indicator_bank as ib   # noqa: E402
from engine import rqs2 as R              # noqa: E402
from tools import s434_fast_data as fd    # noqa: E402

SEED = 20260823
K_PERM = 1000
N_TRIALS = 11
ATR_P = 100
ATR_RANGE_P = 20

FROZEN = {
    'H8': dict(pt=50, alpha=0.7, side='short', k_sl=1.0, rr=1.5, max_hold=32),
}

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_final_S672')


def build_signals(df, cfg):
    n = len(df)
    o = df['open'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    lo = df['low'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    v = df['volume'].values.astype(np.float64)
    pip = se.ASSETS['XAUUSD']['pip']

    atr_pip = ib.atr_s(df, ATR_P).values / pip
    atr20 = ib.atr_s(df, ATR_RANGE_P).values
    valid = np.isfinite(atr_pip) & (atr_pip > 0) & np.isfinite(atr20) & (atr20 > 0)
    valid[:max(ATR_P, ATR_RANGE_P) + 1] = False

    voldry = np.zeros(n, bool)
    voldry[2:] = (v[2:] < v[1:-1]) & (v[2:] < v[:-2])

    pt = cfg['pt']
    sma = np.convolve(c, np.ones(pt) / pt, mode='full')[:n]
    sma[:pt - 1] = np.nan
    upT = c > sma; upT[:pt] = False
    dnT = c < sma; dnT[:pt] = False

    narrow = valid & ((h - lo) < cfg['alpha'] * atr20)
    long_raw = upT & (c < o) & voldry & narrow     # No Supply
    short_raw = dnT & (c > o) & voldry & narrow    # No Demand

    side = cfg['side']
    ls = long_raw if side in ('long', 'both') else np.zeros(n, bool)
    ss = short_raw if side in ('short', 'both') else np.zeros(n, bool)
    return ls, ss, atr_pip, valid, upT, dnT


def _wrpct(tr):
    if tr is None or len(tr) == 0:
        return None
    return 100.0 * float((tr['pnl_pip'] > 0).mean())


def build_null(df, cfg, atr_pip, valid, upT, dnT, n_sig_long, n_sig_short):
    """مدل صفر روند-شرطی: K پرمیوتیشن با ورودهای تصادفی از بارهای هم-روند."""
    rng = np.random.default_rng(SEED)
    n = len(df)
    mh = cfg['max_hold']
    sl_arr = cfg['k_sl'] * atr_pip
    tp_arr = cfg['rr'] * sl_arr
    null = {}
    for side, tmask, n_sig in (('long', upT, n_sig_long),
                               ('short', dnT, n_sig_short)):
        if n_sig == 0:
            null[side] = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                              perm_max=None, perm_k=None)
            continue
        pool = np.where(valid & tmask)[0]
        # uncond: یک نمونهٔ بزرگ
        n_samp = min(20000, len(pool))
        pick = np.sort(rng.choice(len(pool), size=n_samp, replace=False))
        sig = np.zeros(n, bool); sig[pool[pick]] = True
        ls = sig if side == 'long' else np.zeros(n, bool)
        ss = sig if side == 'short' else np.zeros(n, bool)
        tr = se.simulate_trades(df, ls, ss, sl_arr, tp_arr, 'XAUUSD',
                                max_hold=mh, allow_overlap=False)
        uncond_wr = _wrpct(tr)
        del tr
        # K perms با همان تعداد سیگنال واقعی
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
    print(f"[S672-FINAL/{tf}] src={src} n_full={n_full} split_bar={split_bar} "
          f"cfg={cfg}", flush=True)

    ls, ss, atr_pip, valid, upT, dnT = build_signals(df, cfg)
    sl_arr = cfg['k_sl'] * atr_pip
    tp_arr = cfg['rr'] * sl_arr
    tr = se.simulate_trades(df, ls, ss, sl_arr, tp_arr, 'XAUUSD',
                            max_hold=cfg['max_hold'], allow_overlap=False)
    nL = int((tr['direction'] == 'long').sum())
    nS = int(len(tr)) - nL
    print(f"[S672-FINAL/{tf}] trades={len(tr)} (L={nL}/S={nS}) wr={_wrpct(tr)}",
          flush=True)

    null = build_null(df, cfg, atr_pip, valid, upT, dnT, nL, nS)
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
    print(f"[S672-FINAL/{tf}] verdict={res['verdict']} score={res['rqs2_score']} "
          f"({time.time()-t0:.0f}s)", flush=True)
    return out


if __name__ == '__main__':
    tfs = sys.argv[1:] or list(FROZEN)
    for tf in tfs:
        run_tf(tf)
