#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S949 — تولد روند وایلدر (ADX fresh-cross) · XAUUSD · مسیر C
پیش‌ثبت: results/S949_PREREG_WILDER_TREND_BIRTH.md (کامیت d97f858e — قبل از این فایل)

رویداد: عبور تازهٔ ADX از آستانهٔ θ (لبهٔ S526: adx[i]>=θ & adx[i-1]<θ).
جهت با-DI: +DI>−DI → LONG وگرنه SHORT. ضد-DI = آینهٔ کنترل.
هندسه: SL=k×ATR100_geom (کف 5pip) · TP=RR×SL · خروج زمانی hold کندل.

زیرساخت شبیه‌ساز/نال/داور عیناً از s940_volatility_birth (راستی‌آزمایی‌شده).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se                       # noqa: E402
from engine import rqs2                                     # noqa: E402
from tools import s434_fast_data as fd                      # noqa: E402
from strategies.s940_volatility_birth import (              # noqa: E402
    atr_geom_pip, run_combo, build_null, SL_FLOOR_PIP)

ASSET = 'XAUUSD'
OUT = 'results/_scan_S949'
SEED = 949
K_PERM = 1000
SPLIT_FRAC = 0.60
MIN_TRADES_DISC = 150
POWER_GATE = 78.0

# ---- شبکهٔ منجمدِ پیش‌ثبت (۹۶ ترکیب) ----
GRID_P = [14, 34]
GRID_TH = [20.0, 25.0, 30.0]
GRID_DIR = ['withdi', 'antidi']         # antidi = آینهٔ کنترل
GRID_KSL = [2.058, 3.141]
GRID_RR = [1.0, 1.5]
GRID_HOLD = [34, 55]


# ---------------------------------------------------------------- ADX وایلدر
def wilder_smooth(x, p):
    """هموارسازی وایلدر: y[i] = y[i-1] + (x[i]-y[i-1])/p ؛ بذر = میانگین p تای اول."""
    y = np.full(len(x), np.nan)
    if len(x) < p + 1:
        return y
    y[p - 1] = np.nanmean(x[:p])
    a = 1.0 / p
    for i in range(p, len(x)):
        y[i] = y[i - 1] + a * (x[i] - y[i - 1])
    return y


def adx_di(d, p):
    """+DI، −DI و ADX وایلدر استاندارد (دورهٔ p). فقط دادهٔ گذشته."""
    h, l, c = d['high'], d['low'], d['close']
    n = len(c)
    up = np.zeros(n)
    dn = np.zeros(n)
    up[1:] = h[1:] - h[:-1]
    dn[1:] = l[:-1] - l[1:]
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    ndm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = np.zeros(n)
    tr[0] = h[0] - l[0]
    tr[1:] = np.maximum.reduce([h[1:] - l[1:],
                                np.abs(h[1:] - c[:-1]),
                                np.abs(l[1:] - c[:-1])])
    atr = wilder_smooth(tr, p)
    pdi = 100.0 * wilder_smooth(pdm, p) / np.where(atr > 0, atr, np.nan)
    ndi = 100.0 * wilder_smooth(ndm, p) / np.where(atr > 0, atr, np.nan)
    dx = 100.0 * np.abs(pdi - ndi) / np.where(pdi + ndi > 0, pdi + ndi, np.nan)
    dx_clean = np.nan_to_num(dx, nan=0.0)
    adx = wilder_smooth(dx_clean, p)
    # قبل از 2p کندل، ADX معتبر نیست
    adx[:2 * p] = np.nan
    return pdi, ndi, adx


def build_signals(d, p, theta, direction, cache):
    """لبهٔ عبور تازهٔ ADX از θ؛ جهت از DI همان کندل. cache=(pdi,ndi,adx)."""
    pdi, ndi, adx = cache
    n = len(d['close'])
    fresh = np.zeros(n, dtype=bool)
    fresh[1:] = (adx[1:] >= theta) & (adx[:-1] < theta) & ~np.isnan(adx[:-1])
    di_long = pdi > ndi
    ls = np.zeros(n, dtype=bool)
    ss = np.zeros(n, dtype=bool)
    if direction == 'withdi':
        ls[fresh & di_long] = True
        ss[fresh & ~di_long] = True
    else:                                   # آینهٔ کنترل
        ls[fresh & ~di_long] = True
        ss[fresh & di_long] = True
    return ls, ss


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

    t0 = time.time()
    results = dict(done)
    i, n_total = 0, (len(GRID_P) * len(GRID_TH) * len(GRID_DIR)
                     * len(GRID_KSL) * len(GRID_RR) * len(GRID_HOLD))
    for p in GRID_P:
        cache = adx_di(d1, p)
        for theta in GRID_TH:
            for direction in GRID_DIR:
                ls, ss = build_signals(d1, p, theta, direction, cache)
                n_sig = int(ls.sum() + ss.sum())
                for k_sl in GRID_KSL:
                    for rr in GRID_RR:
                        for hold in GRID_HOLD:
                            i += 1
                            key = (f'P{p}_th{int(theta)}_{direction}'
                                   f'_k{k_sl}_rr{rr}_hd{hold}')
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
                                               n_bars=n_all,
                                               src=d['src'],
                                               combos=results), f, indent=1)
                            rr_ = results[key]
                            print(f'[{i:2d}/{n_total}] {key:<36} '
                                  f'n={rr_.get("n", 0):>6} '
                                  f'wr={rr_.get("wr", "-")} '
                                  f'lift={rr_.get("lift", "-")} '
                                  f'score={rr_.get("score", "-")} '
                                  f'({time.time() - t0:.0f}s)', flush=True)

    # قفل: بیشینهٔ lift·√n | فقط with-DI (ضد-DI کنترل) | کف‌ها + سد توان 78
    best_key, best_score = None, -1e18
    for key, r in results.items():
        if 'antidi' in key:
            continue
        if r.get('n', 0) < MIN_TRADES_DISC or r.get('net', -1) <= 0:
            continue
        if r['score'] > best_score:
            best_key, best_score = key, r['score']
    power_ok = best_key is not None and best_score >= POWER_GATE
    locked = dict(layer='S949', tf=tf, split_bar=split, n_bars=n_all,
                  src=d['src'],
                  criterion='max lift*sqrt(n) | withdi-only | n>=150 & net>0 '
                            f'& power lift*sqrt(n)>={POWER_GATE}',
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
    return dict(p=int(t[0][1:]), theta=float(t[1][2:]), direction=t[2],
                k_sl=float(t[3][1:]), rr=float(t[4][2:]), hold=int(t[5][2:]))


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
    hold = p['hold']
    print(f"FINAL ONE-SHOT S949 {tf} · locked={locked['best_key']} · "
          f'holdout=[{split:,},{n_all:,}) · n_trials=1', flush=True)

    df = fd.as_dataframe(d)
    atr_g = atr_geom_pip(d)
    cache = adx_di(d, p['p'])
    ls, ss = build_signals(d, p['p'], p['theta'], p['direction'], cache)
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
    out = dict(layer='S949', tf=tf, locked_key=locked['best_key'],
               src=d['src'], n_bars=n_all, span_years=d['span_years'],
               holdout_from=split, nested_split=nested_split,
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
