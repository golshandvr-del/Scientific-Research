# -*- coding: utf-8 -*-
"""
S802 — شکستِ مطلعِ فشردگی (Informed Squeeze Breakout) = S800 × ρ کایل
================================================================================
پیش‌ثبت: results/S802_PREREG_INFORMED_SQUEEZE_BREAKOUT_XAUUSD.md (کامیت c6284eb،
پیش از هر عدد). صفر پارامتر آزاد:
  • پایه: cfg منجمد هر کارت از results/_scan_S800/<TF>_locked.json (S800)
  • گیت:  ρ = |close−open|/(high−low) ≥ 0.618 روی کندل شکست + بدنه هم‌جهت (S965)
  • داوری: compute_rqs2 v2.6، split_bar = نیمه (همان S800)، n_trials=16
  • بازوی مکمل (ρ<0.618) تشخیصی برای P2
  • استخر {H2,H3,H6,H8} گیت‌دار با engine/rqs2_pool (FIFO تقویمی) + blend null

اجرا:
  python3 strategies/s802_informed_squeeze.py --tf H6        # کارت + مکمل
  python3 strategies/s802_informed_squeeze.py --pool         # استخر
"""
import sys
import os
import gc
import json
import argparse

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se            # noqa: E402
from engine import rqs2                          # noqa: E402
from engine.rqs2_pool import pool_cards          # noqa: E402
from strategies import s800_squeeze_expansion as s800   # noqa: E402

OUT = 'results/_scan_S802'
S800_OUT = 'results/_scan_S800'
ASSET = 'XAUUSD'
SEED = 20260905
K_PERM = 500
RHO = 0.618                       # منجمد S965
N_TRIALS = 16                     # پیش‌ثبت §۳
N_TRIALS_STRESS = 50
CARDS = ['H1', 'H2', 'H3', 'H6', 'H8', 'H12', 'D1']
POOL_CARDS = ['H3', 'H6', 'H8']   # H2 در S800 power_ok نداشت (power 73.1<78) — خطای پیش‌ثبت، ثبت شد


def frozen_cfg(tf):
    L = json.load(open(f'{S800_OUT}/{tf}_locked.json'))
    assert L.get('power_ok'), f'{tf}: S800 lock without power_ok'
    return L['cfg'], L['split']


