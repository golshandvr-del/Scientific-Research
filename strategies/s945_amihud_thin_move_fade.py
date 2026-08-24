# -*- coding: utf-8 -*-
"""S945 — «فیدِ حرکتِ بی‌پشتوانه» (Amihud Thin-Volume Move Fade).

پیش‌ثبت: results/S945_PREREG_multiplicity_route.md (کامیت 8c6dca59، پیش از هر بک‌تستی).

فرضیه (Amihud 2002؛ Kyle 1985): بدنهٔ بیشینهٔ پنجره روی حجمِ زیرِ میانه =
حرکتِ قیمت بدونِ مشارکتِ جریانِ سفارش ⇒ شکننده ⇒ فید (برگشتِ میانگین).

رویدادِ آناتومیک (درسِ S882): بدونِ آستانهٔ توزیعیِ منجمد —
|body| = max(پنجرهٔ w) و vol < median(حجمِ w کندلِ قبلی).
خانوادهٔ منجمد (۲ عضو): w∈{55,144} · n_trials=114 (=19×6 تجمعیِ بلوک S94x)
هندسه/صف/مدلِ صفر عیناً S940..S944 (زیرساختِ راستی‌آزمایی‌شده — یک نسخه).
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

WINDOWS = (55, 144)
N_TRIALS = 114
WARMUP = 576
OUT = 'results/_s945'


@njit(cache=True)
def _rollmax_nb(x, w):
    """بیشینهٔ پنجرهٔ [i-w+1..i] با دِکِ یکنوا — O(n)، فقط گذشته+حال."""
    n = x.shape[0]
    out = np.full(n, np.nan)
    idx = np.empty(n, dtype=np.int64)
    head = 0
    tail = 0
    for i in range(n):
        while tail > head and x[idx[tail - 1]] <= x[i]:
            tail -= 1
        idx[tail] = i
        tail += 1
        while idx[head] <= i - w:
            head += 1
        if i >= w - 1:
            out[i] = x[idx[head]]
    return out


@njit(cache=True)
def _rollmedian_past_nb(x, w):
    """میانهٔ پنجرهٔ «گذشته‌نگرِ خالص» [i-w..i-1] — درجِ مرتب O(n·w) ساده.

    برای w≤144 و n≤5M قابلِ‌قبول است (~کندتر از دِک ولی درست و شفاف).
    """
    n = x.shape[0]
    out = np.full(n, np.nan)
    buf = np.empty(w)         # پنجرهٔ مرتب‌شده
    m = 0
    for i in range(n):
        if m == w:
            # میانه از بافرِ مرتب (پنجرهٔ [i-w..i-1])
            if w % 2 == 1:
                out[i] = buf[w // 2]
            else:
                out[i] = 0.5 * (buf[w // 2 - 1] + buf[w // 2])
        # حذفِ x[i-w] (که از پنجرهٔ گامِ بعد خارج می‌شود)
        if i >= w:
            old = x[i - w]
            # جست‌وجوی دودویی برای old
            lo, hi = 0, m
            while lo < hi:
                mid = (lo + hi) // 2
                if buf[mid] < old:
                    lo = mid + 1
                else:
                    hi = mid
            # شیفت به چپ
            for j in range(lo, m - 1):
                buf[j] = buf[j + 1]
            m -= 1
        # درجِ x[i]
        v = x[i]
        lo, hi = 0, m
        while lo < hi:
            mid = (lo + hi) // 2
            if buf[mid] < v:
                lo = mid + 1
            else:
                hi = mid
        for j in range(m, lo, -1):
            buf[j] = buf[j - 1]
        buf[lo] = v
        m += 1
    return out


def family_dir(opens: np.ndarray, close: np.ndarray,
               vol: np.ndarray) -> np.ndarray:
    """ادغامِ ۲ عضو (OR)؛ رویداد = بدنهٔ بیشینه + حجمِ زیرِ میانهٔ گذشته؛ جهت=فید."""
    n = close.shape[0]
    body = close - opens
    ab = np.abs(body)
    v = vol.astype(np.float64)
    long_any = np.zeros(n, dtype=np.bool_)
    short_any = np.zeros(n, dtype=np.bool_)
    for w in WINDOWS:
        bmax = _rollmax_nb(ab, w)
        vmed = _rollmedian_past_nb(v, w)
        ev = np.nan_to_num((ab >= bmax) & (ab > 0) & (v < vmed), nan=False)
        short_any |= ev & (body > 0)   # فید: صعودی ⇒ SHORT
        long_any |= ev & (body < 0)    # فید: نزولی ⇒ LONG
    long_any[:WARMUP] = False
    short_any[:WARMUP] = False
    d = np.zeros(n, dtype=np.int8)
    d[long_any & ~short_any] = 1
    d[short_any & ~long_any] = -1
    return d


def verify_indicators(n=4000, seed=13) -> float:
    """برابریِ rollmax و rollmedian_past با pandas — پیش از دادهٔ واقعی."""
    import pandas as pd
    rng = np.random.default_rng(seed)
    x = np.abs(rng.gamma(2.0, 300.0, n))
    worst = 0.0
    for w in WINDOWS:
        ref = pd.Series(x).rolling(w).max().to_numpy()
        got = _rollmax_nb(x, w)
        m = np.isfinite(ref)
        worst = max(worst, float(np.nanmax(np.abs(ref[m] - got[m]))))
        ref2 = pd.Series(x).rolling(w).median().shift(1).to_numpy()
        got2 = _rollmedian_past_nb(x, w)
        m2 = np.isfinite(ref2) & np.isfinite(got2)
        worst = max(worst, float(np.nanmax(np.abs(ref2[m2] - got2[m2]))))
    return worst


def run_card(tf: str, verbose=True) -> dict:
    os.makedirs(OUT, exist_ok=True)
    d = fd.load_fast(ASSET, tf)
    n_bars = int(d['n_bars'])
    high, low, close, opens = d['high'], d['low'], d['close'], d['open']
    ps = pip_size(ASSET)

    print(f"\n{'='*84}\n=== S945 AmihudThinMoveFade :: {ASSET}_{tf}  "
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
    print(R.format_rqs2(f'S945_AmihudThinMoveFade_{ASSET}_{tf}', res), flush=True)

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
        print(f'rollmax+rollmedian worst |Δ| vs pandas = {w:.3e}')
        sys.exit(0 if w < 1e-9 else 1)
    tf = sys.argv[1] if len(sys.argv) > 1 else 'M1'
    run_card(tf)
