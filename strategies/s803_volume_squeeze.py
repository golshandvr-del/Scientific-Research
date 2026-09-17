# -*- coding: utf-8 -*-
"""
S803 — شکستِ فشردگی با تأیید حجم (S800 × RVOL_slot ≥ 1.0)
================================================================================
پیش‌ثبت: results/S803_PREREG_VOLUME_CONFIRMED_SQUEEZE_BREAKOUT_XAUUSD.md (پیش از هر عدد).
صفر پارامتر آزاد:
  • پایه: cfg منجمد S800 (results/_scan_S800/<TF>_locked.json)
  • گیت: RVOL_slot = volume / median(30 کندل قبلِ هم‌ساعت، shift 1، min_periods 20) ≥ 1.0
         (S589/S1581 منجمد)؛ D1: میانهٔ 30 کندل قبل بدون اسلات
  • داوری: compute_rqs2 v2.6، split_bar = نیمه، n_trials=32 (+100 تنش)
  • استخر {H3,H6,H8} با سد ریسک (DD≤10%, PF≥1.4 روی نیمهٔ اول) پیش از لمس نیمهٔ دوم
اجرا: python3 strategies/s803_volume_squeeze.py --tf H6 | --pool | --p3
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
from tools import s434_fast_data as fd           # noqa: E402
from strategies import s800_squeeze_expansion as s800   # noqa: E402
from strategies import s802_informed_squeeze as s802    # noqa: E402

OUT = 'results/_scan_S803'
ASSET = 'XAUUSD'
SEED = 20260910
K_PERM = 500
RVOL_THR, SLOT_WIN, SLOT_MINP = 1.0, 30, 20      # منجمد S589
N_TRIALS = 32
N_TRIALS_STRESS = 100
CARDS = ['H1', 'H3', 'H6', 'H8', 'H12', 'D1']
POOL_CARDS = ['H3', 'H6', 'H8']
POOL_DD_MAX, POOL_PF_MIN = 10.0, 1.4


def rvol_slot(tf, n):
    """RVOL هم‌اسلات (S1581 بیت‌به‌بیت) روی کل داده؛ برش بعداً."""
    d = fd.load_fast(ASSET, tf)
    v = pd.Series(d['volume'][:n].astype(np.float64))
    if tf == 'D1':
        ref = v.shift(1).rolling(SLOT_WIN, min_periods=SLOT_MINP).median()
    else:
        hour = pd.Series(d['hour'][:n])
        ref = v.groupby(hour).transform(
            lambda s: s.shift(1).rolling(SLOT_WIN, min_periods=SLOT_MINP).median())
    rv = (v / ref.replace(0, np.nan)).values
    del d
    gc.collect()
    return rv


def gated_signals(df, base, cfg, rv, arm):
    long_b, short_b = s800.donch_signals(df, cfg['p'])
    sqz_ok = base['sqz'] < cfg['q']
    filt = s800.apply_filter(base, cfg['filter'])
    valid_sl = np.isfinite(base['sl_pip']) & (base['sl_pip'] > 0)
    ls = long_b & sqz_ok & filt & valid_sl
    ss = short_b & sqz_ok & filt & valid_sl
    n_raw = int(ls.sum() + ss.sum())
    ok = np.isfinite(rv)
    g = ok & (rv >= RVOL_THR) if arm == 'gated' else ok & (rv < RVOL_THR)
    ls &= g
    ss &= g
    sl = np.where(valid_sl, base['sl_pip'] * cfg['k'], 1.0)
    tp = sl * cfg['rr']
    return ls, ss, sl, tp, n_raw


def judge(tf, df, base, cfg, split, rv, arm, n_trials):
    ls, ss, sl, tp, n_raw = gated_signals(df, base, cfg, rv, arm)
    n_sig = int(ls.sum() + ss.sum())
    tr = se.simulate_trades(df, ls, ss, sl, tp, ASSET,
                            max_hold=cfg['hold'], allow_overlap=False)
    if tr is None or len(tr) < 10:
        return dict(tf=tf, arm=arm, n=0 if tr is None else len(tr), n_raw=n_raw,
                    n_sig=n_sig, verdict='UNPROVEN', score=0.0), None
    null = s800.build_null_barrier(df, ls, ss, sl, tp, cfg['hold'], K=K_PERM, seed=SEED)
    s = s800.summarize(tr, se.ASSETS[ASSET]['spread_pip'])
    sl_med = float(np.median(tr['sl_pip'].values))
    tp_med = sl_med * cfg['rr']
    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=df['time'].values, null=null,
                          n_trials=n_trials, split_bar=split, close=df['close'].values)
    out = dict(tf=tf, arm=arm, cfg=cfg, split=split, bars=len(df), n_raw=n_raw,
               n_sig=n_sig, pass_rate=(n_sig / n_raw if n_raw else None),
               n=s['n'], wr=s['wr'], exp_pip=s['exp_pip'], pf=s['pf'],
               sl_med=sl_med, tp_med=tp_med, n_trials=n_trials,
               verdict=r['verdict'], score=r['rqs2_score'],
               gates={k: (None if v is None else bool(v)) for k, v in r['gates'].items()},
               skill_p_perm=r['metrics'].get('skill_p_perm'),
               metrics={k: (float(v) if isinstance(v, (int, float, np.floating)) else str(v))
                        for k, v in r['metrics'].items()})
    member = dict(card=f'XAUUSD_{tf}', tr=tr,
                  dt=pd.to_datetime(df['time'].values, unit='s').values,
                  lift=float(r['metrics'].get('skill_lift_pp') or 0.0),
                  null=null, sl_med=sl_med, tp_med=tp_med, split=split)
    return out, member


def run_card(tf, want_member=False):
    os.makedirs(OUT, exist_ok=True)
    cfg, split = s802.frozen_cfg(tf)
    meta, df = s800.load(tf)
    base = s800.base_arrays(df, need_filters=(cfg['filter'] != 'none'), tf=tf)
    rv = rvol_slot(tf, len(df))
    res, member = {}, None
    for arm in ('gated', 'counter'):
        out, m = judge(tf, df, base, cfg, split, rv, arm, N_TRIALS)
        out['src'] = meta['src']
        if arm == 'gated' and m is not None:
            member = m
            st, _ = judge(tf, df, base, cfg, split, rv, arm, N_TRIALS_STRESS)
            out['stress'] = dict(n_trials=N_TRIALS_STRESS, verdict=st['verdict'], score=st['score'])
        res[arm] = out
        mm = out.get('metrics', {})
        print(f"[S803/{tf}/{arm}] {out['verdict']} score={out['score']:.1f} n={out['n']} "
              f"(raw {out['n_raw']}→{out['n_sig']}, pass={out.get('pass_rate') or 0:.2f}) "
              f"wr={out.get('wr', 0):.1f} lift={mm.get('skill_lift_pp')} z={mm.get('skill_z')} "
              f"DD={mm.get('max_dd_pct')} PF={mm.get('profit_factor')} "
              f"FAILED={[k for k, v in out.get('gates', {}).items() if v is False]}", flush=True)
    with open(f'{OUT}/{tf}_judge.json', 'w') as f:
        json.dump(res, f, indent=1, default=str)
    if want_member:
        return member
    del df, base
    gc.collect()


def first_half_risk(m):
    """سد ریسک استخر روی نیمهٔ اول فقط (بدون لمس holdout)."""
    tr = m['tr']
    h1 = tr[tr['entry_bar'].astype(int).values < m['split']]
    pnl = h1['pnl_pip'].values.astype(float)
    if len(pnl) == 0:
        return dict(n=0, pf=0.0, dd_pct=99.0)
    gp, gl = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    pf = gp / gl if gl > 0 else float('inf')
    # DD تقریبی درصدی: ریسک ۱٪ در هر معامله ⇒ pnl/sl_pip درصد
    r = pnl / h1['sl_pip'].values.astype(float)
    eq = np.cumsum(r)
    dd = float(np.max(np.maximum.accumulate(eq) - eq)) if len(eq) else 0.0
    return dict(n=int(len(pnl)), pf=float(pf), dd_pct=dd)


def run_pool():
    os.makedirs(OUT, exist_ok=True)
    members = [m for m in (run_card(tf, True) for tf in POOL_CARDS) if m is not None]
    res = pool_cards(members) if members else None
    if res is None:
        json.dump(dict(verdict='NO-POOL'), open(f'{OUT}/POOL_judge.json', 'w'))
        print('[S803/POOL] هیچ عضو lift>0.', flush=True)
        return
    used_cards = {u['card'] for u in res['used']}
    members_used = [m for m in members if m['card'] in used_cards]
    # سد ریسک نیمهٔ اول (پیش‌ثبت §۲) — روی اعضا (تقریب استخر)
    pool = res['pool'].sort_values('t_entry').reset_index(drop=True)
    t0, t1 = pool['t_entry'].min(), pool['t_entry'].max()
    t_split = t0 + 0.5 * (t1 - t0)
    h1 = pool[pool['t_entry'] < t_split]
    pnl = h1['pnl_pip'].values.astype(float)
    gp, gl = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    pf1 = gp / gl if gl > 0 else float('inf')
    r = pnl / h1['sl_pip'].values.astype(float)
    eq = np.cumsum(r)
    dd1 = float(np.max(np.maximum.accumulate(eq) - eq)) if len(eq) else 0.0
    risk = dict(first_half_n=int(len(pnl)), pf=float(pf1), dd_pct=dd1,
                blocked=bool(dd1 > POOL_DD_MAX or pf1 < POOL_PF_MIN))
    print(f"[S803/POOL] used={sorted(used_cards)} dropped={[(d['card'], d['reason']) for d in res['dropped']]} "
          f"n_before={res['n_before']} n_after={res['n_after']} first-half risk={risk}", flush=True)
    out = dict(used=res['used'], dropped=res['dropped'], selection=res['selection'],
               n_before=res['n_before'], n_after=res['n_after'], risk_gate=risk)
    if risk['blocked']:
        out['verdict'] = 'POOL-RISK-BLOCKED'
        print('[S803/POOL] سد ریسک نیمهٔ اول شکست ⇒ POOL-RISK-BLOCKED؛ holdout لمس نشد.', flush=True)
    else:
        null = s802.blend_pool_null(members_used, pool)
        split_idx = int((pool['t_entry'].values < t_split).sum())
        bar_time = (pool['t_entry'].values / 1e9).astype('int64')
        sl_med = float(np.median([m['sl_med'] for m in members_used]))
        tp_med = float(np.median([m['tp_med'] for m in members_used]))
        pool2 = pool.copy()
        pool2['entry_bar'] = np.arange(len(pool2))
        pool2['exit_bar'] = np.arange(len(pool2))
        for nt in (N_TRIALS, N_TRIALS_STRESS):
            rr = rqs2.compute_rqs2(pool2, ASSET, sl_pip=sl_med, tp_pip=tp_med, bar_time=bar_time,
                                   null=null, n_trials=nt, split_bar=split_idx, close=None)
            out[f'n_trials_{nt}'] = dict(verdict=rr['verdict'], score=rr['rqs2_score'],
                                         gates={k: (None if v is None else bool(v)) for k, v in rr['gates'].items()},
                                         metrics={k: (float(v) if isinstance(v, (int, float, np.floating)) else str(v))
                                                  for k, v in rr['metrics'].items()})
            print(f"[S803/POOL n_trials={nt}] {rr['verdict']} score={rr['rqs2_score']:.1f} n={len(pool2)} "
                  f"lift={rr['metrics'].get('skill_lift_pp')} z={rr['metrics'].get('skill_z')} "
                  f"DD={rr['metrics'].get('max_dd_pct')} FAILED={[k for k, v in rr['gates'].items() if v is False]}", flush=True)
        out['verdict'] = out[f'n_trials_{N_TRIALS}']['verdict']
    with open(f'{OUT}/POOL_judge.json', 'w') as f:
        json.dump(out, f, indent=1, default=str)


def run_p3():
    """P3: φ بین (RVOL≥1) و (ρ≥0.618) روی کندل‌های شکست خام S800، H6/H8."""
    out = {}
    for tf in ('H6', 'H8', 'D1'):
        cfg, split = s802.frozen_cfg(tf)
        meta, df = s800.load(tf)
        base = s800.base_arrays(df, need_filters=(cfg['filter'] != 'none'), tf=tf)
        rv = rvol_slot(tf, len(df))
        long_b, short_b = s800.donch_signals(df, cfg['p'])
        sqz_ok = base['sqz'] < cfg['q']
        filt = s800.apply_filter(base, cfg['filter'])
        sig = (long_b | short_b) & sqz_ok & filt & np.isfinite(rv)
        rho, body = s802.rho_arrays(df)
        a = (rv[sig] >= RVOL_THR)
        b = (rho[sig] >= s802.RHO)
        n11 = int((a & b).sum()); n10 = int((a & ~b).sum()); n01 = int((~a & b).sum()); n00 = int((~a & ~b).sum())
        den = np.sqrt((n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00))
        phi = (n11 * n00 - n10 * n01) / den if den > 0 else float('nan')
        out[tf] = dict(n=int(sig.sum()), phi=float(phi), n11=n11, n10=n10, n01=n01, n00=n00,
                       p_rvol=float(a.mean()), p_rho=float(b.mean()))
        print(f"[S803/P3 {tf}] n={sig.sum()} φ(RVOL≥1, ρ≥0.618)={phi:.3f}  P(RVOL≥1)={a.mean():.2f} P(ρ≥.618)={b.mean():.2f}", flush=True)
    json.dump(out, open(f'{OUT}/P3_phi.json', 'w'), indent=1)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--tf')
    ap.add_argument('--pool', action='store_true')
    ap.add_argument('--p3', action='store_true')
    a = ap.parse_args()
    if a.p3:
        run_p3()
    elif a.pool:
        run_pool()
    elif a.tf:
        run_card(a.tf)
