# -*- coding: utf-8 -*-
"""S1912 — «شوکِ مطلع در آرامش و هم‌راستا»: شوک کایل × DUAL (آرامش σ S606 AND قرارداد ۶۰d S604/S966) · XAUUSD · H8

پیش‌ثبت: results/S1912_PREREG_kyle_shock_dual_gate.md (قبل از هر عدد)
قاعده (صفر پارامتر آزاد):
  شوک: rng[t] >= 2.618*ATR21[t-1] ∧ ρ>=0.618 ∧ follow ∧ SL 1.272/TP 2.058×ATR21[t-1] ∧ mh=16     (S965)
  گیت آرامش: σ_t (RiskMetrics λ=0.94، علّی) <= median(σ_{t-233..t-1})  ⇔ regime_ratio<=1        (S606)
  گیت قرارداد: close[t-1]-close[t-1-180] هم‌جهت با معامله (H8، ۶۰ روز)                          (S604/S966)
  DUAL = هر دو گیت. σ/regime عیناً از s605 import.
داوری: یک لمس روی کل داده، n_trials=1. گزارشی: calm-only, drift-only, ungated, جدول ۲×۲ (P3), P5.
اجرا:
  python3 strategies/s1912_kyle_shock_dual.py --tf H8
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
import strategies.s605_engle_sigma_regime as S5           # noqa: E402  (sigma_series, regime_ratio)

SEED = 1912
N_PERM = 500
COST_PIP = 3.3
N_TRIALS = 1
ATR_WIN, THETA, RHO_MIN = 21, 2.618, 0.618
K_SL, K_TP, MAX_HOLD = 1.272, 2.058, 16
W_CALM = 233
DRIFT_K = {'H8': 180}
CARDS = ('H8',)
CKPT_DIR = os.path.join(ROOT, 'results', '_s1912_ckpt')


def load_df(tf):
    d = fd.load_fast('XAUUSD', tf)
    df = fd.as_dataframe(d)
    df.attrs['src'] = d.get('src', '?') if isinstance(d, dict) else '?'
    t = pd.to_datetime(df['time'], unit='s')
    df.attrs['span_years'] = (t.iloc[-1] - t.iloc[0]).days / 365.25
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
    # رژیم σ (S605/S606، علّی): reg_t = σ_t / median(σ_{t-W..t-1})
    reg = S5.regime_ratio(S5.sigma_series(c), W_CALM)
    return shock, rho, np.sign(c - o), atr_prev, reg


def signals(df, tf, arm='dual'):
    """arm: dual (داوری) | calm | drift | ungated | quadrant لیست: calm_al, calm_ag, storm_al, storm_ag."""
    shock, rho, body_sgn, atr_prev, reg = features(df)
    c = df['close'].to_numpy(float); n = len(shock); K = DRIFT_K[tf]
    warm = max(ATR_WIN, W_CALM + 60, K) + 2
    idx = np.arange(n)
    ev = shock & (rho >= RHO_MIN) & (body_sgn != 0) & (idx >= warm) & ~np.isnan(reg)
    drift = np.full(n, np.nan); drift[K + 1:] = c[K:-1] - c[:-K - 1]
    calm = reg <= 1.0
    aligned = ((body_sgn > 0) & (drift > 0)) | ((body_sgn < 0) & (drift < 0))
    against = ((body_sgn > 0) & (drift < 0)) | ((body_sgn < 0) & (drift > 0))
    n_ev = int(ev.sum())
    p5 = {'n_events': n_ev,
          'pr_calm': round(float((ev & calm).sum()) / n_ev, 4) if n_ev else None,
          'pr_drift': round(float((ev & aligned).sum()) / n_ev, 4) if n_ev else None,
          'pr_dual': round(float((ev & calm & aligned).sum()) / n_ev, 4) if n_ev else None}
    if p5['pr_calm'] and p5['pr_drift']:
        p5['collinearity_ratio'] = round(p5['pr_dual'] / (p5['pr_calm'] * p5['pr_drift']), 3)
    sel = {'dual': calm & aligned, 'calm': calm, 'drift': aligned, 'ungated': np.ones(n, bool),
           'calm_al': calm & aligned, 'calm_ag': calm & against,
           'storm_al': ~calm & aligned, 'storm_ag': ~calm & against}[arm]
    ev = ev & sel
    up = ev & (body_sgn > 0); dn = ev & (body_sgn < 0)
    lm = np.zeros(n, bool); sm = np.zeros(n, bool)
    lm[1:] = up[:-1]; sm[1:] = dn[:-1]
    pip = se.ASSETS['XAUUSD']['pip']
    a = np.nan_to_num(atr_prev, nan=0.0)
    return lm, sm, np.maximum(K_SL * a / pip, 1e-9), np.maximum(K_TP * a / pip, 1e-9), warm, p5


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


def judge(tf):
    assert tf in CARDS
    df = load_df(tf)
    assert 'mt5_full' in str(df.attrs['src']), 'داده باید mt5_full باشد'
    print(f'src={df.attrs["src"]} n={len(df)} span={df.attrs["span_years"]:.2f}y')
    rep = {}
    for arm in ('calm', 'drift', 'ungated', 'calm_al', 'calm_ag', 'storm_al', 'storm_ag'):
        lm, sm, sl, tp, warm, _ = signals(df, tf, arm)
        rep[arm] = stat(run(df, lm, sm, sl, tp)); rep[arm].update(n_long=int(lm.sum()), n_short=int(sm.sum()))
    lm, sm, sl, tp, warm, p5 = signals(df, tf, 'dual')
    tr = run(df, lm, sm, sl, tp)
    dual = stat(tr); dual.update(n_long=int(lm.sum()), n_short=int(sm.sum()))
    out = {'tf': tf, 'src': df.attrs['src'], 'n_bars': len(df), 'drift_K': DRIFT_K[tf],
           'rule': dict(theta=THETA, rho_min=RHO_MIN, k_sl=K_SL, k_tp=K_TP, max_hold=MAX_HOLD,
                        atr_win=ATR_WIN, calm_W=W_CALM, lambda_=S5.LAMBDA),
           'dual': dual, 'p1_calm_only': rep['calm'], 'p1_drift_only': rep['drift'],
           'p1_ungated': rep['ungated'],
           'p3_quadrants': {k: rep[k] for k in ('calm_al', 'calm_ag', 'storm_al', 'storm_ag')},
           'p5': p5, 'n_trials': N_TRIALS}
    if tr is None or len(tr) < 30:
        out['verdict'] = 'NO-TRADES'; save(f'judge_{tf}.json', out); print(out); return
    sl_med = float(np.median(tr['sl_pip'])); tp_med = sl_med * (K_TP / K_SL)
    null = null_for(df, lm, sm, sl, tp, warm)
    r = compute_rqs2(tr, 'XAUUSD', sl_pip=sl_med, tp_pip=tp_med,
                     bar_time=pd.to_numeric(df['time']).to_numpy(), close=df['close'].to_numpy(),
                     null=null, n_trials=N_TRIALS, split_bar=len(df) // 2,
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
    save(f'judge_{tf}.json', out)
    print(f"verdict={r.get('verdict')} score={r.get('rqs2_score')}")
    print(json.dumps({k: out[k] for k in ('dual', 'p1_calm_only', 'p1_drift_only', 'p1_ungated',
                                          'p3_quadrants', 'p5', 'failed_gates', 'metrics')},
                     ensure_ascii=False, indent=1, default=str))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--tf', required=True, choices=list(CARDS))
    judge(ap.parse_args().tf)
