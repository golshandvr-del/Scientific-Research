#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S674 — فاز جست‌وجو (فقط نیمهٔ نخست — مسیر C، PREREG در git قبل از این فایل)

Hikkake fade (Chesler 2004): inside-bar در i؛ بارِ i+1 فقط به یک سمت می‌شکند؛
اگر در ≤W بارِ بعد close به سمتِ مخالفِ محدودهٔ inside-bar برود → شکست کاذب →
معامله در جهتِ مخالفِ شکست. گیتِ درفتِ علّی K=180 (منجمد از S966).

  * خانواده: W{1,2,3} × gate{none,aligned} × k_sl{1,1.5,2} × RR{1.5,2} × side{L,S,both} = 108/TF
  * مبنا: gate=none → کانونیکالِ بی‌قید؛ gate=aligned → درفت-شرطی (per side)
  * yearly_net per side برای معیار (f-per-side)
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

SEED = 20260904
WS = (1, 2, 3)
GATES = ('none', 'aligned')
K_SLS = (1.0, 1.5, 2.0)
RRS = (1.5, 2.0)
ATR_P = 100
K_DRIFT = 180
N_UNCOND = 20000

MAX_HOLD = {  # منجمد — همان دیکشنری S670 PREREG
    'M1': 240, 'M3': 240, 'M4': 240, 'M5': 240, 'M6': 240,
    'M10': 120, 'M12': 120, 'M15': 120, 'M20': 120, 'M30': 120,
    'H1': 64, 'H2': 64, 'H3': 64,
    'H6': 32, 'H8': 32, 'H12': 32,
    'D1': 16, 'W1': 8, 'MN1': 8,
}

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_scan_S674')


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


def hikkake_signals(h, lo, c, W):
    """برمی‌گرداند (long_sig, short_sig) در بارِ تأیید k (ورود open[k+1] در موتور).

    inside-bar در i: h[i]<=h[i-1] & lo[i]>=lo[i-1]
    شکستِ صعودی در i+1: h[i+1]>h[i] & lo[i+1]>=lo[i]  → کاندیدای SHORT
      تأیید: اولین k∈[i+2, i+1+W] با c[k]<lo[i]؛ ابطال اگر قبل از آن c[k]>h[i+1]
    آینه برای LONG.
    """
    n = len(c)
    inside = np.zeros(n, bool)
    inside[1:] = (h[1:] <= h[:-1]) & (lo[1:] >= lo[:-1])
    long_sig = np.zeros(n, bool)
    short_sig = np.zeros(n, bool)
    idx = np.where(inside)[0]
    for i in idx:
        j = i + 1
        if j + W + 1 >= n:
            break
        up_break = (h[j] > h[i]) and (lo[j] >= lo[i])
        dn_break = (lo[j] < lo[i]) and (h[j] <= h[i])
        if up_break:
            for k in range(j + 1, j + W + 1):
                if c[k] > h[j]:          # شکست واقعی → ابطال
                    break
                if c[k] < lo[i]:         # تأییدِ کذب → SHORT
                    short_sig[k] = True
                    break
        elif dn_break:
            for k in range(j + 1, j + W + 1):
                if c[k] < lo[j]:
                    break
                if c[k] > h[i]:
                    long_sig[k] = True
                    break
    return long_sig, short_sig


