# -*- coding: utf-8 -*-
"""S944 — «خشکیِ حجم در pullback» (Wyckoff No-Supply / No-Demand).

پیش‌ثبت: results/S944_PREREG_multiplicity_route.md (کامیت 6fd49eae، پیش از هر بک‌تستی).

فرضیه (Wyckoff 1931؛ Easley–O'Hara): در روندِ صعودی، کندلِ اصلاحیِ نزولی با
کمینهٔ حجمِ پنجرهٔ اخیر = غیابِ فروشندهٔ مطلع ⇒ ادامهٔ روند. آینه‌ای برای شورت.

سنتزِ درس‌ها: لنگرِ خارجی EMA233 (S883/S425)، رویدادِ آناتومیکِ window-min نه
z-score (S882)، ورودِ pullback پادزهرِ H10 (S852)، دوریِ از تایمینگِ جهشِ حجم (S943).

خانوادهٔ منجمد (۲ عضو): w∈{21,55} · n_trials=95 (=19×5 تجمعیِ بلوکِ S94x)
هندسه/صف/مدلِ صفر عیناً S940..S943 (زیرساختِ راستی‌آزمایی‌شده — یک نسخه).
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

WINDOWS = (21, 55)     # پنجره‌های کمینهٔ حجم (فیبوناچی)
EMA_P = 233            # لنگرِ روند
N_TRIALS = 95
WARMUP = 1000
OUT = 'results/_s944'


@njit(cache=True)
def _ema_nb(x, p):
    n = x.shape[0]
    out = np.empty(n)
    a = 2.0 / (p + 1.0)
    out[0] = x[0]
    for i in range(1, n):
        out[i] = a * x[i] + (1.0 - a) * out[i - 1]
    return out


@njit(cache=True)
def _rollmin_nb(x, w):
    """کمینهٔ پنجرهٔ [i-w+1..i] با دِکِ یکنوا — O(n)، فقط گذشته+حال."""
    n = x.shape[0]
    out = np.full(n, np.nan)
    idx = np.empty(n, dtype=np.int64)   # deque of indices (increasing values)
    head = 0
    tail = 0                            # [head, tail)
    for i in range(n):
        # حذفِ عناصرِ بزرگ‌تر-مساوی از انتها (کمینهٔ سخت‌گیرانه: > نگه می‌داریم)
        while tail > head and x[idx[tail - 1]] >= x[i]:
            tail -= 1
        idx[tail] = i
        tail += 1
        # حذفِ عناصرِ خارج از پنجره از ابتدا
        while idx[head] <= i - w:
            head += 1
        if i >= w - 1:
            out[i] = x[idx[head]]
    return out


def family_dir(opens: np.ndarray, close: np.ndarray,
               vol: np.ndarray) -> np.ndarray:
    """ادغامِ ۲ عضو (OR)؛ رویداد = کمینهٔ حجمِ پنجره روی کندلِ اصلاحی در جهتِ روند."""
    n = close.shape[0]
    ema = _ema_nb(close.astype(np.float64), EMA_P)
    body = close - opens
    up_trend = close > ema
    dn_trend = close < ema
    v = vol.astype(np.float64)
    long_any = np.zeros(n, dtype=np.bool_)
    short_any = np.zeros(n, dtype=np.bool_)
    for w in WINDOWS:
        rmin = _rollmin_nb(v, w)
        is_min = np.nan_to_num(v <= rmin, nan=False)   # کندلِ فعلی = کمینهٔ پنجره
        long_any |= is_min & up_trend & (body < 0)     # no-supply در روندِ صعودی
        short_any |= is_min & dn_trend & (body > 0)    # no-demand در روندِ نزولی
    long_any[:WARMUP] = False
    short_any[:WARMUP] = False
    d = np.zeros(n, dtype=np.int8)
    d[long_any & ~short_any] = 1
    d[short_any & ~long_any] = -1
    return d


def verify_rollmin(n=5000, seed=11) -> float:
    """برابریِ عددی _rollmin_nb با pandas.rolling(min) — پیش از دادهٔ واقعی."""
    import pandas as pd
    rng = np.random.default_rng(seed)
    v = np.abs(rng.gamma(2.0, 300.0, n))
    worst = 0.0
    for w in WINDOWS:
        ref = pd.Series(v).rolling(w).min().to_numpy()
        got = _rollmin_nb(v, w)
        m = np.isfinite(ref)
        worst = max(worst, float(np.nanmax(np.abs(ref[m] - got[m]))))
    return worst


def run_card(tf: str, verbose=True) -> dict:
    os.makedirs(OUT, exist_ok=True)
    d = fd.load_fast(ASSET, tf)
    n_bars = int(d['n_bars'])
    high, low, close, opens = d['high'], d['low'], d['close'], d['open']
    ps = pip_size(ASSET)

    print(f"\n{'='*84}\n=== S944 WyckoffNoSupply :: {ASSET}_{tf}  "
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
    print(R.format_rqs2(f'S944_WyckoffNoSupply_{ASSET}_{tf}', res), flush=True)

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
        w = verify_rollmin()
        print(f'rollmin worst |Δ| vs pandas = {w:.3e}')
        sys.exit(0 if w < 1e-9 else 1)
    tf = sys.argv[1] if len(sys.argv) > 1 else 'M1'
    run_card(tf)
