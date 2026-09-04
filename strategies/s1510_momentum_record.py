# -*- coding: utf-8 -*-
"""S1510 — رکوردِ تازهٔ مومنتوم ۱۳-باری، هم‌راستا با دریفت ⇒ LONG | هر ۱۹ TF.

پیش‌ثبت: `results/S1510_PREREG_MOMENTUM_RECORD_CONTINUATION.md` (کامیت 6ca34f74 —
**قبل** از هر عدد). مسیر B، صفر پارامتر آزاد.

رویداد: mom = close − close.shift(13)؛ rec = mom > rolling_max(mom, 90).shift(1)
سیگنال = rec & ~rec.shift(1) & (mom>0) & (drift90>0)  — فقط لبهٔ تازه (قانون S963)
هندسه: SL=1.5×median(ATR100)، TP=1.5×SL (عیناً S526). نول شرطی در فضای دریفت-مثبت.
هارنس عیناً از tools/s526_fresh_high_runner.py؛ داده mt5_full با هارد-گارد E-16.
n_trials=24. SEED=20260904, K=2000.
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

OUT = 'results/_scan_S1510'
TFS = ['MN1', 'W1', 'D1', 'H12', 'H8', 'H6', 'H3', 'H2', 'H1',
       'M30', 'M20', 'M15', 'M12', 'M10', 'M6', 'M5', 'M4', 'M3', 'M1']
CARDS = [f'XAUUSD_{tf}' for tf in TFS]
N_TRIALS = 24
K_MOM = 13     # منجمد (فیبوناچی)
LOOKBACK = 90  # منجمد S950/S523/S526
SEED = 20260904


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
    MTF.SEED = SEED
    NM.SEED = SEED

    def load_full(card):
        path = f'data/mt5_full/{card}.csv'
        assert 'mt5_full' in path and os.path.exists(path), f'E-16 GUARD: {path}'
        df = pd.read_csv(path)
        df['dt'] = pd.to_datetime(df['time'], unit='s')
        return df

    L.load = load_full

    # سیگنال: رکورد تازهٔ مومنتوم، مثبت، دریفت-مثبت (همه منجمد در پیش‌ثبت)
    def signals_mom_record(df):
        c = df['close']
        mom = c - c.shift(K_MOM)
        prior_max = mom.rolling(LOOKBACK).max().shift(1)
        rec = (mom > prior_max).fillna(False)
        fresh = rec & ~rec.shift(1).fillna(False)
        return fresh & (mom > 0) & drift_mask(df)

    L.signals = signals_mom_record

    # بازوی پایهٔ P1: همان شرایط منهای شرط رکورد (mom>0 & drift & لبهٔ تازهٔ mom>0)
    def signals_p1_base(df):
        c = df['close']
        mom = c - c.shift(K_MOM)
        pos = (mom > 0).fillna(False)
        fresh = pos & ~pos.shift(1).fillna(False)
        return fresh & drift_mask(df)

    # نول شرطی‌شده در فضای دریفت-مثبت (عیناً S526)
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

    cards = sys.argv[1:] or CARDS
    print(f'S1510 mom-record | mom{K_MOM} > max(mom,{LOOKBACK}).shift(1), fresh edge, '
          f'mom>0, drift>0 | sl_k={L.SL_K} rr={L.RR} side=long | '
          f'conditioned null (drift>0) k={NM.K} seed={SEED} n_trials={N_TRIALS}',
          flush=True)
    for card in cards:
        try:
            r = MTF.run_card(card, L, NM)
            # اندازه‌گیری P1 (تشخیصی — بدون داوری موتور): پایه بدون شرط رکورد
            df = L.load(card)
            ps = L.pip_size(card.split('_')[0])
            sl_abs = float(np.nanmedian(L.atr(df).to_numpy())) * L.SL_K
            sl_pip = sl_abs / ps
            be = 100.0 * (sl_pip + 3.3) / (sl_pip * L.RR + sl_pip)
            trb = L.simulate_trades(df, signals_p1_base(df), sl_abs, L.RR, True, ps)
            if len(trb) >= 30:
                wrb = 100.0 * float((trb['outcome'] == 'win').mean())
                r['p1_base'] = dict(n=int(len(trb)), wr=round(wrb, 2),
                                    lift=round(wrb - be, 2))
            else:
                r['p1_base'] = dict(n=int(len(trb)), wr=None, lift=None)
        except Exception as e:
            print(f'{card}: ERROR {e}', flush=True)
            continue
        r['k_mom'] = K_MOM
        r['lookback'] = LOOKBACK
        with open(f'{OUT}/{card}.json', 'w') as f:
            json.dump(r, f, ensure_ascii=False, default=str)
        print(f'{card}: span={r.get("span_years")}y n={r.get("n_trades")} '
              f'sl={r.get("sl_pip")}pip wr={r.get("wr")} be={r.get("be")} '
              f'lift={r.get("lift")} unc={r.get("uncond_wr")} '
              f'pmax={r.get("perm_max")} z={r.get("z")} '
              f'rqs2={r.get("rqs2")} verdict={r.get("verdict")} '
              f'p1_base={r.get("p1_base")}', flush=True)


if __name__ == '__main__':
    main()
