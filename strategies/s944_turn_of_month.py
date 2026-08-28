#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S944 — رانشِ چرخشِ ماه (Turn-of-the-Month Drift) · XAUUSD · مسیر C
پیش‌ثبت: results/S944_PREREG_TURN_OF_MONTH_DRIFT.md (کامیت f18f9cfe — قبل از این فایل)

رویداد: اولین کندلِ هر روزِ معاملاتی داخل پنجرهٔ TOM
        (آخرین L روزِ ماه + اولین F روزِ ماهِ بعد).
جهت اصلی LONG · آینهٔ SHORT صرفاً کنترل.
هندسه: SL=k×ATR100 (کف 5pip) · TP=SL (RR=1) · hold = h_days×bpd (bpd منجمد از کشف).

زیرساخت شبیه‌ساز/نال/داور عیناً از s940_volatility_birth (راستی‌آزمایی‌شده).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se                       # noqa: E402
from engine import rqs2                                     # noqa: E402
from tools import s434_fast_data as fd                      # noqa: E402
from strategies.s940_volatility_birth import (              # noqa: E402
    atr_geom_pip, run_combo, build_null, SL_FLOOR_PIP)

ASSET = 'XAUUSD'
OUT = 'results/_scan_S944'
SEED = 944
K_PERM = 1000
SPLIT_FRAC = 0.60
MIN_TRADES_DISC = 150

# ---- شبکهٔ منجمدِ پیش‌ثبت (۷۲ ترکیب) ----
GRID_L = [0, 1, 2]
GRID_F = [2, 3, 4]
GRID_KSL = [2.058, 3.141]
GRID_RR = [1.0]
GRID_HOLD_D = [1, 2]
GRID_DIR = ['long', 'short']            # short = آینهٔ کنترل


# ---------------------------------------------------------------- تقویم
def day_index(d):
    """برای هر کندل: شناسهٔ روزِ معاملاتی (تاریخ تقویمی سرور) + فهرست روزها."""
    dt = pd.to_datetime(d['time'], unit='s')
    dates = dt.normalize().values                 # datetime64[ns] per bar
    uniq, first_idx, inv = np.unique(dates, return_index=True,
                                     return_inverse=True)
    return uniq, first_idx, inv, dt


def tom_day_mask(uniq_days, L, F):
    """ماسک روی روزهای معاملاتی: عضو پنجرهٔ TOM؟ (آخرین L روزِ ماه ∪ اولین F روزِ ماه)."""
    months = pd.DatetimeIndex(uniq_days).to_period('M')
    mask = np.zeros(len(uniq_days), dtype=bool)
    codes, starts = np.unique(months.asfreq('M').astype(str),
                              return_index=True)
    order = np.argsort(starts)
    starts_sorted = starts[order]
    bounds = list(starts_sorted) + [len(uniq_days)]
    for bi in range(len(bounds) - 1):
        s, e = bounds[bi], bounds[bi + 1]        # روزهای این ماه: [s, e)
        n_days = e - s
        if F > 0:
            mask[s:s + min(F, n_days)] = True
        if L > 0:
            mask[max(s, e - L):e] = True
    return mask


def build_signals(d, L, F, direction, cache):
    """سیگنال روی اولین کندلِ هر روزِ TOM. cache: خروجی day_index (یک‌بار per slice)."""
    uniq, first_idx, inv, _ = cache
    dmask = tom_day_mask(uniq, L, F)
    sig_bars = first_idx[dmask]
    n = len(d['close'])
    ls = np.zeros(n, dtype=bool)
    ss = np.zeros(n, dtype=bool)
    if direction == 'long':
        ls[sig_bars] = True
    else:
        ss[sig_bars] = True
    return ls, ss


def bars_per_day(cache, n_bars):
    """میانهٔ تعداد کندل per روزِ معاملاتی (روی همان slice — علّی)."""
    uniq, first_idx, inv, _ = cache
    counts = np.bincount(inv)
    return max(1, int(np.median(counts)))


