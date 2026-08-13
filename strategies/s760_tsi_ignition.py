#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S760 — «اشتعالِ TSI» · XAUUSD · لایهٔ نو (نه احیا)

پیش‌ثبت: results/S760_PREREG_TSI_IGNITION.md (commit 69368b85 — پیش از هر آزمون)
مسیرِ چندگانگی: C (hold-out) · SPLIT_FRAC=0.60 · SEED=20260812 · K_PERM=2000

فاز ۱ (این اسکریپت، حالتِ search):
  جستجوی خانوادهٔ منجمدِ ۹۶-پیکربندی فقط روی ۶۰٪ نخستِ کارت.
  خروجی: results/_scan_S760/<TF>_search.json + بهترین پیکربندی per-side.

فاز ۲ (حالتِ holdout — فقط پس از commitِ الحاقیهٔ انجماد):
  یک آزمونِ یگانه روی ۴۰٪ دوم با rqs2.compute_rqs2 و همهٔ ورودی‌های الزامی.

اجرا:
  python3 strategies/s760_tsi_ignition.py search M1
  python3 strategies/s760_tsi_ignition.py holdout M1   # فقط پس از انجماد
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se           # noqa: E402
from engine import rqs2                          # noqa: E402
from tools import s434_fast_data as fd           # noqa: E402

SEED = 20260812
K_PERM = 2000
SPLIT_FRAC = 0.60
ASSET = 'XAUUSD'
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_scan_S760')

# ---- خانوادهٔ منجمدِ پیش‌ثبت (۹۶ پیکربندی) — خارج از این‌ها هیچ چیز ----
TSI_PERIODS = [(25, 13), (34, 13), (55, 21)]
THETAS = [1.0, 1.272, 1.618, 2.0]
SIDES = ['long', 'short']
GEOMS = [(1.0, 1.0), (1.0, 1.5), (1.5, 1.0), (1.5, 1.5)]   # (k_sl, rr) — TP>=SL همیشه
ATR_P = 100

# max_hold منجمدِ per-TF: ≈۴ ساعتِ بازار روی TFهای دقیقه‌ای؛ ۶۴ کندل روی H1+
MAX_HOLD = {
    'M1': 240, 'M3': 80, 'M4': 60, 'M5': 48, 'M6': 40, 'M10': 24,
    'M12': 20, 'M15': 16, 'M20': 12, 'M30': 8,
    'H1': 64, 'H2': 64, 'H3': 64, 'H6': 64, 'H8': 64, 'H12': 64,
    'D1': 64, 'W1': 32, 'MN1': 12,
}


def ema(x: pd.Series, p: int) -> pd.Series:
    return x.ewm(span=p, adjust=False).mean()


def tsi_series(close: pd.Series, long_p: int, short_p: int) -> np.ndarray:
    m = close.diff()
    r = ema(ema(m, long_p), short_p)
    a = ema(ema(m.abs(), long_p), short_p)
    return (100.0 * r / a.replace(0, np.nan)).values


