# -*- coding: utf-8 -*-
"""S1580 — «شوکِ مطلعِ کایل × تأییدِ حجمِ هم‌اسلات»: S965 × گیت RVOL_slot≥1.0 (S589) · XAUUSD · H8/H6/H4

پیش‌ثبت: results/S1580_PREREG_VOLUME_CONFIRMED_KYLE_SHOCK.md (کامیت 9ebf65e8، قبل از این کد)
هارنس: کپیِ عینیِ strategies/s1911_kyle_shock_calm.py؛ تنها تغییر: گیت σ-calm → RVOL_slot.
قاعده (صفر پارامتر آزاد):
  شوک: rng[t] >= 2.618*ATR21[t-1] ∧ ρ>=0.618 ∧ follow ∧ SL 1.272/TP 2.058×ATR21[t-1] ∧ mh=16   (S965)
  گیت حجم: RVOL_slot[t] = volume[t] / median(volume of previous 30 same-hour bars, shift(1)) >= 1.0 (S589)
داوری: یک لمس روی کل داده per card، n_trials=3. بازوهای گزارشی: ungated (P1)، counter (P2)، pass-rate (P3).
اجرا: python3 strategies/s1580_kyle_shock_volume.py --tf H8 [--stress]
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

from engine import scalp_engine as se                     # noqa: E402
from engine.rqs2 import compute_rqs2                      # noqa: E402
from tools import s434_fast_data as fd                    # noqa: E402

SEED = 1580
N_PERM = 500
COST_PIP = 3.3
N_TRIALS = 3
ATR_WIN, THETA, RHO_MIN = 21, 2.618, 0.618
K_SL, K_TP, MAX_HOLD = 1.272, 2.058, 16
RVOL_THR, SLOT_WIN, SLOT_MINP = 1.0, 30, 20
CARDS = ('H8', 'H6', 'H4')
CKPT_DIR = os.path.join(ROOT, 'results', '_s1580_ckpt')
MIN_YEARS = 12.0


def load_df(tf):
    d = fd.load_fast('XAUUSD', tf)
    df = fd.as_dataframe(d)
    df.attrs['src'] = d.get('src', '?') if isinstance(d, dict) else '?'
    t = pd.to_datetime(df['time'], unit='s')
    df.attrs['span_years'] = (t.iloc[-1] - t.iloc[0]).days / 365.25
    assert df.attrs['span_years'] > MIN_YEARS, f'BUG-DATASETDRIFT {tf}: {df.attrs["span_years"]:.2f}y'
    assert 'volume' in df.columns, 'BUG-NOVOLUME'
    df['_hour'] = t.dt.hour.to_numpy()
    return df


def rvol_slot(df):
    v = df['volume'].astype(float)
    ref = v.groupby(df['_hour']).transform(
        lambda s: s.shift(1).rolling(SLOT_WIN, min_periods=SLOT_MINP).median())
    return (v / ref.replace(0, np.nan)).to_numpy(float)


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
    rv = rvol_slot(df)
    return shock, rho, np.sign(c - o), atr_prev, rv


def signals(df, arm='gated'):
    """arm: gated (RVOL>=1، داوری) | ungated (P1 = S965 خام) | counter (P2، RVOL<1)."""
    shock, rho, body_sgn, atr_prev, rv = features(df)
    n = len(shock)
    warm = max(ATR_WIN, SLOT_WIN * 3 + 60) + 2   # ≥ ۳۰ رخداد هر اسلات (۳ اسلات در H8)
    idx = np.arange(n)
    ev = shock & (rho >= RHO_MIN) & (body_sgn != 0) & (idx >= warm) & ~np.isnan(rv)
    n_ev = int(ev.sum()); n_pass = int((ev & (rv >= RVOL_THR)).sum())
    if arm == 'gated':
        ev = ev & (rv >= RVOL_THR)
    elif arm == 'counter':
        ev = ev & (rv < RVOL_THR)
    up = ev & (body_sgn > 0); dn = ev & (body_sgn < 0)
    lm = np.zeros(n, bool); sm = np.zeros(n, bool)
    lm[1:] = up[:-1]; sm[1:] = dn[:-1]
    pip = se.ASSETS['XAUUSD']['pip']
    a = np.nan_to_num(atr_prev, nan=0.0)
    return lm, sm, np.maximum(K_SL * a / pip, 1e-9), np.maximum(K_TP * a / pip, 1e-9), warm, \
        {'n_events': n_ev, 'n_pass': n_pass, 'pass_rate': round(100.0 * n_pass / n_ev, 1) if n_ev else None,
         'rvol_median_at_events': round(float(np.nanmedian(rv[shock & (rho >= RHO_MIN)])), 3)}


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


def judge(tf, stress=False):
    assert tf in CARDS
    n_trials = 50 if stress else N_TRIALS
    df = load_df(tf)
    print(f'src={df.attrs["src"]} n={len(df)} span={df.attrs["span_years"]:.2f}y', flush=True)
    rep = {}
    for arm in ('ungated', 'counter'):
        lm, sm, sl, tp, warm, _ = signals(df, arm)
        rep[arm] = stat(run(df, lm, sm, sl, tp)); rep[arm].update(n_long=int(lm.sum()), n_short=int(sm.sum()))
    lm, sm, sl, tp, warm, p3 = signals(df, 'gated')
    tr = run(df, lm, sm, sl, tp)
    gated = stat(tr); gated.update(n_long=int(lm.sum()), n_short=int(sm.sum()))
    out = {'tf': tf, 'src': df.attrs['src'], 'n_bars': len(df), 'span_years': round(df.attrs['span_years'], 2),
           'rule': dict(theta=THETA, rho_min=RHO_MIN, k_sl=K_SL, k_tp=K_TP, max_hold=MAX_HOLD,
                        atr_win=ATR_WIN, rvol_thr=RVOL_THR, slot_win=SLOT_WIN),
           'gated_rvol': gated, 'p1_ungated': rep['ungated'], 'p2_counter': rep['counter'],
           'p3_passrate': p3, 'n_trials': n_trials, 'stress': stress}
    if tr is None or len(tr) < 30:
        out['verdict'] = 'NO-TRADES'; save(f'judge_{tf}.json', out); print(out); return
    sl_med = float(np.median(tr['sl_pip'])); tp_med = sl_med * (K_TP / K_SL)
    null = null_for(df, lm, sm, sl, tp, warm)
    r = compute_rqs2(tr, 'XAUUSD', sl_pip=sl_med, tp_pip=tp_med,
                     bar_time=pd.to_numeric(df['time']).to_numpy(), close=df['close'].to_numpy(),
                     null=null, n_trials=n_trials, split_bar=len(df) // 2,
                     initial_capital=10000.0, allow_overlap=False)
    g = r.get('gates') or {}; m = r.get('metrics') or {}
    out.update(verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'),
               sl_pip_med=round(sl_med, 1), tp_pip_med=round(tp_med, 1),
               failed_gates=sorted(k for k, v in g.items() if v is False),
               gates={k: g.get(k) for k in sorted(g)},
               metrics={k: m.get(k) for k in (
                   'win_rate', 'null_ref_wr', 'breakeven_wr_cost', 'rr', 'z_obs', 'z_luck_bound',
                   'z_margin', 'skill_p_perm', 'skill_lift_pp', 'p_emp', 'perm_k', 'perm_max',
                   'top_win_share', 'profit_factor', 'max_dd_pct', 'oos_wr', 'is_wr')},
               null=null['long'], notes=(r.get('notes') or [])[:8])
    save(f'judge_{tf}{"_stress50" if stress else ""}.json', out)
    print(f"verdict={r.get('verdict')} score={r.get('rqs2_score')}")
    print(json.dumps({k: out[k] for k in ('gated_rvol', 'p1_ungated', 'p2_counter', 'p3_passrate',
                                          'failed_gates', 'metrics')},
                     ensure_ascii=False, indent=1, default=str))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--tf', required=True, choices=list(CARDS))
    ap.add_argument('--stress', action='store_true')
    a = ap.parse_args()
    judge(a.tf, a.stress)
