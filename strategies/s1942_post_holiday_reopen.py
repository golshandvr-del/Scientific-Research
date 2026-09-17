#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S1942 — رانشِ بازگشاییِ پس‌ازتعطیلات (Post-Holiday Reopening Drift) · XAUUSD · مسیر C
پیش‌ثبت: results/S1942_PREREG_POST_HOLIDAY_REOPEN.md (کامیت c48cedbe — قبل از این فایل)

تقویم عیناً S547 (بازنویسی، نه import — به دلیل os.chdir در آن ماژول).
R = اولین روز کاری پس از تعطیلی. سیگنال روی آخرین کندلِ آخرین روز پیش از R ⇒ ورود open R.
جهت {LONG, SHORT} هر دو در کشف؛ قفل = برنده. هندسه/نول/داور از s940 (راستی‌آزمایی‌شده).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar
from dateutil.easter import easter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se                       # noqa: E402
from engine import rqs2                                     # noqa: E402
from tools import s434_fast_data as fd                      # noqa: E402
from strategies.s940_volatility_birth import (              # noqa: E402
    atr_geom_pip, run_combo, build_null, SL_FLOOR_PIP)
from strategies.s944_turn_of_month import day_index, bars_per_day   # noqa: E402

ASSET = 'XAUUSD'
OUT = 'results/_scan_S1942'
SEED = 1942
K_PERM = 1000
SPLIT_FRAC = 0.60
MIN_TRADES_DISC = 60          # پیشینی (رویداد تقویمی کمیاب — پیش‌ثبت §۱)
POWER_GATE = 78.0

GRID_DIR = ['long', 'short']
GRID_KSL = [2.058, 3.141]
GRID_RR = [1.0, 1.5]
GRID_HOLD_D = [1, 2]


# ---------------------------------------------------------------- تقویم (عیناً S547)
def us_holidays(y0=2010, y1=2027):
    h = USFederalHolidayCalendar().holidays(f'{y0}-01-01', f'{y1}-12-31', return_name=True)
    keep = h[~h.str.contains('Columbus|Veterans')]
    gf = pd.DatetimeIndex([pd.Timestamp(easter(y)) - pd.Timedelta(days=2)
                           for y in range(y0, y1 + 1)])
    return keep.index.union(gf).sort_values()


def postholiday_days(y0=2010, y1=2027):
    """R = اولین روز کاری پس از هر تعطیلی که خودش تعطیل نباشد."""
    hol = us_holidays(y0, y1)
    post = []
    for d in hol:
        r = d + pd.offsets.BDay(1)
        while r in hol:
            r = r + pd.offsets.BDay(1)
        post.append(r)
    return pd.DatetimeIndex(post).unique().sort_values()


_POST = postholiday_days()


def build_signals(d, direction, cache):
    """سیگنال روی آخرین کندل با تاریخ < R (فاصله ≤ 4 روز) — جای‌گذاری S547."""
    uniq, first_idx, inv, dt = cache
    dates = dt.normalize().values
    n = len(d['close'])
    sig = np.zeros(n, dtype=bool)
    for r in _POST.to_numpy():
        k = int(np.searchsorted(dates, r, side='left'))
        if k == 0 or k >= n:
            continue
        gap_days = (r - dates[k - 1]) / np.timedelta64(1, 'D')
        if gap_days <= 4:
            sig[k - 1] = True
    ls = sig if direction == 'long' else np.zeros(n, dtype=bool)
    ss = sig if direction == 'short' else np.zeros(n, dtype=bool)
    return ls, ss


