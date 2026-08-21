# -*- coding: utf-8 -*-
"""S542 — رانرِ Hammer Rejection روی خانوادهٔ ۱۱-کارتیِ XAUUSD (دادهٔ کامل).

پیش‌ثبت: `results/S542_PREREG_HAMMER_REJECTION_XAUUSD_MTF.md`
(commit شده **قبل** از این اجرا — مسیر B، n_trials=44).

اصل معماری: صفر بازنویسی (میراث S520/S540/S541). این رانر هیچ منطق
داوری/شبیه‌سازی از خودش ندارد:

  • شبیه‌ساز/ATR/pip: عیناً `strategies/s382_williamsr_momentum.py`
  • مدل صفر: عیناً `tools/s382_null_model.py` (K=2000)
  • داوری per-card: عیناً `run_card` از `tools/s382_mtf_runner.py`

وصله‌های مجاز (هر سه در پیش‌ثبت قفل):
  ۱) L.signals → رویداد چکش (WICK_K=2.0, UPPER_MAX=0.5، منجمد، بدون جارو)
  ۲) L.load   → data/full/{card}.csv؛ استثنای H4 = data/XAUUSD_H4.csv
  ۳) MTF.SEED=20260820، MTF.N_TRIALS=44
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

OUT = 'results/_s542'
WICK_K = 2.0       # فتیلهٔ پایینی ≥ 2×بدنه — منجمد در پیش‌ثبت §2
UPPER_MAX = 0.5    # فتیلهٔ بالایی ≤ 0.5×بدنه — منجمد
SEED = 20260820
N_TRIALS = 44      # ۱۱ کارت × ۴ واریانت ذهنی طراحی

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
    """چکش: lower_wick >= 2×body و upper_wick <= 0.5×body و body>0 — LONG در close."""
    o = df['open'].to_numpy(float)
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    body = np.abs(c - o)
    lower = np.minimum(o, c) - l
    upper = h - np.maximum(o, c)
    sig = (body > 0) & (lower >= WICK_K * body) & (upper <= UPPER_MAX * body)
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
    print(f'S542 Hammer Rejection | wick_k={WICK_K} upper_max={UPPER_MAX} frozen | '
          f'side=long | geometry: sl=1.5xATR(100) rr={L.RR} | data=full 15.6y | '
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
        r['wick_k'] = WICK_K
        r['upper_max'] = UPPER_MAX
        with open(f'{OUT}/{card}.json', 'w') as f:
            json.dump(r, f, ensure_ascii=False, default=str)
        z = r.get('z')
        print(f'{card}: span={r.get("span_years")}y n={r.get("n_trades")} '
              f'sl={r.get("sl_pip")}pip wr={r.get("wr")} be={r.get("be")} '
              f'lift={r.get("lift")} unc={r.get("uncond_wr")} '
              f'pmax={r.get("perm_max")} z={z} rqs2={r.get("rqs2")} '
              f'verdict={r.get("verdict")}{tag}', flush=True)
        print(f'  saved -> {OUT}/{card}.json', flush=True)


if __name__ == '__main__':
    main()