def atr_pip(df: pd.DataFrame, asset: str, p: int = ATR_P) -> np.ndarray:
    pip = se.ASSETS[asset]['pip']
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.r_[np.nan, c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    atr = pd.Series(tr).ewm(alpha=1.0 / p, adjust=False).mean().values
    return atr / pip


def cross_signals(tsi: np.ndarray, thr_hi: float, thr_lo: float):
    """گذرِ رویدادی با shift(1) ضدِ نشتی: سیگنال روی کندلِ t از دادهٔ t-1/t-2."""
    v1 = np.r_[np.nan, tsi[:-1]]     # مقدارِ t-1
    v2 = np.r_[np.nan, v1[:-1]]      # مقدارِ t-2
    long_sig = (v2 <= thr_hi) & (v1 > thr_hi)
    short_sig = (v2 >= thr_lo) & (v1 < thr_lo)
    return np.nan_to_num(long_sig).astype(bool), np.nan_to_num(short_sig).astype(bool)


def scan_search(tf: str):
    t_all = time.time()
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    n = len(df)
    split = int(n * SPLIT_FRAC)
    dfs = df.iloc[:split].reset_index(drop=True)
    mh = MAX_HOLD[tf]
    atr = atr_pip(dfs, ASSET)
    close_s = pd.Series(dfs['close'].values)
    warm = 4 * (55 + 21) + ATR_P    # گرم‌شدنِ کافی برای بلندترین دوره

    print(f"=== S760 SEARCH {ASSET}-{tf} | src={d['src']} | bars={n:,} "
          f"| search={split:,} | mh={mh} ===", flush=True)

    rows = []
    for (lp, sp) in TSI_PERIODS:
        tsi = tsi_series(close_s, lp, sp)
        tv = tsi[warm:split]
        tv = tv[np.isfinite(tv)]
        mu, sd = float(np.mean(tv)), float(np.std(tv))
        for th in THETAS:
            thr_hi = mu + th * sd
            thr_lo = mu - th * sd
            ls, ss = cross_signals(tsi, thr_hi, thr_lo)
            ls[:warm] = False
            ss[:warm] = False
            for (k, rr) in GEOMS:
                sl = k * atr
                tp = rr * sl
                ok = np.isfinite(sl) & (sl > 0)
                for side in SIDES:
                    sig = ls if side == 'long' else ss
                    sig = sig & ok
                    if sig.sum() < 5:
                        rows.append(dict(lp=lp, sp=sp, th=th, k=k, rr=rr,
                                         side=side, n=int(sig.sum()), skip=True))
                        continue
                    tr = se.simulate_trades(
                        dfs,
                        sig if side == 'long' else np.zeros(len(dfs), bool),
                        sig if side == 'short' else np.zeros(len(dfs), bool),
                        sl_pip=sl, tp_pip=tp, asset=ASSET,
                        max_hold=mh, allow_overlap=False)
                    if tr is None or len(tr) == 0:
                        rows.append(dict(lp=lp, sp=sp, th=th, k=k, rr=rr,
                                         side=side, n=0, skip=True))
                        continue
                    ntr = len(tr)
                    wr = float((tr['pnl_pip'] > 0).mean() * 100)
                    exp = float(tr['pnl_pip'].mean())
                    # مبنای بی‌قیدِ سریعِ فاز جستجو (فاز ۲ null کامل می‌سازد)
                    rows.append(dict(lp=lp, sp=sp, th=th, k=k, rr=rr, side=side,
                                     n=ntr, wr=round(wr, 3), exp_pip=round(exp, 3),
                                     thr_hi=round(thr_hi, 3), thr_lo=round(thr_lo, 3)))
            print(f"  tsi({lp},{sp}) th={th} done "
                  f"({time.time()-t_all:.0f}s)", flush=True)

    # مبنای WR بی‌قید برای هر هندسه (روی نمونهٔ تصادفیِ کندل‌های واجد)
    rng = np.random.default_rng(SEED)
    uncond = {}
    valid = np.where(np.isfinite(atr) & (atr > 0))[0]
    valid = valid[valid >= warm]
    samp = np.sort(rng.choice(valid, size=min(20000, len(valid)), replace=False))
    for (k, rr) in GEOMS:
        sl = k * atr
        tp = rr * sl
        for side in SIDES:
            sig = np.zeros(len(dfs), bool)
            sig[samp] = True
            tr = se.simulate_trades(
                dfs,
                sig if side == 'long' else np.zeros(len(dfs), bool),
                sig if side == 'short' else np.zeros(len(dfs), bool),
                sl_pip=sl, tp_pip=tp, asset=ASSET,
                max_hold=mh, allow_overlap=False)
            key = f"{k}x{rr}_{side}"
            uncond[key] = dict(wr=float((tr['pnl_pip'] > 0).mean() * 100),
                               n=int(len(tr)))

    # رتبه‌بندی به معیارِ پیش‌ثبت: lift×sqrt(n) در برابرِ مبنای بی‌قیدِ هم‌هندسه
    best = {'long': None, 'short': None}
    for r in rows:
        if r.get('skip') or r['n'] < 30:
            continue
        base = uncond[f"{r['k']}x{r['rr']}_{r['side']}"]['wr']
        lift = r['wr'] - base
        score = lift * np.sqrt(r['n'])
        r['lift_pp'] = round(lift, 3)
        r['score'] = round(float(score), 2)
        b = best[r['side']]
        if b is None or r['score'] > b['score']:
            best[r['side']] = r

    os.makedirs(OUT_DIR, exist_ok=True)
    out = dict(tf=tf, src=d['src'], n_full=n, n_search=split,
               split_bar=split, seed=SEED, n_configs=len(TSI_PERIODS) * len(THETAS)
               * len(SIDES) * len(GEOMS), max_hold=mh,
               elapsed_s=round(time.time() - t_all, 1),
               uncond=uncond, best=best, rows=rows)
    fp = os.path.join(OUT_DIR, f"{tf}_search.json")
    with open(fp, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"SAVED {fp} | best_long={best['long']} | best_short={best['short']}",
          flush=True)


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'search'
    tf = sys.argv[2] if len(sys.argv) > 2 else 'M1'
    if mode == 'search':
        scan_search(tf)
    else:
        raise SystemExit('حالتِ holdout فقط پس از الحاقیهٔ انجماد فعال می‌شود.')
