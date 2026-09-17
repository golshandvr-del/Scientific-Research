#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S978 — لبهٔ تازهٔ ۹۰ با جریانِ دیرهنگام (Late-Flow Fresh Extreme)
================================================================================
پیش‌ثبت: results/S978_PREREG_late_flow_fresh_extreme.md (پیش از هر PnL)
معیار:   RQS2 v2.6 gates_only. مسیرِ B — یک تعریفِ منجمد، n_trials=24.

تعریف (بندِ ۲ پیش‌ثبت):
  edge_hi: close>max(close[i−90..i−1]) و کندل قبل نه، c>o؛ edge_lo آینه (S526/S1511 قفل).
  late_share = Σvol(M1 نیمهٔ دوم) / Σvol(M1 کل کندل)؛ ref = median ۲۰ کندلِ قبلیِ هم‌اسلات؛
  exc = late_share − ref؛ LATE: exc ≥ 0.
  LONG: edge_hi∧LATE ؛ SHORT: edge_lo∧LATE. ورود: openِ کندلِ بعدی (موتور).

هندسه (بندِ ۲): SL=1.5×median(ATR100)، TP=1.5×SL، hold=16 کندل (ثابت).
نال (بندِ ۴): جای‌گشتِ مکانِ ورود، K=2000 هر سمت، بذر 20260910، split=0.70.

فقط XAUUSD. H4 بازنمونه از H1. checkpoint: results/_scan_S978/<TF>.json
اجرا: python3 strategies/s978_late_flow_fresh_extreme.py M1 [--kperm 2000]
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
W_REC = 90                    # پنجرهٔ رکوردِ close (S526/S1511 قفل)
REF_N = 20                    # تعداد کندل‌های هم‌اسلاتِ قبلی برای مرجعِ late_share
REF_MINP = 10                 # min_periods مرجع
EXC_MIN = 0.0                 # LATE: late_share − ref ≥ 0
MIN_M1_FRAC = 0.20            # کمینهٔ پوشش M1 درونِ کندل؛ کمتر ⇒ NaN
ATR_WIN = 100                 # براکتِ SL (median ATR100 هر TF — قفل خانواده)
SL_K = 1.5
RR = 1.5
HOLD_BARS = 16                # ثابت (S965/S919)
N_TRIALS = 24
SPLIT_FRAC = 0.70
K_PERM = 2000
SEED = 20260910
NULL_POOL_MAX = 400_000

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_scan_S978')


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


def load_m1_volume_clock():
    """(t1, cumvol) از دادهٔ رسمی M1؛ فقط time و volume نگه می‌دارد (~80MB)؛ OHLC آزاد."""
    m1 = fd.load_fast(ASSET, 'M1')
    t1 = np.ascontiguousarray(m1['time'].astype(np.int64))
    v1 = m1['volume'].astype(np.float64)
    del m1
    cv = np.concatenate(([0.0], np.cumsum(v1)))
    del v1
    return t1, cv