def rho_arrays(df):
    o = df['open'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    rng = h - l
    body = c - o
    with np.errstate(divide='ignore', invalid='ignore'):
        rho = np.where(rng > 0, np.abs(body) / rng, 0.0)
    return rho, body


def gated_signals(df, base, cfg, arm):
    """سیگنال‌های S800 (بیت‌به‌بیت run_cfg) سپس گیت ρ. arm∈{'gated','counter'}."""
    long_b, short_b = s800.donch_signals(df, cfg['p'])
    sqz_ok = base['sqz'] < cfg['q']
    filt = s800.apply_filter(base, cfg['filter'])
    valid_sl = np.isfinite(base['sl_pip']) & (base['sl_pip'] > 0)
    ls = long_b & sqz_ok & filt & valid_sl
    ss = short_b & sqz_ok & filt & valid_sl
    n_raw = int(ls.sum() + ss.sum())
    rho, body = rho_arrays(df)
    informed = rho >= RHO
    if arm == 'gated':
        ls &= informed & (body > 0)
        ss &= informed & (body < 0)
    else:  # counter: ρ<0.618 (بدنه هم‌جهت تا فقط اثر ρ سنجیده شود)
        ls &= (~informed) & (body > 0)
        ss &= (~informed) & (body < 0)
    sl = np.where(valid_sl, base['sl_pip'] * cfg['k'], 1.0)
    tp = sl * cfg['rr']
    return ls, ss, sl, tp, n_raw


def judge_card(tf, df, base, cfg, split, arm, n_trials=N_TRIALS):
    ls, ss, sl, tp, n_raw = gated_signals(df, base, cfg, arm)
    n_sig = int(ls.sum() + ss.sum())
    tr = se.simulate_trades(df, ls, ss, sl, tp, ASSET,
                            max_hold=cfg['hold'], allow_overlap=False)
    if tr is None or len(tr) < 10:
        return dict(tf=tf, arm=arm, n=0 if tr is None else len(tr),
                    verdict='UNPROVEN', score=0.0, note='too few trades',
                    n_raw=n_raw, n_sig=n_sig), None
    null = s800.build_null_barrier(df, ls, ss, sl, tp, cfg['hold'],
                                   K=K_PERM, seed=SEED)
    s = s800.summarize(tr, se.ASSETS[ASSET]['spread_pip'])
    sl_med = float(np.median(tr['sl_pip'].values))
    tp_med = sl_med * cfg['rr']
    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=df['time'].values, null=null,
                          n_trials=n_trials, split_bar=split,
                          close=df['close'].values)
    out = dict(tf=tf, arm=arm, cfg=cfg, split=split, bars=len(df),
               n_raw=n_raw, n_sig=n_sig,
               pass_rate=(n_sig / n_raw if n_raw else None),
               n=s['n'], wr=s['wr'], exp_pip=s['exp_pip'], pf=s['pf'],
               sl_med=sl_med, tp_med=tp_med, n_trials=n_trials,
               verdict=r['verdict'], score=r['rqs2_score'],
               gates={k: (None if v is None else bool(v))
                      for k, v in r['gates'].items()},
               skill_p_perm=r['metrics'].get('skill_p_perm'),
               metrics={k: (float(v) if isinstance(v, (int, float, np.floating))
                            else str(v)) for k, v in r['metrics'].items()})
    member = dict(card=f'XAUUSD_{tf}', tr=tr,
                  dt=pd.to_datetime(df['time'].values, unit='s').values,
                  lift=float(r['metrics'].get('skill_lift_pp') or 0.0),
                  null=null, sl_med=sl_med, tp_med=tp_med)
    return out, member


def run_card(tf, want_member=False):
    os.makedirs(OUT, exist_ok=True)
    cfg, split = frozen_cfg(tf)
    meta, df = s800.load(tf)
    base = s800.base_arrays(df, need_filters=(cfg['filter'] != 'none'), tf=tf)
    res = {}
    member = None
    for arm in ('gated', 'counter'):
        out, m = judge_card(tf, df, base, cfg, split, arm)
        out['src'] = meta['src']
        res[arm] = out
        if arm == 'gated':
            member = m
            # تنش
            if m is not None:
                st, _ = judge_card(tf, df, base, cfg, split, arm,
                                   n_trials=N_TRIALS_STRESS)
                out['stress'] = dict(n_trials=N_TRIALS_STRESS,
                                     verdict=st['verdict'], score=st['score'])
        m_ = out.get('metrics', {})
        print(f"[S802/{tf}/{arm}] {out['verdict']} score={out['score']:.1f} "
              f"n={out['n']} (raw sig={out['n_raw']} → {out['n_sig']}, "
              f"pass={out.get('pass_rate') or 0:.2f}) wr={out.get('wr', 0):.1f} "
              f"lift={m_.get('skill_lift_pp')} z={m_.get('skill_z')} "
              f"FAILED={[k for k, v in out.get('gates', {}).items() if v is False]}",
              flush=True)
    with open(f'{OUT}/{tf}_judge.json', 'w') as f:
        json.dump(res, f, indent=1, default=str)
    if want_member:
        return member
    del df, base
    gc.collect()


