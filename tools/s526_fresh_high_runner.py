# -*- coding: utf-8 -*-
"""S526 — سقفِ تازهٔ غلتان ۹۰-کندلی (fresh edge) ⇒ LONG | H4/H6/H8/H12/D1.

پیش‌ثبت: `results/S526_PREREG_FreshRollingHighContinuation_Xauusd_H4H6H8H12D1.md`
(کامیت شده قبل از این اجرا — مسیر B، صفر پارامتر آزاد).

رویداد: nh = close > rolling_max(close, 90).shift(1)؛ سیگنال = nh & ~nh.shift(1)
نول شرطی‌شده در فضای درفت-مثبت (قانون S523/S502): lift = مهارت ورای بتای رژیم.
هارنس عیناً از s523_drift_gated_runner.py. n_trials=5 (تنش 50 در MD).
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

OUT = 'results/_s526'
CARDS = ['XAUUSD_H4', 'XAUUSD_H6', 'XAUUSD_H8', 'XAUUSD_H12', 'XAUUSD_D1']
N_TRIALS = 5
LOOKBACK = 90   # منجمد S950/S523


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def drift_mask(df):
    c = df['close']
    return ((c.shift(1) - c.shift(LOOKBACK)) > 0).fillna(False)


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

    # رویداد: سقفِ تازهٔ ۹۰-کندلی — فقط لبهٔ تازه (قانون S963)
    def signals_fresh_high(df):
        c = df['close']
        prior_max = c.rolling(LOOKBACK).max().shift(1)
        nh = (c > prior_max).fillna(False)
        return nh & ~nh.shift(1).fillna(False)

    L.signals = signals_fresh_high

    # نول شرطی‌شده در فضای درفت-مثبت (رویداد بنا به ساخت در این فضاست)
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
    print(f'S526 fresh rolling-high | close > max(close,{LOOKBACK}).shift(1), '
          f'fresh edge only | sl_k={L.SL_K} rr={L.RR} side=long | '
          f'conditioned null (drift>0 space) k={NM.K} n_trials={N_TRIALS}',
          flush=True)
    for card in cards:
        try:
            r = MTF.run_card(card, L, NM)
        except Exception as e:
            print(f'{card}: ERROR {e}', flush=True)
            continue
        r['lookback'] = LOOKBACK
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
