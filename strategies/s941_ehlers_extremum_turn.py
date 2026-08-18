# -*- coding: utf-8 -*-
"""S941 — «چرخش در اکسترممِ آشکارسازِ اِلرز» — خانوادهٔ پیش‌ثبت‌شده.

پیش‌ثبت: results/S941_PREREG_multiplicity_route.md (پیش از هر بک‌تستی).

نسبت با S940: تشخیصِ ساختاریِ S940 گفت زیرو-کراس «وسطِ راهِ» چرخه است،
نه نقطهٔ چرخش. اینجا رویداد = اکسترممِ **علّی** آشکارساز:
  قله:  x[i−2] < x[i−1] > x[i]  و  x[i−1] ≥ +1.0   ⇒ short در i
  دره:  x[i−2] > x[i−1] < x[i]  و  x[i−1] ≤ −1.0   ⇒ long در i
آستانهٔ ۱.۰ = یک RMS، واحدِ طبیعیِ نرمال‌سازیِ خودِ اندیکاتور (ثابتِ
ساختاری، نه پارامترِ فیت‌شده).

**بازمصرفِ کاملِ زیرساختِ راستی‌آزمایی‌شدهٔ S940** (اندیکاتورِ numba با
برابریِ 1.6e-12 با بانک؛ شبیه‌سازِ صف با هم‌ارزیِ بیت‌به‌بیت با S382؛
مدلِ صفرِ دوخطی) — یک نسخهٔ واحد، نه دو نسخهٔ ناهمگام.

خانواده و هندسه عیناً S940: {reflex,trendflex}×{21,34,55}، SL=1.5×ATR(100)،
RR=1.5، صفِ تک‌معامله، اولویتِ SL. n_trials=38 (۱۹ کارتِ S940 + ۱۹ اینجا).
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import rqs2 as R                              # noqa: E402
from tools import s434_fast_data as fd                    # noqa: E402
from strategies.s940_ehlers_cycle_turn import (           # noqa: E402
    ASSET, DETECTORS, PERIODS, ATR_P, SL_K, RR, SPLIT_FRAC, SEED, WARMUP,
    pip_size, _flex_nb, atr_rma, sim_queue, build_null)

N_TRIALS = 38          # صادقانه: ۱۹ کارتِ S940 (پرداخت‌شده) + ۱۹ کارتِ S941
X_MIN = 1.0            # یک RMS — ثابتِ ساختاریِ prereg
OUT = 'results/_s941'


def family_dir(close: np.ndarray) -> np.ndarray:
    """رویدادِ اکسترممِ علّی — ادغامِ ۶ عضو؛ تعارض ⇒ ۰ (عیناً قاعدهٔ S940)."""
    n = close.shape[0]
    long_any = np.zeros(n, dtype=np.bool_)
    short_any = np.zeros(n, dtype=np.bool_)
    for det in DETECTORS:
        trend = det == 'trendflex'
        for p in PERIODS:
            x = _flex_nb(close, p, trend)
            x2 = np.empty(n); x2[:2] = np.nan; x2[2:] = x[:-2]   # x[i-2]
            x1 = np.empty(n); x1[:1] = np.nan; x1[1:] = x[:-1]   # x[i-1]
            peak = (x2 < x1) & (x1 > x) & (x1 >= X_MIN)
            trough = (x2 > x1) & (x1 < x) & (x1 <= -X_MIN)
            short_any |= np.nan_to_num(peak)
            long_any |= np.nan_to_num(trough)
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
    high, low, close = d['high'], d['low'], d['close']
    ps = pip_size(ASSET)

    print(f"\n{'='*84}\n=== S941 EhlersExtremumTurn :: {ASSET}_{tf}  "
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

    dirs = family_dir(close)
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
    print(R.format_rqs2(f'S941_EhlersExtremumTurn_{ASSET}_{tf}', res), flush=True)

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