# ---------------------------------------------------------------- فاز کشف
def phase_discover(tf):
    os.makedirs(OUT, exist_ok=True)
    ckpt_fp = os.path.join(OUT, f'discover_{tf}.json')
    d = fd.load_fast(ASSET, tf)
    assert 'mt5_full' in d['src'], 'E-16 guard: data not from mt5_full'
    print(f"DATA src={d['src']}  n_bars={d['n_bars']:,}  span={d['span_years']}y", flush=True)
    n_all = int(d['n_bars'])
    split = int(n_all * SPLIT_FRAC)
    d1 = {k: (v[:split] if isinstance(v, np.ndarray) else v) for k, v in d.items()}
    df1 = fd.as_dataframe(d1)
    atr_g = atr_geom_pip(d1)
    cache = day_index(d1)
    bpd = bars_per_day(cache, split)
    print(f'discovery bars={split:,} · bars/day(median)={bpd}', flush=True)

    t0 = time.time()
    results = {}
    i = 0
    n_total = len(GRID_DIR) * len(GRID_KSL) * len(GRID_RR) * len(GRID_HOLD_D)
    for direction in GRID_DIR:
        ls, ss = build_signals(d1, direction, cache)
        n_sig = int(ls.sum() + ss.sum())
        for k_sl in GRID_KSL:
            for rr in GRID_RR:
                for hd in GRID_HOLD_D:
                    i += 1
                    key = f'{direction}_k{k_sl}_rr{rr}_hd{hd}'
                    hold = hd * bpd
                    if n_sig < 10:
                        results[key] = dict(n=0)
                    else:
                        r = run_combo(df1, d1, atr_g, ls, ss, k_sl, rr, hold)
                        results[key] = r if r else dict(n=0)
                    rr_ = results[key]
                    print(f'[{i:2d}/{n_total}] {key:<28} n_sig={n_sig:>4} '
                          f'n={rr_.get("n", 0):>5} wr={rr_.get("wr", "-")} '
                          f'lift={rr_.get("lift", "-")} score={rr_.get("score", "-")} '
                          f'({time.time() - t0:.0f}s)', flush=True)
    with open(ckpt_fp, 'w') as f:
        json.dump(dict(tf=tf, split=split, n_bars=n_all, src=d['src'], bpd=bpd,
                       n_events=len(_POST), combos=results), f, indent=1)

    best_key, best_score = None, -1e18
    for key, r in results.items():
        if r.get('n', 0) < MIN_TRADES_DISC or r.get('net', -1) <= 0:
            continue
        if r['score'] > best_score:
            best_key, best_score = key, r['score']
    power_ok = best_key is not None and best_score >= POWER_GATE
    locked = dict(layer='S1942', tf=tf, split_bar=split, n_bars=n_all, src=d['src'], bpd=bpd,
                  criterion=f'max lift*sqrt(n) | both arms | n>={MIN_TRADES_DISC} & net>0 '
                            f'& power lift*sqrt(n)>={POWER_GATE}',
                  best_key=best_key if power_ok else None,
                  best=results.get(best_key) if power_ok else None,
                  best_unpowered=(dict(key=best_key, **results.get(best_key))
                                  if (best_key and not power_ok) else None),
                  score=round(best_score, 2) if best_key else None,
                  power_ok=bool(power_ok))
    lock_fp = os.path.join(OUT, f'lock_XAUUSD-{tf}.json')
    with open(lock_fp, 'w') as f:
        json.dump(locked, f, indent=2)
    print(f'\nLOCKED -> {lock_fp}\n' + json.dumps(locked, indent=2), flush=True)


# ---------------------------------------------------------------- فاز نهایی
def parse_key(key):
    t = key.split('_')
    return dict(direction=t[0], k_sl=float(t[1][1:]), rr=float(t[2][2:]), hd=int(t[3][2:]))


def phase_final(tf):
    lock_fp = os.path.join(OUT, f'lock_XAUUSD-{tf}.json')
    with open(lock_fp) as f:
        locked = json.load(f)
    if not locked.get('best_key'):
        print(f'{tf}: NO-CANDIDATE — holdout stays virgin.', flush=True)
        return
    p = parse_key(locked['best_key'])
    d = fd.load_fast(ASSET, tf)
    assert d['src'] == locked['src'] and 'mt5_full' in d['src'], 'data source changed!'
    assert int(d['n_bars']) == int(locked['n_bars']), 'n_bars changed!'
    split = int(locked['split_bar'])
    n_all = int(d['n_bars'])
    hold = p['hd'] * int(locked['bpd'])
    print(f"FINAL ONE-SHOT S1942 {tf} · locked={locked['best_key']} · hold={hold} · "
          f'holdout=[{split:,},{n_all:,}) · n_trials=1', flush=True)
    df = fd.as_dataframe(d)
    atr_g = atr_geom_pip(d)
    cache = day_index(d)
    ls, ss = build_signals(d, p['direction'], cache)
    ls[:split] = False
    ss[:split] = False
    sl = np.nan_to_num(np.clip(p['k_sl'] * atr_g, SL_FLOOR_PIP, None), nan=SL_FLOOR_PIP)
    tp = p['rr'] * sl
    tr = se.simulate_trades(df, ls, ss, sl, tp, ASSET, max_hold=hold, allow_overlap=False)
    print(f'holdout trades = {len(tr)}', flush=True)
    if len(tr) == 0:
        print('ZERO trades on holdout.', flush=True)
        return
    null = build_null(d, ls, ss, sl, p['rr'], hold, split, n_all, K=K_PERM, seed=SEED)
    with open(os.path.join(OUT, f'null_XAUUSD-{tf}.json'), 'w') as f:
        json.dump(null, f, indent=2)
    nested_split = split + int(0.60 * (n_all - split))
    sl_med = float(np.median(tr['sl_pip'].values))
    tp_med = p['rr'] * sl_med
    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=df['time'].values, null=null, n_trials=1,
                          split_bar=nested_split, close=df['close'].values)
    out = dict(layer='S1942', tf=tf, locked_key=locked['best_key'], src=d['src'],
               n_bars=n_all, span_years=d['span_years'], holdout_from=split,
               nested_split=nested_split, hold_bars=hold, n_trades=int(len(tr)),
               sl_med=round(sl_med, 1), tp_med=round(tp_med, 1), n_trials=1,
               verdict=r['verdict'], score=r.get('rqs2_score'), gates=r.get('gates'),
               metrics=r.get('metrics'), notes=r.get('notes'))
    with open(os.path.join(OUT, f'final_XAUUSD-{tf}.json'), 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nVERDICT={r['verdict']}  score={r.get('rqs2_score')}  "
          f"p_perm={r.get('metrics', {}).get('skill_p_perm')}", flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', choices=['discover', 'final'], required=True)
    ap.add_argument('--tf', required=True)
    a = ap.parse_args()
    (phase_discover if a.phase == 'discover' else phase_final)(a.tf)
