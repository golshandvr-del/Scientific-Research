# -*- coding: utf-8 -*-
"""S917 — «موج سفته‌بازانه‌ی دوطرفه»: شوک حجم ۱۳باره + بدنه + هم‌جهتی دریفت · XAUUSD · Long+Short

پیش‌ثبت: results/S917_PREREG_speculative_wave_bidirectional.md (کامیت d9a8c3bd)
مسیر C: کارت اصلی H2، جست‌وجو فقط در ۶۰٪ نخست، n_trials=2 (خانواده بار دوم پس از S916).

سیگنال (منجمد — تنها تفاوت با S916: پنجرهٔ حجم 55→13 و سمت SHORT آینه‌ای):
  شوک حجم : volume[t] > max(volume[t-13..t-1])
  LONG    : شوک ∧ close[t]>open[t] ∧ close[t]>close[t-21]
  SHORT   : شوک ∧ close[t]<open[t] ∧ close[t]<close[t-21]
  ورود کندل بعد. allow_overlap=False.

هندسه: TP=q60(MFE_train) · SL=q30(MAE_train) · TP>=SL · max_hold=34
(MFE/MAE هر سمت در جهت خودش سنجیده و برای هندسهٔ واحد تجمیع می‌شود)

اجرا:
  python3 strategies/s917_speculative_wave.py --phase train --tf H2
  python3 strategies/s917_speculative_wave.py --phase holdout --tf H2 --n_trials 2
  python3 strategies/s917_speculative_wave.py --phase family
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

SEED = 917
TREND_LB = 21                    # منجمد — فیبوناچی
VOL_LB = 13                      # منجمد — فیبوناچی (تفاوت با S916: 55→13)
MAX_HOLD = 34                    # منجمد — فیبوناچی
TRAIN_FRAC = 0.60
N_PERM = 500
COST_PIP = 3.3
GOLD_TFS = ('M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20', 'M30',
            'H1', 'H2', 'H3', 'H6', 'H8', 'H12', 'D1', 'W1', 'MN1')
CKPT_DIR = os.path.join(ROOT, 'results', '_s917_ckpt')


def load_df(tf: str) -> pd.DataFrame:
    d = fd.load_fast('XAUUSD', tf)
    df = fd.as_dataframe(d)
    df.attrs['src'] = d['src']
    df.attrs['span_years'] = d['span_years']
    return df


def wave_signals(df: pd.DataFrame):
    """موج سفته‌بازانه دوطرفه — آناتومیک محض؛ ورود کندل بعد."""
    o = df['open'].to_numpy()
    c = df['close'].to_numpy()
    v = df['volume'].to_numpy(dtype=float)
    n = len(c)
    vmax_prev = pd.Series(v).shift(1).rolling(VOL_LB).max().to_numpy()
    ev_l = np.zeros(n, bool)
    ev_s = np.zeros(n, bool)
    t = np.arange(VOL_LB + TREND_LB + 1, n)
    vshock = v[t] > vmax_prev[t]
    d = c[t] - c[t - TREND_LB]
    ev_l[t] = vshock & (c[t] > o[t]) & (d > 0)
    ev_s[t] = vshock & (c[t] < o[t]) & (d < 0)
    lm = np.zeros(n, bool); sm = np.zeros(n, bool)
    lm[1:] = ev_l[:-1]             # ورود در کندل بعد
    sm[1:] = ev_s[:-1]
    return lm, sm


def mfe_mae_both(df, lm, sm, mh):
    """MFE/MAE هر سمت در جهت خودش — تجمیع برای هندسهٔ واحد."""
    pip = se.ASSETS['XAUUSD']['pip']
    h = df['high'].to_numpy(); l = df['low'].to_numpy(); c = df['close'].to_numpy()
    n = len(df)
    mfes, maes = [], []
    for i in np.flatnonzero(lm):
        j0, j1 = i + 1, min(i + 1 + mh, n)
        if j1 <= j0:
            continue
        mfes.append((h[j0:j1].max() - c[i]) / pip)
        maes.append((c[i] - l[j0:j1].min()) / pip)
    for i in np.flatnonzero(sm):
        j0, j1 = i + 1, min(i + 1 + mh, n)
        if j1 <= j0:
            continue
        mfes.append((c[i] - l[j0:j1].min()) / pip)
        maes.append((h[j0:j1].max() - c[i]) / pip)
    return np.array(mfes), np.array(maes)


def geometry_from_train(df_tr, lm, sm):
    mfes, maes = mfe_mae_both(df_tr, lm, sm, MAX_HOLD)
    if len(mfes) < 30:
        return None
    tp = float(np.percentile(mfes, 60))
    sl = float(np.percentile(maes, 30))
    if tp < sl:
        tp = sl                                     # قید TP>=SL (پیش‌ثبت §۳)
    return {'tp': round(tp, 1), 'sl': round(sl, 1), 'n_sig': int(len(mfes)),
            'rr': round(tp / sl, 3) if sl else None}


def train_edge(df_tr, lm, sm, geo):
    tr = se.simulate_trades(df_tr, lm, sm, geo['sl'], geo['tp'], 'XAUUSD',
                            max_hold=MAX_HOLD, allow_overlap=False)
    if tr is None or len(tr) < 30:
        return None
    pnl = tr['pnl_pip'].to_numpy()
    return {'n': int(len(tr)),
            'wr': round(100.0 * float((pnl > 0).mean()), 2),
            'e_pip': round(float(pnl.mean()), 2),
            'e_over_sl_pct': round(100.0 * float(pnl.mean()) / geo['sl'], 2),
            'cost_over_sl_pct': round(100.0 * COST_PIP / geo['sl'], 2)}


def null_for(df, lm, sm, sl, tp, mh, n_perm=N_PERM, seed=SEED):
    """الگوی tools/s437_adjudicate.py — دوطرفه؛ گارد BUG-PERMK.

    جای‌گشت: k موقعیت تصادفی با همان نسبت long/short مشاهده‌شده.
    """
    n = len(df)
    warmup = VOL_LB + TREND_LB + 2
    valid = np.zeros(n, bool)
    valid[warmup:n - mh - 1] = True
    vidx = np.flatnonzero(valid)
    rng = np.random.default_rng(seed)

    # WR غیرشرطی — دو سمت جدا (هر کدام 25k)
    z = np.zeros(n, bool)
    pick = rng.choice(vidx, size=min(50000, len(vidx)), replace=False)
    half = len(pick) // 2
    uml = np.zeros(n, bool); uml[pick[:half]] = True
    ums = np.zeros(n, bool); ums[pick[half:]] = True
    tu = se.simulate_trades(df, uml, ums, sl, tp, 'XAUUSD', max_hold=mh,
                            allow_overlap=True)
    wr_unc = 100.0 * float((tu['pnl_pip'].values > 0).mean()) if tu is not None and len(tu) else None

    kl, ks = int(lm.sum()), int(sm.sum())
    k = kl + ks
    perm = []
    for _ in range(n_perm):
        p = rng.choice(vidx, size=min(k, len(vidx)), replace=False)
        rng.shuffle(p)
        pl = np.zeros(n, bool); pl[p[:kl]] = True
        ps = np.zeros(n, bool); ps[p[kl:]] = True
        t = se.simulate_trades(df, pl, ps, sl, tp, 'XAUUSD', max_hold=mh,
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
    lm, sm = wave_signals(df_tr)
    out = {'tf': tf, 'split_bar': split, 'n_train': len(df_tr),
           'n_sig_long': int(lm.sum()), 'n_sig_short': int(sm.sum()),
           'trend_lb': TREND_LB, 'vol_lb': VOL_LB, 'max_hold': MAX_HOLD}
    geo = geometry_from_train(df_tr, lm, sm)
    out['geometry'] = geo
    if geo:
        out['train'] = train_edge(df_tr, lm, sm, geo)
    save_ckpt(f'train_{tf}.json', out)
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str))


def phase_holdout(tf: str, n_trials: int):
    with open(os.path.join(CKPT_DIR, f'train_{tf}.json')) as f:
        trn = json.load(f)
    df = load_df(tf)
    split = trn['split_bar']
    df_ho = df.iloc[split:].reset_index(drop=True)
    lm, sm = wave_signals(df_ho)
    geo = trn['geometry']
    sl, tp = geo['sl'], geo['tp']
    tr = se.simulate_trades(df_ho, lm, sm, sl, tp, 'XAUUSD',
                            max_hold=MAX_HOLD, allow_overlap=False)
    if tr is None or len(tr) < 30:
        res = {'error': f'n<30 (n={0 if tr is None else len(tr)})'}
        save_ckpt(f'holdout_{tf}.json', res)
        print(res)
        return
    null = null_for(df_ho, lm, sm, sl, tp, MAX_HOLD)
    inner_split = int(len(df_ho) * 0.70)
    r = compute_rqs2(tr, 'XAUUSD', sl_pip=sl, tp_pip=tp,
                     bar_time=pd.to_numeric(df_ho['time']).to_numpy(),
                     close=df_ho['close'].to_numpy(),
                     null=null, n_trials=n_trials, split_bar=inner_split,
                     initial_capital=10000.0, allow_overlap=False)
    g = r.get('gates') or {}
    m = r.get('metrics') or {}
    res = {'geometry': geo, 'n_trades': int(len(tr)),
           'n_long': int(lm.sum()), 'n_short': int(sm.sum()),
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
        lm, sm = wave_signals(df_tr)
        row = {'n_bars': len(df), 'n_train': split,
               'n_sig_long': int(lm.sum()), 'n_sig_short': int(sm.sum()),
               'span_years': round(df.attrs['span_years'], 2)}
        geo = geometry_from_train(df_tr, lm, sm)
        row['geometry'] = geo
        if geo:
            row['train'] = train_edge(df_tr, lm, sm, geo)
        fam[tf] = row
        save_ckpt('family.json', fam)              # اندک اندک
        print(f'[family] {tf}: {row}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', required=True, choices=['train', 'holdout', 'family'])
    ap.add_argument('--tf', default='H2')
    ap.add_argument('--n_trials', type=int, default=2)
    a = ap.parse_args()
    if a.phase == 'train':
        phase_train(a.tf)
    elif a.phase == 'holdout':
        phase_holdout(a.tf, a.n_trials)
    else:
        phase_family()