# ---------------------------------------------------------------- فاز کشف
def phase_discover(tf):
    os.makedirs(OUT, exist_ok=True)
    ckpt_fp = os.path.join(OUT, f'discover_{tf}.json')
    done = {}
    if os.path.exists(ckpt_fp):
        with open(ckpt_fp) as f:
            done = json.load(f).get('combos', {})
        print(f'[resume] {len(done)} combos checkpointed', flush=True)

    d = fd.load_fast(ASSET, tf)
    print(f"DATA src={d['src']}  n_bars={d['n_bars']:,}  "
          f"span={d['span_years']}y", flush=True)
    n_all = int(d['n_bars'])
    split = int(n_all * SPLIT_FRAC)
    d1 = {k: (v[:split] if isinstance(v, np.ndarray) else v)
          for k, v in d.items()}
    df1 = fd.as_dataframe(d1)
    atr_g = atr_geom_pip(d1)
    cache = day_index(d1)
    bpd = bars_per_day(cache, split)
    print(f'discovery bars={split:,} · bars/day(median)={bpd}', flush=True)

    t0 = time.time()
    results = dict(done)
    i, n_total = 0, len(GRID_L) * len(GRID_F) * len(GRID_DIR) \
        * len(GRID_KSL) * len(GRID_RR) * len(GRID_HOLD_D)
    for L in GRID_L:
        for F in GRID_F:
            for direction in GRID_DIR:
                ls, ss = build_signals(d1, L, F, direction, cache)
                n_sig = int(ls.sum() + ss.sum())
                for k_sl in GRID_KSL:
                    for rr in GRID_RR:
                        for hd in GRID_HOLD_D:
                            i += 1
                            hold = hd * bpd
                            key = (f'L{L}_F{F}_{direction}'
                                   f'_k{k_sl}_rr{rr}_hd{hd}')
                            if key in results:
                                continue
                            if n_sig < 10:
                                results[key] = dict(n=0)
                            else:
                                r = run_combo(df1, d1, atr_g, ls, ss,
                                              k_sl, rr, hold)
                                results[key] = r if r else dict(n=0)
                            with open(ckpt_fp, 'w') as f:
                                json.dump(dict(tf=tf, split=split,
                                               n_bars=n_all, bpd=bpd,
                                               src=d['src'],
                                               combos=results), f, indent=1)
                            rr_ = results[key]
                            print(f'[{i:2d}/{n_total}] {key:<34} '
                                  f'n={rr_.get("n", 0):>5} '
                                  f'wr={rr_.get("wr", "-")} '
                                  f'lift={rr_.get("lift", "-")} '
                                  f'score={rr_.get("score", "-")} '
                                  f'({time.time() - t0:.0f}s)', flush=True)

    # قفل: بیشینهٔ lift·√n با کف‌های پیش‌ثبت + سدِ توان 78 + فقط LONG اصلی
    # (آینهٔ short کنترل است و طبق پیش‌ثبت نامزد قفل نیست مگر برتریِ فاحش —
    #  برای انضباط: قفل فقط از خانوادهٔ long انتخاب می‌شود؛ نتایج short گزارش می‌شوند.)
    best_key, best_score = None, -1e18
    for key, r in results.items():
        if 'short' in key:                     # آینهٔ کنترل — نامزد قفل نیست
            continue
        if r.get('n', 0) < MIN_TRADES_DISC or r.get('net', -1) <= 0:
            continue
        if r['score'] > best_score:
            best_key, best_score = key, r['score']
    power_ok = best_key is not None and best_score >= 78.0
    locked = dict(layer='S944', tf=tf, split_bar=split, n_bars=n_all,
                  src=d['src'], bpd=bpd,
                  criterion='max lift*sqrt(n) | long-only | n>=150 & net>0 '
                            '& power lift*sqrt(n)>=78',
                  best_key=best_key if power_ok else None,
                  best=results.get(best_key) if power_ok else None,
                  best_unpowered=(dict(key=best_key,
                                       **results.get(best_key))
                                  if (best_key and not power_ok) else None),
                  score=round(best_score, 2) if best_key else None,
                  power_ok=bool(power_ok))
    lock_fp = os.path.join(OUT, f'lock_XAUUSD-{tf}.json')
    with open(lock_fp, 'w') as f:
        json.dump(locked, f, indent=2)
    print(f'\nLOCKED -> {lock_fp}')
    print(json.dumps(locked, indent=2), flush=True)


