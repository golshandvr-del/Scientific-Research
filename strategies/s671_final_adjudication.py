#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S671 — داوری نهایی (مسیر C؛ PREREG + PREREG-2 در git)

هر TF منجمد: یک compute_rqs2 روی کل داده، split_bar=n_full//2.
مدل صفر اندازه‌گیری‌شدهٔ **مشروط به رژیم**، K=1000، n_trials=10.

اجرا:  python3 strategies/s671_final_adjudication.py H2 H8
"""
import gc
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se                          # noqa: E402
from engine import indicator_bank as ib                        # noqa: E402
from engine import rqs2 as R                                   # noqa: E402
from tools import s434_fast_data as fd                         # noqa: E402
from tools.s670_trendflex_fast import trendflex_fast, ssf_fast  # noqa: E402

SEED = 20260813
K_PERM = 1000
N_TRIALS = 10          # ۸ فینال S670 (آلودگی افشاشده) + ۲ فینال S671
N_UNCOND = 20000
ATR_P = 100
L_SLOPE = 8

FROZEN = {
    'H2': dict(period=34, theta=1.272, period_f=144, side='both',
               k_sl=1.0, rr=1.5, max_hold=64),
    'H8': dict(period=34, theta=1.272, period_f=144, side='short',
               k_sl=1.5, rr=1.5, max_hold=32),
}

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_final_S671')


def wr_of(tr):
    if tr is None or len(tr) == 0:
        return None
    return 100.0 * float((tr['pnl_pip'] > 0).mean())


def sim(df, ls, ss, sl_arr, tp_arr, mh):
    return se.simulate_trades(df, ls, ss, sl_arr, tp_arr, 'XAUUSD',
                              max_hold=mh, allow_overlap=False)


def build_null(df, pools, sl_arr, tp_arr, mh, n_long, n_short, rng):
    """مبنای مشروط به رژیم: ورودهای تصادفی فقط از بارهای هم‌رژیمِ همان سمت."""
    n = len(df)
    null = {}
    for side, n_side in (('long', n_long), ('short', n_short)):
        d = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                 perm_max=None, perm_k=None)
        pool = pools[side]
        if n_side > 0 and len(pool) >= 2:
            n_samp = min(N_UNCOND, len(pool))
            pick = np.sort(rng.choice(len(pool), size=n_samp, replace=False))
            sig = np.zeros(n, bool); sig[pool[pick]] = True
            ls = sig if side == 'long' else np.zeros(n, bool)
            ss = sig if side == 'short' else np.zeros(n, bool)
            tr_u = sim(df, ls, ss, sl_arr, tp_arr, mh)
            d['uncond_wr'] = wr_of(tr_u)
            del tr_u
            wrs = []
            for _ in range(K_PERM):
                pick = np.sort(rng.choice(len(pool), size=min(n_side, len(pool)),
                                          replace=False))
                sig = np.zeros(n, bool); sig[pool[pick]] = True
                ls = sig if side == 'long' else np.zeros(n, bool)
                ss = sig if side == 'short' else np.zeros(n, bool)
                w = wr_of(sim(df, ls, ss, sl_arr, tp_arr, mh))
                if w is not None:
                    wrs.append(w)
            if wrs:
                a = np.asarray(wrs, 'float64')
                d.update(perm_mean=float(a.mean()), perm_sd=float(a.std(ddof=1)),
                         perm_max=float(a.max()), perm_k=int(len(a)))
        null[side] = d
        print(f"    null {side:<5} uncond={d['uncond_wr']} "
              f"perm_mean={d['perm_mean']} sd={d['perm_sd']} k={d['perm_k']}",
              flush=True)
    return null


def run_tf(tf):
    cfg = FROZEN[tf]
    t0 = time.time()
    d = fd.load_fast('XAUUSD', tf)
    df = fd.as_dataframe(d)
    n_full = len(df)
    split_bar = n_full // 2
    src = d['src']
    d.clear(); gc.collect()
    mh = cfg['max_hold']
    pip = se.ASSETS['XAUUSD']['pip']
    print(f"[S671-FINAL/{tf}] src={src} n_full={n_full} split_bar={split_bar} "
          f"cfg={cfg}", flush=True)

    atr_pip = ib.atr_s(df, ATR_P).values / pip
    valid = np.isfinite(atr_pip) & (atr_pip > 0)
    valid[:ATR_P + 1] = False
    close_arr = df['close'].values.astype(np.float64)
    sl_arr = cfg['k_sl'] * atr_pip
    tp_arr = cfg['rr'] * sl_arr

    # فیلتر رژیم منجمد
    s = ssf_fast(close_arr, cfg['period_f'])
    up = np.zeros(n_full, bool); dn = np.zeros(n_full, bool)
    up[L_SLOPE:] = s[L_SLOPE:] > s[:-L_SLOPE]
    dn[L_SLOPE:] = s[L_SLOPE:] < s[:-L_SLOPE]
    up[:cfg['period_f'] + L_SLOPE] = False
    dn[:cfg['period_f'] + L_SLOPE] = False

    # سیگنال منجمد
    tfx = trendflex_fast(close_arr, cfg['period'])
    prev = np.roll(tfx, 1); prev[0] = 0.0
    th = cfg['theta']
    long_raw = (prev <= th) & (tfx > th) & valid & up
    short_raw = (prev >= -th) & (tfx < -th) & valid & dn
    ls = long_raw if cfg['side'] in ('long', 'both') else np.zeros(n_full, bool)
    ss = short_raw if cfg['side'] in ('short', 'both') else np.zeros(n_full, bool)

    tr = sim(df, ls, ss, sl_arr, tp_arr, mh)
    n_tr = len(tr)
    n_long = int((tr['direction'] == 'long').sum()) if n_tr else 0
    n_short = n_tr - n_long
    print(f"[S671-FINAL/{tf}] trades={n_tr} (L={n_long}/S={n_short}) "
          f"wr={wr_of(tr)}", flush=True)

    pools = {'long': np.where(valid & up)[0], 'short': np.where(valid & dn)[0]}
    rng = np.random.default_rng(SEED)
    null = build_null(df, pools, sl_arr, tp_arr, mh, n_long, n_short, rng)

    sl_pip_med = float(np.median(tr['sl_pip'].values)) if n_tr else None
    tp_pip_med = cfg['rr'] * sl_pip_med if sl_pip_med else None

    res = R.compute_rqs2(
        tr, 'XAUUSD',
        sl_pip=sl_pip_med, tp_pip=tp_pip_med,
        bar_time=df['time'].values, close=df['close'].values,
        null=null, n_trials=N_TRIALS, split_bar=split_bar)

    print(R.format_rqs2(f'S671_TrendFlexRegime_XAUUSD_{tf}', res), flush=True)

    os.makedirs(OUT_DIR, exist_ok=True)
    out = dict(tf=tf, src=src, n_full=n_full, split_bar=split_bar, cfg=cfg,
               seed=SEED, k_perm=K_PERM, n_trials=N_TRIALS,
               n_trades=n_tr, n_long=n_long, n_short=n_short,
               null=null, rqs2=res, elapsed_s=round(time.time() - t0, 1))
    with open(os.path.join(OUT_DIR, f'{tf}.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    tr.to_csv(os.path.join(OUT_DIR, f'{tf}_trades.csv'), index=False)
    print(f"[S671-FINAL/{tf}] verdict={res['verdict']} score={res['rqs2_score']} "
          f"({time.time()-t0:.0f}s)", flush=True)
    del df, tr
    gc.collect()
    return out


if __name__ == '__main__':
    tfs = sys.argv[1:] or list(FROZEN)
    for tf in tfs:
        if tf not in FROZEN:
            print(f"[S671-FINAL] {tf} منجمد نیست — رد", flush=True)
            continue
        run_tf(tf)
