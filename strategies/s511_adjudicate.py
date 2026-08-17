# -*- coding: utf-8 -*-
"""
S511 — مرحلهٔ ۲: مدلِ صفر + داوریِ رسمیِ برندگانِ سرشماری (یکی per کارت)
================================================================================
پیش‌ثبت: `results/S511_PREREG_GROSS_EDGE_CENSUS_401.md`. برندگان از
`results/_scan_S511/<tf>_summary.json` (top20[0]) خوانده می‌شوند — نه از حافظه
(انضباط ضدباگ: رابط از مصنوعِ تولیدشده خوانده می‌شود).

قواعد قفل‌شده:
  * آستانه‌های q10/q90 و SL از **پنجرهٔ اکتشاف** منجمدند و روی کل نمونه
    فقط اعمال می‌شوند (هیچ بازتنظیمی روی دادهٔ داوری نیست).
  * مدل صفر: پروتکل S382/S510 — ① بی‌قید stride 1,3,7 (سخت‌ترین)
    ② جایگشتِ زمان‌بندی K=2000، بذر 20260814. برای SHORT همان آینهٔ
    اثبات‌شده به‌کار می‌رود و مدل صفر هم در **همان آینه** ساخته می‌شود
    (مقایسهٔ عادلانه: لایه و صفر در یک جهان).
  * داوری: compute_rqs2 با n_trials=4812 و split_bar اکتشاف.

اجرا:  python3 strategies/s511_adjudicate.py --card M15|M30|H1 [--stage null|judge]
"""
import sys
import os
import json
import argparse

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import rqs2 as R                                        # noqa: E402
from engine import indicator_bank as ib                             # noqa: E402
from tools.s434_fast_data import as_dataframe                       # noqa: E402
from strategies.s510_rr_lowtf_wpr import atr_np, simulate           # noqa: E402
from strategies.s511_gross_census import (                          # noqa: E402
    cross_above, cross_below, OUT, SEED, SPLIT_FRAC, WARMUP,
    SL_K, RR, Q_LO, Q_HI, PIP, load_card)

K_PERM = 2000
N_TRIALS = 4812


def winner_of(tf):
    with open(f'{OUT}/{tf}_summary.json') as f:
        s = json.load(f)
    if not s['top20']:
        raise SystemExit(f'{tf}: هیچ برنده‌ای نیست')
    return s['top20'][0]


def build_signals(d, w):
    """سیگنالِ برنده روی **کل** نمونه با آستانهٔ منجمد از اکتشاف."""
    n = d['n_bars']
    split = int(SPLIT_FRAC * n)
    df_full = as_dataframe({k: d[k] for k in
                            ('time', 'open', 'high', 'low', 'close', 'volume')})
    x = ib.compute(w['ind'], df_full).to_numpy()
    x[:WARMUP] = np.nan
    # آستانه فقط از پنجرهٔ اکتشاف — منجمد
    q = float(np.nanquantile(x[:split], Q_HI if w['ev'] == 'A' else Q_LO))
    sig_bool = cross_above(x, q) if w['ev'] == 'A' else cross_below(x, q)
    sig_bool = np.nan_to_num(sig_bool, nan=False).astype(bool)
    sig_bool[:WARMUP] = False
    return sig_bool, split, q


def sim_side(d, sig_idx, sl_abs, is_long):
    if is_long:
        return simulate(d, sig_idx, sl_abs, RR)
    mirror = {'high': -d['low'], 'low': -d['high'], 'close': -d['close']}
    tr = simulate(mirror, sig_idx, sl_abs, RR)
    tr = tr.copy()
    tr['direction'] = 'short'
    return tr


