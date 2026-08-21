#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S972 — شوکِ اسپردِ Corwin-Schultz → بازگشتِ مؤلفهٔ گذرا (fade)
================================================================================
پیش‌ثبت: results/S972_PREREG_cs_spread_shock_fade.md (commit c325c98c — پیش از هر PnL)
معیار:   RQS2 v2.6 gates_only. مسیرِ B — یک تعریفِ منجمد، n_trials=24.

تعریف (بندِ ۱ پیش‌ثبت):
  β_i = ln(H_{i−1}/L_{i−1})² + ln(H_i/L_i)²
  γ_i = ln(max(H_{i−1},H_i)/min(L_{i−1},L_i))²
  α = (√(2β)−√β)/(3−2√2) − √(γ/(3−2√2)) ;  S = 2(e^α−1)/(1+e^α) ; S<0→0
  شوک: S_i > q99ِ رولینگِ ۵۰۰ روی پنجرهٔ منتهی به i−1 (shift(1)) و S_i>0
  جهت: fade دوکندله d = −sign(close_i − close_{i−2}) ; ورود open کندلِ i+1

هندسه (بندِ ۲): SL=1.0×median(ATR14)، TP=1.5×SL، hold=6h ثابت (کف ۴ کندل).
نال (بندِ ۴): جای‌گشتِ مکانِ ورود، K=2000 هر سمت، بذر 20260820، split=0.70.

