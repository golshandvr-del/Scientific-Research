#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S976 — بازگشتِ مؤلفهٔ گذرای شوکِ کم‌ماندگار، هم‌راستا با قرارداد (Transitory Shock Dip)
================================================================================
پیش‌ثبت: results/S976_PREREG_transitory_shock_dip.md (پیش از هر PnL)
معیار:   RQS2 v2.6 gates_only. مسیرِ B — یک تعریفِ منجمد، n_trials=24.

تعریف (بندِ ۲ پیش‌ثبت):
  shock: (h−l)[i] ≥ 1.618×ATR21[i−1]؛ low_ret: ρ=|c−o|/(h−l) ≤ 0.5؛
  exc_dn: (o−l) > (h−o). drift = close[i−1]−close[i−1−B]، B=round(60d×24×bph).
  LONG: shock∧low_ret∧exc_dn∧drift>0 ؛ SHORT: shock∧low_ret∧¬exc_dn∧drift<0.
  ورود: openِ کندلِ بعدی (موتور).

هندسه (بندِ ۲): SL=1.0×median(ATR14)، TP=1.5×SL، hold=16 کندل (ثابت).
نال (بندِ ۴): جای‌گشتِ مکانِ ورود، K=2000 هر سمت، بذر 20260905، split=0.70.

فقط XAUUSD. H4 بازنمونه از H1. checkpoint: results/_scan_S976/<TF>.json
اجرا: python3 strategies/s976_transitory_shock_dip.py M1 [--kperm 2000]
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
SHOCK_ATR_WIN = 21            # ATR علّی برای مقیاسِ شوک (S965/S919)
SHOCK_K = 1.618               # (h−l) ≥ SHOCK_K × ATR21[i−1]
RHO_MAX = 0.5                 # ماندگاریِ پایین: ρ ≤ 0.5 ⇒ مؤلفهٔ گذرا غالب
K_DRIFT_DAYS = 60             # گیتِ قرارداد: ۶۰ روز تقویمی (S604/S919)
ATR_WIN = 14                  # براکتِ SL (median ATR14 هر TF)
SL_K = 1.0
RR = 1.5
HOLD_BARS = 16                # ثابت (S965/S919)
N_TRIALS = 24
SPLIT_FRAC = 0.70
K_PERM = 2000
SEED = 20260905
NULL_POOL_MAX = 400_000

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_scan_S976')


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


def build_signals(df):
    """(sig_idx, is_long) — شوکِ کم‌ماندگار + گردشِ غالب + گیتِ قرارداد؛ causal.

    shock: (h−l)[i] ≥ SHOCK_K×ATR21[i−1] (shift(1)). low_ret: ρ ≤ RHO_MAX.
    exc_dn: (o−l) > (h−o). drift = close[i−1]−close[i−1−B] (فقط گذشته).
    LONG = shock∧low_ret∧exc_dn∧drift>0 (fade فشارِ فروشِ خلافِ قرارداد)؛
    SHORT آینه. همه برداری؛ روی M1 چند آرایهٔ 40MB گذرا (امن)؛ del صریح.
    ورود در کندلِ بعدی توسطِ queue_rr/barrier انجام می‌شود (sig+1).
    """
    o = df['open'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    n = len(c)

    bph = bars_per_hour(df)
    B = int(round(K_DRIFT_DAYS * 24 * bph))
    B = max(1, min(B, n - 2))

    prev_c = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    del prev_c
    atr21 = pd.Series(tr).rolling(SHOCK_ATR_WIN).mean().shift(1).values
    del tr
    rng_ = h - l
    shock = rng_ >= SHOCK_K * atr21                          # NaN ⇒ False
    del atr21
    rho = np.divide(np.abs(c - o), rng_, out=np.zeros(n), where=rng_ > 0)
    low_ret = rho <= RHO_MAX
    del rho, rng_
    exc_dn = (o - l) > (h - o)

    drift_up = np.zeros(n, dtype=bool)
    drift_dn = np.zeros(n, dtype=bool)
    # drift[i] = c[i−1] − c[i−1−B]  برای i ≥ B+1
    drift_up[B + 1:] = c[B:-1] > c[:-B - 1]
    drift_dn[B + 1:] = c[B:-1] < c[:-B - 1]

    long_sig = shock & low_ret & exc_dn & drift_up
    short_sig = shock & low_ret & (~exc_dn) & drift_dn
    del shock, low_ret, exc_dn, drift_up, drift_dn

    sig = np.flatnonzero(long_sig | short_sig)
    is_long = long_sig[sig]
    del long_sig, short_sig
    return sig.astype(np.int64), is_long.astype(bool)


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
    print(f"\n{'='*88}\n=== S976 TRANSITORY-SHOCK-DIP :: {ASSET}-{tf}  bars={n:,}  "
          f"src={d['src']}\n    split_bar={split} · hold={hold} bars "
          f"(fixed) · cost={cost_pip(ASSET):.2f}pip · "
          f"N_TRIALS={N_TRIALS} · K={k_perm}", flush=True)

    out = dict(strategy='S976_TransitoryShockDip', asset=ASSET, tf=tf, bars=n,
               src=str(d['src']), split_bar=split, hold=hold,
               n_trials=N_TRIALS, k_perm=k_perm, seed=seed,
               prereg='results/S976_PREREG_transitory_shock_dip.md')

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

    # بندِ ۴ پیش‌ثبت: warmup = max(ATR_WIN+2, SHOCK_ATR_WIN+2, B+2)
    _B = max(1, min(int(round(K_DRIFT_DAYS * 24 * bph)), n - 2))
    warmup = max(ATR_WIN + 2, SHOCK_ATR_WIN + 2, _B + 2)
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

    sig, is_long = build_signals(df)
    keep = sig >= warmup
    sig, is_long = sig[keep], is_long[keep]
    out['n_signals'] = int(len(sig))
    print(f"    transitory-shock-dip signals: {len(sig):,} (L={int(is_long.sum()):,}"
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
    print('\n' + rqs2.format_rqs2(f'S976-{tf}', r), flush=True)

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