# ---------------------------------------------------------------- فاز نهایی
def parse_key(key):
    t = key.split('_')
    return dict(L=int(t[0][1:]), F=int(t[1][1:]), direction=t[2],
                k_sl=float(t[3][1:]), rr=float(t[4][2:]), hd=int(t[5][2:]))


def phase_final(tf):
    lock_fp = os.path.join(OUT, f'lock_XAUUSD-{tf}.json')
    with open(lock_fp) as f:
        locked = json.load(f)
    if not locked.get('best_key'):
        print(f'{tf}: NO-CANDIDATE (discovery floor/power unmet) — '
              'holdout stays virgin.', flush=True)
        return
    p = parse_key(locked['best_key'])
    d = fd.load_fast(ASSET, tf)
    assert d['src'] == locked['src'], 'data source changed since lock!'
    assert int(d['n_bars']) == int(locked['n_bars']), 'n_bars changed!'
    split = int(locked['split_bar'])
    n_all = int(d['n_bars'])
    bpd = int(locked['bpd'])                    # منجمد از کشف — بدون بازمحاسبه
    hold = p['hd'] * bpd
    print(f"FINAL ONE-SHOT S944 {tf} · locked={locked['best_key']} · "
          f'holdout=[{split:,},{n_all:,}) · n_trials=1', flush=True)

    df = fd.as_dataframe(d)
    atr_g = atr_geom_pip(d)
    cache = day_index(d)
    ls, ss = build_signals(d, p['L'], p['F'], p['direction'], cache)
    ls[:split] = False
    ss[:split] = False

    sl = np.nan_to_num(np.clip(p['k_sl'] * atr_g, SL_FLOOR_PIP, None),
                       nan=SL_FLOOR_PIP)
    tp = p['rr'] * sl
    tr = se.simulate_trades(df, ls, ss, sl, tp, ASSET,
                            max_hold=hold, allow_overlap=False)
    print(f'holdout trades = {len(tr)}', flush=True)
    if len(tr) == 0:
        print('ZERO trades on holdout — dead for this TF.', flush=True)
        return

    null = build_null(d, ls, ss, sl, p['rr'], hold, split, n_all,
                      K=K_PERM, seed=SEED)
    with open(os.path.join(OUT, f'null_XAUUSD-{tf}.json'), 'w') as f:
        json.dump(null, f, indent=2)

    nested_split = split + int(0.60 * (n_all - split))
    sl_med = float(np.median(tr['sl_pip'].values))
    tp_med = p['rr'] * sl_med
    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=df['time'].values, null=null,
                          n_trials=1, split_bar=nested_split,
                          close=df['close'].values)
    out = dict(layer='S944', tf=tf, locked_key=locked['best_key'],
               src=d['src'], n_bars=n_all, span_years=d['span_years'],
               holdout_from=split, nested_split=nested_split, bpd=bpd,
               hold_bars=hold, n_trades=int(len(tr)),
               sl_med=round(sl_med, 1), tp_med=round(tp_med, 1), n_trials=1,
               verdict=r['verdict'], score=r.get('rqs2_score'),
               gates=r.get('gates'), metrics=r.get('metrics'),
               notes=r.get('notes'))
    with open(os.path.join(OUT, f'final_XAUUSD-{tf}.json'), 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nVERDICT={r['verdict']}  score={r.get('rqs2_score')}")
    print(f"skill_p_perm={r.get('metrics', {}).get('skill_p_perm')}",
          flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', choices=['discover', 'final'], required=True)
    ap.add_argument('--tf', required=True)
    a = ap.parse_args()
    (phase_discover if a.phase == 'discover' else phase_final)(a.tf)
