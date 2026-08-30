#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S948 — اهرم انتخاب علّی روی رانش آغاز ماه · XAUUSD · مسیر C (ادامهٔ برش S944)
پیش‌ثبت: results/S948_PREREG_TOM_SELECTION_LEVER.md (کامیت c2386eec — قبل از این فایل)

پایه: کارت‌های قفل S944 (L/F/k/hd منجمد؛ RR=1). درجهٔ آزادی جدید: اهرم انتخاب.
- CALM(qv): رد سیگنال اگر vol_ref(روز قبل) > چندک qv رولینگ 250روزهٔ علّی (تعریف S562).
- DRIFT(Wd): پذیرش فقط اگر close(دیروز) − close(Wd روز معاملاتی قبل) > 0.
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
from strategies.s944_turn_of_month import (                 # noqa: E402
    day_index, tom_day_mask, bars_per_day)

ASSET = 'XAUUSD'
OUT = 'results/_scan_S948'
S944_OUT = 'results/_scan_S944'
SEED = 948
K_PERM = 1000
MIN_TRADES_DISC = 150
POWER_BAR = 78.0

# کارت‌های پایهٔ منجمد (عیناً از lock S944 — پیش‌ثبت §2)
BASE_CARDS = {
    'D1':  dict(L=0, F=2, k_sl=3.141, hd=1),
    'H3':  dict(L=0, F=3, k_sl=3.141, hd=1),
    'H12': dict(L=0, F=3, k_sl=3.141, hd=2),
    'H6':  dict(L=0, F=3, k_sl=2.058, hd=2),
    'H2':  dict(L=0, F=2, k_sl=3.141, hd=1),
    'H8':  dict(L=0, F=3, k_sl=3.141, hd=2),
    'H1':  dict(L=0, F=3, k_sl=3.141, hd=2),
}
RR = 1.0
LEVERS = [('calm', 70), ('calm', 78), ('calm', 85),
          ('drift', 8), ('drift', 21), ('drift', 55)]


# --------------------------------------------------------------- سنجه‌های روزانه
def daily_features(d, cache):
    """برای هر روزِ معاملاتی: دامنهٔ (high-low) و آخرین close. علّی در سطح روز."""
    uniq, first_idx, inv, _ = cache
    n_days = len(uniq)
    hi = np.full(n_days, -np.inf)
    lo = np.full(n_days, np.inf)
    np.maximum.at(hi, inv, d['high'])
    np.minimum.at(lo, inv, d['low'])
    rng = hi - lo
    # آخرین close هر روز: چون کندل‌ها مرتب‌اند، آخرین اندیس هر گروه
    last_idx = np.zeros(n_days, dtype=np.int64)
    np.maximum.at(last_idx, inv, np.arange(len(inv)))
    dclose = d['close'][last_idx]
    return rng, dclose


def calm_pass(day_rng, qv):
    """برای روزِ j (روزِ سیگنال): vol_ref = میانگین ۱۴ روزِ کاملِ قبل [j-14, j-1)؛
    آستانه = صدک qv از رولینگ ۲۵۰ مقدارِ قبلیِ vol_ref (min 60). عبوری اگر ≤ آستانه."""
    n = len(day_rng)
    vol_ref = pd.Series(day_rng).rolling(14).mean().shift(1).values  # تا روز j-1
    vr = pd.Series(vol_ref)
    thr = vr.rolling(250, min_periods=60).quantile(qv / 100.0).shift(1).values
    ok = np.zeros(n, dtype=bool)
    valid = ~np.isnan(vol_ref) & ~np.isnan(thr)
    ok[valid] = vol_ref[valid] <= thr[valid]
    return ok


def drift_pass(dclose, wd):
    """عبوری اگر close(روز j-1) − close(روز j-1-wd) > 0."""
    n = len(dclose)
    ok = np.zeros(n, dtype=bool)
    prev = np.roll(dclose, 1)          # close روزِ قبل
    ref = np.roll(dclose, 1 + wd)
    idx = np.arange(n) >= (1 + wd)
    ok[idx] = (prev[idx] - ref[idx]) > 0
    return ok


def build_signals_levered(d, cache, base, lever, param):
    uniq, first_idx, inv, _ = cache
    dmask = tom_day_mask(uniq, base['L'], base['F'])
    day_rng, dclose = daily_features(d, cache)
    if lever == 'calm':
        lever_ok = calm_pass(day_rng, param)
    else:
        lever_ok = drift_pass(dclose, param)
    sel_days = dmask & lever_ok
    sig_bars = first_idx[sel_days]
    n = len(d['close'])
    ls = np.zeros(n, dtype=bool)
    ls[sig_bars] = True
    ss = np.zeros(n, dtype=bool)
    return ls, ss


