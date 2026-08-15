#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S621 — فاز جست‌وجو (نیمهٔ نخست فقط — PREREG commit 4d5dd276)

تلاقی MTF: خروج LagRSI از اشباع خرید در TF پایه (H1/H2/H3) — SHORT —
فقط وقتی LagRSI(0.5) در TF تأیید (H12/D1) از آخرین کندلِ بسته‌شده ≥ c باشد.

forward-safe بودن تأیید: برای هر بار پایه با زمان t، مقدار TF بالا از کندلی
برداشته می‌شود که «زمان شروعش + طول دوره‌اش ≤ t» است (searchsorted، سپس یک گام عقب).
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

SEED = 20260813
BASE_GAMMAS = (0.4, 0.5)
BASE_THS = (15.0, 20.0)
CONF_TFS = ('H12', 'D1')
CONF_GAMMA = 0.5
CONF_LEVELS = (70.0, 80.0)
K_SLS = (1.5, 2.0)
RRS = (1.0, 1.5)
ATR_P = 100
MAX_HOLD = 64
N_UNCOND = 20000
TF_SECONDS = {'H12': 12 * 3600, 'D1': 24 * 3600}

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_scan_S621')


def wr_of(tr):
    if tr is None or len(tr) == 0:
        return None
    return 100.0 * float((tr['pnl_pip'] > 0).mean())


def load_half(tf):
    d = fd.load_fast('XAUUSD', tf)
    df_full = fd.as_dataframe(d)
    half = len(df_full) // 2
    df = df_full.iloc[:half].reset_index(drop=True).copy()
    src = d['src']
    n_full = len(df_full)
    del df_full
    d.clear()
    gc.collect()
    return df, src, n_full, half


def conf_series_at(base_time, conf_df, conf_lag, conf_tf):
    """مقدار LagRSI تأیید از آخرین کندلِ *بسته‌شدهٔ* TF بالا برای هر بار پایه."""
    closes = conf_df['time'].values.astype(np.int64) + TF_SECONDS[conf_tf]
    # اندیس آخرین کندل تأیید که پیش از (یا در) زمان بار پایه بسته شده
    idx = np.searchsorted(closes, base_time, side='right') - 1
    out = np.full(len(base_time), np.nan)
    ok = idx >= 0
    out[ok] = conf_lag[idx[ok]]
    return out