def yearly_nets_side(tr, years_arr, side):
    x = tr[tr['direction'] == side]
    if len(x) == 0:
        return {}
    eb = x['entry_bar'].values
    pnl = x['pnl_pip'].values
    yrs = years_arr[eb]
    return {int(y): round(float(pnl[yrs == y].sum()), 1) for y in np.unique(yrs)}


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
        print(f"[S674/{tf}] ⚠️ src={d_src} خارج از mt5_full — E-16 رد شد", flush=True)
        return None
    print(f"[S674/{tf}] src={d_src} n_full={n_full} search_half={n} max_hold={mh}",
          flush=True)

    h = df['high'].values.astype(np.float64)
    lo = df['low'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    years = pd.to_datetime(df['time'].values, unit='s').year.values

    atr_pip = ib.atr_s(df, ATR_P).values / pip
    valid = np.isfinite(atr_pip) & (atr_pip > 0)
    valid[:max(ATR_P, K_DRIFT) + 2] = False

    # درفتِ علّی: close[k-1] vs close[k-1-K]
    drift_up = np.zeros(n, bool)
    drift_dn = np.zeros(n, bool)
    drift_up[K_DRIFT + 1:] = c[K_DRIFT:-1] > c[:-(K_DRIFT + 1)]
    drift_dn[K_DRIFT + 1:] = c[K_DRIFT:-1] < c[:-(K_DRIFT + 1)]

    rng = np.random.default_rng(SEED)

    # --- مبناها: (gate, k_sl, rr, side) ---
    pools = {('none', 'long'): np.where(valid)[0],
             ('none', 'short'): np.where(valid)[0],
             ('aligned', 'long'): np.where(valid & drift_up)[0],
             ('aligned', 'short'): np.where(valid & drift_dn)[0]}
    uncond = {}
    for (gate, side), pool in pools.items():
        if len(pool) < 100:
            for k_sl in K_SLS:
                for rr in RRS:
                    uncond[(gate, k_sl, rr, side)] = dict(wr=None, n=0)
            continue
        n_samp = min(N_UNCOND, len(pool))
        pick = np.sort(rng.choice(len(pool), size=n_samp, replace=False))
        sig = np.zeros(n, bool); sig[pool[pick]] = True
        for k_sl in K_SLS:
            sl_arr = k_sl * atr_pip
            for rr in RRS:
                tp_arr = rr * sl_arr
                ls = sig if side == 'long' else np.zeros(n, bool)
                ss = sig if side == 'short' else np.zeros(n, bool)
                tr = se.simulate_trades(df, ls, ss, sl_arr, tp_arr, 'XAUUSD',
                                        max_hold=mh, allow_overlap=False)
                uncond[(gate, k_sl, rr, side)] = dict(wr=wr_of(tr), n=int(len(tr)))
                del tr
    gc.collect()
    print(f"[S674/{tf}] مبناها اندازه‌گیری شد ({len(uncond)} سلول، {time.time()-t0:.0f}s)",
          flush=True)

    rows = []
    cfg_i = 0
    for W in WS:
        L_raw, S_raw = hikkake_signals(h, lo, c, W)
        L_raw &= valid; S_raw &= valid
        for gate in GATES:
            if gate == 'aligned':
                Lg = L_raw & drift_up
                Sg = S_raw & drift_dn
            else:
                Lg, Sg = L_raw, S_raw
            for k_sl in K_SLS:
                sl_arr = k_sl * atr_pip
                for rr in RRS:
                    tp_arr = rr * sl_arr
                    for side in ('long', 'short', 'both'):
                        cfg_i += 1
                        ls = Lg if side in ('long', 'both') else np.zeros(n, bool)
                        ss = Sg if side in ('short', 'both') else np.zeros(n, bool)
                        if not (ls.any() or ss.any()):
                            continue
                        tr = se.simulate_trades(df, ls, ss, sl_arr, tp_arr,
                                                'XAUUSD', max_hold=mh,
                                                allow_overlap=False)
                        n_tr = int(len(tr))
                        if n_tr == 0:
                            continue
                        wr = wr_of(tr); pf_val = pf_of(tr)
                        nL = int((tr['direction'] == 'long').sum()); nS = n_tr - nL
                        refs, wts = [], []
                        for s2, cnt in (('long', nL), ('short', nS)):
                            u = uncond[(gate, k_sl, rr, s2)]['wr']
                            if u is not None and cnt > 0:
                                refs.append(u * cnt); wts.append(cnt)
                        ref = sum(refs) / sum(wts) if wts else None
                        lift = (wr - ref) if ref is not None else None
                        pnl = tr['pnl_pip'].values
                        rows.append(dict(
                            W=W, gate=gate, side=side, k_sl=k_sl, rr=rr,
                            n=n_tr, n_long=nL, n_short=nS, wr=round(wr, 3),
                            ref_wr=None if ref is None else round(ref, 3),
                            lift=None if lift is None else round(lift, 3),
                            pf=round(pf_val, 3),
                            exp_pip=round(float(pnl.mean()), 3),
                            net=round(float(pnl.sum()), 1),
                            yearly_net_long=yearly_nets_side(tr, years, 'long'),
                            yearly_net_short=yearly_nets_side(tr, years, 'short'),
                            lift_sqrt_n=None if lift is None
                            else round(float(lift * np.sqrt(n_tr)), 1)))
                        del tr
        gc.collect()
    dt = time.time() - t0
    rows.sort(key=lambda r: -(r['lift_sqrt_n'] if r['lift_sqrt_n'] is not None
                              else -1e9))
    out = dict(tf=tf, src=d_src, n_full=n_full, n_search=n, half_bar=half,
               seed=SEED, n_configs=cfg_i, max_hold=mh, k_drift=K_DRIFT,
               elapsed_s=round(dt, 1),
               uncond={f"{k[0]}_{k[1]}x{k[2]}_{k[3]}": v for k, v in uncond.items()},
               top30=rows[:30], n_rows=len(rows))
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f'{tf}.json')
    with open(path, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"[S674/{tf}] تمام شد: {cfg_i} پیکربندی، {len(rows)} نتیجه، {dt:.0f}s → {path}",
          flush=True)
    if rows:
        r = {k: v for k, v in rows[0].items() if not k.startswith('yearly')}
        print(f"[S674/{tf}] بهترین: {r}", flush=True)
    return out


if __name__ == '__main__':
    tfs = sys.argv[1:] or list(MAX_HOLD)
    for tf in tfs:
        run_tf(tf)
