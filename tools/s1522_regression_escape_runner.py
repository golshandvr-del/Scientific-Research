# -*- coding: utf-8 -*-
"""S1522 — گریز از کانال رگرسیون ۹۰-کندلی (لبهٔ تازهٔ z_res ≥ 2.5) ⇒ LONG | H8/H12/D1/H6.

پیش‌ثبت: results/S1522_PREREG_RegressionChannelEscape_Xauusd_H8H12D1H6.md (کامیت f4e7733b، قبل از این کد).
نول: بی‌قید (پیش‌فرض tools/s382_null_model.py) — رویداد در فضای درفت زندگی نمی‌کند.
هارنس عیناً tools/s382_mtf_runner.run_card. داده: data/full = gunzip از data/mt5_full (۱۵.۶ سال).
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

OUT = 'results/_s1522'
CARDS = ['XAUUSD_H8', 'XAUUSD_H12', 'XAUUSD_D1', 'XAUUSD_H6']
N_TRIALS = 8
L_FIT = 90       # منجمد
Z_THR = 2.5      # منجمد


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def resid_z(close, L=L_FIT):
    c = np.asarray(close, float)
    n = len(c)
    x = np.arange(L, dtype=float)
    xm = x.mean()
    sxx = ((x - xm) ** 2).sum()
    z = np.full(n, np.nan)
    for t in range(L - 1, n):
        y = c[t - L + 1:t + 1]
        ym = y.mean()
        b = ((x - xm) * (y - ym)).sum() / sxx
        a = ym - b * xm
        res = y - (a + b * x)
        s = res[:-1].std(ddof=2)
        if s > 0:
            z[t] = res[-1] / s
    return pd.Series(z)


def signals_escape(df):
    z = resid_z(df['close'].values)
    z.index = df.index
    esc = (z >= Z_THR).fillna(False)
    return esc & ~esc.shift(1).fillna(False)


def main():
    cards = [a for a in sys.argv[1:] if a.startswith('XAUUSD')] or CARDS
    os.makedirs(OUT, exist_ok=True)
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')
    NM = _mod('tools/s382_null_model.py', '_nm')
    MTF = _mod('tools/s382_mtf_runner.py', '_mtf')
    MTF.N_TRIALS = N_TRIALS

    def load_full(card):
        path = f'data/full/{card}.csv'
        assert os.path.exists(path), f'{path} missing — gunzip from data/mt5_full first'
        df = pd.read_csv(path)
        df['dt'] = pd.to_datetime(df['time'], unit='s')
        return df

    L.load = load_full
    L.signals = signals_escape

    print(f'S1522 regression-channel escape | OLS L={L_FIT}, z_res>={Z_THR}, fresh edge, LONG | '
          f'sl_k={L.SL_K} rr={L.RR} | UNCONDITIONAL null k={NM.K} n_trials={N_TRIALS}', flush=True)
    for card in cards:
        try:
            r = MTF.run_card(card, L, NM)
        except Exception as e:
            print(f'{card}: ERROR {e}', flush=True)
            continue
        r['l_fit'] = L_FIT
        r['z_thr'] = Z_THR
        r['null'] = 'unconditional'
        r['data_src'] = f'data/full/{card}.csv (gunzip of data/mt5_full)'
        with open(f'{OUT}/{card}.json', 'w') as f:
            json.dump(r, f, ensure_ascii=False, default=str)
        print(f'{card}: span={r.get("span_years")}y n={r.get("n_trades")} sl={r.get("sl_pip")}pip '
              f'wr={r.get("wr")} be={r.get("be")} lift={r.get("lift")} unc={r.get("uncond_wr")} '
              f'pmax={r.get("perm_max")} z={r.get("z")} rqs2={r.get("rqs2")} verdict={r.get("verdict")}',
              flush=True)
        print(f'  saved -> {OUT}/{card}.json', flush=True)


if __name__ == '__main__':
    main()