def stage_null(tf):
    w = winner_of(tf)
    d = load_card(tf)
    n = d['n_bars']
    is_long = (w['side'] == 'long')
    sig_bool, split, q = build_signals(d, w)
    sig_idx = np.flatnonzero(sig_bool)
    a = atr_np(d['high'], d['low'], d['close'])
    sl_abs = float(np.nanmedian(a[:split])) * SL_K

    tr = sim_side(d, sig_idx, sl_abs, is_long)
    obs_wr = 100.0 * float((tr['outcome'] == 'win').mean())
    print(f"[NULL {tf}] winner={w['ind']} {w['ev']}/{w['side']}  thr={q:.5g}  "
          f"n_sig={len(sig_idx)}  n_trades={len(tr)}  wr={obs_wr:.2f}%", flush=True)

    # مبنای ①: بی‌قید — در همان جهت
    uncond_rows = []
    for stride in (1, 3, 7):
        idx = np.arange(WARMUP, n - 2, stride, dtype=np.int64)
        t0 = sim_side(d, idx, sl_abs, is_long)
        wr0 = 100.0 * float((t0['outcome'] == 'win').mean()) if len(t0) else None
        uncond_rows.append((stride, wr0, len(t0)))
        print(f'  uncond stride={stride}: n={len(t0)}  wr={wr0:.2f}%', flush=True)
    uncond_wr = max(r[1] for r in uncond_rows if r[1] is not None)

    # مبنای ②: جایگشتِ زمان‌بندی
    rng = np.random.default_rng(SEED)
    space = np.arange(WARMUP, n - 2, dtype=np.int64)
    wrs = []
    for k in range(K_PERM):
        pos = np.sort(rng.choice(space, size=min(len(sig_idx), len(space)),
                                 replace=False))
        tp_ = sim_side(d, pos, sl_abs, is_long)
        if len(tp_) >= 30:
            wrs.append(100.0 * float((tp_['outcome'] == 'win').mean()))
        if (k + 1) % 400 == 0:
            print(f'  perm {k+1}/{K_PERM}', flush=True)
    arr = np.asarray(wrs, float)
    perm = dict(mean=float(arr.mean()), sd=float(arr.std(ddof=1)),
                max=float(arr.max()), p95=float(np.percentile(arr, 95)),
                k=int(len(arr)))
    z = (obs_wr - perm['mean']) / perm['sd'] if perm['sd'] > 0 else float('nan')
    print(f'  perm: mean={perm["mean"]:.2f} sd={perm["sd"]:.2f} '
          f'max={perm["max"]:.2f}  ->  z={z:.2f}', flush=True)

    side_null = dict(uncond_wr=uncond_wr, perm_mean=perm['mean'],
                     perm_sd=perm['sd'], perm_max=perm['max'], perm_k=perm['k'])
    empty = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                 perm_max=None, perm_k=None)
    null = {'long': side_null if is_long else empty,
            'short': side_null if not is_long else empty}
    with open(f'{OUT}/{tf}_null.json', 'w') as f:
        json.dump(dict(card=f'XAUUSD_{tf}', winner=w, thr=q, obs_wr=obs_wr,
                       n_trades=len(tr), sl_abs=sl_abs, uncond=uncond_rows,
                       perm=perm, null=null, seed=SEED, k=K_PERM,
                       z_preview=z), f, ensure_ascii=False)
    print(f'saved -> {OUT}/{tf}_null.json')


def stage_judge(tf):
    w = winner_of(tf)
    with open(f'{OUT}/{tf}_null.json') as f:
        nm = json.load(f)
    d = load_card(tf)
    is_long = (w['side'] == 'long')
    sig_bool, split, q = build_signals(d, w)
    sl_abs = float(nm['sl_abs'])
    tr = sim_side(d, np.flatnonzero(sig_bool), sl_abs, is_long)

    sl_pip = sl_abs / PIP
    tp_pip = RR * sl_abs / PIP
    for col in ('pnl_pip', 'outcome', 'sl_pip', 'entry_bar', 'exit_bar',
                'direction'):
        assert col in tr.columns, f'missing column {col}'

    res = R.compute_rqs2(tr, 'XAUUSD', sl_pip=sl_pip, tp_pip=tp_pip,
                         bar_time=d['time'], close=d['close'],
                         null=nm['null'], n_trials=N_TRIALS, split_bar=split)
    tag = f"S511_{tf}_{w['ind']}_{w['ev']}_{w['side']}"
    print(R.format_rqs2(tag, res))
    with open(f'{OUT}/{tf}_rqs2.json', 'w') as f:
        json.dump(res, f, ensure_ascii=False, default=str)
    tr.to_csv(f'{OUT}/{tf}_trades.csv', index=False)
    print(f'saved -> {OUT}/{tf}_rqs2.json + {tf}_trades.csv')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--card', required=True, choices=['M15', 'M30', 'H1'])
    ap.add_argument('--stage', default='null', choices=['null', 'judge'])
    args = ap.parse_args()
    {'null': stage_null, 'judge': stage_judge}[args.stage](args.card)
