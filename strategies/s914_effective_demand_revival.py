# -*- coding: utf-8 -*-
"""S914 — «احیای تقاضای مؤثر»: دیپ دوپله‌ای + بار احیا در ساختار صعودی · XAUUSD · Long-only

پیش‌ثبت: results/S914_PREREG_effective_demand_revival.md (کامیت 2cae9649)
مسیر C: کارت اصلی H1، جست‌وجو فقط در ۶۰٪ نخست، تست نهایی ۱ اجرا (n_trials=1).

سیگنال (منجمد — آناتومیک، صفر پارامترِ توزیعی — درس S882):
  ساختار صعودی: close[t] > close[t-21]
  دیپ دوپله‌ای: low[t-1] < low[t-2] و low[t-2] < low[t-3]
  بار احیا: close[t] > open[t] و close[t] > high[t-1]
  ورود کندل بعد (بدون نگاه به آینده). فقط LONG.

هندسه: TP=q60(MFE_train) · SL=q30(MAE_train) · TP>=SL · max_hold=21

اجرا:
  python3 strategies/s914_effective_demand_revival.py --phase train --tf H1
  python3 strategies/s914_effective_demand_revival.py --phase holdout --tf H1 --n_trials 1
  python3 strategies/s914_effective_demand_revival.py --phase family
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
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from engine import scalp_engine as se          # noqa: E402
from engine.rqs2 import compute_rqs2           # noqa: E402
from tools import s434_fast_data as fd         # noqa: E402

SEED = 914
TREND_LB = 21                    # منجمد — فیبوناچی: پنجرهٔ ساختار صعودی
MAX_HOLD = 21                    # منجمد — فیبوناچی
TRAIN_FRAC = 0.60
N_PERM = 500
COST_PIP = 3.3
GOLD_TFS = ('M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20', 'M30',
            'H1', 'H2', 'H3', 'H6', 'H8', 'H12', 'D1', 'W1', 'MN1')
CKPT_DIR = os.path.join(ROOT, 'results', '_s914_ckpt')


def load_df(tf: str) -> pd.DataFrame:
    d = fd.load_fast('XAUUSD', tf)
    df = fd.as_dataframe(d)
    df.attrs['src'] = d['src']
    df.attrs['span_years'] = d['span_years']
    return df


def ignition_signal(df: pd.DataFrame) -> np.ndarray:
    """احیای تقاضای مؤثر — آناتومیک محض؛ ورود کندل بعد (بدون نگاه به آینده)."""
    o = df['open'].to_numpy()
    h = df['high'].to_numpy()
    l = df['low'].to_numpy()
    c = df['close'].to_numpy()
    n = len(c)
    ev = np.zeros(n, bool)
    t = np.arange(TREND_LB + 3, n)             # نیازمند t-21 و t-3
    up_struct = c[t] > c[t - TREND_LB]          # ساختار صعودی (ترتیبی)
    dip2 = (l[t - 1] < l[t - 2]) & (l[t - 2] < l[t - 3])   # دیپ دوپله‌ای
    revival = (c[t] > o[t]) & (c[t] > h[t - 1])            # بار احیا
    ev[t] = up_struct & dip2 & revival
    out = np.zeros(n, bool)
    out[1:] = ev[:-1]              # ورود در کندل بعد
    return out


def mfe_mae_long(df, mask, mh):
    pip = se.ASSETS['XAUUSD']['pip']
    h = df['high'].to_numpy(); l = df['low'].to_numpy(); c = df['close'].to_numpy()
    idx = np.flatnonzero(mask)
    n = len(df)
    mfes, maes = [], []
    for i in idx:
        j0, j1 = i + 1, min(i + 1 + mh, n)
        if j1 <= j0:
            continue
        mfes.append((h[j0:j1].max() - c[i]) / pip)
        maes.append((c[i] - l[j0:j1].min()) / pip)
    return np.array(mfes), np.array(maes)


def geometry_from_train(df_tr, mask):
    mfes, maes = mfe_mae_long(df_tr, mask, MAX_HOLD)
    if len(mfes) < 30:
        return None
    tp = float(np.percentile(mfes, 60))
    sl = float(np.percentile(maes, 30))
    if tp < sl:
        tp = sl                                     # قید TP>=SL (پیش‌ثبت §۴)
    return {'tp': round(tp, 1), 'sl': round(sl, 1), 'n_sig': int(len(mfes)),
            'rr': round(tp / sl, 3) if sl else None}


def train_edge(df_tr, sig, geo):
    z = np.zeros(len(df_tr), bool)
    tr = se.simulate_trades(df_tr, sig, z, geo['sl'], geo['tp'], 'XAUUSD',
                            max_hold=MAX_HOLD, allow_overlap=False)
    if tr is None or len(tr) < 30:
        return None
    pnl = tr['pnl_pip'].to_numpy()
    return {'n': int(len(tr)),
            'wr': round(100.0 * float((pnl > 0).mean()), 2),
            'e_pip': round(float(pnl.mean()), 2),
            'e_over_sl_pct': round(100.0 * float(pnl.mean()) / geo['sl'], 2),
            'cost_over_sl_pct': round(100.0 * COST_PIP / geo['sl'], 2)}


def null_for(df, mask, sl, tp, mh, n_perm=N_PERM, seed=SEED):
    """الگوی tools/s437_adjudicate.py — گارد BUG-PERMK."""
    n = len(df)
    z = np.zeros(n, bool)
    warmup = TREND_LB + 4
    valid = np.zeros(n, bool)
    valid[warmup:n - mh - 1] = True
    vidx = np.flatnonzero(valid)
    rng = np.random.default_rng(seed)

    pick = rng.choice(vidx, size=min(50000, len(vidx)), replace=False)
    um = np.zeros(n, bool); um[pick] = True
    tu = se.simulate_trades(df, um, z, sl, tp, 'XAUUSD', max_hold=mh,
                            allow_overlap=True)
    wr_unc = 100.0 * float((tu['pnl_pip'].values > 0).mean()) if tu is not None and len(tu) else None

    k = int(mask.sum())
    perm = []
    for _ in range(n_perm):
        p = rng.choice(vidx, size=min(k, len(vidx)), replace=False)
        pm = np.zeros(n, bool); pm[p] = True
        t = se.simulate_trades(df, pm, z, sl, tp, 'XAUUSD', max_hold=mh,
                               allow_overlap=False)
        if t is not None and len(t):
            perm.append(100.0 * float((t['pnl_pip'].values > 0).mean()))
    pa = np.array(perm, float) if perm else np.array([])
    d = dict(uncond_wr=wr_unc,
             perm_mean=float(pa.mean()) if pa.size else None,
             perm_sd=float(pa.std(ddof=1)) if pa.size > 1 else None,
             perm_max=float(pa.max()) if pa.size else None,
             perm_k=int(pa.size))                    # 🔴 گارد BUG-PERMK
    return {'long': d, 'short': dict(d)}


def save_ckpt(name, obj):
    os.makedirs(CKPT_DIR, exist_ok=True)
    p = os.path.join(CKPT_DIR, name)
    with open(p, 'w') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=str)
    print(f'[ckpt] {p}')


def phase_train(tf: str):
    df = load_df(tf)
    print(f'src={df.attrs["src"]} n={len(df)} span={df.attrs["span_years"]:.2f}y')
    split = int(len(df) * TRAIN_FRAC)
    df_tr = df.iloc[:split].reset_index(drop=True)
    sig = ignition_signal(df_tr)
    out = {'tf': tf, 'split_bar': split, 'n_train': len(df_tr),
           'n_sig': int(sig.sum()), 'trend_lb': TREND_LB,
           'max_hold': MAX_HOLD}
    geo = geometry_from_train(df_tr, sig)
    out['geometry'] = geo
    if geo:
        out['train'] = train_edge(df_tr, sig, geo)
    save_ckpt(f'train_{tf}.json', out)
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str))


def phase_holdout(tf: str, n_trials: int):
    with open(os.path.join(CKPT_DIR, f'train_{tf}.json')) as f:
        trn = json.load(f)
    df = load_df(tf)
    split = trn['split_bar']
    df_ho = df.iloc[split:].reset_index(drop=True)
    sig = ignition_signal(df_ho)
    geo = trn['geometry']
    sl, tp = geo['sl'], geo['tp']
    z = np.zeros(len(df_ho), bool)
    tr = se.simulate_trades(df_ho, sig, z, sl, tp, 'XAUUSD',
                            max_hold=MAX_HOLD, allow_overlap=False)
    if tr is None or len(tr) < 30:
        res = {'error': f'n<30 (n={0 if tr is None else len(tr)})'}
        save_ckpt(f'holdout_{tf}.json', res)
        print(res)
        return
    null = null_for(df_ho, sig, sl, tp, MAX_HOLD)
    inner_split = int(len(df_ho) * 0.70)
    r = compute_rqs2(tr, 'XAUUSD', sl_pip=sl, tp_pip=tp,
                     bar_time=pd.to_numeric(df_ho['time']).to_numpy(),
                     close=df_ho['close'].to_numpy(),
                     null=null, n_trials=n_trials, split_bar=inner_split,
                     initial_capital=10000.0, allow_overlap=False)
    g = r.get('gates') or {}
    m = r.get('metrics') or {}
    res = {'geometry': geo, 'n_trades': int(len(tr)),
           'verdict': r.get('verdict'), 'rqs2_score': r.get('rqs2_score'),
           'failed_gates': sorted(k for k, v in g.items() if v is False),
           'unknown_gates': sorted(k for k, v in g.items() if v is None),
           'gates': {k: g.get(k) for k in sorted(g)},
           'metrics': {k: m.get(k) for k in (
               'wr', 'null_ref_wr', 'breakeven_wr_cost', 'rr',
               'z_obs', 'z_luck_bound', 'z_margin', 'skill_p_perm',
               'p_emp', 'perm_k', 'perm_max', 'top_win_share',
               'net_pip', 'oos_wr', 'is_wr')},
           'null': null['long'], 'n_trials': n_trials}
    save_ckpt(f'holdout_{tf}.json', res)
    print(f"verdict={r.get('verdict')} score={r.get('rqs2_score')}")
    print(json.dumps(res, ensure_ascii=False, indent=1, default=str))


def phase_family():
    """اسکن ۱۹ TF — فقط ناحیهٔ train هر TF (توصیفی) · چک‌پوینت هر TF."""
    fam = {}
    fam_path = os.path.join(CKPT_DIR, 'family.json')
    if os.path.exists(fam_path):
        with open(fam_path) as f:
            fam = json.load(f)
    for tf in GOLD_TFS:
        if tf in fam:
            print(f'[skip] {tf}')
            continue
        try:
            df = load_df(tf)
        except FileNotFoundError as e:
            fam[tf] = {'error': str(e)}
            save_ckpt('family.json', fam)
            continue
        split = int(len(df) * TRAIN_FRAC)
        df_tr = df.iloc[:split].reset_index(drop=True)
        sig = ignition_signal(df_tr)
        row = {'n_bars': len(df), 'n_train': split, 'n_sig': int(sig.sum()),
               'span_years': round(df.attrs['span_years'], 2)}
        geo = geometry_from_train(df_tr, sig)
        row['geometry'] = geo
        if geo:
            row['train'] = train_edge(df_tr, sig, geo)
        fam[tf] = row
        save_ckpt('family.json', fam)              # اندک اندک
        print(f'[family] {tf}: {row}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', required=True, choices=['train', 'holdout', 'family'])
    ap.add_argument('--tf', default='H1')
    ap.add_argument('--n_trials', type=int, default=1)
    a = ap.parse_args()
    if a.phase == 'train':
        phase_train(a.tf)
    elif a.phase == 'holdout':
        phase_holdout(a.tf, a.n_trials)
    else:
        phase_family()
