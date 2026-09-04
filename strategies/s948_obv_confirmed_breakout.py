# -*- coding: utf-8 -*-
"""S948 — «اکسترممِ تازهٔ قیمت با تأییدِ OBV» (OBV-Confirmed Fresh Extremum Continuation).

پیش‌ثبت: results/S948_PREREG_multiplicity_route.md (کامیت 48389de3، پیش از هر بک‌تستی).

فرضیه (Granville 1963 — اصلِ تأیید): قلهٔ تازهٔ قیمت که OBV هم‌زمان قلهٔ تازهٔ
خود را بزند = حرکتِ با پشتوانهٔ حجمِ جهت‌دار ⇒ continuation. مکملِ منطقیِ S946
(واگرایی⇒فید، REJECT) — بستنِ خانهٔ چهارمِ ماتریسِ ۲×۲ اکسترمم×تأیید.

رویداد LONG:  high[i] ≥ max(high[i−w..i−1]) و OBV[i] ≥ max(OBV[i−w..i−1])
رویداد SHORT: low[i] ≤ min(low[i−w..i−1]) و OBV[i] ≤ min(OBV[i−w..i−1])
خانوادهٔ منجمد: w∈{55,144} (عیناً S946) · n_trials=171 (=19×9 تجمعیِ بلوک S94x)
هندسه/صف/مدلِ صفر عیناً S940..S947 (یک نسخهٔ راستی‌آزمایی‌شده).
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import rqs2 as R                              # noqa: E402
from tools import s434_fast_data as fd                    # noqa: E402
from strategies.s940_ehlers_cycle_turn import (           # noqa: E402
    ASSET, SL_K, RR, SPLIT_FRAC, SEED,
    pip_size, atr_rma, sim_queue, build_null)
from strategies.s946_obv_divergence import (              # noqa: E402
    _obv_nb, _past_max, _past_min)

WINDOWS = (55, 144)
N_TRIALS = 171
WARMUP = 576
OUT = 'results/_s948'


def family_dir(high: np.ndarray, low: np.ndarray, close: np.ndarray,
               vol: np.ndarray) -> np.ndarray:
    """ادغامِ ۲ عضو (OR)؛ اکسترممِ تازهٔ قیمت + تأییدِ هم‌زمانِ OBV ⇒ continuation."""
    n = close.shape[0]
    h = np.ascontiguousarray(high, dtype=np.float64)
    lo = np.ascontiguousarray(low, dtype=np.float64)
    c = np.ascontiguousarray(close, dtype=np.float64)
    v = np.ascontiguousarray(vol, dtype=np.float64)
    obv = _obv_nb(c, v)
    long_any = np.zeros(n, dtype=np.bool_)
    short_any = np.zeros(n, dtype=np.bool_)
    for w in WINDOWS:
        hmax = _past_max(h, w)
        lmin = _past_min(lo, w)
        omax = _past_max(obv, w)
        omin = _past_min(obv, w)
        lg = np.nan_to_num((h >= hmax) & (obv >= omax), nan=False)
        sh = np.nan_to_num((lo <= lmin) & (obv <= omin), nan=False)
        long_any |= lg
        short_any |= sh
    long_any[:WARMUP] = False
    short_any[:WARMUP] = False
    d = np.zeros(n, dtype=np.int8)
    d[long_any & ~short_any] = 1
    d[short_any & ~long_any] = -1
    return d


def verify_indicators(n=4000, seed=29) -> float:
    """OBV و past-extrema (از S946 وارد شده) دوباره مقابل pandas — پیش از دادهٔ واقعی."""
    import pandas as pd
    rng = np.random.default_rng(seed)
    c = 2000.0 + np.cumsum(rng.normal(0, 1.0, n))
    v = np.abs(rng.gamma(2.0, 300.0, n))
    sgn = np.sign(pd.Series(c).diff().fillna(0.0).to_numpy())
    ref_obv = np.cumsum(sgn * v)
    got_obv = _obv_nb(c, v)
    worst = float(np.max(np.abs(ref_obv - got_obv)))
    for w in WINDOWS:
        ref = pd.Series(c).rolling(w).max().shift(1).to_numpy()
        got = _past_max(c, w)
        m = np.isfinite(ref) & np.isfinite(got)
        worst = max(worst, float(np.nanmax(np.abs(ref[m] - got[m]))))
        ref2 = pd.Series(c).rolling(w).min().shift(1).to_numpy()
        got2 = _past_min(c, w)
        m2 = np.isfinite(ref2) & np.isfinite(got2)
        worst = max(worst, float(np.nanmax(np.abs(ref2[m2] - got2[m2]))))
    # آزمونِ مکمل‌بودن: روی دادهٔ مصنوعی، سیگنال‌های S948 و S946 نباید هم‌جهت هم‌کندل باشند
    from strategies.s946_obv_divergence import family_dir as fd946
    h = c + np.abs(rng.normal(0, 0.6, n))
    lo = c - np.abs(rng.normal(0, 0.6, n))
    d948 = family_dir(h, lo, c, v)
    d946 = fd946(h, lo, c, v)
    same_dir = int(np.sum((d948 != 0) & (d948 == d946)))
    print(f'  complementarity: bars where S948 dir == S946 dir = {same_dir} '
          f'(expected 0: confirmation vs divergence are mutually exclusive per w... '
          f'OR-merge may create rare overlaps)')
    return worst


def run_card(tf: str, verbose=True) -> dict:
    os.makedirs(OUT, exist_ok=True)
    d = fd.load_fast(ASSET, tf)
    n_bars = int(d['n_bars'])
    high, low, close = d['high'], d['low'], d['close']
    ps = pip_size(ASSET)

    print(f"\n{'='*84}\n=== S948 ObvConfirmedBreakout :: {ASSET}_{tf}  "
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

    dirs = family_dir(high, low, close, d['volume'])
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
    print(R.format_rqs2(f'S948_ObvConfirmedBreakout_{ASSET}_{tf}', res), flush=True)

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
    if len(sys.argv) > 1 and sys.argv[1] == 'verify':
        w = verify_indicators()
        print(f'OBV+past-extrema worst |Δ| vs pandas = {w:.3e}')
        sys.exit(0 if w < 1e-9 else 1)
    tf = sys.argv[1] if len(sys.argv) > 1 else 'M1'
    run_card(tf)
