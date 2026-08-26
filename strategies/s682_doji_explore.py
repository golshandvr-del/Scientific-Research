# -*- coding: utf-8 -*-
"""
s682_doji_explore.py — اکتشافِ S682 فقط روی **نیمهٔ اول** (مسیرِ C)
================================================================================
پیش‌ثبت: results/S682_PREREG_DOJI_STRETCH_FADE.md (کامیت a0d674b3 — قبل از اجرا).

سیگنال: دوجی (body ≤ b×range) در کششِ افراطی (|close−EMA34|/ATR34 ≥ s)
⇒ فیدِ بازگشتی به سمتِ میانگین. گریدِ قفل: b∈{0.1,0.25} × s∈{1.5,2.5} ×
rr∈{1,1.5,2} = ۱۲ سلول per کارت.

هندسه: SL = 1.618×median(ATR34 نیمهٔ اول)، TP=rr×SL، mh جدولِ قفلِ S680.
نیمهٔ دوم هرگز لمس نمی‌شود.
"""
from __future__ import annotations

import gc
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import scalp_engine as se                    # noqa: E402
from tools import s434_fast_data as fd                   # noqa: E402

OUT_DIR = os.path.join(ROOT, 'results', '_s682_explore')

BS = (0.10, 0.25)
SS = (1.5, 2.5)
RRS = (1.0, 1.5, 2.0)

MAX_HOLD = {'M1': 34, 'M3': 34, 'M4': 34, 'M5': 34, 'M6': 21, 'M10': 21,
            'M12': 21, 'M15': 21, 'M20': 21, 'M30': 21, 'H1': 13, 'H2': 13,
            'H3': 13, 'H6': 13, 'H8': 13, 'H12': 13, 'D1': 8, 'W1': 8,
            'MN1': 5}


def ema(x: np.ndarray, per: int) -> np.ndarray:
    a = 2.0 / (per + 1)
    out = np.empty_like(x)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def atr_wilder(h, l, c, per: int) -> np.ndarray:
    n = len(c)
    tr = np.empty(n)
    tr[0] = h[0] - l[0]
    pc = c[:-1]
    tr[1:] = np.maximum(h[1:] - l[1:],
                        np.maximum(np.abs(h[1:] - pc), np.abs(l[1:] - pc)))
    out = np.empty(n)
    out[0] = tr[0]
    a = 1.0 / per
    for i in range(1, n):
        out[i] = out[i - 1] + a * (tr[i] - out[i - 1])
    return out


def explore(tf: str, asset: str = 'XAUUSD') -> dict:
    t0 = time.time()
    d = fd.load_fast(asset, tf)
    src = d['src']
    df_full = fd.as_dataframe(d)
    del d
    gc.collect()
    n_full = len(df_full)
    n_half = n_full // 2
    df = df_full.iloc[:n_half].reset_index(drop=True)   # فقط نیمهٔ اول
    del df_full
    gc.collect()

    o = df['open'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)

    pip = se.ASSETS[asset]['pip']                        # BUG-PIPGUESS
    cost = se.ASSETS[asset]['spread_pip'] + 2 * se.ASSETS[asset]['slip_pip']

    e34 = ema(c, 34)
    a34 = atr_wilder(h, l, c, 34)
    sl = round(float(np.median(a34[100:]) / pip) * 1.618, 1)  # غیرگرد
    mh = MAX_HOLD[tf]

    rng_ = h - l
    body = np.abs(c - o)
    with np.errstate(divide='ignore', invalid='ignore'):
        stretch = np.where(a34 > 0, (c - e34) / a34, 0.0)

    cells = []
    for b in BS:
        doji = (rng_ > 0) & (body <= b * rng_)
        for s in SS:
            short_sig = doji & (stretch >= s)   # کششِ مثبت ⇒ فید SHORT
            long_sig = doji & (stretch <= -s)
            warm = 100
            short_sig[:warm] = False
            long_sig[:warm] = False
            nsig = int(long_sig.sum() + short_sig.sum())
            for rr in RRS:
                tp = round(rr * sl, 1)
                if nsig == 0:
                    cells.append(dict(b=b, s=s, rr=rr, n=0, skipped='no_sig'))
                    continue
                tr = se.simulate_trades(df, long_sig, short_sig, sl, tp,
                                        asset, max_hold=mh,
                                        allow_overlap=False)
                if tr is None or len(tr) == 0:
                    cells.append(dict(b=b, s=s, rr=rr, n=0,
                                      skipped='no_trades'))
                    continue
                pnl = tr['pnl_pip'].values
                n = len(pnl)
                wr = 100.0 * float((pnl > 0).mean())
                be = 100.0 * (sl + cost) / (sl + tp)     # WR سربه‌سر با هزینه
                lift = wr - be
                zsc = (wr - be) / max(1e-9,
                                      (100.0 * np.sqrt(be / 100 * (1 - be / 100)
                                                       / n)))
                dirv = tr['direction'].values
                nl = int((dirv == 'long').sum()) if dirv.dtype.kind in 'OU' \
                    else int((dirv > 0).sum())
                cells.append(dict(b=b, s=s, rr=rr, n=n, n_long=nl,
                                  wr=round(wr, 2), be_wr=round(be, 2),
                                  lift_be=round(lift, 2),
                                  exp_pip=round(float(pnl.mean()), 3),
                                  z_screen=round(float(zsc), 2)))
    res = dict(asset=asset, tf=tf, src=src, n_full=n_full, n_half=n_half,
               sl_pip=sl, atr_per=34, sl_mult=1.618, max_hold=mh,
               cost_pip=cost, grid_cells=len(BS) * len(SS) * len(RRS),
               cells=cells, elapsed_s=round(time.time() - t0, 1))
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, f'explore_{tf}.json'), 'w',
              encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    best = max([x for x in cells if 'skipped' not in x],
               key=lambda x: x['z_screen'], default=None)
    print(f'[{tf}] done {res["elapsed_s"]}s sl={sl} best={best}', flush=True)
    del df
    gc.collect()
    return res


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--tfs', required=True)
    a = ap.parse_args()
    for tf in [t.strip() for t in a.tfs.split(',') if t.strip()]:
        try:
            explore(tf)
        except Exception as e:  # noqa: BLE001
            import traceback; traceback.print_exc()
            print(f'!! {tf}: {type(e).__name__}: {e}', flush=True)
        gc.collect()
    print('[explore batch done]', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
