# -*- coding: utf-8 -*-
"""S942 — «ادامهٔ حرکت پس از جهشِ حجم» (Volume-Surge Continuation).

پیش‌ثبت: results/S942_PREREG_multiplicity_route.md (پیش از هر بک‌تستی).

فرضیه (Clark 1973؛ Easley–O'Hara PIN): جهشِ ناگهانیِ حجم = ورودِ اطلاعِ
تازه؛ قیمت هنوز کامل جذب نکرده ⇒ ادامه در جهتِ کندلِ جهش.

خانوادهٔ منجمد (۴ عضو): w∈{55,144} × thr∈{1.618, 2.618}
رویداد: عبورِ vz از آستانه به بالا (cross) ⇒ ورود در closeِ همان کندل،
جهت = علامتِ بدنهٔ کندلِ جهش (دوجی ⇒ هیچ).
هندسه/صف/مدلِ صفر عیناً S940/S941 (زیرساختِ راستی‌آزمایی‌شده — یک نسخه).
n_trials = 57 (۱۹×۳ کارزارِ S940/S941/S942).
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd
from numba import njit

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import rqs2 as R                              # noqa: E402
from tools import s434_fast_data as fd                    # noqa: E402
from strategies.s940_ehlers_cycle_turn import (           # noqa: E402
    ASSET, ATR_P, SL_K, RR, SPLIT_FRAC, SEED,
    pip_size, atr_rma, sim_queue, build_null)

WINDOWS = (55, 144)              # فیبوناچی
THRESHOLDS = (1.618, 2.618)      # φ و φ² — غیررند
N_TRIALS = 57
WARMUP = max(4 * max(WINDOWS), 250)   # 576
OUT = 'results/_s942'


@njit(cache=True)
def _vz_nb(vol, w):
    """z-scoreِ حجم نسبت به پنجرهٔ گذشته (فقط گذشته — بدونِ نگاهِ پیش‌رس).

    میانگین/انحرافِ پنجرهٔ [i−w, i−1] با جمعِ غلتان O(n).
    """
    n = vol.shape[0]
    out = np.full(n, np.nan)
    s = 0.0
    s2 = 0.0
    for i in range(n):
        if i >= w:
            mean = s / w
            var = s2 / w - mean * mean
            if var > 1e-12:
                out[i] = (vol[i] - mean) / np.sqrt(var)
        # به‌روزرسانیِ پنجره برای گامِ بعد: s باید sum(vol[i−w..i−1]) بماند
        s += vol[i]
        s2 += vol[i] * vol[i]
        if i >= w:
            s -= vol[i - w]
            s2 -= vol[i - w] * vol[i - w]
    return out


def family_dir(opens: np.ndarray, close: np.ndarray,
               vol: np.ndarray) -> np.ndarray:
    """ادغامِ ۴ عضو؛ رویداد = cross بالای آستانه؛ جهت = بدنهٔ کندل؛ تعارض⇒۰."""
    n = close.shape[0]
    long_any = np.zeros(n, dtype=np.bool_)
    short_any = np.zeros(n, dtype=np.bool_)
    body = close - opens
    for w in WINDOWS:
        vz = _vz_nb(vol.astype(np.float64), w)
        prev = np.empty(n)
        prev[0] = np.nan
        prev[1:] = vz[:-1]
        for thr in THRESHOLDS:
            cross = np.nan_to_num(
                (prev <= thr) & (vz > thr), nan=False)
            long_any |= cross & (body > 0)
            short_any |= cross & (body < 0)
    long_any[:WARMUP] = False
    short_any[:WARMUP] = False
    d = np.zeros(n, dtype=np.int8)
    d[long_any & ~short_any] = 1
    d[short_any & ~long_any] = -1
    return d


def run_card(tf: str, verbose=True) -> dict:
    os.makedirs(OUT, exist_ok=True)
    d = fd.load_fast(ASSET, tf)
    n_bars = int(d['n_bars'])
    high, low, close, opens = d['high'], d['low'], d['close'], d['open']
    ps = pip_size(ASSET)

    print(f"\n{'='*84}\n=== S942 VolumeSurgeCont :: {ASSET}_{tf}  "
          f"bars={n_bars:,}  span={d['span_years']}y\n"
          f"    src={d['src']}  ({d['first_utc']} → {d['last_utc']})", flush=True)

    if n_bars < WARMUP + 200:
        out = dict(card=f'{ASSET}_{tf}', verdict='TOO_SHORT', bars=n_bars)
        _save(tf, out)
        return out

    atr = atr_rma(high, low, close)
    sl_abs = float(np.nanmedian(atr)) * SL_K
    sl_pip = sl_abs / ps
    tp_pip = sl_pip * RR
    print(f'    geom: SL={sl_pip:.2f}pip  TP={tp_pip:.2f}pip  rr={RR}', flush=True)

    dirs = family_dir(opens, close, d['volume'])
    nL_sig = int((dirs == 1).sum()); nS_sig = int((dirs == -1).sum())
    print(f'    family events: long={nL_sig:,}  short={nS_sig:,}', flush=True)

    tr = sim_queue(high, low, close, dirs, sl_abs, ps)
    if len(tr) < 5:
        out = dict(card=f'{ASSET}_{tf}', verdict='NO_TRADES', bars=n_bars,
                   n_trades=int(len(tr)))
        _save(tf, out)
        return out
    nL = int((tr['direction'] == 'long').sum())
    nS = int((tr['direction'] == 'short').sum())
    wr = 100.0 * float((tr['outcome'] == 'win').mean())
    print(f'    trades={len(tr):,} (L={nL:,} S={nS:,})  wr={wr:.2f}%', flush=True)

    k_perm = 500 if n_bars > 1_500_000 else 1000
    strides = (7, 21) if n_bars > 1_000_000 else (3, 7, 13)
    rng = np.random.default_rng(SEED)
    print(f'    building null: K={k_perm}  strides={strides}  seed={SEED}', flush=True)
    null = build_null(high, low, close, sl_abs, nL, nS, n_bars,
                      k_perm, strides, rng, verbose=verbose)

    split_bar = int(SPLIT_FRAC * n_bars)
    res = R.compute_rqs2(tr, ASSET, sl_pip=sl_pip, tp_pip=tp_pip,
                         bar_time=d['time'], close=close, null=null,
                         n_trials=N_TRIALS, split_bar=split_bar)
    print()
    print(R.format_rqs2(f'S942_VolumeSurgeCont_{ASSET}_{tf}', res), flush=True)

    payload = dict(card=f'{ASSET}_{tf}', src=d['src'],
                   first_utc=d['first_utc'], last_utc=d['last_utc'],
                   span_years=d['span_years'], bars=n_bars,
                   sl_pip=sl_pip, tp_pip=tp_pip, rr=RR,
                   events_long=nL_sig, events_short=nS_sig,
                   n_trades=int(len(tr)), n_long=nL, n_short=nS, wr=wr,
                   null=null, k_perm=k_perm, seed=SEED, rqs2=res)
    _save(tf, payload)
    tr.to_csv(f'{OUT}/{ASSET}_{tf}_trades.csv', index=False)
    return payload


def _save(tf, obj):
    os.makedirs(OUT, exist_ok=True)
    with open(f'{OUT}/{ASSET}_{tf}_rqs2.json', 'w') as f:
        json.dump(obj, f, ensure_ascii=False, default=str)


if __name__ == '__main__':
    tf = sys.argv[1] if len(sys.argv) > 1 else 'M1'
    run_card(tf)
