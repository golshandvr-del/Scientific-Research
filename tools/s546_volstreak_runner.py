# -*- coding: utf-8 -*-
"""S546 — رانرِ Volume-Streak Advance روی خانوادهٔ ۱۱-کارتیِ XAUUSD (دادهٔ کامل).

پیش‌ثبت: `results/S546_PREREG_VOLUME_STREAK_ADVANCE_XAUUSD_MTF.md`
(commit شده **قبل** از این فایل — n_trials=66).

صفر بازنویسی (میراث S520/S541..S545):
  • شبیه‌ساز/ATR/pip: عیناً `strategies/s382_williamsr_momentum.py`
  • مدل صفر: عیناً `tools/s382_null_model.py` (K=2000)
  • داوری per-card: عیناً `run_card` از `tools/s382_mtf_runner.py`

وصله‌های مجاز (قفل در پیش‌ثبت):
  ۱) L.signals → رگهٔ حجم صعودی ۳باره + پیشروی قیمت (R=3، پیشروی خالص)
  ۲) L.load   → data/full/{card}.csv؛ استثنای H4 = data/XAUUSD_H4.csv
  ۳) MTF.SEED=20260824، MTF.N_TRIALS=66
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

OUT = 'results/_s546'
SEED = 20260824
N_TRIALS = 66      # ۱۱ کارت × ۶ واریانت ذهنی (R×قید پیشروی)

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
    """رگهٔ حجم صعودی ۳باره + پیشروی خالص قیمت — LONG (قانون S522)."""
    v = df['volume'].to_numpy(float)
    c = df['close'].to_numpy(float)
    n = len(df)
    sig = np.zeros(n, dtype=bool)
    # v[t] > v[t-1] > v[t-2]  و  c[t] > c[t-3]
    sig[3:] = (v[3:] > v[2:-1]) & (v[2:-1] > v[1:-2]) & (c[3:] > c[:-3])
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
        if (df['volume'] <= 0).mean() > 0.001:
            raise RuntimeError(f'BUG-VOLZERO: volume zeros >0.1% for {card}')
        return df

    L.load = load_full
    MTF.SEED = SEED
    MTF.N_TRIALS = N_TRIALS

    for card in HEADLINE + REPORT_ONLY:
        tag = 'REPORT-ONLY' if card in REPORT_ONLY else 'HEADLINE'
        print(f'\n===== S546 [{tag}] {card} =====', flush=True)
        try:
            res = MTF.run_card(card, L, NM)
        except Exception as e:  # noqa: BLE001
            res = {'card': card, 'error': str(e)}
            print(f'  [ERROR] {e}', flush=True)
        with open(f'{OUT}/{card}.json', 'w') as f:
            json.dump(res, f, ensure_ascii=False, indent=1, default=str)
        print(f'  [SAVED] {OUT}/{card}.json', flush=True)

    print('\nS546 ALL CARDS DONE', flush=True)


if __name__ == '__main__':
    main()
