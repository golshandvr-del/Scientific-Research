#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S975 — رکوردِ حجمیِ تازهٔ هم‌راستا با دریفت (Fresh Volume-Record, Drift-Aligned)
================================================================================
پیش‌ثبت: results/S975_PREREG_volume_record_drift_aligned.md (پیش از هر PnL)
معیار:   RQS2 v2.6 gates_only. مسیرِ B — یک تعریفِ منجمد، n_trials=24.

تعریف (بندِ ۲ پیش‌ثبت):
  رکورد: v[i] > max(v[i−20..i−1]) و فقط لبهٔ تازه (بارِ قبلی رکورد نباشد).
  جهت: بدنهٔ همان بار (دوجی ⇒ هیچ). گیتِ دریفت: LONG فقط اگر close[i]>close[i−B]،
  SHORT برعکس؛ B = round(60روز × bars_per_hour×24). ورود: openِ کندلِ بعدی.

هندسه (بندِ ۲): SL=1.0×median(ATR14)، TP=1.5×SL، hold=6h (کف ۴ کندل).
نال (بندِ ۴): جای‌گشتِ مکانِ ورود، K=2000 هر سمت، بذر 20260902، split=0.70.

فقط XAUUSD. H4 بازنمونه از H1. checkpoint: results/_scan_S975/<TF>.json
اجرا: python3 strategies/s975_volume_record_drift_aligned.py M1 [--kperm 2000]
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
K_VOL = 20                    # پنجرهٔ رکوردِ حجمی (بار)
K_DRIFT_DAYS = 60             # گیتِ دریفت: ۶۰ روز والی (منبع: S604/S950/S526)
ATR_WIN = 14
SL_K = 1.0
RR = 1.5
HOLD_HOURS = 6.0
HOLD_MIN_BARS = 4
N_TRIALS = 24
SPLIT_FRAC = 0.70
K_PERM = 2000
SEED = 20260902
NULL_POOL_MAX = 400_000

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_scan_S975')


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
    """(sig_idx, is_long) — رکوردِ حجمیِ لبه‌ای + جهتِ بدنه + گیتِ دریفت؛ causal.

    رکورد: v[i] > max(v[i−K_VOL..i−1]) (shift(1)، فقط گذشته). لبه: بارِ قبلی
    رکورد نباشد. جهت = بدنهٔ همان بار (دوجی حذف). گیتِ دریفتِ ۶۰روزه:
    LONG فقط اگر close[i]>close[i−B]، SHORT برعکس. همه برداری — روی M1 (5M بار)
    فقط چند آرایهٔ گذرای 40MB می‌سازد (امن برای قانون OOM)؛ del صریح.
    ورود در کندلِ بعدی توسطِ queue_rr/barrier انجام می‌شود (sig+1).
    """
    v = df['volume'].values.astype(np.float64)
    o = df['open'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    n = len(v)

    bph = bars_per_hour(df)
    B = int(round(K_DRIFT_DAYS * 24 * bph))
    B = max(1, min(B, n - 1))

    rollmax = pd.Series(v).shift(1).rolling(K_VOL).max().values
    rec = v > rollmax                                        # NaN ⇒ False
    del rollmax
    edge = rec & ~np.concatenate(([False], rec[:-1]))        # فقط لبهٔ تازه
    del rec

    up_body = c > o
    dn_body = c < o

    drift_up = np.zeros(n, dtype=bool)
    drift_dn = np.zeros(n, dtype=bool)
    drift_up[B:] = c[B:] > c[:-B]
    drift_dn[B:] = c[B:] < c[:-B]

    long_sig = edge & up_body & drift_up
    short_sig = edge & dn_body & drift_dn
    del edge, up_body, dn_body, drift_up, drift_dn

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
    hold = max(HOLD_MIN_BARS, int(round(HOLD_HOURS * bph)))
    print(f"\n{'='*88}\n=== S975 VOLUME-RECORD-DRIFT-ALIGNED :: {ASSET}-{tf}  bars={n:,}  "
          f"src={d['src']}\n    split_bar={split} · hold={hold} bars "
          f"(~{HOLD_HOURS}h) · cost={cost_pip(ASSET):.2f}pip · "
          f"N_TRIALS={N_TRIALS} · K={k_perm}", flush=True)

    out = dict(strategy='S975_VolumeRecordDriftAligned', asset=ASSET, tf=tf, bars=n,
               src=str(d['src']), split_bar=split, hold=hold,
               n_trials=N_TRIALS, k_perm=k_perm, seed=seed,
               prereg='results/S975_PREREG_volume_record_drift_aligned.md')

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

    # بندِ ۴ پیش‌ثبت: warmup = max(ATR_WIN+2, K_VOL+2, B+1) — B همان گیتِ دریفت
    _B = max(1, min(int(round(K_DRIFT_DAYS * 24 * bph)), n - 1))
    warmup = max(ATR_WIN + 2, K_VOL + 2, _B + 1)
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
    print(f"    volume-record drift-aligned signals: {len(sig):,} (L={int(is_long.sum()):,}"
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
    print('\n' + rqs2.format_rqs2(f'S975-{tf}', r), flush=True)

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
