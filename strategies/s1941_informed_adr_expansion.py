#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S1941 — انبساطِ مطلعِ ADR = استخر منجمد S770 {D1,H8} × گیت ρ کایل (≥0.618).
پیش‌ثبت: results/S1941_PREREG_INFORMED_ADR_EXPANSION.md (کامیت 4ee8ff06 — قبل از این فایل)

همه‌چیز از s770 به ارث رسیده (import، بدون تغییر فایل‌های S770):
  build_features/signals_for/geometry/build_null/load_card، θ=0.65، hold=16،
  SL=1.272×ATR100، RR=2.058، pool_cards، blend_pool_null، محور H1، holdout 60% زمانِ ورود.
تنها افزوده: گیت ρ روی کندلِ سیگنال. mode: gated (رسمی) | counter (P2) | raw (sanity).
n_trials = 304 (301 S770 + 1 استخر + 2 تک‌کارت).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import scalp_engine as se                                # noqa: E402
from engine import rqs2                                               # noqa: E402
from engine.rqs2_pool import pool_cards                               # noqa: E402
from tools import s434_fast_data as fd                                # noqa: E402
from strategies.s770_adr_expansion import (                           # noqa: E402
    load_card, build_features, signals_for, geometry, build_null,
    SEED, SPLIT_FRAC)
from strategies.s770_pool_adjudicate import blend_pool_null           # noqa: E402

OUT = os.path.join(ROOT, 'results', '_scan_S1941')
S770_SCAN = os.path.join(ROOT, 'results', '_scan_S770')
MEMBER_TFS = ('D1', 'H8')       # منجمد S770-POOL2
RHO_THR = 0.618                 # منجمد S965/S1520
N_TRIALS = 304


def rho_series(df):
    rng = (df['high'] - df['low']).values
    body = (df['close'] - df['open']).values
    with np.errstate(divide='ignore', invalid='ignore'):
        r = np.where(rng > 0, body / rng, 0.0)
    return r


def frozen_cell(tf):
    with open(os.path.join(S770_SCAN, f'{tf}_verdict.json')) as f:
        v = json.load(f)
    return float(v['theta']), int(v['hold'])


def member_for(tf, rng, mode):
    """اجرای منجمد S770 روی کارت + گیت ρ. lift از نول per-کارت محاسبه می‌شود."""
    theta, hold = frozen_cell(tf)
    df, src = load_card(tf)
    assert 'mt5_full' in src, 'E-16 guard'
    frac = build_features(df)
    sl_pip, tp_pip, _ = geometry(df)
    valid = np.isfinite(frac) & np.isfinite(sl_pip) & (sl_pip > 0)
    lsig, ssig = signals_for(frac, theta)
    lsig &= valid; ssig &= valid
    n_raw = int(lsig.sum() + ssig.sum())

    r = rho_series(df)
    if mode == 'gated':
        lsig &= (r >= RHO_THR); ssig &= (r <= -RHO_THR)
    elif mode == 'counter':
        lsig &= (r < RHO_THR); ssig &= (r > -RHO_THR)
    n_sig = int(lsig.sum() + ssig.sum())
    pass_rate = 100.0 * n_sig / max(1, n_raw)

    tr = se.simulate_trades(df, lsig, ssig, sl_pip, tp_pip, asset='XAUUSD',
                            max_hold=hold, allow_overlap=False)
    dt = pd.to_datetime(df['time'], unit='s').values
    n = len(tr)
    n_long = int((tr['direction'] == 'long').sum()) if n else 0
    n_short = n - n_long
    wr = float((tr['pnl_pip'] > 0).mean() * 100) if n else float('nan')
    print(f'[member {tf} {mode}] θ={theta} hold={hold} raw_sig={n_raw} '
          f'gated_sig={n_sig} pass={pass_rate:.1f}% trades n={n} '
          f'(L={n_long} S={n_short}) WR={wr:.2f} src={src}', flush=True)

    # نول per-کارت: فضای valid (همان S770) — بی‌قید + جایگشت K=800
    vi = np.where(valid)[0]
    null = build_null(df, vi, sl_pip, tp_pip, n_long, n_short, hold, rng)
    # lift وزنی دو سمت برای pool_cards
    num = den = 0.0
    for side, ns in (('long', n_long), ('short', n_short)):
        u = null[side].get('uncond_wr')
        if ns > 0 and u is not None:
            side_wr = float((tr.loc[tr['direction'] == side, 'pnl_pip'] > 0).mean() * 100)
            num += (side_wr - u) * ns; den += ns
    lift = num / den if den else 0.0
    print(f'    lift_vs_uncond={lift:+.2f}pp', flush=True)
    return dict(card=f'XAUUSD_{tf}', tr=tr, dt=dt, lift=float(lift), null=null,
                sl_med=float(np.nanmedian(sl_pip)), tp_med=float(np.nanmedian(tp_pip)),
                src=src, theta=theta, hold=hold, n_raw=n_raw, n_sig=n_sig,
                pass_rate=pass_rate, df_time=df['time'].values,
                df_close=df['close'].values, split=int(len(df) * SPLIT_FRAC))


