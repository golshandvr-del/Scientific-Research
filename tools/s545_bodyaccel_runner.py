# -*- coding: utf-8 -*-
"""S545 — رانرِ Body-Acceleration روی خانوادهٔ ۱۱-کارتیِ XAUUSD (دادهٔ کامل).

پیش‌ثبت: `results/S545_PREREG_BODY_ACCELERATION_XAUUSD_MTF.md`
(commit شده **قبل** از این اجرا — مسیر B، n_trials=66).

صفر بازنویسی (میراث S520/S541..S544):
  • شبیه‌ساز/ATR/pip: عیناً `strategies/s382_williamsr_momentum.py`
  • مدل صفر: عیناً `tools/s382_null_model.py` (K=2000)
  • داوری per-card: عیناً `run_card` از `tools/s382_mtf_runner.py`

وصله‌های مجاز (قفل در پیش‌ثبت):
  ۱) L.signals → سه کندل صعودی با بدنه‌های اکیداً بزرگ‌شونده (R=3, k=0)
  ۲) L.load   → data/full/{card}.csv؛ استثنای H4 = data/XAUUSD_H4.csv
  ۳) MTF.SEED=20260823، MTF.N_TRIALS=66
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
os.chdir(ROOT)

OUT = 'results/_s545'
SEED = 20260823
N_TRIALS = 66      # ۱۱ کارت × ۶ واریانت ذهنی (R×k)

HEADLINE = ['XAUUSD_M15', 'XAUUSD_M20', 'XAUUSD_M30', 'XAUUSD_H1',
            'XAUUSD_H2', 'XAUUSD_H3', 'XAUUSD_H4', 'XAUUSD_H6',
            'XAUUSD_H8', 'XAUUSD_H12', 'XAUUSD_D1']
REPORT_ONLY = ['XAUUSD_W1']


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def make_signals(df):
    """سه کندل صعودی با بدنه‌های اکیداً بزرگ‌شونده — LONG در کلوز سومی."""
    o = df['open'].to_numpy(float)
    c = df['close'].to_numpy(float)
    b = c - o
    n = len(df)
    sig = np.zeros(n, dtype=bool)
    sig[2:] = (b[:-2] > 0) & (b[1:-1] > b[:-2]) & (b[2:] > b[1:-1])
    return pd.Series(sig, index=df.index)


def main():
    os.makedirs(OUT, exist_ok=True)
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')
    NM = _mod('tools/s382_null_model.py', '_nm')
    MTF = _mod('tools/s382_mtf_runner.py', '_mtf')

    L.signals = make_signals

    def load_full(card):
        path = f'data/{card}.csv' if card == 'XAUUSD_H4' else f'data/full/{card}.csv'
        df = pd.read_csv(path)
        df['dt'] = pd.to_datetime(df['time'], unit='s')
        span = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days / 365.25
        print(f'  [DATA] {path} rows={len(df)} '
              f'{df["dt"].iloc[0].date()} → {df["dt"].iloc[-1].date()} '
              f'({span:.2f}y)', flush=True)
        if span < 14.0:
            raise RuntimeError(f'BUG-DATASETDRIFT: span {span:.2f}y < 14y for {card}')
        return df

    L.load = load_full
    MTF.SEED = SEED
    MTF.N_TRIALS = N_TRIALS

    cards = sys.argv[1:] or (HEADLINE + REPORT_ONLY)
    print(f'S545 Body-Acceleration | R=3 k=0 frozen | side=long | '
          f'geometry: sl=1.5xATR(100) rr={L.RR} | data=full 15.6y | '
          f'k={MTF.K} seed={SEED} n_trials={N_TRIALS}', flush=True)
    for card in cards:
        tag = ' [REPORT-ONLY]' if card in REPORT_ONLY else ''
        print(f'--- {card}{tag} ---', flush=True)
        try:
            r = MTF.run_card(card, L, NM)
        except Exception as e:
            print(f'{card}: ERROR {e}', flush=True)
            continue
        r['report_only'] = card in REPORT_ONLY
        with open(f'{OUT}/{card}.json', 'w') as f:
            json.dump(r, f, ensure_ascii=False, default=str)
        print(f'{card}: span={r.get("span_years")}y n={r.get("n_trades")} '
              f'sl={r.get("sl_pip")}pip wr={r.get("wr")} be={r.get("be")} '
              f'lift={r.get("lift")} unc={r.get("uncond_wr")} '
              f'pmax={r.get("perm_max")} z={r.get("z")} rqs2={r.get("rqs2")} '
              f'verdict={r.get("verdict")}{tag}', flush=True)
        print(f'  saved -> {OUT}/{card}.json', flush=True)


if __name__ == '__main__':
    main()
