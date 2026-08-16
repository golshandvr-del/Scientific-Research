#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S741 — «جذبِ ناکام ⇒ ادامهٔ حرکت» (Failed-Absorption Continuation)
================================================================================
پیش‌ثبت: results/S741_PREREG_FAILED_ABSORPTION_CONTINUATION_PATH_C.md (پیش از این کد)
وارونهٔ جهتِ S740: رویدادِ جذب در کفِ پنجره ⇒ SHORT (ادامهٔ سقوط)؛ سقف ⇒ LONG.
چندگانگیِ موروثی: n_trials = 64(S740) + 64(S741) = 128.
قید: M5 حداکثر UNPROVEN (holdoutش در S740 دیده شده).
اجرا: python3 strategies/s741_failed_absorption.py <TF> [--kperm 500]
"""
import sys
import os
import json
import time as _time
import argparse

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import s434_fast_data as fd                              # noqa: E402
from engine import rqs2                                             # noqa: E402
from strategies.s348_rr_sweep import queue_rr, trades_df, cost_pip  # noqa: E402
from strategies import s740_absorption as s740                      # noqa: E402

ASSET = 'XAUUSD'
N_TRIALS = 128                # موروثی: 64 (S740) + 64 (S741)
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_scan_S741')
M5_VERDICT_CAP = 'UNPROVEN'   # قیدِ خودتحمیلیِ پیش‌ثبت‌شده


def build_signals_reversed(df, atr, v_win, k_vol, k_rng, loc_win):
    """همان رویدادهای S740 اما با جهتِ وارونه: کف ⇒ SHORT، سقف ⇒ LONG."""
    sig, was_long = s740.build_signals(df, atr, v_win, k_vol, k_rng, loc_win)
    return sig, ~was_long


def discover(df, atr, split, c_pip):
    """جاروبِ همان ۶۴ پیکربندی، جهتِ وارونه. Holdout دیده نمی‌شود."""
    rows = []
    df_d = df.iloc[:split]
    atr_d = atr[:split]
    for v_win in s740.V_WIN_GRID:
        for k_vol in s740.K_VOL_GRID:
            for k_rng in s740.K_RNG_GRID:
                for loc_win in s740.LOC_WIN_GRID:
                    sig, is_long = build_signals_reversed(
                        df_d, atr_d, v_win, k_vol, k_rng, loc_win)
                    for k_sl in s740.K_SL_GRID:
                        for rr in s740.RR_GRID:
                            row = dict(v_win=v_win, k_vol=k_vol, k_rng=k_rng,
                                       loc_win=loc_win, k_sl=k_sl, rr=rr,
                                       n=0, wr=None, pf=None, z=None)
                            if len(sig) >= s740.MIN_N_DISC:
                                st = queue_rr(df_d, sig, is_long,
                                              k_sl * atr_d[sig],
                                              ASSET, s740.HOLD, rr)
                                if st is not None and st['n'] >= s740.MIN_N_DISC:
                                    sl_med = float(np.median(st['sl_pip']))
                                    tp_med = float(np.median(st['tp_pip']))
                                    be = rqs2.breakeven_wr_cost(sl_med, tp_med,
                                                                c_pip)
                                    lift = st['wr'] - be
                                    p0 = be / 100.0
                                    sepc = 100.0 * np.sqrt(
                                        max(p0 * (1 - p0), 1e-9) / st['n'])
                                    row.update(n=st['n'], wr=round(st['wr'], 2),
                                               pf=round(st['pf'], 3),
                                               exp=round(st['exp'], 2),
                                               sl_med=round(sl_med, 2),
                                               tp_med=round(tp_med, 2),
                                               be=round(be, 2),
                                               lift=round(lift, 2),
                                               z=round(lift / sepc, 3)
                                               if sepc > 0 else None)
                            rows.append(row)
    cand = [r for r in rows if r['z'] is not None
            and r['n'] >= s740.MIN_N_DISC and (r['pf'] or 0) >= s740.MIN_PF_DISC]
    winner = max(cand, key=lambda r: r['z']) if cand else None
    return rows, winner


def run_tf(tf, k_perm=500, seed=741):
    t0 = _time.time()
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f'{tf}.json')
    rng = np.random.default_rng(seed)

    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    n = len(df)
    split = int(s740.SPLIT_FRAC * n)
    c_pip = cost_pip(ASSET)
    print(f"\n{'='*88}\n=== S741 FAILED-ABSORPTION :: {ASSET}-{tf}  bars={n:,}  "
          f"src={d['src']}\n    span={d['first_utc']} → {d['last_utc']} "
          f"({d['span_years']:.2f}y) · split_bar={split} · cost={c_pip:.2f}pip "
          f"· N_TRIALS={N_TRIALS}", flush=True)

    out = dict(strategy='S741_FailedAbsorptionContinuation', asset=ASSET, tf=tf,
               bars=n, src=d['src'], span_years=round(float(d['span_years']), 2),
               split_bar=split, n_trials=N_TRIALS, k_perm=k_perm,
               prereg='results/S741_PREREG_FAILED_ABSORPTION_CONTINUATION_PATH_C.md')

    def _default(o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, (np.bool_,)):
            return bool(o)
        return str(o)

    def _save():
        json.dump(out, open(out_path, 'w'), ensure_ascii=False, indent=1,
                  default=_default)

    warmup = max(max(s740.V_WIN_GRID), s740.ATR_WIN, max(s740.LOC_WIN_GRID)) + 1
    if n < warmup + 200:
        out['verdict'] = 'TOO_SHORT'
        _save()
        print('    TOO_SHORT — رد شد.', flush=True)
        return out

    atr = s740.atr_plain(df['high'].values, df['low'].values,
                         df['close'].values)

    grid, winner = discover(df, atr, split, c_pip)
    out['grid_summary'] = dict(
        tested=len(grid),
        with_trades=sum(1 for r in grid if r['n'] >= s740.MIN_N_DISC),
        eligible=sum(1 for r in grid if r['z'] is not None
                     and r['n'] >= s740.MIN_N_DISC
                     and (r['pf'] or 0) >= s740.MIN_PF_DISC))
    out['grid_top5'] = sorted([r for r in grid if r['z'] is not None],
                              key=lambda r: -r['z'])[:5]
    if winner is None:
        out['verdict'] = 'NO_CANDIDATE'
        _save()
        print(f"    هیچ نامزدی واجد نشد (eligible=0 از {len(grid)}).",
              flush=True)
        return out
    out['winner_params'] = {k: winner[k] for k in
                            ('v_win', 'k_vol', 'k_rng', 'loc_win', 'k_sl', 'rr')}
    out['winner_disc'] = {k: winner[k] for k in
                          ('n', 'wr', 'pf', 'exp', 'lift', 'z',
                           'sl_med', 'tp_med')}
    print(f"    نامزدِ اکتشاف: {out['winner_params']} → n={winner['n']} "
          f"wr={winner['wr']} pf={winner['pf']} z={winner['z']}", flush=True)

    w = winner
    sig, is_long = build_signals_reversed(df, atr, w['v_win'], w['k_vol'],
                                          w['k_rng'], w['loc_win'])
    st = queue_rr(df, sig, is_long, w['k_sl'] * atr[sig], ASSET,
                  s740.HOLD, w['rr'])
    if st is None or st['n'] < 5:
        out['verdict'] = 'NO_TRADES_FULL'
        _save()
        return out
    tr = trades_df(st)
    n_long = int((tr['direction'] == 'long').sum())
    n_short = int(st['n'] - n_long)
    sl_med = float(np.median(st['sl_pip']))
    tp_med = float(np.median(st['tp_pip']))
    print(f"    کلِ داده: n={st['n']} (L={n_long}/S={n_short}) "
          f"wr={st['wr']:.2f} exp={st['exp']:.2f}pip pf={st['pf']:.3f}",
          flush=True)

    null, pool_note = s740.build_null(df, atr, n_long, n_short,
                                      w['k_sl'], w['rr'], k_perm, rng)
    out['null'] = null
    out['null_pool'] = pool_note

    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=d['time'], null=null, n_trials=N_TRIALS,
                          split_bar=split, close=d['close'],
                          allow_overlap=False)
    print('\n' + rqs2.format_rqs2(f'S741-{tf}', r), flush=True)

    verdict = r['verdict']
    if tf == 'M5' and verdict == 'ACCEPT':
        out['verdict_engine'] = verdict
        verdict = M5_VERDICT_CAP        # قیدِ پیش‌ثبت‌شده: holdout M5 بکر نیست
        print(f"    ⚠ قیدِ پیش‌ثبت: M5 از ACCEPT به {verdict} کاسته شد.",
              flush=True)
    out['verdict'] = verdict
    out['rqs2_score'] = r.get('rqs2_score')
    out['gates'] = {k: (bool(v) if isinstance(v, (bool, np.bool_)) else v)
                    for k, v in (r.get('gates') or {}).items()}
    out['metrics'] = {k: v for k, v in (r.get('metrics') or {}).items()
                      if isinstance(v, (int, float, str, bool, np.integer,
                                        np.floating, np.bool_)) or v is None}
    out['full'] = dict(n=int(st['n']), n_long=n_long, n_short=n_short,
                       wr=round(float(st['wr']), 2),
                       exp_pip=round(float(st['exp']), 3),
                       pf=round(float(st['pf']), 3),
                       sl_med=round(sl_med, 2), tp_med=round(tp_med, 2))
    out['elapsed_s'] = round(_time.time() - t0, 1)
    _save()
    print(f"    ✔ checkpoint → {out_path} ({out['elapsed_s']}s)", flush=True)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('tf')
    ap.add_argument('--kperm', type=int, default=500)
    a = ap.parse_args()
    run_tf(a.tf.upper(), k_perm=a.kperm)