def blend_pool_null(members_used, pool_df):
    """ترکیب وزنی نول‌ها با وزن = سهم هر کارت در استخر (الگوی S431/S770)."""
    w_by_card = pool_df['src_card'].value_counts().to_dict()
    out = {}
    for side in ('long', 'short'):
        num_u = num_m = num_s = den_u = den_p = 0.0
        kmin = None
        for m in members_used:
            w = float(w_by_card.get(m['card'], 0))
            if w <= 0:
                continue
            d = m['null'][side]
            num_u += d['uncond_wr'] * w
            den_u += w
            num_m += d['perm_mean'] * w
            num_s += (d['perm_sd'] ** 2) * (w ** 2)
            den_p += w
            kmin = d['perm_k'] if kmin is None else min(kmin, d['perm_k'])
        out[side] = dict(uncond_wr=num_u / den_u if den_u else None,
                         perm_mean=num_m / den_p if den_p else None,
                         perm_sd=float(np.sqrt(num_s)) / den_p if den_p else None,
                         perm_max=None, perm_k=kmin)
    return out


def run_pool():
    os.makedirs(OUT, exist_ok=True)
    members = []
    for tf in POOL_CARDS:
        m = run_card(tf, want_member=True)
        if m is not None:
            members.append(m)
    if not members:
        print('[S802/POOL] هیچ عضوی.', flush=True)
        return
    res = pool_cards(members)
    if res is None:
        print('[S802/POOL] هیچ عضو معتبری (lift>0) نماند.', flush=True)
        json.dump(dict(verdict='NO-POOL'), open(f'{OUT}/POOL_judge.json', 'w'))
        return
    print(f"[S802/POOL] selection={json.dumps(res['selection'], default=str)}",
          flush=True)
    print(f"[S802/POOL] used={[u['card'] for u in res['used']]} "
          f"dropped={[(d['card'], d['reason']) for d in res['dropped']]} "
          f"n_before={res['n_before']} n_after={res['n_after']}", flush=True)
    pool = res['pool'].sort_values('t_entry').reset_index(drop=True)
    used_cards = {u['card'] for u in res['used']}
    members_used = [m for m in members if m['card'] in used_cards]
    null = blend_pool_null(members_used, pool)
    # split تقویمی: نیمهٔ زمانی (همان مرز S800 — میانهٔ بازهٔ داده)
    t0, t1 = pool['t_entry'].min(), pool['t_entry'].max()
    t_split = t0 + 0.5 * (t1 - t0)
    split_idx = int((pool['t_entry'].values < t_split).sum())
    bar_time = (pool['t_entry'].values / 1e9).astype('int64')
    sl_med = float(np.median([m['sl_med'] for m in members_used]))
    tp_med = float(np.median([m['tp_med'] for m in members_used]))
    pool2 = pool.copy()
    pool2['entry_bar'] = np.arange(len(pool2))
    pool2['exit_bar'] = np.arange(len(pool2))
    out = {}
    for nt in (N_TRIALS, N_TRIALS_STRESS):
        r = rqs2.compute_rqs2(pool2, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                              bar_time=bar_time, null=null, n_trials=nt,
                              split_bar=split_idx, close=None)
        out[f'n_trials_{nt}'] = dict(
            verdict=r['verdict'], score=r['rqs2_score'],
            gates={k: (None if v is None else bool(v)) for k, v in r['gates'].items()},
            metrics={k: (float(v) if isinstance(v, (int, float, np.floating))
                         else str(v)) for k, v in r['metrics'].items()})
        print(f"[S802/POOL n_trials={nt}] {r['verdict']} score={r['rqs2_score']:.1f} "
              f"n={len(pool2)} lift={r['metrics'].get('skill_lift_pp')} "
              f"z={r['metrics'].get('skill_z')} p={r['metrics'].get('skill_p_perm')} "
              f"FAILED={[k for k, v in r['gates'].items() if v is False]}", flush=True)
    out['used'] = res['used']
    out['dropped'] = res['dropped']
    out['selection'] = res['selection']
    out['n_before'] = res['n_before']
    out['n_after'] = res['n_after']
    out['split_idx'] = split_idx
    out['null'] = null
    with open(f'{OUT}/POOL_judge.json', 'w') as f:
        json.dump(out, f, indent=1, default=str)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--tf')
    ap.add_argument('--pool', action='store_true')
    a = ap.parse_args()
    if a.pool:
        run_pool()
    elif a.tf:
        run_card(a.tf)
