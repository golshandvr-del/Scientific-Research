# -*- coding: utf-8 -*-
"""S523 — WPR(14)>−13 (رویداد) + دروازهٔ درفت S950 ⇒ LONG | H6/H8/H12.

پیش‌ثبت: `results/S523_PREREG_DriftGatedWPR_Xauusd_H6H8H12.md`
(commit شده قبل از این اجرا — مسیر B، صفر پارامتر آزاد).

دروازهٔ درفت (تعریف منجمد از S950ِ پذیرفته‌شده، علّی):
    drift(i) = close[i−1] − close[i−90] > 0

اصل صفر-بازنویسی — وصله‌های مجاز:
  ۱) L.load → data/full/
  ۲) L.signals → گذرِ S382 AND drift>0 (warm-up: i<90 حذف خودکارِ NaN)
  ۳) مدل صفر **هم‌شرط**: NM.uncond_baseline و NM.perm_baseline بازنویسی
     می‌شوند تا فقط در کندل‌های drift>0 نمونه بگیرند — تعدادِ سیگنالِ
     جایگشت حفظ می‌شود (نمونه‌گیری از فضای معتبر، نه ماسکِ پس‌ازآن)،
     وگرنه مقایسه به نفع سیگنال ناعادلانه می‌شد. K=2000، بذر 20260805،
     stride 1/3/7 سخت‌ترین — عین پروتکل منجمد.

n_trials = 23773 (23770 قبلی + 3 عضو این خانواده).
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

OUT = 'results/_s523'
CARDS = ['XAUUSD_H8', 'XAUUSD_H6', 'XAUUSD_H12']
N_TRIALS = 23773
DRIFT_LOOKBACK = 90   # close[i-1] - close[i-90] — عین S950


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

    # وصلهٔ ۲: سیگنال = گذرِ منجمد S382 و درفت مثبت
    def signals_gated(df):
        w = L.willr(df)
        cross = (w.shift(1) <= L.WILLR_THR) & (w > L.WILLR_THR)
        return cross & drift_mask(df)

    L.signals = signals_gated

    # وصلهٔ ۳: مدل صفر هم‌شرط — نمونه‌گیری فقط از کندل‌های drift>0
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
        valid = np.where(m[200:n - 2])[0] + 200   # همان حاشیهٔ منجمد
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
    print(f'S523 drift-gated WPR | cross>{L.WILLR_THR} AND '
          f'close[i-1]>close[i-{DRIFT_LOOKBACK}] | sl_k={L.SL_K} rr={L.RR} '
          f'side=long | conditioned null (uncond+perm in drift>0 space) '
          f'k={NM.K} n_trials={N_TRIALS}', flush=True)
    for card in cards:
        try:
            r = MTF.run_card(card, L, NM)
        except Exception as e:
            print(f'{card}: ERROR {e}', flush=True)
            continue
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
