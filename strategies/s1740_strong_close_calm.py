#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S1740 — بستهٔ قوی × رانش دوگانه × رژیم آرام (Strong-Close Dual-Drift × Calm-σ) — XAUUSD
================================================================================
پیش‌ثبت: results/S1740_PREREG_STRONG_CLOSE_CALM_REGIME_PATH_C.md (کامیت قبل از کد)
قاعده: S749/S748-H2 winner_params (از JSON) + گیت آرامش s605 (σ RiskMetrics، reg≤1، W=233).
بدون شبکه. n_trials=643 رسمی؛ 2000/5176 تنش. کارت داوری H2؛ H4/H6 تأییدی.
داده: فقط data/mt5_full (کد src را چک می‌کند و در غیر این صورت خطا می‌دهد).
اجرا: python3 strategies/s1740_strong_close_calm.py <TF>
"""
import os
import sys
import json
import time as _time
import argparse

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools import s434_fast_data as fd                              # noqa: E402
from engine import rqs2                                             # noqa: E402
from strategies.s348_rr_sweep import queue_rr, trades_df, cost_pip  # noqa: E402
from strategies import s740_absorption as s740                      # noqa: E402
from strategies import s748_dual_drift as s748                      # noqa: E402
import strategies.s605_engle_sigma_regime as S5                     # noqa: E402

ASSET = 'XAUUSD'
N_TRIALS = 643
N_STRESS = (2000, 5176)
W_CALM = 233
SEED = 1740
K_PERM = 500
SPLIT_FRAC = 0.60
PARAMS_SRC = os.path.join(ROOT, 'results', '_scan_S748', 'H2.json')
OUT_DIR = os.path.join(ROOT, 'results', '_scan_S1740')
PREREG = 'results/S1740_PREREG_STRONG_CLOSE_CALM_REGIME_PATH_C.md'


def _default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return str(o)


def frozen_params():
    with open(PARAMS_SRC) as f:
        wp = json.load(f)['winner_params']
    assert wp == {'k_r': 2.5, 'clv_k': 0.8, 'w_d': 100, 'mode': 'long_only',
                  'k_sl': 2.5, 'rr': 1.5}, wp
    return wp


def stats_of(df, atr, sig, is_long, c_pip):
    if len(sig) < 5:
        return None, None
    st = queue_rr(df, sig, is_long, s748.K_SL * atr[sig], ASSET, s748.HOLD, s748.RR)
    if st is None or st['n'] < 5:
        return None, None
    be = rqs2.breakeven_wr_cost(float(np.median(st['sl_pip'])),
                                float(np.median(st['tp_pip'])), c_pip)
    return st, dict(n=int(st['n']), wr=round(float(st['wr']), 2),
                    pf=round(float(st['pf']), 3), exp=round(float(st['exp']), 2),
                    lift_vs_be=round(float(st['wr']) - be, 2))


def run_tf(tf):
    t0 = _time.time()
    os.makedirs(OUT_DIR, exist_ok=True)
    wp = frozen_params()
    d = fd.load_fast(ASSET, tf)
    if '/data/mt5_full/' not in d['src']:
        raise SystemExit(f"❌ src خارج از mt5_full: {d['src']} — حکم بی‌اعتبار؛ توقف.")
    df = fd.as_dataframe(d)
    n = len(df)
    split = int(SPLIT_FRAC * n)
    c_pip = cost_pip(ASSET)
    rng_ = np.random.default_rng(SEED)
    print(f"\n{'='*88}\n=== S1740 STRONG-CLOSE × CALM :: {ASSET}-{tf} bars={n:,} src={d['src']}\n"
          f"    span={d['first_utc']} → {d['last_utc']} ({d['span_years']:.2f}y) "
          f"split_bar={split} N_TRIALS={N_TRIALS} W_CALM={W_CALM}", flush=True)

    atr = s740.atr_plain(df['high'].values, df['low'].values, df['close'].values)
    sig_all, is_long_all = s748.build_signals(df, atr, wp['clv_k'], wp['w_d'], wp['mode'])
    reg = S5.regime_ratio(S5.sigma_series(df['close'].values), W_CALM)
    calm_mask = np.isfinite(reg[sig_all]) & (reg[sig_all] <= 1.0)
    storm_mask = np.isfinite(reg[sig_all]) & (reg[sig_all] > 1.0)
    n_ev = len(sig_all)
    n_calm = int(calm_mask.sum())
    pass_rate = round(100.0 * n_calm / n_ev, 1) if n_ev else None
    print(f"    events={n_ev} calm={n_calm} storm={int(storm_mask.sum())} "
          f"pass_rate={pass_rate}%", flush=True)

    out = dict(strategy='S1740_StrongCloseCalm', asset=ASSET, tf=tf, bars=n,
               src=d['src'], span_years=round(float(d['span_years']), 2),
               split_bar=split, n_trials=N_TRIALS, seed=SEED, k_perm=K_PERM,
               prereg=PREREG, params=dict(**wp, w_calm=W_CALM, lambda_=S5.LAMBDA),
               p5_passrate=dict(n_events=n_ev, n_calm=n_calm, pass_rate=pass_rate))

    # بازوهای گزارشی: بی‌گیت (=S749) و طوفان
    st_u, rep_u = stats_of(df, atr, sig_all, is_long_all, c_pip)
    st_s, rep_s = stats_of(df, atr, sig_all[storm_mask], is_long_all[storm_mask], c_pip)
    out['p1_ungated'] = rep_u
    out['p3_storm'] = rep_s
    print(f"    ungated: {rep_u}\n    storm:   {rep_s}", flush=True)

    # بازوی داوری: آرام
    sig = sig_all[calm_mask]
    is_long = is_long_all[calm_mask]
    st, rep = stats_of(df, atr, sig, is_long, c_pip)
    out['gated_calm_summary'] = rep
    print(f"    CALM:    {rep}", flush=True)
    if st is None:
        out['verdict'] = 'NO_TRADES'
        json.dump(out, open(os.path.join(OUT_DIR, f'{tf}.json'), 'w'),
                  ensure_ascii=False, indent=1, default=_default)
        return out

    tr = trades_df(st)
    n_long = int((tr['direction'] == 'long').sum())
    n_short = int(st['n'] - n_long)
    sl_med = float(np.median(st['sl_pip']))
    tp_med = float(np.median(st['tp_pip']))
    null, pool_note = s740.build_null(df, atr, n_long, n_short, s748.K_SL,
                                      s748.RR, K_PERM, rng_)
    out['null'] = null
    out['null_pool'] = pool_note

    def judge(nt, label):
        r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                              bar_time=d['time'], null=null, n_trials=nt,
                              split_bar=split, close=d['close'], allow_overlap=False)
        print('\n' + rqs2.format_rqs2(label, r), flush=True)
        m = r.get('metrics') or {}
        return dict(verdict=r['verdict'], rqs2_score=r.get('rqs2_score'),
                    gates={k: (bool(v) if isinstance(v, (bool, np.bool_)) else v)
                           for k, v in (r.get('gates') or {}).items()},
                    metrics={k: v for k, v in m.items()
                             if isinstance(v, (int, float, str, bool, np.integer,
                                               np.floating, np.bool_)) or v is None},
                    notes=r.get('notes'))

    off = judge(N_TRIALS, f'S1740-{tf} CALM ({N_TRIALS})')
    out['official'] = off
    out['stress'] = {str(nt): judge(nt, f'S1740-{tf} STRESS ({nt})') for nt in N_STRESS}
    out['verdict'] = off['verdict']
    out['rqs2_score'] = off['rqs2_score']
    out['full'] = dict(n=int(st['n']), n_long=n_long, n_short=n_short,
                       wr=round(float(st['wr']), 2), exp_pip=round(float(st['exp']), 3),
                       pf=round(float(st['pf']), 3), sl_med=round(sl_med, 2),
                       tp_med=round(tp_med, 2))
    # P1: گیت باید lift را نسبت به بی‌گیت بالا ببرد
    lift_g = off['metrics'].get('skill_lift_pp')
    out['p1_pass'] = (rep_u is not None and lift_g is not None
                      and rep['lift_vs_be'] > rep_u['lift_vs_be'])
    out['elapsed_s'] = round(_time.time() - t0, 1)
    json.dump(out, open(os.path.join(OUT_DIR, f'{tf}.json'), 'w'),
              ensure_ascii=False, indent=1, default=_default)
    print(f"    P1(lift_vs_be calm {rep['lift_vs_be']} > ungated {rep_u['lift_vs_be']}): "
          f"{out['p1_pass']}  ✔ {tf}.json ({out['elapsed_s']}s)", flush=True)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('tf')
    a = ap.parse_args()
    run_tf(a.tf.upper())
