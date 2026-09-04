#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S673 — فاز جست‌وجو (فقط نیمهٔ نخست — مسیر C، PREREG در git قبل از این فایل)

فرضیه (George & Hwang 2004): مجاورتِ close به سقفِ رولینگِ N-باره (لنگرگاه) +
پول‌بکِ یک‌باره (بارِ نزولی) → ادامهٔ صعود. آینه برای کف/short.

  * جست‌وجو فقط [0, n/2) — نگه‌داشت لمس نمی‌شود
  * خانواده: N{100,200,400} × θ{1,2} × k_sl{1,1.5,2} × RR{1.5,2} × side{L,S,both} = 108/TF
  * مبنای بی‌قیدِ کانونیکال: ورودهای تصادفی از همهٔ بارهای valid (per k_sl,rr,side)
  * معیارِ (f): سازگاریِ سالانه — net هر سال در نیمهٔ جستجو ثبت می‌شود
  * چک‌پوینت: JSON هر TF در results/_scan_S673/

اجرا:  python3 strategies/s673_highprox_search.py M1
"""
import gc
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se          # noqa: E402
from engine import indicator_bank as ib        # noqa: E402
from tools import s434_fast_data as fd         # noqa: E402

SEED = 20260824
NS = (100, 200, 400)
THETAS = (1.0, 2.0)
K_SLS = (1.0, 1.5, 2.0)
RRS = (1.5, 2.0)
ATR_P = 100
N_UNCOND = 20000

MAX_HOLD = {  # منجمد — همان دیکشنری S670 PREREG
    'M1': 240, 'M3': 240, 'M4': 240, 'M5': 240, 'M6': 240,
    'M10': 120, 'M12': 120, 'M15': 120, 'M20': 120, 'M30': 120,
    'H1': 64, 'H2': 64, 'H3': 64,
    'H6': 32, 'H8': 32, 'H12': 32,
    'D1': 16, 'W1': 8, 'MN1': 8,
}

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_scan_S673')


def wr_of(tr):
    if tr is None or len(tr) == 0:
        return None
    return 100.0 * float((tr['pnl_pip'] > 0).mean())


def pf_of(tr):
    if tr is None or len(tr) == 0:
        return None
    p = tr['pnl_pip'].values
    gw = p[p > 0].sum()
    gl = -p[p < 0].sum()
    return float(gw / gl) if gl > 0 else 999.0


def rolling_max_prev(x, N):
    """سقفِ رولینگِ N بارِ قبل (تا i-1؛ shift(1)) — بدون نگاه به آینده."""
    s = pd.Series(x).rolling(N, min_periods=N).max().shift(1).values
    return s


def rolling_min_prev(x, N):
    s = pd.Series(x).rolling(N, min_periods=N).min().shift(1).values
    return s


def yearly_nets(tr, years_arr):
    """net (pip) به تفکیک سالِ ورود."""
    eb = tr['entry_bar'].values
    pnl = tr['pnl_pip'].values
    yrs = years_arr[eb]
    out = {}
    for y in np.unique(yrs):
        out[int(y)] = round(float(pnl[yrs == y].sum()), 1)
    return out


def run_tf(tf):
    t0 = time.time()
    d = fd.load_fast('XAUUSD', tf)
    df_full = fd.as_dataframe(d)
    n_full = len(df_full)
    half = n_full // 2
    df = df_full.iloc[:half].reset_index(drop=True).copy()
    del df_full
    d_src = d['src']
    d.clear(); gc.collect()
    n = len(df)
    mh = MAX_HOLD[tf]
    pip = se.ASSETS['XAUUSD']['pip']
    if 'mt5_full' not in d_src:
        print(f"[S673/{tf}] ⚠️ src={d_src} خارج از mt5_full — طبق تلهٔ E-16 رد شد",
              flush=True)
        return None
    print(f"[S673/{tf}] src={d_src} n_full={n_full} search_half={n} max_hold={mh}",
          flush=True)

    o = df['open'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    lo = df['low'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    years = pd.to_datetime(df['time'].values, unit='s').year.values

    atr_raw = ib.atr_s(df, ATR_P).values
    atr_pip = atr_raw / pip
    valid = np.isfinite(atr_pip) & (atr_pip > 0)
    valid[:ATR_P + 1] = False
    dn_bar = c < o
    up_bar = c > o

    rng = np.random.default_rng(SEED)

    # --- مبنای بی‌قیدِ کانونیکال: per (k_sl, rr, side) ---
    uncond = {}
    pool = np.where(valid)[0]
    n_samp = min(N_UNCOND, len(pool))
    pick = np.sort(rng.choice(len(pool), size=n_samp, replace=False))
    sig_u = np.zeros(n, bool); sig_u[pool[pick]] = True
    for k_sl in K_SLS:
        sl_arr = k_sl * atr_pip
        for rr in RRS:
            tp_arr = rr * sl_arr
            for side in ('long', 'short'):
                ls = sig_u if side == 'long' else np.zeros(n, bool)
                ss = sig_u if side == 'short' else np.zeros(n, bool)
                tr = se.simulate_trades(df, ls, ss, sl_arr, tp_arr, 'XAUUSD',
                                        max_hold=mh, allow_overlap=False)
                uncond[(k_sl, rr, side)] = dict(wr=wr_of(tr), n=int(len(tr)))
                del tr
    gc.collect()
    print(f"[S673/{tf}] مبنای بی‌قید اندازه‌گیری شد ({len(uncond)} سلول، "
          f"{time.time()-t0:.0f}s)", flush=True)

    # --- جست‌وجوی خانوادهٔ منجمد ---
    rows = []
    cfg_i = 0
    for N in NS:
        if n <= N + ATR_P + 5:
            continue
        hi_prev = rolling_max_prev(h, N)
        lo_prev = rolling_min_prev(lo, N)
        okN = valid & np.isfinite(hi_prev) & np.isfinite(lo_prev)
        for theta in THETAS:
            near_hi = okN & ((hi_prev - c) <= theta * atr_raw) & (c <= hi_prev)
            near_lo = okN & ((c - lo_prev) <= theta * atr_raw) & (c >= lo_prev)
            long_raw = near_hi & dn_bar
            short_raw = near_lo & up_bar
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
                        tr = se.simulate_trades(df, ls, ss, sl_arr, tp_arr,
                                                'XAUUSD', max_hold=mh,
                                                allow_overlap=False)
                        n_tr = int(len(tr))
                        if n_tr == 0:
                            continue
                        wr = wr_of(tr)
                        pf_val = pf_of(tr)
                        if side == 'both':
                            nL = int((tr['direction'] == 'long').sum())
                            nS = n_tr - nL
                            refs, wts = [], []
                            for s2, cnt in (('long', nL), ('short', nS)):
                                u = uncond[(k_sl, rr, s2)]['wr']
                                if u is not None and cnt > 0:
                                    refs.append(u * cnt); wts.append(cnt)
                            ref = sum(refs) / sum(wts) if wts else None
                        else:
                            ref = uncond[(k_sl, rr, side)]['wr']
                        lift = (wr - ref) if ref is not None else None
                        pnl = tr['pnl_pip'].values
                        ynets = yearly_nets(tr, years)
                        rows.append(dict(
                            N=N, theta=theta, side=side, k_sl=k_sl, rr=rr,
                            n=n_tr, wr=round(wr, 3),
                            ref_wr=None if ref is None else round(ref, 3),
                            lift=None if lift is None else round(lift, 3),
                            pf=round(pf_val, 3),
                            exp_pip=round(float(pnl.mean()), 3),
                            net=round(float(pnl.sum()), 1),
                            yearly_net=ynets,
                            lift_sqrt_n=None if lift is None
                            else round(float(lift * np.sqrt(n_tr)), 1)))
                        del tr
        gc.collect()
    dt = time.time() - t0
    rows.sort(key=lambda r: -(r['lift_sqrt_n'] if r['lift_sqrt_n'] is not None
                              else -1e9))
    out = dict(tf=tf, src=d_src, n_full=n_full, n_search=n, half_bar=half,
               seed=SEED, n_configs=cfg_i, max_hold=mh, elapsed_s=round(dt, 1),
               uncond={f"{k[0]}x{k[1]}_{k[2]}": v for k, v in uncond.items()},
               top30=rows[:30], n_rows=len(rows))
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f'{tf}.json')
    with open(path, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"[S673/{tf}] تمام شد: {cfg_i} پیکربندی، {len(rows)} نتیجه، {dt:.0f}s → {path}",
          flush=True)
    if rows:
        r = dict(rows[0]); r.pop('yearly_net', None)
        print(f"[S673/{tf}] بهترین: {r}", flush=True)
    return out


if __name__ == '__main__':
    tfs = sys.argv[1:] or list(MAX_HOLD)
    for tf in tfs:
        run_tf(tf)
