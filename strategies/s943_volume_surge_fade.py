# -*- coding: utf-8 -*-
"""S943 — «فیدِ جهشِ حجم» (Volume-Surge FADE).

پیش‌ثبت: results/S943_PREREG_multiplicity_route.md (کامیت 64bb846c، پیش از هر بک‌تستی).

فرضیه: در طلا جهشِ ناگهانیِ حجم = اوجِ هیجان/ظرفیتِ اشباع‌شده؛ S942 نشان داد
جهتِ ادامه آنتی‌مهارت شدید دارد (z=-13.7 در M1) ⇒ جهتِ معکوسِ بدنهٔ کندلِ جهش.
⚠️ چرخشِ جهت data-motivated است — صادقانه افشا شده؛ n_trials تجمعی = 76.

خانوادهٔ منجمد عیناً S942 (۴ عضو): w∈{55,144} × thr∈{1.618, 2.618}
رویداد: عبورِ vz از آستانه به بالا؛ ورود در closeِ همان کندل؛
جهت = **معکوسِ** علامتِ بدنهٔ کندلِ جهش (بدنهٔ صعودی ⇒ SHORT؛ نزولی ⇒ LONG؛ دوجی ⇒ هیچ).
هندسه/صف/مدلِ صفر عیناً S940..S942 (یک نسخهٔ راستی‌آزمایی‌شده).
اگر ACCEPT: ممیزیِ هم‌پوشانی با آرشیوِ MeanRev (S355/S431) فوراً اجرا می‌شود (§6 پیش‌ثبت).
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
from strategies.s942_volume_surge_continuation import (   # noqa: E402
    _vz_nb, WINDOWS, THRESHOLDS, WARMUP)

N_TRIALS = 76        # 19×4 کارزار (S940+S941+S942+S943) — شمارشِ صادقانهٔ تجمعی
OUT = 'results/_s943'


def family_dir(opens: np.ndarray, close: np.ndarray,
               vol: np.ndarray) -> np.ndarray:
    """ادغامِ ۴ عضو؛ رویداد = cross بالای آستانه؛ جهت = «معکوسِ» بدنه؛ تعارض⇒۰.

    تنها تفاوت با S942: جهتِ ورود برعکس شده (fade به‌جای continuation).
    """
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
            cross = np.nan_to_num((prev <= thr) & (vz > thr), nan=False)
            # ⇄ FADE: بدنهٔ صعودی ⇒ SHORT؛ بدنهٔ نزولی ⇒ LONG
            short_any |= cross & (body > 0)
            long_any |= cross & (body < 0)
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

    print(f"\n{'='*84}\n=== S943 VolumeSurgeFADE :: {ASSET}_{tf}  "
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
    print(R.format_rqs2(f'S943_VolumeSurgeFade_{ASSET}_{tf}', res), flush=True)

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
