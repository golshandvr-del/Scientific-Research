# -*- coding: utf-8 -*-
"""S947 — «کمینهٔ MFI در روند» (Money-Flow Exhaustion Pullback).

پیش‌ثبت: results/S947_PREREG_multiplicity_route.md (کامیت f9707676، پیش از هر بک‌تستی).

فرضیه (Quong & Soudack 1989): MFI = RSIِ وزن‌شده با حجم روی typical price —
فشارِ خرید/فروشِ دلاری. در روندِ صعودی (لنگرِ EMA233 — درسِ S883)، وقتی MFI به
کمینهٔ تازهٔ پنجرهٔ اخیر می‌رسد (رویدادِ آناتومیک — درسِ S882)، فشارِ فروشِ
دلاری تهی شده ⇒ ازسرگیریِ روند ⇒ LONG. آینه برای SHORT.

رویداد LONG:  close > EMA233 و MFI[i] ≤ min(MFI[i−w..i−1])
رویداد SHORT: close < EMA233 و MFI[i] ≥ max(MFI[i−w..i−1])
خانوادهٔ منجمد: w∈{34,89} · MFI_P=14 ثابت · n_trials=152 (=19×8 تجمعیِ بلوک S94x)
هندسه/صف/مدلِ صفر عیناً S940..S946 (یک نسخهٔ راستی‌آزمایی‌شده).
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
from strategies.s944_wyckoff_no_supply import _ema_nb, _rollmin_nb  # noqa: E402
from strategies.s945_amihud_thin_move_fade import _rollmax_nb  # noqa: E402

WINDOWS = (34, 89)
MFI_P = 14
EMA_P = 233
N_TRIALS = 152
WARMUP = 1000
OUT = 'results/_s947'


@njit(cache=True)
def _mfi_nb(high, low, close, vol, p):
    """MFI(p) — پورتِ دقیقِ engine/indicator_bank.py::mfi (خط 534).

    tp = (H+L+C)/3 · mf = tp·vol
    up = rolling-sum(p) of mf where tp>tp[-1] · dn = mirror با tp<tp[-1]
    mfi = 100 − 100/(1 + up/dn) · dn==0 ⇒ NaN (مثلِ replace(0, nan) مرجع)
    p کندلِ اول (پنجرهٔ ناقصِ rolling) ⇒ NaN مثلِ pandas.
    """
    n = close.shape[0]
    out = np.full(n, np.nan)
    up = np.zeros(n)
    dn = np.zeros(n)
    tp_prev = (high[0] + low[0] + close[0]) / 3.0
    for i in range(1, n):
        tp = (high[i] + low[i] + close[i]) / 3.0
        mf = tp * vol[i]
        if tp > tp_prev:
            up[i] = mf
        elif tp < tp_prev:
            dn[i] = mf
        tp_prev = tp
    su = 0.0
    sd = 0.0
    for i in range(n):
        su += up[i]
        sd += dn[i]
        if i >= p:
            su -= up[i - p]
            sd -= dn[i - p]
        if i >= p - 1:
            # pandas rolling(p) از i=p−1 مقدار می‌دهد؛ اما بارِ اولِ tp.diff،
            # NaN است (mf.where ⇒ 0.0 در مرجع) — پس همان جمعِ ساده کافی است.
            if sd > 0.0:
                out[i] = 100.0 - 100.0 / (1.0 + su / sd)
    return out


def _past_min(x, w):
    """min(x[i−w..i−1]) — کمینهٔ پنجرهٔ صرفاً-گذشته (شیفتِ rollmin)."""
    r = _rollmin_nb(x, w)
    out = np.full(x.shape[0], np.nan)
    out[1:] = r[:-1]
    return out


def _past_max(x, w):
    r = _rollmax_nb(x, w)
    out = np.full(x.shape[0], np.nan)
    out[1:] = r[:-1]
    return out


def family_dir(high: np.ndarray, low: np.ndarray, close: np.ndarray,
               vol: np.ndarray) -> np.ndarray:
    """ادغامِ ۲ عضو (OR)؛ کمینه/بیشینهٔ تازهٔ MFI در جهتِ روندِ EMA233."""
    n = close.shape[0]
    h = high.astype(np.float64)
    lo = low.astype(np.float64)
    c = close.astype(np.float64)
    v = vol.astype(np.float64)
    mfi = _mfi_nb(h, lo, c, v, MFI_P)
    ema = _ema_nb(c, EMA_P)
    up_trend = c > ema
    dn_trend = c < ema
    long_any = np.zeros(n, dtype=np.bool_)
    short_any = np.zeros(n, dtype=np.bool_)
    for w in WINDOWS:
        pmin = _past_min(mfi, w)
        pmax = _past_max(mfi, w)
        lg = np.nan_to_num(up_trend & (mfi <= pmin), nan=False)
        sh = np.nan_to_num(dn_trend & (mfi >= pmax), nan=False)
        long_any |= lg
        short_any |= sh
    long_any[:WARMUP] = False
    short_any[:WARMUP] = False
    d = np.zeros(n, dtype=np.int8)
    d[long_any & ~short_any] = 1
    d[short_any & ~long_any] = -1
    return d


def verify_indicators(n=4000, seed=23) -> float:
    """MFI مقابلِ engine/indicator_bank.py::mfi + past-extrema مقابل pandas."""
    import pandas as pd
    from engine.indicator_bank import mfi as bank_mfi
    rng = np.random.default_rng(seed)
    c = 2000.0 + np.cumsum(rng.normal(0, 1.0, n))
    h = c + np.abs(rng.normal(0, 0.6, n))
    lo = c - np.abs(rng.normal(0, 0.6, n))
    v = np.abs(rng.gamma(2.0, 300.0, n))
    df = pd.DataFrame(dict(high=h, low=lo, close=c, volume=v))
    ref = bank_mfi(df, MFI_P).to_numpy()
    got = _mfi_nb(h, lo, c, v, MFI_P)
    m = np.isfinite(ref) & np.isfinite(got)
    # پوششِ NaN باید یکسان باشد (به‌جز dn==0 که هر دو NaN می‌دهند)
    mism = int(np.sum(np.isfinite(ref) != np.isfinite(got)))
    worst = float(np.nanmax(np.abs(ref[m] - got[m])))
    if mism > 0:
        worst = max(worst, 1.0)
        print(f'  NaN-mask mismatch: {mism} bars')
    for w in WINDOWS:
        r2 = pd.Series(c).rolling(w).min().shift(1).to_numpy()
        g2 = _past_min(c, w)
        m2 = np.isfinite(r2) & np.isfinite(g2)
        worst = max(worst, float(np.nanmax(np.abs(r2[m2] - g2[m2]))))
        r3 = pd.Series(c).rolling(w).max().shift(1).to_numpy()
        g3 = _past_max(c, w)
        m3 = np.isfinite(r3) & np.isfinite(g3)
        worst = max(worst, float(np.nanmax(np.abs(r3[m3] - g3[m3]))))
    return worst


def run_card(tf: str, verbose=True) -> dict:
    os.makedirs(OUT, exist_ok=True)
    d = fd.load_fast(ASSET, tf)
    n_bars = int(d['n_bars'])
    high, low, close = d['high'], d['low'], d['close']
    ps = pip_size(ASSET)

    print(f"\n{'='*84}\n=== S947 MfiExhaustionPullback :: {ASSET}_{tf}  "
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
    print(R.format_rqs2(f'S947_MfiExhaustionPullback_{ASSET}_{tf}', res), flush=True)

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
        print(f'MFI+past-extrema worst |Δ| vs bank/pandas = {w:.3e}')
        sys.exit(0 if w < 1e-9 else 1)
    tf = sys.argv[1] if len(sys.argv) > 1 else 'M1'
    run_card(tf)
