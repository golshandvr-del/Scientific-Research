#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S623 — فاز جست‌وجو (نیمهٔ نخست فقط — PREREG commit 7fa24b13)
رویداد منجمد S622 (G=$10, τ=0.2×ATR100, دوسویه) × هندسهٔ درشت.
"""
import gc
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se            # noqa: E402
from engine import indicator_bank as ib          # noqa: E402
from tools import s434_fast_data as fd           # noqa: E402

SEED = 20260815
G = 10.0
TAU = 0.20
K_SLS = (4.0, 8.0, 16.0)
RRS = (1.0, 1.5)
HOLDS = (480, 960)
ATR_P = 100
N_UNCOND = 12000

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_scan_S623')


def wr_of(tr):
    return None if tr is None or len(tr) == 0 else 100.0 * float((tr['pnl_pip'] > 0).mean())


def run_tf(tf):
    t0 = time.time()
    d = fd.load_fast('XAUUSD', tf)
    df_full = fd.as_dataframe(d)
    n_full = len(df_full)
    half = n_full // 2
    df = df_full.iloc[:half].reset_index(drop=True).copy()
    src = d['src']
    del df_full
    d.clear()
    gc.collect()
    n = len(df)
    pip = se.ASSETS['XAUUSD']['pip']
    print(f"[S623/{tf}] src={src} n_full={n_full} search_half={n}", flush=True)

    hi = df['high'].values.astype(np.float64)
    lo = df['low'].values.astype(np.float64)
    cl = df['close'].values.astype(np.float64)
    atr_price = ib.atr_s(df, ATR_P).values
    atr_pip = atr_price / pip
    valid = np.isfinite(atr_pip) & (atr_pip > 0)
    valid[:ATR_P + 1] = False

    # رویداد منجمد
    r_lo = np.round(lo / G) * G
    r_hi = np.round(hi / G) * G
    tau = TAU * atr_price
    long_raw = (np.abs(lo - r_lo) <= tau) & (cl > r_lo + tau) & valid
    short_raw = (np.abs(hi - r_hi) <= tau) & (cl < r_hi - tau) & valid
    print(f"[S623/{tf}] رویدادها: long={int(long_raw.sum())} short={int(short_raw.sum())}",
          flush=True)

    rng = np.random.default_rng(SEED)
    vidx = np.where(valid)[0]
    n_samp = min(N_UNCOND, len(vidx))
    pick = np.sort(rng.choice(len(vidx), size=n_samp, replace=False))
    bsig = np.zeros(n, bool)
    bsig[vidx[pick]] = True

    rows = []
    cfg_i = 0
    for mh in HOLDS:
        # مبنای بی‌قید به تفکیک (k, rr, side) برای این max_hold
        uncond = {}
        for k_sl in K_SLS:
            sl_arr = k_sl * atr_pip
            for rr in RRS:
                for side in ('long', 'short'):
                    ls = bsig if side == 'long' else np.zeros(n, bool)
                    ss = bsig if side == 'short' else np.zeros(n, bool)
                    tr = se.simulate_trades(df, ls, ss, sl_arr, rr * sl_arr,
                                            'XAUUSD', max_hold=mh,
                                            allow_overlap=False)
                    uncond[(k_sl, rr, side)] = dict(wr=wr_of(tr), n=int(len(tr)))
                    del tr
        gc.collect()
        for k_sl in K_SLS:
            sl_arr = k_sl * atr_pip
            for rr in RRS:
                tp_arr = rr * sl_arr
                for side in ('long', 'short', 'both'):
                    cfg_i += 1
                    ls = long_raw if side in ('long', 'both') else np.zeros(n, bool)
                    ss = short_raw if side in ('short', 'both') else np.zeros(n, bool)
                    if not (ls.any() or ss.any()):
                        continue
                    tr = se.simulate_trades(df, ls, ss, sl_arr, tp_arr, 'XAUUSD',
                                            max_hold=mh, allow_overlap=False)
                    n_tr = int(len(tr))
                    if n_tr == 0:
                        continue
                    wr = wr_of(tr)
                    if side == 'both':
                        nL = int((tr['direction'] == 'long').sum())
                        nS = n_tr - nL
                        refs, wts = [], []
                        for s2, cnt in (('long', nL), ('short', nS)):
                            u = uncond[(k_sl, rr, s2)]['wr']
                            if u is not None and cnt > 0:
                                refs.append(u * cnt)
                                wts.append(cnt)
                        ref = sum(refs) / sum(wts) if wts else None
                    else:
                        ref = uncond[(k_sl, rr, side)]['wr']
                    lift = (wr - ref) if ref is not None else None
                    rows.append(dict(
                        mh=mh, side=side, k_sl=k_sl, rr=rr, n=n_tr,
                        wr=round(wr, 3),
                        ref_wr=None if ref is None else round(ref, 3),
                        lift=None if lift is None else round(lift, 3),
                        exp_pip=round(float(np.mean(tr['pnl_pip'])), 3),
                        lift_sqrt_n=None if lift is None
                        else round(float(lift * np.sqrt(n_tr)), 1)))
                    del tr
        gc.collect()
        print(f"[S623/{tf}] mh={mh} تمام ({time.time()-t0:.0f}s)", flush=True)
    rows.sort(key=lambda r: -(r['lift_sqrt_n'] if r['lift_sqrt_n'] is not None
                              else -1e9))
    out = dict(tf=tf, src=src, n_full=n_full, n_search=n, half_bar=half,
               seed=SEED, n_configs=cfg_i, event=dict(G=G, tau=TAU),
               elapsed_s=round(time.time() - t0, 1), top20=rows[:20],
               n_rows=len(rows))
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, f'{tf}.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"[S623/{tf}] تمام: {cfg_i} پیکربندی → {tf}.json", flush=True)
    # چاپ گذرندگان چهارشرطی
    import math
    for r in rows:
        if r['lift'] and r['lift'] >= 4 and r['exp_pip'] > 0:
            p0 = r['ref_wr'] / 100
            nreq = (3.09 * 100 * math.sqrt(p0 * (1 - p0)) / r['lift']) ** 2
            tag = '✓✓✓' if r['n'] >= nreq else '✗n'
            print(f"[S623/{tf}] {tag} {r} n_req={nreq:.0f}", flush=True)
    del df
    gc.collect()
    return out


if __name__ == '__main__':
    for tf in (sys.argv[1:] or ['M5', 'M1']):
        run_tf(tf)
