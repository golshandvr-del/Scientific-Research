#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S671 — فاز جست‌وجو (فقط نیمهٔ نخست — مسیر C پیش‌ثبت‌شده، PREREG در git)

فرضیه: گذر TrendFlex از ±θ فقط با رژیم بلندمدتِ هم‌جهت (شیب ssf) لبهٔ
هر-معامله‌ای ضخیم‌تر از هزینه دارد (PF≥1.3) روی H2–D1 طلا.

  * جست‌وجو فقط [0, n/2) — نگه‌داشت لمس نمی‌شود
  * خانوادهٔ منجمد: 3×3×3×2×3×2 = 324 پیکربندی per TF؛ TFها: H2,H3,H6,H8,H12,D1
  * مبنای بی‌قید با **همان فیلتر رژیم** روی ورودهای تصادفی (مدل صفر مشروط)
  * قانون اندک‌اندک: JSON هر TF در results/_scan_S671/

اجرا:  python3 strategies/s671_trendflex_regime_search.py H2
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
from tools import s434_fast_data as fd                         # noqa: E402
from tools.s670_trendflex_fast import trendflex_fast, ssf_fast  # noqa: E402

SEED = 20260813
PERIODS = (13, 21, 34)
THETAS = (1.0, 1.272, 1.618)
PERIOD_FS = (89, 144)
L_SLOPE = 8
K_SLS = (1.0, 1.5, 2.0)
RRS = (1.5, 2.0)
ATR_P = 100
N_UNCOND = 20000

MAX_HOLD = {'H2': 64, 'H3': 64, 'H6': 32, 'H8': 32, 'H12': 32, 'D1': 16}

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_scan_S671')


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
    print(f"[S671/{tf}] src={d_src} n_full={n_full} search_half={n} max_hold={mh}",
          flush=True)

    atr_pip = ib.atr_s(df, ATR_P).values / pip
    valid = np.isfinite(atr_pip) & (atr_pip > 0)
    valid[:ATR_P + 1] = False
    close_arr = df['close'].values.astype(np.float64)

    # --- فیلترهای رژیم (مشترک برای همهٔ پیکربندی‌ها) ---
    regimes = {}
    for pf_ in PERIOD_FS:
        s = ssf_fast(close_arr, pf_)
        up = np.zeros(n, bool)
        dn = np.zeros(n, bool)
        up[L_SLOPE:] = s[L_SLOPE:] > s[:-L_SLOPE]
        dn[L_SLOPE:] = s[L_SLOPE:] < s[:-L_SLOPE]
        up[:pf_ + L_SLOPE] = False
        dn[:pf_ + L_SLOPE] = False
        regimes[pf_] = (up, dn)
        del s
    gc.collect()

    rng = np.random.default_rng(SEED)

    # --- مبنای بی‌قیدِ مشروط: به تفکیک (period_f, k_sl, rr, side) ---
    # مبنا باید همان قید رژیم را ببیند: ورودهای تصادفی از بارهای valid∧regime.
    uncond = {}
    for pf_ in PERIOD_FS:
        up, dn = regimes[pf_]
        for side, rmask in (('long', up), ('short', dn)):
            pool = np.where(valid & rmask)[0]
            if len(pool) < 100:
                for k_sl in K_SLS:
                    for rr in RRS:
                        uncond[(pf_, k_sl, rr, side)] = dict(wr=None, n=0)
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
                    uncond[(pf_, k_sl, rr, side)] = dict(wr=wr_of(tr), n=int(len(tr)))
                    del tr
    gc.collect()
    print(f"[S671/{tf}] مبنای مشروط اندازه‌گیری شد ({len(uncond)} سلول، "
          f"{time.time()-t0:.0f}s)", flush=True)

    # --- جست‌وجوی خانوادهٔ منجمد ---
    rows = []
    cfg_i = 0
    for period in PERIODS:
        tfx = trendflex_fast(close_arr, period)
        prev = np.roll(tfx, 1); prev[0] = 0.0
        for th in THETAS:
            long_ev = (prev <= th) & (tfx > th) & valid
            short_ev = (prev >= -th) & (tfx < -th) & valid
            for pf_ in PERIOD_FS:
                up, dn = regimes[pf_]
                long_raw = long_ev & up
                short_raw = short_ev & dn
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
                                    u = uncond[(pf_, k_sl, rr, s2)]['wr']
                                    if u is not None and cnt > 0:
                                        refs.append(u * cnt); wts.append(cnt)
                                ref = sum(refs) / sum(wts) if wts else None
                            else:
                                ref = uncond[(pf_, k_sl, rr, side)]['wr']
                            lift = (wr - ref) if ref is not None else None
                            rows.append(dict(
                                period=period, theta=th, period_f=pf_, side=side,
                                k_sl=k_sl, rr=rr, n=n_tr, wr=round(wr, 3),
                                ref_wr=None if ref is None else round(ref, 3),
                                lift=None if lift is None else round(lift, 3),
                                pf=round(pf_val, 3),
                                exp_pip=round(float(np.mean(tr['pnl_pip'])), 3),
                                lift_sqrt_n=None if lift is None
                                else round(float(lift * np.sqrt(n_tr)), 1)))
                            del tr
        del tfx, prev
        gc.collect()
        print(f"[S671/{tf}] period={period} تمام شد ({time.time()-t0:.0f}s)",
              flush=True)
    dt = time.time() - t0
    rows.sort(key=lambda r: -(r['lift_sqrt_n'] if r['lift_sqrt_n'] is not None
                              else -1e9))
    out = dict(tf=tf, src=d_src, n_full=n_full, n_search=n, half_bar=half,
               seed=SEED, n_configs=cfg_i, max_hold=mh, elapsed_s=round(dt, 1),
               uncond={f"{k[0]}_{k[1]}x{k[2]}_{k[3]}": v for k, v in uncond.items()},
               top30=rows[:30], n_rows=len(rows))
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f'{tf}.json')
    with open(path, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"[S671/{tf}] تمام شد: {cfg_i} پیکربندی، {len(rows)} نتیجه، {dt:.0f}s → {path}",
          flush=True)
    if rows:
        print(f"[S671/{tf}] بهترین: {rows[0]}", flush=True)
    return out


if __name__ == '__main__':
    tfs = sys.argv[1:] or list(MAX_HOLD)
    for tf in tfs:
        run_tf(tf)