# --------------------------------------------------------------- فاز کشف
def phase_discover(tf):
    os.makedirs(OUT, exist_ok=True)
    base = BASE_CARDS[tf]
    with open(os.path.join(S944_OUT, f'lock_XAUUSD-{tf}.json')) as f:
        l944 = json.load(f)
    d = fd.load_fast(ASSET, tf)
    assert d['src'] == l944['src'], 'src mismatch vs S944 lock!'
    assert int(d['n_bars']) == int(l944['n_bars']), 'n_bars mismatch!'
    split = int(l944['split_bar'])
    bpd = int(l944['bpd'])
    hold = base['hd'] * bpd
    print(f"DATA src={d['src']} n_bars={d['n_bars']:,} split={split:,} "
          f'bpd={bpd} hold={hold}', flush=True)

    d1 = {k: (v[:split] if isinstance(v, np.ndarray) else v)
          for k, v in d.items()}
    df1 = fd.as_dataframe(d1)
    atr_g = atr_geom_pip(d1)
    cache = day_index(d1)

    results = {}
    t0 = time.time()
    for lever, param in LEVERS:
        ls, ss = build_signals_levered(d1, cache, base, lever, param)
        key = f'{lever}{param}'
        if ls.sum() < 10:
            results[key] = dict(n=0)
        else:
            r = run_combo(df1, d1, atr_g, ls, ss, base['k_sl'], RR, hold)
            results[key] = r if r else dict(n=0)
        rr_ = results[key]
        print(f'{tf} {key:<9} n={rr_.get("n", 0):>5} wr={rr_.get("wr", "-")} '
              f'lift={rr_.get("lift", "-")} score={rr_.get("score", "-")} '
              f'({time.time() - t0:.0f}s)', flush=True)

    ckpt = dict(tf=tf, base=base, split=split, n_bars=int(d['n_bars']),
                bpd=bpd, src=d['src'], combos=results)
    with open(os.path.join(OUT, f'discover_{tf}.json'), 'w') as f:
        json.dump(ckpt, f, indent=1)

    best_key, best_score = None, -1e18
    for key, r in results.items():
        if r.get('n', 0) < MIN_TRADES_DISC or r.get('net', -1) <= 0:
            continue
        if r['score'] > best_score:
            best_key, best_score = key, r['score']
    power_ok = best_key is not None and best_score >= POWER_BAR
    locked = dict(layer='S948', tf=tf, base=base, rr=RR, split_bar=split,
                  n_bars=int(d['n_bars']), bpd=bpd, src=d['src'],
                  criterion=f'max lift*sqrt(n) | n>=150 & net>0 & '
                            f'power>={POWER_BAR}',
                  best_key=best_key if power_ok else None,
                  best=results.get(best_key) if power_ok else None,
                  best_unpowered=(dict(key=best_key, **results[best_key])
                                  if (best_key and not power_ok) else None),
                  score=round(best_score, 2) if best_key else None,
                  power_ok=bool(power_ok))
    with open(os.path.join(OUT, f'lock_XAUUSD-{tf}.json'), 'w') as f:
        json.dump(locked, f, indent=2)
    print(json.dumps(locked, indent=2), flush=True)


# --------------------------------------------------------------- فاز نهایی
def phase_final(tf):
    with open(os.path.join(OUT, f'lock_XAUUSD-{tf}.json')) as f:
        locked = json.load(f)
    if not locked.get('best_key'):
        print(f'{tf}: NO-CANDIDATE — holdout stays virgin.', flush=True)
        return
    base = locked['base']
    key = locked['best_key']
    lever = 'calm' if key.startswith('calm') else 'drift'
    param = int(key.replace(lever, ''))
    d = fd.load_fast(ASSET, tf)
    assert d['src'] == locked['src'] and int(d['n_bars']) == locked['n_bars']
    split = int(locked['split_bar'])
    n_all = int(d['n_bars'])
    hold = base['hd'] * int(locked['bpd'])
    print(f'FINAL ONE-SHOT S948 {tf} · {key} · holdout=[{split:,},{n_all:,}) '
          f'· n_trials=1', flush=True)

    df = fd.as_dataframe(d)
    atr_g = atr_geom_pip(d)
    cache = day_index(d)
    ls, ss = build_signals_levered(d, cache, base, lever, param)
    ls[:split] = False
    ss[:split] = False
    sl = np.nan_to_num(np.clip(base['k_sl'] * atr_g, SL_FLOOR_PIP, None),
                       nan=SL_FLOOR_PIP)
    tp = RR * sl
    tr = se.simulate_trades(df, ls, ss, sl, tp, ASSET,
                            max_hold=hold, allow_overlap=False)
    print(f'holdout trades = {len(tr)}', flush=True)
    if len(tr) == 0:
        print('ZERO trades on holdout — dead.', flush=True)
        return
    null = build_null(d, ls, ss, sl, RR, hold, split, n_all,
                      K=K_PERM, seed=SEED)
    with open(os.path.join(OUT, f'null_XAUUSD-{tf}.json'), 'w') as f:
        json.dump(null, f, indent=2)
    nested_split = split + int(0.60 * (n_all - split))
    sl_med = float(np.median(tr['sl_pip'].values))
    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=RR * sl_med,
                          bar_time=df['time'].values, null=null,
                          n_trials=1, split_bar=nested_split,
                          close=df['close'].values)
    out = dict(layer='S948', tf=tf, locked_key=key, base=base,
               src=d['src'], n_bars=n_all, holdout_from=split,
               nested_split=nested_split, hold_bars=hold,
               n_trades=int(len(tr)), sl_med=round(sl_med, 1),
               n_trials=1, verdict=r['verdict'], score=r.get('rqs2_score'),
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
