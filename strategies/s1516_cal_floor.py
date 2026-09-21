# -*- coding: utf-8 -*-
"""S1516 — رکوردِ تازهٔ کف با پنجرهٔ تقویم‌همتا (۳۰ روز معاملاتی) ⇒ LONG | H4(180)/H6(120)/H3(240).

پیش‌ثبت: `results/S1516_PREREG_CALENDAR_MATCHED_FRESH_FLOOR.md` (کامیت 00ee7d3d — **قبل** از هر عدد).
رویداد: ff = low[t] > max(low[t−L..t−1])، L={H4:180,H6:120,H3:240}؛ سیگنال = ff & ~ff.shift(1) & driftL>0
هندسه: SL=1.5×median(ATR100)، TP=1.5×SL (عیناً S526). نول شرطی در فضای دریفت-مثبت.
هارنس عیناً S1510/S526 (tools/s382_*). داده mt5_full با هارد-گارد E-16.
n_trials=10. SEED=20260910, K=2000.
تشخیصی (بدون داوری): بازوی ۹۰-کندلیِ خام روی همان کارت (P3).
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

OUT = 'results/_scan_S1516'
TFS = ['H4', 'H6', 'H3']
L_CAL = {'H4': 180, 'H6': 120, 'H3': 240}  # ۳۰ روز معاملاتی (قانون S1523)
CARDS = [f'XAUUSD_{tf}' for tf in TFS]
N_TRIALS = 10
LOOKBACK = 90  # مقدار پیش‌فرض؛ در main به‌ازای کارت روی L_CAL تنظیم می‌شود
SEED = 20260910


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _b(s):
    return s.astype('boolean').fillna(False).astype(bool)


def drift_mask(df):
    c = df['close']
    return _b((c.shift(1) - c.shift(LOOKBACK)) > 0)


def ff_state(df):
    lo = df['low']
    return _b(lo > lo.rolling(LOOKBACK).max().shift(1))


def sig_fresh(df):
    ff = ff_state(df)
    return ff & ~ff.shift(1, fill_value=False) & drift_mask(df)


def sig_raw90(df):  # P3: بازوی ۹۰-کندلیِ خام (تشخیصی)
    lo = df['low']; c = df['close']
    ff = _b(lo > lo.rolling(90).max().shift(1))
    d = _b((c.shift(1) - c.shift(90)) > 0)
    return ff & ~ff.shift(1, fill_value=False) & d


def main():
    os.makedirs(OUT, exist_ok=True)
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')
    NM = _mod('tools/s382_null_model.py', '_nm')
    MTF = _mod('tools/s382_mtf_runner.py', '_mtf')
    MTF.N_TRIALS = N_TRIALS
    MTF.SEED = SEED
    NM.SEED = SEED

    def load_full(card):
        path = f'data/mt5_full/{card}.csv'
        assert 'mt5_full' in path and os.path.exists(path), f'E-16 GUARD: {path}'
        df = pd.read_csv(path)
        df['dt'] = pd.to_datetime(df['time'], unit='s')
        return df

    L.load = load_full
    L.signals = sig_fresh

    def uncond_cond(L_, df, sl_abs, ps, stride):
        m = drift_mask(df).to_numpy()
        idx = np.where(m)[0][::stride]
        sig = pd.Series(False, index=df.index)
        sig.iloc[idx] = True
        tr = L_.simulate_trades(df, sig, sl_abs, L_.RR, True, ps)
        if len(tr) == 0:
            return None, 0
        return 100.0 * float((tr['outcome'] == 'win').mean()), len(tr)

    def perm_cond(L_, df, sl_abs, ps, n_sig, k=NM.K, seed=SEED):
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

    def diag(df, sigfn, sl_abs, ps, be):
        tr = L.simulate_trades(df, sigfn(df), sl_abs, L.RR, True, ps)
        if len(tr) >= 30:
            wr = 100.0 * float((tr['outcome'] == 'win').mean())
            return dict(n=int(len(tr)), wr=round(wr, 2), lift=round(wr - be, 2))
        return dict(n=int(len(tr)), wr=None, lift=None)

    cards = sys.argv[1:] or CARDS
    print(f'S1516 calendar-matched fresh-floor | L={L_CAL} | fresh edge, driftL>0 | '
          f'sl_k={L.SL_K} rr={L.RR} side=long | conditioned null k={NM.K} seed={SEED} '
          f'n_trials={N_TRIALS}', flush=True)
    global LOOKBACK
    for card in cards:
        LOOKBACK = L_CAL[card.split('_')[1]]
        try:
            r = MTF.run_card(card, L, NM)
            df = L.load(card)
            ps = L.pip_size(card.split('_')[0])
            sl_abs = float(np.nanmedian(L.atr(df).to_numpy())) * L.SL_K
            sl_pip = sl_abs / ps
            be = 100.0 * (sl_pip + 3.3) / (sl_pip * L.RR + sl_pip)
            r['p3_raw90'] = diag(df, sig_raw90, sl_abs, ps, be)
            r['L'] = LOOKBACK
            r['n_event'] = int(sig_fresh(df).sum())
        except Exception as e:
            print(f'{card}: ERROR {e}', flush=True)
            continue
        r['lookback'] = LOOKBACK
        with open(f'{OUT}/{card}.json', 'w') as f:
            json.dump(r, f, ensure_ascii=False, default=str)
        print(f'{card}: span={r.get("span_years")}y n={r.get("n_trades")} '
              f'sl={r.get("sl_pip")}pip wr={r.get("wr")} be={r.get("be")} '
              f'lift={r.get("lift")} unc={r.get("uncond_wr")} '
              f'pmax={r.get("perm_max")} z={r.get("z")} pf={r.get("pf")} '
              f'rqs2={r.get("rqs2")} verdict={r.get("verdict")} '
              f'L={LOOKBACK} raw90={r.get("p3_raw90")}',
              flush=True)


if __name__ == '__main__':
    main()