فقط XAUUSD. H4 بازنمونه از H1. checkpoint: results/_scan_S972/<TF>.json
اجرا: python3 strategies/s972_cs_spread_shock_fade.py M1 [--kperm 2000]
"""
import sys
import os
import json
import time as _time
import argparse

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import s434_fast_data as fd                                # noqa: E402
from engine import scalp_engine as se                                 # noqa: E402
from engine import rqs2                                               # noqa: E402
from strategies.s348_rr_sweep import queue_rr, trades_df, cost_pip    # noqa: E402
from strategies.s346_fast import barrier_outcomes, select_non_overlap  # noqa: E402

ASSET = 'XAUUSD'

# ---- ثابت‌های منجمدِ پیش‌ثبت ----
CS_WIN = 500
CS_Q = 0.99
ATR_WIN = 14
SL_K = 1.0
RR = 1.5
HOLD_HOURS = 6.0
HOLD_MIN_BARS = 4
N_TRIALS = 24
SPLIT_FRAC = 0.70
K_PERM = 2000
SEED = 20260820
NULL_POOL_MAX = 400_000

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_scan_S972')

_C1 = 3.0 - 2.0 * np.sqrt(2.0)


def load_tf(tf):
    if tf != 'H4':
        d = fd.load_fast(ASSET, tf)
        return fd.as_dataframe(d), d
    d1 = fd.load_fast(ASSET, 'H1')
    df1 = fd.as_dataframe(d1)
    t = df1['time'].values.astype(np.int64)
    grp = t // (4 * 3600)
    df = df1.groupby(grp).agg(
        time=('time', 'first'), open=('open', 'first'), high=('high', 'max'),
        low=('low', 'min'), close=('close', 'last'), volume=('volume', 'sum'),
    ).reset_index(drop=True)
    d = dict(d1)
    d['src'] = str(d1['src']) + ' (H4 resampled from H1)'
    return df, d


def bars_per_hour(df):
    dt = np.diff(df['time'].values.astype(np.int64))
    dt = dt[dt > 0]
    med = float(np.median(dt))
    return 3600.0 / med


def atr_plain(h, l, c, win=ATR_WIN):
    prev_c = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    return pd.Series(tr).rolling(win).mean().values


def cs_spread(h, l):
    """برآوردگرِ اسپردِ Corwin-Schultz (2012) — برداری، بدونِ look-ahead.

    S_i از (H,L)ِ کندل‌های i−1 و i ساخته می‌شود (فقط گذشته/حال).
    مقادیرِ منفی به صفر برش می‌خورند (استانداردِ مقاله).
    """
    lh = np.log(h)
    ll = np.log(l)
    hl2 = (lh - ll) ** 2                                   # ln(H/L)²
    beta = np.full_like(hl2, np.nan)
    beta[1:] = hl2[:-1] + hl2[1:]
    hmax = np.maximum.reduce([h, np.roll(h, 1)])
    lmin = np.minimum.reduce([l, np.roll(l, 1)])
    gamma = (np.log(hmax) - np.log(lmin)) ** 2
    gamma[0] = np.nan
    alpha = (np.sqrt(2.0 * beta) - np.sqrt(beta)) / _C1 - np.sqrt(gamma / _C1)
    s = 2.0 * (np.exp(alpha) - 1.0) / (1.0 + np.exp(alpha))
    s = np.where(np.isfinite(s), np.maximum(s, 0.0), np.nan)
    return s


def rolling_q_causal(x, w=CS_WIN, q=CS_Q, chunk=1_000_000):
    """چندکِ رولینگِ علّی: q روی پنجرهٔ w منتهی به i−1 (shift(1)).

    ⚡ chunked از ابتدا (درسِ OOMِ S971 روی M1ِ ۵M): هم‌پوشانیِ w+1 بین قطعه‌ها
    خروجی را بیت‌به‌بیت با نسخهٔ یک‌تکه برابر نگه می‌دارد.
    """
    n = len(x)
    out = np.full(n, np.nan)
    for s0 in range(0, n, chunk):
        e = min(n, s0 + chunk)
        start = max(0, s0 - (w + 1))
        seg = pd.Series(x[start:e])
        rq = seg.rolling(w, min_periods=w).quantile(q).shift(1).values
        out[s0:e] = rq[s0 - start:]
        del seg, rq
    return out


def build_signals(df):
    """(sig_idx, is_long) — شوکِ CS روی کندلِ i؛ fade دوکندله؛ ورود i+1."""
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    s = cs_spread(h, l)
    thr = rolling_q_causal(s)
    shock = np.isfinite(s) & np.isfinite(thr) & (s > thr) & (s > 0.0)
    idx = np.flatnonzero(shock)
    idx = idx[idx >= 2]
    move = c[idx] - c[idx - 2]
    keep = move != 0
    idx = idx[keep]
    return idx, ~(move[keep] > 0)          # fade: حرکتِ بالا ⇒ short


def build_null(df, sl_pip_scalar, hold, n_long, n_short, k_perm, rng, warmup):
    cfg = se.ASSETS[ASSET]
    pip, spread = float(cfg['pip']), float(cfg['spread_pip'])
    slip = float(cfg.get('slip_pip', 0.0))
    n = len(df)
    valid = np.arange(warmup, n - hold - 1)
    pool_note = f'full_valid={len(valid)}'
    if len(valid) > NULL_POOL_MAX:
        valid = np.sort(rng.choice(valid, size=NULL_POOL_MAX, replace=False))
        pool_note += f' pooled_to={NULL_POOL_MAX}'

    sl_d = np.full(len(valid), sl_pip_scalar * pip)
    tp_d = np.maximum(RR * sl_d, sl_d)

    null = {}
    for side, flag, n_side in (('long', True, n_long), ('short', False, n_short)):
        d = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                 perm_max=None, perm_k=None)
        if n_side >= 1 and len(valid) >= 2:
            fo = barrier_outcomes(df, valid, np.full(len(valid), flag),
                                  sl_d, tp_d, hold, pip, spread, slip)
            keep = select_non_overlap(fo['entry_bar'], fo['exit_off'])
            w_all = fo['win'][keep]
            if len(w_all):
                d['uncond_wr'] = float(w_all.mean() * 100.0)
            m = len(fo['entry_bar'])
            if m > n_side:
                wrs = []
                for _ in range(k_perm):
                    pick = np.sort(rng.choice(m, size=n_side, replace=False))
                    kp = select_non_overlap(fo['entry_bar'][pick],
                                            fo['exit_off'][pick])
                    wv = fo['win'][pick][kp]
                    if len(wv):
                        wrs.append(float(wv.mean() * 100.0))
                if wrs:
                    a = np.asarray(wrs)
                    d.update(perm_mean=float(a.mean()),
                             perm_sd=float(a.std(ddof=1)),
                             perm_max=float(a.max()), perm_k=int(len(a)))
        null[side] = d
        print(f"    null {side:<5} uncond={d['uncond_wr']} "
              f"perm_mean={d['perm_mean']} sd={d['perm_sd']} k={d['perm_k']}",
              flush=True)
    return null, pool_note


def run_tf(tf, k_perm=K_PERM, seed=SEED):
    t0 = _time.time()
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f'{tf}.json')
    rng = np.random.default_rng(seed)

    df, d = load_tf(tf)
    n = len(df)
    split = int(SPLIT_FRAC * n)
    bph = bars_per_hour(df)
    hold = max(HOLD_MIN_BARS, int(round(HOLD_HOURS * bph)))
    print(f"\n{'='*88}\n=== S972 CS-SPREAD-SHOCK-FADE :: {ASSET}-{tf}  bars={n:,}  "
          f"src={d['src']}\n    split_bar={split} · hold={hold} bars "
          f"(~{HOLD_HOURS}h) · cost={cost_pip(ASSET):.2f}pip · "
          f"N_TRIALS={N_TRIALS} · K={k_perm}", flush=True)

    out = dict(strategy='S972_CsSpreadShockFade', asset=ASSET, tf=tf, bars=n,
               src=str(d['src']), split_bar=split, hold=hold,
               n_trials=N_TRIALS, k_perm=k_perm, seed=seed,
               prereg='results/S972_PREREG_cs_spread_shock_fade.md')

    def _default(o):
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.bool_):
            return bool(o)
        return str(o)

    def _save():
        json.dump(out, open(out_path, 'w'), ensure_ascii=False, indent=1,
                  default=_default)

    warmup = CS_WIN + ATR_WIN + 3
    if n < warmup + 200:
        out['verdict'] = 'TOO_SHORT'
        _save()
        print('    TOO_SHORT.', flush=True)
        return out

    atr = atr_plain(df['high'].values, df['low'].values, df['close'].values)
    pip = float(se.ASSETS[ASSET]['pip'])
    sl_pip_scalar = float(np.nanmedian(atr)) * SL_K / pip
    tp_pip_scalar = sl_pip_scalar * RR
    out['sl_pip'] = round(sl_pip_scalar, 3)
    out['tp_pip'] = round(tp_pip_scalar, 3)
    print(f"    SL={sl_pip_scalar:.2f}pip TP={tp_pip_scalar:.2f}pip (RR={RR})",
          flush=True)

    sig, is_long = build_signals(df)
    sig_keep = sig >= warmup
    sig, is_long = sig[sig_keep], is_long[sig_keep]
    out['n_signals'] = int(len(sig))
    print(f"    shocks: {len(sig):,} (L={int(is_long.sum()):,}"
          f"/S={int((~is_long).sum()):,})", flush=True)
    if len(sig) < 5:
        out['verdict'] = 'NO_TRADES_FULL'
        _save()
        return out

    sl_dist = np.full(len(sig), sl_pip_scalar * pip)
    st = queue_rr(df, sig, is_long, sl_dist, ASSET, hold, RR)
    if st is None or st['n'] < 5:
        out['verdict'] = 'NO_TRADES_FULL'
        _save()
        return out
    tr = trades_df(st)
    n_long = int((tr['direction'] == 'long').sum())
    n_short = int(st['n'] - n_long)
    print(f"    کلِ داده: n={st['n']:,} (L={n_long:,}/S={n_short:,}) "
          f"wr={st['wr']:.2f}% exp={st['exp']:.3f}pip pf={st['pf']:.3f}",
          flush=True)

    null, pool_note = build_null(df, sl_pip_scalar, hold, n_long, n_short,
                                 k_perm, rng, warmup)
    out['null'] = null
    out['null_pool'] = pool_note

    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_pip_scalar, tp_pip=tp_pip_scalar,
                          bar_time=df['time'].values, null=null,
                          n_trials=N_TRIALS, split_bar=split,
                          close=df['close'].values, allow_overlap=False)
    print('\n' + rqs2.format_rqs2(f'S972-{tf}', r), flush=True)

    out['verdict'] = r['verdict']
    out['rqs2_score'] = r.get('rqs2_score')
    out['gates'] = {k: (bool(v) if isinstance(v, (bool, np.bool_)) else v)
                    for k, v in (r.get('gates') or {}).items()}
    out['metrics'] = {k: v for k, v in (r.get('metrics') or {}).items()
                      if isinstance(v, (int, float, str, bool, np.integer,
                                        np.floating, np.bool_)) or v is None}
    out['full'] = dict(n=int(st['n']), n_long=n_long, n_short=n_short,
                       wr=round(float(st['wr']), 2),
                       exp_pip=round(float(st['exp']), 3),
                       pf=round(float(st['pf']), 3))
    out['elapsed_s'] = round(_time.time() - t0, 1)
    _save()
    print(f"    ✔ checkpoint → {out_path} ({out['elapsed_s']}s)", flush=True)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('tf')
    ap.add_argument('--kperm', type=int, default=K_PERM)
    a = ap.parse_args()
    run_tf(a.tf.upper(), k_perm=a.kperm)
