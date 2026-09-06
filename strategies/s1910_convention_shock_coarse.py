# -*- coding: utf-8 -*-
"""S1910 — شوکِ مطلعِ هم‌راستا با قرارداد — کارت‌های درشت H12 + D1 + استخر مکانیکی

پیش‌ثبت: results/S1910_PREREG_convention_shock_coarse_cards.md (قبل از هر عدد)
قاعده = عیناً S919 (S965 شوک/ρ/براکت/mh + گیت قرارداد ۶۰ روزهٔ S604)؛ K: H12=120، D1=60.
داوری: هر کارت یک بار روی کل داده؛ استخر {H12,D1} با engine/rqs2_pool.pool_cards (مکانیکی)
+ blend_pool_null + محور تقویمی مشترک (الگوی s431؛ اصلاح BUG-AXIS/BUG-SPAN).
n_trials=3 (H12, D1, pool). بازوهای گزارشی: ungated (P1/P4)، against (P3).
اجرا:
  python3 strategies/s1910_convention_shock_coarse.py --tf H12
  python3 strategies/s1910_convention_shock_coarse.py --tf D1
  python3 strategies/s1910_convention_shock_coarse.py --pool
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

from engine import scalp_engine as se                              # noqa: E402
from engine.rqs2 import compute_rqs2                               # noqa: E402
from engine.rqs2_pool import pool_cards, blend_pool_null           # noqa: E402
from tools import s434_fast_data as fd                             # noqa: E402

SEED = 1910
N_PERM = 500
COST_PIP = 3.3
N_TRIALS = 3
ATR_WIN, THETA, RHO_MIN = 21, 2.618, 0.618
K_SL, K_TP, MAX_HOLD = 1.272, 2.058, 16
DRIFT_K = {'H12': 120, 'D1': 60}
CKPT_DIR = os.path.join(ROOT, 'results', '_s1910_ckpt')


def load_df(tf):
    d = fd.load_fast('XAUUSD', tf)
    df = fd.as_dataframe(d)
    df.attrs['src'] = d.get('src', '?') if isinstance(d, dict) else '?'
    t = pd.to_datetime(df['time'], unit='s')
    df.attrs['span_years'] = (t.iloc[-1] - t.iloc[0]).days / 365.25
    df.attrs['dt'] = t.to_numpy().astype('datetime64[ns]')
    return df


def features(df):
    o = df['open'].to_numpy(float); h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float); c = df['close'].to_numpy(float)
    n = len(c)
    tr = np.zeros(n)
    tr[1:] = np.maximum.reduce([h[1:] - l[1:], np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])])
    atr = pd.Series(tr).rolling(ATR_WIN).mean().to_numpy()
    atr_prev = np.full(n, np.nan); atr_prev[1:] = atr[:-1]
    rng = h - l
    shock = (rng >= THETA * np.nan_to_num(atr_prev, nan=np.inf)) & (rng > 0)
    rho = np.divide(np.abs(c - o), rng, out=np.zeros(n), where=rng > 0)
    return shock, rho, np.sign(c - o), atr_prev


def signals(df, tf, arm='gated'):
    shock, rho, body_sgn, atr_prev = features(df)
    c = df['close'].to_numpy(float); n = len(c); K = DRIFT_K[tf]
    warm = ATR_WIN + K + 2
    idx = np.arange(n)
    ev = shock & (rho >= RHO_MIN) & (body_sgn != 0) & (idx >= warm)
    drift = np.full(n, np.nan); drift[K + 1:] = c[K:-1] - c[:-K - 1]
    up = ev & (body_sgn > 0); dn = ev & (body_sgn < 0)
    if arm == 'gated':
        up &= drift > 0; dn &= drift < 0
    elif arm == 'against':
        up &= drift < 0; dn &= drift > 0
    lm = np.zeros(n, bool); sm = np.zeros(n, bool)
    lm[1:] = up[:-1]; sm[1:] = dn[:-1]
    pip = se.ASSETS['XAUUSD']['pip']
    a = np.nan_to_num(atr_prev, nan=0.0)
    return lm, sm, np.maximum(K_SL * a / pip, 1e-9), np.maximum(K_TP * a / pip, 1e-9), warm


def run(df, lm, sm, sl, tp):
    return se.simulate_trades(df, lm, sm, sl, tp, 'XAUUSD', max_hold=MAX_HOLD, allow_overlap=False)


def stat(tr):
    if tr is None or len(tr) == 0:
        return {'n': 0}
    p = tr['pnl_pip'].to_numpy()
    return {'n': int(len(tr)), 'wr': round(100 * float((p > 0).mean()), 2),
            'e_pip': round(float(p.mean()), 2), 'net_pip': round(float(p.sum()), 1)}


def null_for(df, lm, sm, sl, tp, warm, n_perm=N_PERM, seed=SEED):
    n = len(df)
    valid = np.zeros(n, bool); valid[warm:n - MAX_HOLD - 1] = True
    vidx = np.flatnonzero(valid); rng = np.random.default_rng(seed)
    pick = rng.choice(vidx, size=min(50000, len(vidx)), replace=False); half = len(pick) // 2
    uml = np.zeros(n, bool); uml[pick[:half]] = True
    ums = np.zeros(n, bool); ums[pick[half:]] = True
    tu = se.simulate_trades(df, uml, ums, sl, tp, 'XAUUSD', max_hold=MAX_HOLD, allow_overlap=True)
    wr_unc = 100.0 * float((tu['pnl_pip'].values > 0).mean()) if tu is not None and len(tu) else None
    kl, ks = int(lm.sum()), int(sm.sum()); k = kl + ks
    perm = []
    for _ in range(n_perm):
        p = rng.choice(vidx, size=min(k, len(vidx)), replace=False); rng.shuffle(p)
        pl = np.zeros(n, bool); pl[p[:kl]] = True
        ps = np.zeros(n, bool); ps[p[kl:]] = True
        t = se.simulate_trades(df, pl, ps, sl, tp, 'XAUUSD', max_hold=MAX_HOLD, allow_overlap=False)
        if t is not None and len(t):
            perm.append(100.0 * float((t['pnl_pip'].values > 0).mean()))
    pa = np.array(perm, float)
    d = dict(uncond_wr=wr_unc, perm_mean=float(pa.mean()) if pa.size else None,
             perm_sd=float(pa.std(ddof=1)) if pa.size > 1 else None,
             perm_max=float(pa.max()) if pa.size else None, perm_k=int(pa.size))
    return {'long': d, 'short': dict(d)}


def save(name, obj):
    os.makedirs(CKPT_DIR, exist_ok=True)
    p = os.path.join(CKPT_DIR, name)
    with open(p, 'w') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=str)
    print(f'[ckpt] {p}')


def pack(r, extra):
    g = r.get('gates') or {}; m = r.get('metrics') or {}
    extra.update(verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'),
                 failed_gates=sorted(k for k, v in g.items() if v is False),
                 gates={k: g.get(k) for k in sorted(g)},
                 metrics={k: m.get(k) for k in (
                     'win_rate', 'null_ref_wr', 'breakeven_wr_cost', 'rr', 'z_obs', 'z_luck_bound',
                     'z_margin', 'skill_p_perm', 'skill_lift_pp', 'p_emp', 'perm_k', 'perm_max',
                     'top_win_share', 'profit_factor', 'max_dd_pct', 'oos_wr', 'is_wr')},
                 notes=(r.get('notes') or [])[:8])
    return extra


def judge(tf):
    df = load_df(tf)
    print(f'src={df.attrs["src"]} n={len(df)} span={df.attrs["span_years"]:.2f}y')
    rep = {}
    for arm in ('ungated', 'against'):
        lm, sm, sl, tp, warm = signals(df, tf, arm)
        rep[arm] = stat(run(df, lm, sm, sl, tp)); rep[arm].update(n_long=int(lm.sum()), n_short=int(sm.sum()))
    lm, sm, sl, tp, warm = signals(df, tf, 'gated')
    tr = run(df, lm, sm, sl, tp)
    out = {'tf': tf, 'src': df.attrs['src'], 'n_bars': len(df), 'drift_K': DRIFT_K[tf],
           'gated': stat(tr), 'p1_p4_ungated': rep['ungated'], 'p3_against': rep['against'],
           'n_trials': N_TRIALS}
    out['gated'].update(n_long=int(lm.sum()), n_short=int(sm.sum()))
    if tr is None or len(tr) < 30:
        out['verdict'] = 'NO-TRADES'; save(f'judge_{tf}.json', out); print(out); return
    sl_med = float(np.median(tr['sl_pip'])); tp_med = sl_med * (K_TP / K_SL)
    null = null_for(df, lm, sm, sl, tp, warm)
    r = compute_rqs2(tr, 'XAUUSD', sl_pip=sl_med, tp_pip=tp_med,
                     bar_time=pd.to_numeric(df['time']).to_numpy(), close=df['close'].to_numpy(),
                     null=null, n_trials=N_TRIALS, split_bar=len(df) // 2,
                     initial_capital=10000.0, allow_overlap=False)
    out.update(sl_pip_med=round(sl_med, 1), tp_pip_med=round(tp_med, 1), null=null['long'])
    # مواد استخر (برای --pool؛ بدون داوری مجدد)
    out['_pool_material'] = dict(sl_pip=sl_med, tp_pip=tp_med, lift=None)
    save(f'judge_{tf}.json', pack(r, out))
    print(f"verdict={r.get('verdict')} score={r.get('rqs2_score')}")
    print(json.dumps({k: out[k] for k in ('gated', 'p1_p4_ungated', 'p3_against', 'failed_gates', 'metrics')},
                     ensure_ascii=False, indent=1, default=str))


def pool():
    """استخر مکانیکی {H12, D1}: عضویت و حذف را pool_cards تعیین می‌کند، نه من."""
    members = []
    for tf in DRIFT_K:
        jp = os.path.join(CKPT_DIR, f'judge_{tf}.json')
        assert os.path.exists(jp), f'ابتدا کارت {tf} داوری شود'
        j = json.load(open(jp))
        df = load_df(tf)
        lm, sm, sl, tp, warm = signals(df, tf, 'gated')
        tr = run(df, lm, sm, sl, tp)
        lift = j['metrics'].get('skill_lift_pp') if 'metrics' in j else None
        members.append(dict(card=tf, tr=tr, dt=df.attrs['dt'], lift=lift,
                            null=null_for(df, lm, sm, sl, tp, warm),
                            sl_pip=j['sl_pip_med'], tp_pip=j['tp_pip_med'], asset='XAUUSD'))
        print(f'[member] {tf}: n={len(tr)} lift={lift}')
    res = pool_cards(members)
    out = {'members': [dict(card=m['card'], n=int(len(m['tr'])), lift=m['lift']) for m in members],
           'n_trials': N_TRIALS}
    if res is None:
        out['verdict'] = 'NO-POOL (pool_cards returned None: no co-directional member)'
        save('judge_POOL.json', out); print(out); return
    out.update(used=[u['card'] for u in res['used']], dropped=res['dropped'],
               n_before=res['n_before'], n_after=res['n_after'])
    if len(res['used']) < 2:
        out['verdict'] = f"NO-POOL (only {out['used']} survived selection — pooling would re-adjudicate a single card)"
        save('judge_POOL.json', out); print(out); return
    pl = res['pool']
    used = [m for m in members if m['card'] in set(out['used'])]
    null = blend_pool_null(used, pl)
    shares = pl['src_card'].value_counts(normalize=True).to_dict()
    by = {m['card']: m for m in used}
    sl_med = float(sum(by[c]['sl_pip'] * w for c, w in shares.items()))
    tp_med = float(sum(by[c]['tp_pip'] * w for c, w in shares.items()))
    # محور تقویمی مشترک (اصلاح BUG-AXIS/BUG-SPAN از s431): شبکهٔ H1 یکنواخت
    STEP = 3600 * 1_000_000_000
    t_lo = int(pl['t_entry'].values.astype(np.int64).min()); t_hi = int(pl['t_exit'].values.astype(np.int64).max())
    axis_t = np.arange(t_lo - STEP, t_hi + 2 * STEP, STEP, dtype=np.int64)
    ref = load_df('H1'); ref_t = ref.attrs['dt'].astype(np.int64); ref_c = ref['close'].to_numpy(float)
    pos = np.clip(np.searchsorted(ref_t, axis_t, 'right') - 1, 0, len(ref_c) - 1)
    axis_close = ref_c[pos]
    pl = pl.copy()
    pl['entry_bar'] = np.clip(np.searchsorted(axis_t, pl['t_entry'].values.astype(np.int64), 'left'), 0, len(axis_t) - 1)
    pl['exit_bar'] = np.clip(np.searchsorted(axis_t, pl['t_exit'].values.astype(np.int64), 'left'), 0, len(axis_t) - 1)
    pl['exit_bar'] = np.maximum(pl['exit_bar'], pl['entry_bar'])
    pl = pl.sort_values('exit_bar', kind='mergesort').reset_index(drop=True)
    split_ns = t_lo + (t_hi - t_lo) // 2
    holdout = pl['t_entry'].values.astype(np.int64) >= split_ns
    r = compute_rqs2(pl, 'XAUUSD', sl_pip=sl_med, tp_pip=tp_med,
                     bar_time=axis_t // 1_000_000_000, close=axis_close, null=null,
                     holdout_mask=holdout, n_trials=N_TRIALS, initial_capital=10000.0,
                     allow_overlap=False)
    out.update(sl_pip_med=round(sl_med, 1), tp_pip_med=round(tp_med, 1), pool_stat=stat(pl), null=null)
    save('judge_POOL.json', pack(r, out))
    print(f"POOL verdict={r.get('verdict')} score={r.get('rqs2_score')} used={out['used']} n={len(pl)}")
    print(json.dumps({k: out[k] for k in ('pool_stat', 'dropped', 'failed_gates', 'metrics')},
                     ensure_ascii=False, indent=1, default=str))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--tf', choices=list(DRIFT_K))
    ap.add_argument('--pool', action='store_true')
    a = ap.parse_args()
    if a.pool:
        pool()
    else:
        judge(a.tf)
