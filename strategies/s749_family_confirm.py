#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S749 — تأیید قاعدهٔ منجمد S748 با قیمت‌گذاری کامل چندگانگی خانواده — XAUUSD
================================================================================
پیش‌ثبت: results/S749_PREREG_STRONG_CLOSE_FAMILY_MULTIPLICITY_CONFIRM.md
بازوی A: H2 تک‌کارت، همان پارامتر/نول/seed S748، فقط n_trials=640 (+ تنش 2000).
بازوی B: استخر FIFO {H2,H4,H6} با پارامترهای منجمد per-کارت از JSON S748.
هیچ جست‌وجویی. پارامترها فقط از results/_scan_S748/{TF}.json خوانده می‌شوند.
اجرا: python3 strategies/s749_family_confirm.py
"""
import os
import sys
import json
import time as _time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools import s434_fast_data as fd                              # noqa: E402
from engine import rqs2                                             # noqa: E402
from engine.rqs2_pool import pool_cards                             # noqa: E402
from strategies.s348_rr_sweep import queue_rr, trades_df, cost_pip  # noqa: E402
from strategies import s740_absorption as s740                      # noqa: E402
from strategies import s748_dual_drift as s748                      # noqa: E402

ASSET = 'XAUUSD'
N_TRIALS_OFFICIAL = 640      # 320 (S746) + 160 (S747) + 160 (S748)
N_TRIALS_STRESS = 2000
POOL_TFS = ('H2', 'H4', 'H6')
SEED = 748                   # همان S748 — نول بازتولیدپذیر
K_PERM = 500
SPLIT_FRAC = 0.60
SCAN_S748 = os.path.join(ROOT, 'results', '_scan_S748')
OUT_DIR = os.path.join(ROOT, 'results', '_scan_S749')
PREREG = 'results/S749_PREREG_STRONG_CLOSE_FAMILY_MULTIPLICITY_CONFIRM.md'


def _default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return str(o)


def frozen_params(tf):
    with open(os.path.join(SCAN_S748, f'{tf}.json')) as f:
        d = json.load(f)
    wp = d['winner_params']
    assert wp['k_r'] == s748.K_R and wp['k_sl'] == s748.K_SL and wp['rr'] == s748.RR
    return wp, d


def run_card(tf, rng):
    """اجرای منجمد S748 روی یک کارت + نول per-کارت. بدون جست‌وجو."""
    wp, d748 = frozen_params(tf)
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    n = len(df)
    split = int(SPLIT_FRAC * n)
    atr = s740.atr_plain(df['high'].values, df['low'].values, df['close'].values)
    sig, is_long = s748.build_signals(df, atr, wp['clv_k'], wp['w_d'], wp['mode'])
    st = queue_rr(df, sig, is_long, s748.K_SL * atr[sig], ASSET, s748.HOLD, s748.RR)
    tr = trades_df(st)
    n_long = int((tr['direction'] == 'long').sum())
    n_short = int(st['n'] - n_long)
    sl_med = float(np.median(st['sl_pip']))
    tp_med = float(np.median(st['tp_pip']))
    null, pool_note = s740.build_null(df, atr, n_long, n_short, s748.K_SL,
                                      s748.RR, K_PERM, rng)
    # تأیید بازتولید S748
    rep = dict(n=int(st['n']), wr=round(float(st['wr']), 2))
    print(f"[card {tf}] params={wp} n={st['n']} (L={n_long}/S={n_short}) "
          f"wr={st['wr']:.2f} pf={st['pf']:.3f} | S748 had n={d748['full']['n']} "
          f"wr={d748['full']['wr']} | src={d['src']}", flush=True)
    dt = pd.to_datetime(df['time'], unit='s').values if 'time' in df else \
        pd.to_datetime(d['time'], unit='s').values
    return dict(card=f'{ASSET}_{tf}', tf=tf, tr=tr, dt=dt, df=df, d=d,
                split=split, null=null, null_pool=pool_note,
                sl_med=sl_med, tp_med=tp_med, params=wp,
                lift=float(d748['metrics']['skill_lift_pp']),
                rep=rep, s748_full=d748['full'], src=d['src'])


def judge(tr, sl_med, tp_med, bar_time, null, n_trials, split_bar, close, label):
    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=bar_time, null=null, n_trials=n_trials,
                          split_bar=split_bar, close=close, allow_overlap=False)
    print('\n' + rqs2.format_rqs2(label, r), flush=True)
    m = r.get('metrics') or {}
    return dict(verdict=r['verdict'], rqs2_score=r.get('rqs2_score'),
                gates={k: (bool(v) if isinstance(v, (bool, np.bool_)) else v)
                       for k, v in (r.get('gates') or {}).items()},
                metrics={k: v for k, v in m.items()
                         if isinstance(v, (int, float, str, bool, np.integer,
                                           np.floating, np.bool_)) or v is None},
                notes=r.get('notes'))


def blend_pool_null(members_used, pool_df):
    """ترکیب وزنی نول‌ها با وزن = سهم هر کارت (الگوی S431/S770 — عیناً)."""
    w_by_card = pool_df['src_card'].value_counts().to_dict()
    out = {}
    for side in ('long', 'short'):
        num_u = num_m = num_s = den_u = den_p = 0.0
        kmin = None
        for m in members_used:
            w = float(w_by_card.get(m['card'], 0))
            if w <= 0:
                continue
            dd = m['null'][side]
            if dd.get('uncond_wr') is not None:
                num_u += dd['uncond_wr'] * w
                den_u += w
            if dd.get('perm_mean') is not None and dd.get('perm_sd') is not None:
                num_m += dd['perm_mean'] * w
                num_s += (dd['perm_sd'] ** 2) * (w ** 2)
                den_p += w
                k = dd.get('perm_k')
                if k is not None:
                    kmin = k if kmin is None else min(kmin, k)
        out[side] = dict(
            uncond_wr=(num_u / den_u) if den_u > 0 else None,
            perm_mean=(num_m / den_p) if den_p > 0 else None,
            perm_sd=(float(np.sqrt(num_s)) / den_p) if den_p > 0 else None,
            perm_max=None, perm_k=kmin)
    return out


def main():
    t0 = _time.time()
    os.makedirs(OUT_DIR, exist_ok=True)
    rng = np.random.default_rng(SEED)
    out = dict(strategy='S749_StrongCloseFamilyConfirm', asset=ASSET,
               prereg=PREREG, n_trials_official=N_TRIALS_OFFICIAL,
               n_trials_stress=N_TRIALS_STRESS, seed=SEED, k_perm=K_PERM)

    # ---------- بازوی A: H2 تک‌کارت ----------
    print('=' * 88 + '\n=== S749 ARM A :: H2 single-card, frozen S748 rule, n_trials=640', flush=True)
    h2 = run_card('H2', rng)
    A_off = judge(h2['tr'], h2['sl_med'], h2['tp_med'], h2['d']['time'], h2['null'],
                  N_TRIALS_OFFICIAL, h2['split'], h2['d']['close'], 'S749-A-H2 (640)')
    A_str = judge(h2['tr'], h2['sl_med'], h2['tp_med'], h2['d']['time'], h2['null'],
                  N_TRIALS_STRESS, h2['split'], h2['d']['close'], 'S749-A-H2 STRESS (2000)')
    out['arm_A'] = dict(card='H2', params=h2['params'], src=h2['src'],
                        span_years=round(float(h2['d']['span_years']), 2),
                        bars=len(h2['df']), split_bar=h2['split'],
                        reproduce=dict(now=h2['rep'], s748=h2['s748_full']),
                        null=h2['null'], null_pool=h2['null_pool'],
                        official=A_off, stress=A_str)
    json.dump(out, open(os.path.join(OUT_DIR, 'S749.json'), 'w'),
              ensure_ascii=False, indent=1, default=_default)

    # ---------- بازوی B: استخر FIFO ----------
    print('\n' + '=' * 88 + '\n=== S749 ARM B :: FIFO pool {H2,H4,H6}, frozen per-card params', flush=True)
    members = [h2] + [run_card(tf, rng) for tf in POOL_TFS if tf != 'H2']
    res = pool_cards([dict(card=m['card'], tr=m['tr'], dt=m['dt'], lift=m['lift'])
                      for m in members])
    if res is None:
        out['arm_B'] = dict(verdict='NO_POOL')
    else:
        print(f"[pool selection] {json.dumps(res['selection'], ensure_ascii=False, default=str)}",
              flush=True)
        print(f"[pool] n_before={res['n_before']} n_after={res['n_after']} "
              f"used={[u['card'] for u in res['used']]} "
              f"dropped={[(d_['card'], d_['reason']) for d_ in res['dropped']]}", flush=True)
        pool = res['pool'].sort_values('t_entry').reset_index(drop=True)
        used_cards = {u['card'] for u in res['used']}
        members_used = [m for m in members if m['card'] in used_cards]
        null = blend_pool_null(members_used, pool)
        t_a, t_b = pool['t_entry'].min(), pool['t_entry'].max()
        t_split = t_a + SPLIT_FRAC * (t_b - t_a)
        bar_time = (pool['t_entry'].values / 1e9).astype('int64')
        split_idx = int((pool['t_entry'].values < t_split).sum())
        sl_med = float(np.median([m['sl_med'] for m in members_used]))
        tp_med = float(np.median([m['tp_med'] for m in members_used]))
        pool2 = pool.copy()
        pool2['entry_bar'] = np.arange(len(pool2))
        pool2['exit_bar'] = np.arange(len(pool2))
        B_off = judge(pool2, sl_med, tp_med, bar_time, null, N_TRIALS_OFFICIAL,
                      split_idx, None, 'S749-B-POOL (640)')
        B_str = judge(pool2, sl_med, tp_med, bar_time, null, N_TRIALS_STRESS,
                      split_idx, None, 'S749-B-POOL STRESS (2000)')
        share = pool['src_card'].value_counts().to_dict()
        out['arm_B'] = dict(members=[dict(card=m['card'], params=m['params'],
                                          n=int(len(m['tr'])), lift=m['lift'],
                                          src=m['src']) for m in members],
                            selection=res['selection'], used=res['used'],
                            dropped=res['dropped'], n_before=res['n_before'],
                            n_after=res['n_after'], share_after_fifo=share,
                            split_idx=split_idx, null=null,
                            sl_med=sl_med, tp_med=tp_med,
                            official=B_off, stress=B_str)

    # ---------- حکم رسمی لایه (قاعدهٔ پیش‌ثبت §۴) ----------
    out['official_verdict'] = out['arm_A']['official']['verdict']
    out['official_score'] = out['arm_A']['official']['rqs2_score']
    out['elapsed_s'] = round(_time.time() - t0, 1)
    json.dump(out, open(os.path.join(OUT_DIR, 'S749.json'), 'w'),
              ensure_ascii=False, indent=1, default=_default)
    print(f"\n>>> S749 OFFICIAL (arm A, n_trials=640): {out['official_verdict']} "
          f"RQS2={out['official_score']}  [{out['elapsed_s']}s]", flush=True)


if __name__ == '__main__':
    main()
