# -*- coding: utf-8 -*-
"""S524 — Spring وایکوف: شکست کاذب کف ۲۰-کندلی در رژیم درفت مثبت ⇒ LONG.

پیش‌ثبت: `results/S524_PREREG_SpringFailedBreakdown_Xauusd_H4H6H8H12D1.md`
(commit شده قبل از این اجرا — مسیر B، ۵ کارت، صفر پارامتر آزاد).

رویداد (علّی، تک‌کندلی):
    ref_low(t) = min(low[t−20 … t−1])
    spring(t)  = low[t] < ref_low(t)  AND  close[t] > ref_low(t)
دروازهٔ رژیم (عین S950): close[t−1] − close[t−90] > 0

اجزای بازاستفاده (صفر-بازنویسی): شبیه‌ساز/ATR/هندسهٔ منجمد S382،
run_card منجمد، مدل صفر هم‌شرط (الگوی اثبات‌شدهٔ S523 — stride و
جایگشت هر دو در فضای drift>0). n_trials=50 (خانوادهٔ رویدادی تازه).
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

OUT = 'results/_s524'
CARDS = ['XAUUSD_H4', 'XAUUSD_H6', 'XAUUSD_H8', 'XAUUSD_H12', 'XAUUSD_D1']
N_TRIALS = 50
LOOKBACK = 20         # کف ۲۰-کندلی (قرارداد Donchian)
DRIFT_LOOKBACK = 90   # عین S950


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def drift_mask(df):
    c = df['close']
    return ((c.shift(1) - c.shift(DRIFT_LOOKBACK)) > 0).fillna(False)


def main():
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

    def signals_spring(df):
        ref_low = df['low'].shift(1).rolling(LOOKBACK).min()
        spring = (df['low'] < ref_low) & (df['close'] > ref_low)
        return (spring & drift_mask(df)).fillna(False)

    L.signals = signals_spring

    # مدل صفر هم‌شرط — عین الگوی S523
    def uncond_cond(L_, df, sl_abs, ps, stride):
        m = drift_mask(df).to_numpy()
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
        m = drift_mask(df).to_numpy()
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

    cards = sys.argv[1:] or CARDS
    print(f'S524 spring | low<min(low[-{LOOKBACK}:]) AND close>ref AND '
          f'drift{DRIFT_LOOKBACK}>0 | sl_k={L.SL_K} rr={L.RR} side=long | '
          f'conditioned null k={NM.K} n_trials={N_TRIALS}', flush=True)
    for card in cards:
        try:
            r = MTF.run_card(card, L, NM)
        except Exception as e:
            print(f'{card}: ERROR {e}', flush=True)
            continue
        r['lookback'] = LOOKBACK
        r['drift_lookback'] = DRIFT_LOOKBACK
        with open(f'{OUT}/{card}.json', 'w') as f:
            json.dump(r, f, ensure_ascii=False, default=str)
        print(f'{card}: span={r.get("span_years")}y n={r.get("n_trades")} '
              f'sl={r.get("sl_pip")}pip wr={r.get("wr")} be={r.get("be")} '
              f'lift={r.get("lift")} unc={r.get("uncond_wr")} '
              f'pmax={r.get("perm_max")} z={r.get("z")} '
              f'rqs2={r.get("rqs2")} verdict={r.get("verdict")}', flush=True)
        print(f'  saved -> {OUT}/{card}.json', flush=True)


if __name__ == '__main__':
    main()
