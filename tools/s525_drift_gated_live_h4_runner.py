# -*- coding: utf-8 -*-
"""S525 — گیتِ درفت S950 روی کارتِ زندهٔ S382 (XAUUSD-H4) + کنترل ضد-درفت.

پیش‌ثبت: `results/S525_PREREG_DriftGatedWPR_LiveH4_Xauusd_H4.md`
(کامیت 8159f0e3 — قبل از این اجرا؛ صفر پارامتر آزاد).

هارنس عیناً از s523_drift_gated_runner.py — تنها تفاوت‌ها:
  - CARDS = [XAUUSD_H4] (کارت زندهٔ S382، data/XAUUSD_H4.csv کامل ۱۵.۵۳y)
  - N_TRIALS = 23783 (وراثت صادقانه: 23773 + 5 S524 + 2 این آزمایش +3 s523 دوباره‌شماری‌نشده)
  - MODE از argv: 'gated' (drift>0) یا 'anti' (drift<=0 — کنترل علمی، فقط تفسیر)
نول شرطی‌شده در فضای همان گیت (قانون S523).
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

OUT = 'results/_s525'
CARD = 'XAUUSD_H4'
N_TRIALS = 23783
DRIFT_LOOKBACK = 90   # منجمد S950/S523


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'gated'   # gated | anti
    assert mode in ('gated', 'anti')
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

    def gate_mask(df):
        c = df['close']
        drift = ((c.shift(1) - c.shift(DRIFT_LOOKBACK)) > 0).fillna(False)
        if mode == 'gated':
            return drift
        # anti: درفت نامثبت، اما warm-up (NaN) همچنان حذف
        warm = c.shift(DRIFT_LOOKBACK).notna() & c.shift(1).notna()
        return (~drift) & warm

    def signals_gated(df):
        w = L.willr(df)
        cross = (w.shift(1) <= L.WILLR_THR) & (w > L.WILLR_THR)
        return cross & gate_mask(df)

    L.signals = signals_gated

    # نول شرطی‌شده — نمونه‌گیری فقط در فضای همان گیت (قانون S523)
    def uncond_cond(L_, df, sl_abs, ps, stride):
        m = gate_mask(df).to_numpy()
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
        m = gate_mask(df).to_numpy()
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

    print(f'S525 mode={mode} | WPR cross>{L.WILLR_THR} AND drift'
          f'{">0" if mode == "gated" else "<=0"} (L={DRIFT_LOOKBACK}) | '
          f'card={CARD} | conditioned null k={NM.K} n_trials={N_TRIALS}',
          flush=True)
    r = MTF.run_card(CARD, L, NM)
    r['drift_lookback'] = DRIFT_LOOKBACK
    r['mode'] = mode
    with open(f'{OUT}/{CARD}_{mode}.json', 'w') as f:
        json.dump(r, f, ensure_ascii=False, default=str)
    print(f'{CARD} [{mode}]: span={r.get("span_years")}y n={r.get("n_trades")} '
          f'sl={r.get("sl_pip")}pip wr={r.get("wr")} be={r.get("be")} '
          f'lift={r.get("lift")} unc={r.get("uncond_wr")} '
          f'pmax={r.get("perm_max")} z={r.get("z")} '
          f'rqs2={r.get("rqs2")} verdict={r.get("verdict")}', flush=True)
    print(f'  saved -> {OUT}/{CARD}_{mode}.json', flush=True)


if __name__ == '__main__':
    main()