def run_base_tf(base_tf, conf_cache):
    t0 = time.time()
    df, src, n_full, half = load_half(base_tf)
    n = len(df)
    pip = se.ASSETS['XAUUSD']['pip']
    base_time = df['time'].values.astype(np.int64)
    print(f"[S621/{base_tf}] src={src} n_full={n_full} search_half={n}", flush=True)

    atr_pip = ib.atr_s(df, ATR_P).values / pip
    valid = np.isfinite(atr_pip) & (atr_pip > 0)
    valid[:ATR_P + 1] = False

    rng = np.random.default_rng(SEED)
    vidx = np.where(valid)[0]

    # تأیید MTF (forward-safe) — یک بار برای هر TF تأیید
    conf_vals = {}
    for ctf in CONF_TFS:
        cdf, clag = conf_cache[ctf]
        conf_vals[ctf] = conf_series_at(base_time, cdf, clag, ctf)

    # --- مبنای بی‌قید: شرطی به دروازهٔ تأیید نیست؟ چرا، هست! ---
    # نکتهٔ روش‌شناختی: مهارت ادعایی مالِ «زمان‌بندی رویداد پایه در بافت اشباع» است.
    # پس مبنا باید ورودِ بی‌قید *درون همان بافت* باشد (بی‌قید نسبت به سیگنال پایه)،
    # وگرنه lift بافت را به حساب سیگنال می‌گذاریم (خطای S346: drift ≠ skill).
    rows = []
    cfg_i = 0
    for ctf in CONF_TFS:
        cv = conf_vals[ctf]
        for clev in CONF_LEVELS:
            gate = np.isfinite(cv) & (cv >= clev)
            gidx = np.where(valid & gate)[0]
            if len(gidx) < 200:
                continue
            # مبنای بی‌قید درون بافت، به تفکیک هندسه
            uncond = {}
            n_samp = min(N_UNCOND, len(gidx))
            pick = np.sort(rng.choice(len(gidx), size=n_samp, replace=False))
            ub = gidx[pick]
            bsig = np.zeros(n, bool)
            bsig[ub] = True
            for k_sl in K_SLS:
                sl_arr = k_sl * atr_pip
                for rr in RRS:
                    tr = se.simulate_trades(df, np.zeros(n, bool), bsig,
                                            sl_arr, rr * sl_arr, 'XAUUSD',
                                            max_hold=MAX_HOLD, allow_overlap=False)
                    uncond[(k_sl, rr)] = dict(wr=wr_of(tr), n=int(len(tr)))
            for gamma in BASE_GAMMAS:
                lag = ib.laguerre_rsi(df, gamma).values
                prev = np.roll(lag, 1)
                prev[0] = 50.0
                for th in BASE_THS:
                    sig = (prev > 100.0 - th) & (lag <= 100.0 - th) & valid & gate
                    for k_sl in K_SLS:
                        sl_arr = k_sl * atr_pip
                        for rr in RRS:
                            cfg_i += 1
                            if not sig.any():
                                continue
                            tr = se.simulate_trades(df, np.zeros(n, bool), sig,
                                                    sl_arr, rr * sl_arr, 'XAUUSD',
                                                    max_hold=MAX_HOLD,
                                                    allow_overlap=False)
                            n_tr = int(len(tr))
                            if n_tr == 0:
                                continue
                            wr = wr_of(tr)
                            ref = uncond[(k_sl, rr)]['wr']
                            lift = (wr - ref) if ref is not None else None
                            rows.append(dict(
                                conf_tf=ctf, conf_lev=clev, gamma=gamma, th=th,
                                k_sl=k_sl, rr=rr, n=n_tr, wr=round(wr, 3),
                                ref_wr=None if ref is None else round(ref, 3),
                                lift=None if lift is None else round(lift, 3),
                                exp_pip=round(float(np.mean(tr['pnl_pip'])), 3),
                                lift_sqrt_n=None if lift is None
                                else round(float(lift * np.sqrt(n_tr)), 1)))
                            del tr
                del lag, prev
                gc.collect()
            print(f"[S621/{base_tf}] conf={ctf}≥{clev} تمام "
                  f"(gate_bars={len(gidx)}, {time.time()-t0:.0f}s)", flush=True)
    rows.sort(key=lambda r: -(r['lift_sqrt_n'] if r['lift_sqrt_n'] is not None
                              else -1e9))
    out = dict(base_tf=base_tf, src=src, n_full=n_full, n_search=n,
               half_bar=half, seed=SEED, n_configs=cfg_i,
               elapsed_s=round(time.time() - t0, 1),
               top20=rows[:20], n_rows=len(rows))
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f'{base_tf}.json')
    with open(path, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"[S621/{base_tf}] تمام: {cfg_i} پیکربندی → {path}", flush=True)
    if rows:
        print(f"[S621/{base_tf}] بهترین: {rows[0]}", flush=True)
    return out


if __name__ == '__main__':
    # کندل‌های تأیید (نیمهٔ نخست) یک بار بارگیری و LagRSI(0.5) محاسبه می‌شود
    conf_cache = {}
    for ctf in CONF_TFS:
        cdf, csrc, _, _ = load_half(ctf)
        conf_cache[ctf] = (cdf, ib.laguerre_rsi(cdf, CONF_GAMMA).values)
        print(f"[S621] تأیید {ctf} آماده (src={csrc}, n={len(cdf)})", flush=True)
    for tf in (sys.argv[1:] or ['H1', 'H2', 'H3']):
        run_base_tf(tf, conf_cache)
