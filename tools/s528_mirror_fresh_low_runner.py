# -*- coding: utf-8 -*-
"""S528 — آینهٔ S526: کفِ تازهٔ غلتان ۹۰-کندلی (fresh edge) ⇒ SHORT | H4/H6/H8/H12/D1.

پیش‌ثبت: `results/S528_PREREG_MirrorFreshLowShort_Xauusd_H4H6H8H12D1.md`
(کامیت e73ca81b قبل از این کد — صفر پارامتر آزاد، همه از S526 منجمد).

رویداد: nl = close < rolling_min(close, 90).shift(1)؛ سیگنال = nl & ~nl.shift(1)
پروتکل S522: is_long=False به‌طور یکنواخت برای سیگنال و هر دو نول (wrapper).
نول شرطی‌شده در فضای درفت-منفی (drift<0) — آینهٔ دقیق S526.
n_trials=10 (۵ کارت S526 + ۵ کارت آینه).
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

OUT = 'results/_s528'
CARDS = ['XAUUSD_H4', 'XAUUSD_H6', 'XAUUSD_H8', 'XAUUSD_H12', 'XAUUSD_D1']
N_TRIALS = 10
LOOKBACK = 90   # منجمد S950/S523/S526


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def neg_drift_mask(df):
    """درفت-منفی: close[t-1] - close[t-90] < 0 (آینهٔ دقیق S526)."""
    c = df['close']
    return ((c.shift(1) - c.shift(LOOKBACK)) < 0).fillna(False)


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

    # پروتکل S522: wrapper شورت — is_long=False برای سیگنال و هر دو نول
    _sim = L.simulate_trades

    def simulate_short(df, sig, sl_px, tp_px_mult, is_long, ps):
        return _sim(df, sig, sl_px, tp_px_mult, False, ps)

    L.simulate_trades = simulate_short

    # رویداد: کفِ تازهٔ ۹۰-کندلی — فقط لبهٔ تازه (آینهٔ S526 / قانون S963)
    def signals_fresh_low(df):
        c = df['close']
        prior_min = c.rolling(LOOKBACK).min().shift(1)
        nl = (c < prior_min).fillna(False)
        return nl & ~nl.shift(1).fillna(False)

    L.signals = signals_fresh_low

    # نول شرطی‌شده در فضای درفت-منفی (رویداد بنا به ساخت در این فضاست)
    def uncond_cond(L_, df, sl_abs, ps, stride):
        m = neg_drift_mask(df).to_numpy()
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
        m = neg_drift_mask(df).to_numpy()
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
    print(f'S528 mirror fresh rolling-LOW => SHORT | '
          f'close < min(close,{LOOKBACK}).shift(1), fresh edge only | '
          f'sl_k={L.SL_K} rr={L.RR} side=SHORT (wrapper, S522 protocol) | '
          f'conditioned null (drift<0 space) k={NM.K} n_trials={N_TRIALS}',
          flush=True)
    for card in cards:
        try:
            r = MTF.run_card(card, L, NM)
        except Exception as e:
            print(f'{card}: ERROR {e}', flush=True)
            continue
        r['lookback'] = LOOKBACK
        r['side'] = 'short'
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