def late_share(bar_start, bar_sec, t1, cv):
    """سهمِ حجمِ نیمهٔ دومِ کندل از M1 — فقط M1های درونِ [start, start+T)؛ causal پس از close.

    bar_sec زوج ≥ 120 لازم است (نیمهٔ کندل ≥ ۱ دقیقه)؛ در غیر این صورت NaN.
    پوشش M1 < MIN_M1_FRAC یا Σvol=0 ⇒ NaN.
    """
    n = len(bar_start)
    out = np.full(n, np.nan)
    if bar_sec < 120:
        return out
    half = bar_sec // 2
    ia = np.searchsorted(t1, bar_start, side='left')
    im = np.searchsorted(t1, bar_start + half, side='left')
    ib = np.searchsorted(t1, bar_start + bar_sec, side='left')
    tot = cv[ib] - cv[ia]
    late = cv[ib] - cv[im]
    cover = (ib - ia) >= max(1, int(MIN_M1_FRAC * (bar_sec // 60)))
    ok = (tot > 0) & cover
    out[ok] = late[ok] / tot[ok]
    return out


def bar_seconds(df):
    dt = np.diff(df['time'].values.astype(np.int64))
    dt = dt[dt > 0]
    return int(np.median(dt))


def build_signals(df, t1=None, cv=None):
    """(sig_idx, is_long, diag) — لبهٔ تازهٔ ۹۰ + جریانِ دیرهنگامِ نرمال‌شدهٔ روزانه؛ causal.

    edge_hi: c>max(c[i−90..i−1]) (shift(1)) و بار قبل نه، c>o؛ edge_lo آینه.
    late_share از M1های درونِ همان کندل برای *همهٔ* کندل‌ها (لازم برای مرجع)؛
    ref = median از REF_N کندلِ قبلیِ هم‌اسلات (shift(1) درون گروه اسلات)؛ exc=ls−ref.
    LONG = edge_hi∧exc≥0؛ SHORT = edge_lo∧exc≥0. diag: شمارش بازوی exc<0 برای P1.
    ورود در کندلِ بعدی توسطِ queue_rr/barrier انجام می‌شود (sig+1).
    """
    t = df['time'].values.astype(np.int64)
    o = df['open'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    n = len(c)

    cs = pd.Series(c)
    hi = cs.shift(1).rolling(W_REC).max().values
    lo = cs.shift(1).rolling(W_REC).min().values
    del cs
    nh = c > hi
    nl = c < lo
    del hi, lo
    edge_hi = nh & ~np.concatenate(([False], nh[:-1])) & (c > o)
    edge_lo = nl & ~np.concatenate(([False], nl[:-1])) & (c < o)
    del nh, nl

    cand = np.flatnonzero(edge_hi | edge_lo)
    diag = dict(n_edge=int(len(cand)), n_late=0, n_early=0, n_nan=0)
    if len(cand) == 0:
        return (np.zeros(0, np.int64), np.zeros(0, bool), diag)

    if t1 is None:
        t1, cv = load_m1_volume_clock()
    sec = bar_seconds(df)
    starts = t.copy()
    if sec == 4 * 3600:
        starts = (starts // sec) * sec                       # H4 بازنمونه: کفِ 4h
    ls = late_share(starts, sec, t1, cv)                    # همهٔ کندل‌ها (مرجع لازم دارد)
    # اسلاتِ روزانه؛ برای TFهای ≥ ۱ روز همه در اسلات ۰
    slot = (starts % 86400) // sec if sec < 86400 else np.zeros(n, dtype=np.int64)
    ref = np.full(n, np.nan)
    for s in np.unique(slot):
        idx = np.flatnonzero(slot == s)
        ref[idx] = (pd.Series(ls[idx]).shift(1)
                    .rolling(REF_N, min_periods=REF_MINP).median().values)
    exc = ls - ref
    del ls, ref, slot, starts

    e = exc[cand]
    diag['n_nan'] = int(np.isnan(e).sum())
    late = e >= EXC_MIN                                      # NaN ⇒ False
    diag['n_late'] = int(late.sum())
    diag['n_early'] = int((e < 0).sum())
    del exc

    sig = cand[late]
    is_long = edge_hi[sig]
    return sig.astype(np.int64), is_long.astype(bool), diag


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
    hold = HOLD_BARS
    print(f"\n{'='*88}\n=== S978 LATE-FLOW-FRESH-EXTREME :: {ASSET}-{tf}  bars={n:,}  "
          f"src={d['src']}\n    split_bar={split} · hold={hold} bars "
          f"(fixed) · cost={cost_pip(ASSET):.2f}pip · "
          f"N_TRIALS={N_TRIALS} · K={k_perm}", flush=True)

    out = dict(strategy='S978_LateFlowFreshExtreme', asset=ASSET, tf=tf, bars=n,
               src=str(d['src']), split_bar=split, hold=hold,
               n_trials=N_TRIALS, k_perm=k_perm, seed=seed,
               prereg='results/S978_PREREG_late_flow_fresh_extreme.md')

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

    # بندِ ۴ پیش‌ثبت: warmup = max(ATR_WIN+2, W_REC+2)
    warmup = max(ATR_WIN + 2, W_REC + 2)
    if n < warmup + 500:
        out['verdict'] = 'TOO_SHORT'
        _save()
        print('    TOO_SHORT.', flush=True)
        return out

    atr = atr_plain(df['high'].values, df['low'].values, df['close'].values)
    pip = float(se.ASSETS[ASSET]['pip'])
    sl_pip_scalar = float(np.nanmedian(atr)) * SL_K / pip
    del atr
    tp_pip_scalar = sl_pip_scalar * RR
    out['sl_pip'] = round(sl_pip_scalar, 3)
    out['tp_pip'] = round(tp_pip_scalar, 3)
    print(f"    SL={sl_pip_scalar:.2f}pip TP={tp_pip_scalar:.2f}pip (RR={RR})",
          flush=True)

    sig, is_long, diag = build_signals(df)
    out['diag'] = diag
    keep = sig >= warmup
    sig, is_long = sig[keep], is_long[keep]
    out['n_signals'] = int(len(sig))
    print(f"    fresh-90 edges={diag['n_edge']:,} late={diag['n_late']:,} "
          f"early={diag['n_early']:,} nan={diag['n_nan']:,}", flush=True)
    print(f"    late-flow fresh-extreme signals: {len(sig):,} (L={int(is_long.sum()):,}"
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
    print('\n' + rqs2.format_rqs2(f'S978-{tf}', r), flush=True)

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
