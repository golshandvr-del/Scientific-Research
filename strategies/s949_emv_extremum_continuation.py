# -*- coding: utf-8 -*-
"""S949 — «اکسترممِ تازهٔ سهولتِ حرکت» (EMV Fresh-Extremum Continuation).

پیش‌ثبت: results/S949_PREREG_multiplicity_route.md (کامیت 6ddbc080، پیش از هر بک‌تستی).

فرضیه (Arms 1971): وقتی Ease-of-Movement هموارشده به اکسترممِ تازهٔ پنجرهٔ گذشته
می‌رسد، حرکت در مسیرِ کم‌مقاومت جریان یافته ⇒ ادامه در همان جهت.

رویداد LONG:  EMV14[i] ≥ max(EMV14[i−w..i−1]) و EMV14[i] > 0
رویداد SHORT: EMV14[i] ≤ min(EMV14[i−w..i−1]) و EMV14[i] < 0
خانوادهٔ منجمد: w∈{55,144} · EMV_P=14 ثابت (استانداردِ بانک) ·
n_trials=190 (=19×10 تجمعیِ کاملِ بلوک S940–S949).
هندسه/صف/مدلِ صفر عیناً S940..S948 (یک نسخهٔ راستی‌آزمایی‌شده).
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
from numba import njit

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import rqs2 as R                              # noqa: E402
from tools import s434_fast_data as fd                    # noqa: E402
from strategies.s940_ehlers_cycle_turn import (           # noqa: E402
    ASSET, SL_K, RR, SPLIT_FRAC, SEED,
    pip_size, atr_rma, sim_queue, build_null)
from strategies.s946_obv_divergence import (              # noqa: E402
    _past_max, _past_min)

WINDOWS = (55, 144)
EMV_P = 14
N_TRIALS = 190
WARMUP = 576
OUT = 'results/_s949'


@njit(cache=True)
def _emv_nb(high, low, close, vol, p):
    """پورتِ دقیقِ engine/indicator_bank.py::emv:
    mid_diff = Δ((H+L)/2); box = (vol/1e6)/(H−L); raw = mid_diff/box (0 اگر تعریف‌نشده);
    خروجی SMA(p) از raw (NaN برای p−1 بارِ اول، مطابقِ pandas rolling)."""
    n = high.shape[0]
    raw = np.zeros(n)
    for i in range(1, n):
        rng_ = high[i] - low[i]
        if rng_ == 0.0:
            raw[i] = 0.0
            continue
        box = (vol[i] / 1e6) / rng_
        if box == 0.0:
            raw[i] = 0.0
            continue
        mid_d = (high[i] + low[i]) * 0.5 - (high[i - 1] + low[i - 1]) * 0.5
        raw[i] = mid_d / box
    out = np.full(n, np.nan)
    s = 0.0
    for i in range(n):
        s += raw[i]
        if i >= p:
            s -= raw[i - p]
        if i >= p - 1:
            out[i] = s / p
    return out


def family_dir(high: np.ndarray, low: np.ndarray, close: np.ndarray,
               vol: np.ndarray) -> np.ndarray:
    """ادغامِ ۲ عضو (OR)؛ اکسترممِ تازهٔ EMV با علامتِ هم‌جهت ⇒ continuation."""
    n = close.shape[0]
    h = np.ascontiguousarray(high, dtype=np.float64)
    lo = np.ascontiguousarray(low, dtype=np.float64)
    c = np.ascontiguousarray(close, dtype=np.float64)
    v = np.ascontiguousarray(vol, dtype=np.float64)
    emv = _emv_nb(h, lo, c, v, EMV_P)
    emv_f = np.nan_to_num(emv, nan=0.0)   # فقط برای مقایسه؛ NaN در past-window خودش نامعتبر می‌ماند
    long_any = np.zeros(n, dtype=np.bool_)
    short_any = np.zeros(n, dtype=np.bool_)
    for w in WINDOWS:
        pmax = _past_max(emv_f, w)
        pmin = _past_min(emv_f, w)
        with np.errstate(invalid='ignore'):
            lg = (emv_f >= pmax) & (emv_f > 0.0)
            sh = (emv_f <= pmin) & (emv_f < 0.0)
        long_any |= np.nan_to_num(lg, nan=False)
        short_any |= np.nan_to_num(sh, nan=False)
    long_any[:WARMUP] = False
    short_any[:WARMUP] = False
    d = np.zeros(n, dtype=np.int8)
    d[long_any & ~short_any] = 1
    d[short_any & ~long_any] = -1
    return d


def verify_indicators(n=4000, seed=31) -> float:
    """پورتِ numbaی EMV مقابلِ engine/indicator_bank.py::emv + past-extrema مقابلِ pandas.
    باید < 1e-9 باشد پیش از هر تماسی با دادهٔ واقعی."""
    import pandas as pd
    from engine.indicator_bank import emv as bank_emv
    rng = np.random.default_rng(seed)
    c = 2000.0 + np.cumsum(rng.normal(0, 1.0, n))
    h = c + np.abs(rng.normal(0, 0.6, n))
    lo = c - np.abs(rng.normal(0, 0.6, n))
    v = np.abs(rng.gamma(2.0, 300.0, n))
    # چند کندلِ range=0 و volume=0 برای آزمونِ شاخه‌های لبه‌ای
    z = rng.choice(n, 25, replace=False)
    h[z] = lo[z] = c[z]
    v[rng.choice(n, 25, replace=False)] = 0.0
    df = pd.DataFrame(dict(open=c, high=h, low=lo, close=c, volume=v))
    ref = bank_emv(df, EMV_P).to_numpy()
    got = _emv_nb(h, lo, c, v, EMV_P)
    m = np.isfinite(ref) & np.isfinite(got)
    assert np.array_equal(np.isfinite(ref), np.isfinite(got)), 'NaN pattern mismatch'
    worst = float(np.max(np.abs(ref[m] - got[m])))
    e = np.nan_to_num(got, nan=0.0)
    for w in WINDOWS:
        r1 = pd.Series(e).rolling(w).max().shift(1).to_numpy(); g1 = _past_max(e, w)
        m1 = np.isfinite(r1) & np.isfinite(g1)
        worst = max(worst, float(np.nanmax(np.abs(r1[m1] - g1[m1]))))
        r2 = pd.Series(e).rolling(w).min().shift(1).to_numpy(); g2 = _past_min(e, w)
        m2 = np.isfinite(r2) & np.isfinite(g2)
        worst = max(worst, float(np.nanmax(np.abs(r2[m2] - g2[m2]))))
    d = family_dir(h, lo, c, v)
    print(f'  synthetic events: long={int((d==1).sum())} short={int((d==-1).sum())} '
          f'(sign-gate sanity: long EMV>0 all={bool(np.all(e[d==1] > 0))}, '
          f'short EMV<0 all={bool(np.all(e[d==-1] < 0))})')
    return worst


def run_card(tf: str, verbose=True) -> dict:
    os.makedirs(OUT, exist_ok=True)
    d = fd.load_fast(ASSET, tf)
    n_bars = int(d['n_bars'])
    high, low, close = d['high'], d['low'], d['close']
    ps = pip_size(ASSET)

    print(f"\n{'='*84}\n=== S949 EmvExtremumContinuation :: {ASSET}_{tf}  "
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
    print(R.format_rqs2(f'S949_EmvExtremumContinuation_{ASSET}_{tf}', res), flush=True)

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
        print(f'EMV+past-extrema worst |Δ| vs bank/pandas = {w:.3e}')
        sys.exit(0 if w < 1e-9 else 1)
    tf = sys.argv[1] if len(sys.argv) > 1 else 'M1'
    run_card(tf)
