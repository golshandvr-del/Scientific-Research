# -*- coding: utf-8 -*-
"""S529 — سقف تازهٔ ۹۰-کندلی (پایهٔ منجمد S526) × گیت درفت ۱۸۰-کندلی علّی (اهرم S966).

پیش‌ثبت: `results/S529_PREREG_FreshHighDriftAligned_Xauusd_H8H4.md` (کامیت 13a28810
قبل از این کد). Playbook اثبات‌شدهٔ S604/S966 روی پایهٔ خودم.

حالت‌ها (argv[1]): 'aligned' (drift180>0) | 'counter' (drift180<0, ممیزی P2)
کارت‌ها (argv[2:]): پیش‌فرض H8 و H4.
نول شرطی‌شده در فضای گیت‌شدهٔ همان حالت (قانون S523). n_trials=15.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

OUT = 'results/_s529'
CARDS = ['XAUUSD_H8', 'XAUUSD_H4']
N_TRIALS = 15
LOOKBACK = 90     # منجمد S526
DRIFT_L = 180     # منجمد S966


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def drift180_mask(df, mode):
    """گیت S966 عیناً: close[i-1] > close[i-1-180] (علّی). counter = آینه."""
    c = df['close']
    d = c.shift(1) - c.shift(1 + DRIFT_L)
    if mode == 'aligned':
        return (d > 0).fillna(False)
    return (d < 0).fillna(False)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'aligned'
    assert mode in ('aligned', 'counter')
    os.makedirs(OUT, exist_ok=True)
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')
    NM = _mod('tools/s382_null_model.py', '_nm')
    MTF = _mod('tools/s382_mtf_runner.py', '_mtf')
    MTF.N_TRIALS = N_TRIALS

    def load_full(card):
        path = f'data/full/{card}.csv'
        if not os.path.exists(path):
            path = f'data/{card}.csv'
        df = pd.read_csv(path)
        df['dt'] = pd.to_datetime(df['time'], unit='s')
        return df

    L.load = load_full

    # رویداد S526 منجمد × گیت درفت180
    def signals_gated(df):
        c = df['close']
        prior_max = c.rolling(LOOKBACK).max().shift(1)
        nh = (c > prior_max).fillna(False)
        fresh = nh & ~nh.shift(1).fillna(False)
        g = drift180_mask(df, mode)
        # نرخ عبور گیت (برای ممیزی «گیت تهی» پیش‌ثبت)
        n_base = int(fresh.sum())
        n_gated = int((fresh & g).sum())
        print(f'  gate pass-rate: {n_gated}/{n_base} '
              f'({100.0*n_gated/max(n_base,1):.1f}%) mode={mode}', flush=True)
        return fresh & g

    L.signals = signals_gated

    # نول شرطی‌شده در فضای گیت‌شدهٔ همان حالت
    def uncond_cond(L_, df, sl_abs, ps, stride):
        m = drift180_mask(df, mode).to_numpy()
        idx = np.where(m)[0][::stride]
        sig = pd.Series(False, index=df.index)
        sig.iloc[idx] = True
        tr = L_.simulate_trades(df, sig, sl_abs, L_.RR, True, ps)
        if len(tr) == 0:
            return None, 0
        return 100.0 * float((tr['outcome'] == 'win').mean()), len(tr)

    def perm_cond(L_, df, sl_abs, ps, n_sig, k=NM.K, seed=NM.SEED):
        rng = np.random.default_rng(seed)
        n = len(df)
        m = drift180_mask(df, mode).to_numpy()
        valid = np.where(m[200:n - 2])[0] + 200
        wrs = []
        for _ in range(k):
            pos = rng.choice(valid, size=min(n_sig, len(valid)), replace=False)
            sig = pd.Series(False, index=df.index)
            sig.iloc[np.sort(pos)] = True
            tr = L_.simulate_trades(df, sig, sl_abs, L_.RR, True, ps)
            if len(tr) >= 30:
                wrs.append(100.0 * float((tr['outcome'] == 'win').mean()))
        a = np.asarray(wrs, float)
        return dict(mean=float(a.mean()), sd=float(a.std(ddof=1)),
                    max=float(a.max()), min=float(a.min()),
                    p95=float(np.percentile(a, 95)), k=int(len(a)))

    NM.uncond_baseline = uncond_cond
    NM.perm_baseline = perm_cond

    cards = sys.argv[2:] or CARDS
    print(f'S529 fresh-high(90) x drift180 gate [{mode}] | '
          f'sl_k={L.SL_K} rr={L.RR} side=long | conditioned null in {mode} space '
          f'k={NM.K} n_trials={N_TRIALS}', flush=True)
    for card in cards:
        try:
            r = MTF.run_card(card, L, NM)
        except Exception as e:
            print(f'{card}: ERROR {e}', flush=True)
            continue
        r['lookback'] = LOOKBACK
        r['drift_l'] = DRIFT_L
        r['mode'] = mode
        with open(f'{OUT}/{card}_{mode}.json', 'w') as f:
            json.dump(r, f, ensure_ascii=False, default=str)
        print(f'{card} [{mode}]: span={r.get("span_years")}y n={r.get("n_trades")} '
              f'sl={r.get("sl_pip")}pip wr={r.get("wr")} be={r.get("be")} '
              f'lift={r.get("lift")} unc={r.get("uncond_wr")} '
              f'pmax={r.get("perm_max")} z={r.get("z")} '
              f'rqs2={r.get("rqs2")} verdict={r.get("verdict")}', flush=True)
        print(f'  saved -> {OUT}/{card}_{mode}.json', flush=True)


if __name__ == '__main__':
    main()
