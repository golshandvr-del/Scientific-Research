# -*- coding: utf-8 -*-
"""S1520 — سقفِ تازهٔ ۹۰-کندلی (پایهٔ منجمد S526) × گیت کندلِ مطلع ρ≥0.618 (اهرم منجمد S965).

پیش‌ثبت: results/S1520_PREREG_InformedFreshHigh_Xauusd_H8H4H12.md (کامیت ab904dab، قبل از این کد).
هارنس عیناً s526_fresh_high_runner.py؛ تنها تغییر: گیت ρ روی کندل سیگنال.
حالت‌ها: gated (ρ≥0.618) | counter (ρ<0.618) — برای ابطال‌گر P2.
نول شرطی‌شده در فضای درفت>0 (همان S526) — تا lift گیت‌شده با پایهٔ S526 هم‌مقیاس باشد.
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

OUT = 'results/_s1520'
CARDS = ['XAUUSD_H8', 'XAUUSD_H4', 'XAUUSD_H12']
N_TRIALS = 17
LOOKBACK = 90     # منجمد S526
RHO_THR = 0.618   # منجمد S965


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def drift_mask(df):
    c = df['close']
    return ((c.shift(1) - c.shift(LOOKBACK)) > 0).fillna(False)


def fresh_high(df):
    c = df['close']
    nh = (c > c.rolling(LOOKBACK).max().shift(1)).fillna(False)
    return nh & ~nh.shift(1).fillna(False)


def rho(df):
    rng = (df['high'] - df['low']).replace(0, np.nan)
    return ((df['close'] - df['open']) / rng).fillna(0.0)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ('gated', 'counter') else 'gated'
    cards = [a for a in sys.argv[1:] if a.startswith('XAUUSD')] or CARDS
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

    def signals(df):
        base = fresh_high(df)
        r = rho(df)
        g = (r >= RHO_THR) if mode == 'gated' else (r < RHO_THR)
        sig = base & g
        print(f'  gate pass-rate: {int(sig.sum())}/{int(base.sum())} '
              f'({100.0 * sig.sum() / max(1, base.sum()):.1f}%) mode={mode}', flush=True)
        return sig

    L.signals = signals

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

    print(f'S1520 informed fresh-high(90) x rho>={RHO_THR} [{mode}] | sl_k={L.SL_K} rr={L.RR} '
          f'side=long | conditioned null (drift>0) k={NM.K} n_trials={N_TRIALS}', flush=True)
    for card in cards:
        try:
            r = MTF.run_card(card, L, NM)
        except Exception as e:
            print(f'{card}: ERROR {e}', flush=True)
            continue
        r['lookback'] = LOOKBACK
        r['rho_thr'] = RHO_THR
        r['mode'] = mode
        with open(f'{OUT}/{card}_{mode}.json', 'w') as f:
            json.dump(r, f, ensure_ascii=False, default=str)
        print(f'{card} [{mode}]: span={r.get("span_years")}y n={r.get("n_trades")} '
              f'sl={r.get("sl_pip")}pip wr={r.get("wr")} be={r.get("be")} '
              f'lift={r.get("lift")} unc={r.get("uncond_wr")} pmax={r.get("perm_max")} '
              f'z={r.get("z")} rqs2={r.get("rqs2")} verdict={r.get("verdict")}', flush=True)
        print(f'  saved -> {OUT}/{card}_{mode}.json', flush=True)


if __name__ == '__main__':
    main()
