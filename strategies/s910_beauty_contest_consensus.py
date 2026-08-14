# -*- coding: utf-8 -*-
"""S910 — «مسابقهٔ زیبایی»: اجماع مومنتوم چندافقی · XAUUSD

پیش‌ثبت: results/S910_PREREG_beauty_contest_consensus.md (کامیت 9017b1e6)
مسیر چندگانگی: C (هولد-اوت). جست‌وجو فقط در ۶۰٪ نخست؛ تست نهایی: حداکثر ۲ اجرا
(long/short) روی ۴۰٪ پایانی. n_trials=2.

سیگنال (منجمد در پیش‌ثبت):
  roc_h = close − close.shift(h) برای H={8,21,55,144}
  اجماع صعودی: هر چهار roc>0 و کندل قبل چنین نبود (لبه). ورود کندل بعد.
  اجماع نزولی: قرینهٔ کامل.

هندسه (قاعدهٔ پیش‌ثبت‌شده): TP=q60(MFE_train) · SL=q30(MAE_train) · TP>=SL
max_hold = 89 (فیبوناچی، منجمد — بدون جاروب)

اجرا:
  python3 strategies/s910_beauty_contest_consensus.py --phase train --tf M1
  python3 strategies/s910_beauty_contest_consensus.py --phase holdout --tf M1
  python3 strategies/s910_beauty_contest_consensus.py --phase family        # 19 TF
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

SEED = 20260813
HORIZONS = (8, 21, 55, 144)      # منجمد در پیش‌ثبت — فیبوناچی، غیر رند
MAX_HOLD = 89                    # منجمد — فیبوناچی
TRAIN_FRAC = 0.60                # منجمد در پیش‌ثبت (مسیر C)
N_PERM = 500                     # درس S435: زیر ۵۰۰ حکم H3 نوسانی است
N_TRIALS_HOLDOUT = 2             # حداکثر ۲ اجرای نهایی (long/short)
COST_PIP = 3.3                   # هزینهٔ طلا
GOLD_TFS = ('M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20', 'M30',
            'H1', 'H2', 'H3', 'H6', 'H8', 'H12', 'D1', 'W1', 'MN1')
CKPT_DIR = os.path.join(ROOT, 'results', '_s910_ckpt')


def load_df(tf: str) -> pd.DataFrame:
    d = fd.load_fast('XAUUSD', tf)
    df = fd.as_dataframe(d)
    df.attrs['src'] = d['src']
    df.attrs['span_years'] = d['span_years']
    return df


def consensus_signals(df: pd.DataFrame):
    """لبهٔ تولد اجماع؛ ورود کندل بعد (بدون نگاه به آینده)."""
    c = df['close'].to_numpy()
    n = len(c)
    up = np.ones(n, bool)
    dn = np.ones(n, bool)
    for h in HORIZONS:
        roc = np.empty(n)
        roc[:h] = 0.0
        roc[h:] = c[h:] - c[:-h]
        up &= roc > 0
        dn &= roc < 0
    warm = max(HORIZONS)
    up[:warm] = False
    dn[:warm] = False

    def edge(state):
        prev = np.zeros(n, bool)
        prev[1:] = state[:-1]
        e = state & ~prev
        out = np.zeros(n, bool)
        out[1:] = e[:-1]          # ورود در کندل بعد
        return out

    return edge(up), edge(dn)


def mfe_mae(df, mask, mh, side):
    pip = se.ASSETS['XAUUSD']['pip']
    h = df['high'].to_numpy(); l = df['low'].to_numpy(); c = df['close'].to_numpy()
    idx = np.flatnonzero(mask)
    n = len(df)
    mfes, maes = [], []
    for i in idx:
        j0, j1 = i + 1, min(i + 1 + mh, n)
        if j1 <= j0:
            continue
        if side == 'long':
            mfes.append((h[j0:j1].max() - c[i]) / pip)
            maes.append((c[i] - l[j0:j1].min()) / pip)
        else:
            mfes.append((c[i] - l[j0:j1].min()) / pip)
            maes.append((h[j0:j1].max() - c[i]) / pip)
    return np.array(mfes), np.array(maes)


def geometry_from_train(df_tr, mask, side):
    """قاعدهٔ پیش‌ثبت: TP=q60(MFE) · SL=q30(MAE) · TP>=SL."""
    mfes, maes = mfe_mae(df_tr, mask, MAX_HOLD, side)
    if len(mfes) < 30:
        return None
    tp = float(np.percentile(mfes, 60))
    sl = float(np.percentile(maes, 30))
    if tp < sl:
        tp = sl                                     # قید TP>=SL (پیش‌ثبت §۴)
    return {'tp': round(tp, 1), 'sl': round(sl, 1), 'n_sig': int(len(mfes)),
            'rr': round(tp / sl, 3) if sl else None}


def train_edge(df_tr, long_sig, short_sig, geo, side):
    z = np.zeros(len(df_tr), bool)
    ls = long_sig if side == 'long' else z
    ss = short_sig if side == 'short' else z
    tr = se.simulate_trades(df_tr, ls, ss, geo['sl'], geo['tp'], 'XAUUSD',
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
    """الگوی tools/s437_adjudicate.py — گارد BUG-PERMK رعایت شده."""
    n = len(df)
    z = np.zeros(n, bool)
    warmup = max(HORIZONS) + 2
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


# ───────────────────────── فازها ─────────────────────────

def phase_train(tf: str):
    df = load_df(tf)
    print(f'src={df.attrs["src"]} n={len(df)} span={df.attrs["span_years"]:.2f}y')
    split = int(len(df) * TRAIN_FRAC)
    df_tr = df.iloc[:split].reset_index(drop=True)
    long_sig, short_sig = consensus_signals(df_tr)
    out = {'tf': tf, 'split_bar': split, 'n_train': len(df_tr),
           'n_long_sig': int(long_sig.sum()), 'n_short_sig': int(short_sig.sum()),
           'horizons': list(HORIZONS), 'max_hold': MAX_HOLD}
    for side, sig in (('long', long_sig), ('short', short_sig)):
        geo = geometry_from_train(df_tr, sig, side)
        out[side] = {'geometry': geo}
        if geo:
            out[side]['train'] = train_edge(df_tr, long_sig, short_sig, geo, side)
    save_ckpt(f'train_{tf}.json', out)
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str))


def phase_holdout(tf: str, sides: list[str], n_trials: int = N_TRIALS_HOLDOUT):
    """تست نهایی — فقط جهت‌هایی که در train زنده ماندند.

    کارت M1: n_trials=2 (پیش‌ثبت §۳). کارت غیر-M1: n_trials=19 (پیش‌ثبت §۵).
    """
    with open(os.path.join(CKPT_DIR, f'train_{tf}.json')) as f:
        trn = json.load(f)
    df = load_df(tf)
    split = trn['split_bar']
    df_ho = df.iloc[split:].reset_index(drop=True)
    long_sig, short_sig = consensus_signals(df_ho)
    results = {}
    for side in sides:
        geo = trn[side]['geometry']
        sl, tp = geo['sl'], geo['tp']
        z = np.zeros(len(df_ho), bool)
        ls = long_sig if side == 'long' else z
        ss = short_sig if side == 'short' else z
        mask = long_sig if side == 'long' else short_sig
        tr = se.simulate_trades(df_ho, ls, ss, sl, tp, 'XAUUSD',
                                max_hold=MAX_HOLD, allow_overlap=False)
        if tr is None or len(tr) < 30:
            results[side] = {'error': f'n<30 (n={0 if tr is None else len(tr)})'}
            save_ckpt(f'holdout_{tf}.json', results)
            continue
        null = null_for(df_ho, mask, sl, tp, MAX_HOLD)
        inner_split = int(len(df_ho) * 0.70)
        res = compute_rqs2(tr, 'XAUUSD', sl_pip=sl, tp_pip=tp,
                           bar_time=pd.to_numeric(df_ho['time']).to_numpy(),
                           close=df_ho['close'].to_numpy(),
                           null=null, n_trials=n_trials,
                           split_bar=inner_split,
                           initial_capital=10000.0, allow_overlap=False)
        g = res.get('gates') or {}
        m = res.get('metrics') or {}
        results[side] = {
            'geometry': geo, 'n_trades': int(len(tr)),
            'verdict': res.get('verdict'), 'rqs2_score': res.get('rqs2_score'),
            'failed_gates': sorted(k for k, v in g.items() if v is False),
            'unknown_gates': sorted(k for k, v in g.items() if v is None),
            'gates': {k: g.get(k) for k in sorted(g)},
            'metrics': {k: m.get(k) for k in (
                'wr', 'null_ref_wr', 'breakeven_wr_cost', 'rr',
                'z_obs', 'z_luck_bound', 'z_margin', 'skill_p_perm',
                'p_emp', 'perm_k', 'perm_max', 'top_win_share',
                'net_pip', 'oos_wr', 'is_wr')},
            'null': null['long'], 'n_trials': n_trials,
        }
        save_ckpt(f'holdout_{tf}.json', results)   # اندک اندک
        print(f"[{side}] verdict={res.get('verdict')} score={res.get('rqs2_score')}")
    print(json.dumps(results, ensure_ascii=False, indent=1, default=str))


def phase_family():
    """اسکن خانواده روی ۱۹ TF — **فقط بخشِ train (۶۰٪ نخست)** هر TF.

    قاعدهٔ هندسه (TP=q60(MFE)·SL=q30(MAE)) منجمد است و بر train همان TF
    اعمال می‌شود — هولد-اوتِ هیچ TFی لمس نمی‌شود. این جست‌وجوی مجاز در
    ناحیهٔ train است (مسیر C)؛ اگر کارتی به داوری برود n_trials=19.
    چک‌پوینت پس از هر TF («اندک اندک»).
    """
    fam = {}
    fam_path = os.path.join(CKPT_DIR, 'family.json')
    if os.path.exists(fam_path):
        with open(fam_path) as f:
            fam = json.load(f)
    for tf in GOLD_TFS:
        if tf in fam:
            print(f'[skip] {tf} (checkpointed)')
            continue
        try:
            df = load_df(tf)
        except FileNotFoundError as e:
            fam[tf] = {'error': str(e)}
            save_ckpt('family.json', fam)
            continue
        split = int(len(df) * TRAIN_FRAC)
        df_tr = df.iloc[:split].reset_index(drop=True)
        long_sig, short_sig = consensus_signals(df_tr)
        row = {'n_bars': len(df), 'n_train': split,
               'span_years': round(df.attrs['span_years'], 2)}
        for side, sig in (('long', long_sig), ('short', short_sig)):
            geo = geometry_from_train(df_tr, sig, side)
            if not geo:
                row[side] = {'geometry': None, 'note': 'n_sig<30'}
                continue
            edge = train_edge(df_tr, long_sig, short_sig, geo, side)
            row[side] = {'geometry': geo, 'train': edge}
        fam[tf] = row
        save_ckpt('family.json', fam)              # اندک اندک — هر TF
        print(f'[family] {tf}: {row}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', required=True, choices=['train', 'holdout', 'family'])
    ap.add_argument('--tf', default='M1')
    ap.add_argument('--sides', default='long,short')
    ap.add_argument('--n_trials', type=int, default=N_TRIALS_HOLDOUT)
    a = ap.parse_args()
    if a.phase == 'train':
        phase_train(a.tf)
    elif a.phase == 'holdout':
        phase_holdout(a.tf, [s for s in a.sides.split(',') if s], a.n_trials)
    else:
        phase_family()