def judge_single(m, tag):
    """داوری تک‌کارت (گزارشی؛ شمرده‌شده در n_trials)."""
    tr = m['tr']
    if len(tr) == 0:
        return dict(card=m['card'], verdict='NO_TRADES')
    r = rqs2.compute_rqs2(tr, 'XAUUSD', sl_pip=m['sl_med'], tp_pip=m['tp_med'],
                          bar_time=m['df_time'], null=m['null'], n_trials=N_TRIALS,
                          split_bar=m['split'], close=m['df_close'])
    print(rqs2.format_rqs2(tag, r), flush=True)
    return dict(card=m['card'], n=int(len(tr)), verdict=r['verdict'],
                score=r.get('rqs2_score'), gates=r.get('gates'),
                metrics=_safe(r.get('metrics', {})), notes=r.get('notes'))


def judge_pool(members, tag):
    res = pool_cards(members)
    if res is None:
        print(f'[{tag}] pool empty', flush=True)
        return dict(verdict='NO_POOL')
    print(f"[{tag} selection] {json.dumps(res['selection'], ensure_ascii=False, default=str)}",
          flush=True)
    pool = res['pool']
    used_cards = {u['card'] for u in res['used']}
    members_used = [m for m in members if m['card'] in used_cards]
    null = blend_pool_null(members_used, pool)

    dh = fd.load_fast('XAUUSD', 'H1')
    assert 'mt5_full' in dh['src'], 'E-16 guard'
    ref_t = (dh['time'].astype(np.int64) * 10**9)
    ref_c = dh['close'].astype(np.float64)
    pool = pool.sort_values('t_entry', kind='mergesort').reset_index(drop=True)
    pool['entry_bar'] = np.clip(np.searchsorted(ref_t, pool['t_entry'].values, 'left'),
                                0, len(ref_t) - 1)
    pool['exit_bar'] = np.clip(np.searchsorted(ref_t, pool['t_exit'].values, 'left'),
                               0, len(ref_t) - 1)
    pool['exit_bar'] = np.maximum(pool['exit_bar'], pool['entry_bar'])
    pool = pool.sort_values('exit_bar', kind='mergesort').reset_index(drop=True)
    bar_time = (ref_t / 10**9).astype('int64')

    te_all = pool['t_entry'].values.astype(np.int64)
    split_ns = int(np.quantile(te_all, SPLIT_FRAC))
    holdout = te_all >= split_ns
    print(f'[{tag} split] boundary={np.datetime64(split_ns, "ns")} '
          f'explore={int((~holdout).sum())} oos={int(holdout.sum())}', flush=True)

    sl_med = float(np.median([m['sl_med'] for m in members_used]))
    tp_med = float(np.median([m['tp_med'] for m in members_used]))
    r = rqs2.compute_rqs2(pool, 'XAUUSD', sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=bar_time, null=null, close=ref_c,
                          holdout_mask=holdout, n_trials=N_TRIALS,
                          allow_overlap=False)
    print('\n' + rqs2.format_rqs2(tag, r), flush=True)
    return dict(members=[dict(card=u['card'], lift=u['lift'], n=u['n']) for u in res['used']],
                dropped=res['dropped'], n_before=res['n_before'], n_after=res['n_after'],
                null=null, verdict=r['verdict'], score=r.get('rqs2_score'),
                gates=r.get('gates'), metrics=_safe(r.get('metrics', {})),
                notes=r.get('notes'))


def _safe(m):
    return {k: (float(v) if isinstance(v, (int, float, np.floating)) else str(v))
            for k, v in m.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['gated', 'counter', 'raw'], required=True)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(SEED)
    members = [member_for(tf, rng, a.mode) for tf in MEMBER_TFS]
    out = dict(layer='S1941', mode=a.mode, rho_thr=RHO_THR, n_trials=N_TRIALS,
               members_meta=[dict(card=m['card'], theta=m['theta'], hold=m['hold'],
                                  n_raw=m['n_raw'], n_sig=m['n_sig'],
                                  pass_rate=round(m['pass_rate'], 1),
                                  n_trades=int(len(m['tr'])), lift=round(m['lift'], 3),
                                  src=m['src']) for m in members])
    if a.mode == 'gated':
        out['single'] = [judge_single(m, f'S1941-{m["card"]}-gated') for m in members]
    out['pool'] = judge_pool(members, f'S1941-POOL-{a.mode}')
    with open(os.path.join(OUT, f'verdict_{a.mode}.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"\n[S1941 {a.mode}] POOL VERDICT = {out['pool'].get('verdict')} "
          f"score={out['pool'].get('score')}", flush=True)


if __name__ == '__main__':
    main()
