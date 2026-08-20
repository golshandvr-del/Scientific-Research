#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S624 — فاز جست‌وجو (نیمهٔ نخست فقط — PREREG commit 1ec6d97e)

پس‌زنی EMA در روند صعودی، فقط LONG:
  (الف) کندل قبل تماماً بالای EMA(P): low[i-1] > EMA[i-1]
  (ب) low[i] ≤ EMA[i] (بوسهٔ حمایت)
  (ج) close[i] > EMA[i] (پس‌زنی موفق)
"""
import gc
import json
import math
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se            # noqa: E402
from engine import indicator_bank as ib          # noqa: E402
from tools import s434_fast_data as fd           # noqa: E402

SEED = 20260816
EMA_PS = (89, 144, 233)
K_SLS = (1.5, 2.0)
RRS = (1.0, 1.5)
ATR_P = 100
N_UNCOND = 20000
MAX_HOLD = {'M30': 120, 'H1': 64, 'H2': 64, 'H3': 64}

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_scan_S624')


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
    mh = MAX_HOLD[tf]
    pip = se.ASSETS['XAUUSD']['pip']
    print(f"[S624/{tf}] src={src} n_full={n_full} search_half={n} mh={mh}", flush=True)

    lo = df['low'].values.astype(np.float64)
    cl = df['close'].values.astype(np.float64)
    atr_pip = ib.atr_s(df, ATR_P).values / pip
    valid = np.isfinite(atr_pip) & (atr_pip > 0)
    valid[:max(ATR_P, max(EMA_PS)) + 1] = False

    rng = np.random.default_rng(SEED)
    vidx = np.where(valid)[0]
    n_samp = min(N_UNCOND, len(vidx))
    pick = np.sort(rng.choice(len(vidx), size=n_samp, replace=False))
    bsig = np.zeros(n, bool)
    bsig[vidx[pick]] = True

    # مبنای بی‌قید LONG به تفکیک هندسه (یک بار؛ مستقل از P)
    uncond = {}
    for k_sl in K_SLS:
        sl_arr = k_sl * atr_pip
        for rr in RRS:
            tr = se.simulate_trades(df, bsig, np.zeros(n, bool), sl_arr,
                                    rr * sl_arr, 'XAUUSD', max_hold=mh,
                                    allow_overlap=False)
            uncond[(k_sl, rr)] = dict(wr=wr_of(tr), n=int(len(tr)))
            del tr
    gc.collect()
    print(f"[S624/{tf}] مبنای بی‌قید LONG آماده ({time.time()-t0:.0f}s)", flush=True)

    rows = []
    cfg_i = 0
    for P in EMA_PS:
        ema = df['close'].ewm(span=P, adjust=False).mean().values
        above_prev = np.zeros(n, bool)
        above_prev[1:] = lo[:-1] > ema[:-1]          # کندل قبل تماماً بالای EMA
        sig = above_prev & (lo <= ema) & (cl > ema) & valid
        n_ev = int(sig.sum())
        for k_sl in K_SLS:
            sl_arr = k_sl * atr_pip
            for rr in RRS:
                cfg_i += 1
                if n_ev == 0:
                    continue
                tr = se.simulate_trades(df, sig, np.zeros(n, bool), sl_arr,
                                        rr * sl_arr, 'XAUUSD', max_hold=mh,
                                        allow_overlap=False)
                n_tr = int(len(tr))
                if n_tr == 0:
                    continue
                wr = wr_of(tr)
                ref = uncond[(k_sl, rr)]['wr']
                lift = (wr - ref) if ref is not None else None
                rows.append(dict(
                    P=P, k_sl=k_sl, rr=rr, n=n_tr, n_events=n_ev,
                    wr=round(wr, 3),
                    ref_wr=None if ref is None else round(ref, 3),
                    lift=None if lift is None else round(lift, 3),
                    exp_pip=round(float(np.mean(tr['pnl_pip'])), 3),
                    lift_sqrt_n=None if lift is None
                    else round(float(lift * np.sqrt(n_tr)), 1)))
                del tr
        del ema
        gc.collect()
        print(f"[S624/{tf}] P={P} تمام (events={n_ev}, {time.time()-t0:.0f}s)",
              flush=True)
    rows.sort(key=lambda r: -(r['lift_sqrt_n'] if r['lift_sqrt_n'] is not None
                              else -1e9))
    out = dict(tf=tf, src=src, n_full=n_full, n_search=n, half_bar=half,
               seed=SEED, n_configs=cfg_i,
               elapsed_s=round(time.time() - t0, 1), top20=rows[:20],
               n_rows=len(rows),
               uncond={f"{k[0]}x{k[1]}": v for k, v in uncond.items()})
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, f'{tf}.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"[S624/{tf}] تمام: {cfg_i} پیکربندی → {tf}.json", flush=True)
    for r in rows:
        if r['lift'] and r['lift'] >= 4 and r['exp_pip'] > 0:
            p0 = r['ref_wr'] / 100
            nreq = (3.09 * 100 * math.sqrt(p0 * (1 - p0)) / r['lift']) ** 2
            tag = '✓✓✓ گذرندهٔ چهارشرطی' if r['n'] >= nreq else f'✗n(req={nreq:.0f})'
            print(f"[S624/{tf}] {tag} {r}", flush=True)
    del df
    gc.collect()
    return out


if __name__ == '__main__':
    for tf in (sys.argv[1:] or ['H1', 'H2', 'H3', 'M30']):
        run_tf(tf)
