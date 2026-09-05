# -*- coding: utf-8 -*-
"""S919 — «شوکِ مطلعِ هم‌راستا با قرارداد بازار» · XAUUSD · H6 (اصلی) + H3

پیش‌ثبت: results/S919_PREREG_convention_aligned_informed_shock.md (قبل از هر عدد)
قاعده (صفر پارامتر آزاد — همه به ارث از S965 و S604):
  شوک      : rng[t] >= 2.618 * ATR21[t-1]   (ATR علّی)
  retention: rho[t] = |c-o|/rng >= 0.618
  جهت      : follow (بدنه صعودی -> LONG، نزولی -> SHORT)
  گیت قرارداد (S604، 60 روز تقویمی): drift = close[t-1] - close[t-1-K]
             LONG فقط اگر drift>0، SHORT فقط اگر drift<0
             H6: K=240 · H3: K=480 · (H8 عامدانه حذف: S965 ACCEPT دارد)
  براکت    : SL=1.272*ATR21[t-1], TP=2.058*ATR21[t-1] · max_hold=16 · ورود open کندل بعد
داوری: یک لمس روی کل 15.6 سال (هیچ فاز کشفی وجود ندارد)، n_trials=2.
بازوهای گزارشی (داوری نمی‌شوند): ungated (=S965 روی همان کارت، سنجهٔ P1)،
                                  against (شوک خلاف drift، سنجهٔ P3).
اجرا:
  python3 strategies/s919_convention_aligned_shock.py --tf H6
  python3 strategies/s919_convention_aligned_shock.py --tf H3
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

from engine import scalp_engine as se          # noqa: E402
from engine.rqs2 import compute_rqs2           # noqa: E402
from tools import s434_fast_data as fd         # noqa: E402

SEED = 919
N_PERM = 500
COST_PIP = 3.3
N_TRIALS = 2                                    # پیش‌ثبت §۲

ATR_WIN = 21                                    # S965
THETA = 2.618                                   # S965
RHO_MIN = 0.618                                 # S965
K_SL, K_TP = 1.272, 2.058                       # S965
MAX_HOLD = 16                                   # S965
DRIFT_K = {'H6': 240, 'H3': 480}                # S604: 60 روز تقویمی
CKPT_DIR = os.path.join(ROOT, 'results', '_s919_ckpt')


def load_df(tf: str) -> pd.DataFrame:
    d = fd.load_fast('XAUUSD', tf)
    df = fd.as_dataframe(d)
    df.attrs['src'] = d.get('src', '?') if isinstance(d, dict) else '?'
    t = pd.to_datetime(df['time'])
    df.attrs['span_years'] = (t.iloc[-1] - t.iloc[0]).days / 365.25
    return df


def features(df):
    o = df['open'].to_numpy(float); h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float); c = df['close'].to_numpy(float)
    n = len(c)
    tr = np.zeros(n)
    tr[1:] = np.maximum.reduce([h[1:] - l[1:], np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])])
    atr = pd.Series(tr).rolling(ATR_WIN).mean().to_numpy()
    atr_prev = np.full(n, np.nan); atr_prev[1:] = atr[:-1]         # علّی
    rng = h - l
    shock = (rng >= THETA * np.nan_to_num(atr_prev, nan=np.inf)) & (rng > 0)
    rho = np.divide(np.abs(c - o), rng, out=np.zeros(n), where=rng > 0)
    body_sgn = np.sign(c - o)
    return shock, rho, body_sgn, atr_prev


def signals(df, tf, arm='gated'):
    """arm: gated (داوری) | ungated (P1) | against (P3). ورود کندل بعد."""
    shock, rho, body_sgn, atr_prev = features(df)
    c = df['close'].to_numpy(float)
    n = len(c); K = DRIFT_K[tf]
    warm = ATR_WIN + K + 2
    idx = np.arange(n)
    ev = shock & (rho >= RHO_MIN) & (body_sgn != 0) & (idx >= warm)
    drift = np.full(n, np.nan)
    drift[K + 1:] = c[K:-1] - c[:-K - 1]                          # close[t-1]-close[t-1-K]
    up = ev & (body_sgn > 0); dn = ev & (body_sgn < 0)
    if arm == 'gated':
        up = up & (drift > 0); dn = dn & (drift < 0)
    elif arm == 'against':
        up = up & (drift < 0); dn = dn & (drift > 0)
    lm = np.zeros(n, bool); sm = np.zeros(n, bool)
    lm[1:] = up[:-1]; sm[1:] = dn[:-1]
    # براکت شناور در کندل ورود: ATR21 تا کندل رویداد (t) = atr_prev[t+1]
    pip = se.ASSETS['XAUUSD']['pip']
    a = np.nan_to_num(atr_prev, nan=0.0)
    sl_arr = np.maximum(K_SL * a / pip, 1e-9)
    tp_arr = np.maximum(K_TP * a / pip, 1e-9)
    return lm, sm, sl_arr, tp_arr, warm


def run(df, lm, sm, sl_arr, tp_arr):
    return se.simulate_trades(df, lm, sm, sl_arr, tp_arr, 'XAUUSD',
                              max_hold=MAX_HOLD, allow_overlap=False)


def stat(tr):
    if tr is None or len(tr) == 0:
        return {'n': 0}
    p = tr['pnl_pip'].to_numpy()
    return {'n': int(len(tr)), 'wr': round(100 * float((p > 0).mean()), 2),
            'e_pip': round(float(p.mean()), 2), 'net_pip': round(float(p.sum()), 1)}


def null_for(df, lm, sm, sl_arr, tp_arr, warm, n_perm=N_PERM, seed=SEED):
    """جایگشت هم‌هندسه (براکت شناور همان کندل)، همان k و نسبت L/S؛ گارد BUG-PERMK."""
    n = len(df)
    valid = np.zeros(n, bool); valid[warm:n - MAX_HOLD - 1] = True
    vidx = np.flatnonzero(valid)
    rng = np.random.default_rng(seed)
    pick = rng.choice(vidx, size=min(50000, len(vidx)), replace=False)
    half = len(pick) // 2
    uml = np.zeros(n, bool); uml[pick[:half]] = True
    ums = np.zeros(n, bool); ums[pick[half:]] = True
    tu = se.simulate_trades(df, uml, ums, sl_arr, tp_arr, 'XAUUSD',
                            max_hold=MAX_HOLD, allow_overlap=True)
    wr_unc = 100.0 * float((tu['pnl_pip'].values > 0).mean()) if tu is not None and len(tu) else None
    kl, ks = int(lm.sum()), int(sm.sum()); k = kl + ks
    perm = []
    for _ in range(n_perm):
        p = rng.choice(vidx, size=min(k, len(vidx)), replace=False)
        rng.shuffle(p)
        pl = np.zeros(n, bool); pl[p[:kl]] = True
        ps = np.zeros(n, bool); ps[p[kl:]] = True
        t = se.simulate_trades(df, pl, ps, sl_arr, tp_arr, 'XAUUSD',
                               max_hold=MAX_HOLD, allow_overlap=False)
        if t is not None and len(t):
            perm.append(100.0 * float((t['pnl_pip'].values > 0).mean()))
    pa = np.array(perm, float)
    d = dict(uncond_wr=wr_unc,
             perm_mean=float(pa.mean()) if pa.size else None,
             perm_sd=float(pa.std(ddof=1)) if pa.size > 1 else None,
             perm_max=float(pa.max()) if pa.size else None,
             perm_k=int(pa.size))
    return {'long': d, 'short': dict(d)}


def save(name, obj):
    os.makedirs(CKPT_DIR, exist_ok=True)
    p = os.path.join(CKPT_DIR, name)
    with open(p, 'w') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=str)
    print(f'[ckpt] {p}')


def judge(tf: str):
    assert tf in DRIFT_K, 'کارت خارج از پیش‌ثبت'
    df = load_df(tf)
    print(f'src={df.attrs["src"]} n={len(df)} span={df.attrs["span_years"]:.2f}y')
    # بازوهای گزارشی (فقط سنجه، داوری نمی‌شوند)
    report = {}
    for arm in ('ungated', 'against'):
        lm, sm, sl_arr, tp_arr, warm = signals(df, tf, arm)
        report[arm] = stat(run(df, lm, sm, sl_arr, tp_arr))
        report[arm].update(n_long=int(lm.sum()), n_short=int(sm.sum()))
    # بازوی داوری
    lm, sm, sl_arr, tp_arr, warm = signals(df, tf, 'gated')
    tr = run(df, lm, sm, sl_arr, tp_arr)
    gated = stat(tr); gated.update(n_long=int(lm.sum()), n_short=int(sm.sum()))
    out = {'tf': tf, 'src': df.attrs['src'], 'n_bars': len(df), 'drift_K': DRIFT_K[tf],
           'rule': dict(theta=THETA, rho_min=RHO_MIN, k_sl=K_SL, k_tp=K_TP,
                        max_hold=MAX_HOLD, atr_win=ATR_WIN),
           'gated': gated, 'p1_ungated': report['ungated'], 'p3_against': report['against'],
           'n_trials': N_TRIALS}
    if tr is None or len(tr) < 30:
        out['verdict'] = 'NO-TRADES'
        save(f'judge_{tf}.json', out); print(out); return
    sl_med = float(np.median(tr['sl_pip'].values)); tp_med = sl_med * (K_TP / K_SL)
    null = null_for(df, lm, sm, sl_arr, tp_arr, warm)
    split = int(len(df) * 0.5)
    r = compute_rqs2(tr, 'XAUUSD', sl_pip=sl_med, tp_pip=tp_med,
                     bar_time=pd.to_numeric(df['time']).to_numpy(),
                     close=df['close'].to_numpy(), null=null, n_trials=N_TRIALS,
                     split_bar=split, initial_capital=10000.0, allow_overlap=False)
    g = r.get('gates') or {}; m = r.get('metrics') or {}
    out.update(verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'),
               sl_pip_med=round(sl_med, 1), tp_pip_med=round(tp_med, 1),
               failed_gates=sorted(k for k, v in g.items() if v is False),
               gates={k: g.get(k) for k in sorted(g)},
               metrics={k: m.get(k) for k in (
                   'wr', 'win_rate', 'null_ref_wr', 'breakeven_wr_cost', 'rr',
                   'z_obs', 'skill_z', 'z_luck_bound', 'z_margin', 'skill_p_perm',
                   'skill_lift_pp', 'p_emp', 'perm_k', 'perm_max', 'top_win_share',
                   'net_pip', 'profit_factor', 'oos_wr', 'is_wr', 'max_dd_pct')},
               null=null['long'], notes=(r.get('notes') or [])[:8])
    save(f'judge_{tf}.json', out)
    print(f"verdict={r.get('verdict')} score={r.get('rqs2_score')}")
    print(json.dumps({k: out[k] for k in ('gated', 'p1_ungated', 'p3_against', 'failed_gates', 'metrics')},
                     ensure_ascii=False, indent=1, default=str))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--tf', required=True, choices=list(DRIFT_K))
    a = ap.parse_args()
    judge(a.tf)
