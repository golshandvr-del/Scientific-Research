# -*- coding: utf-8 -*-
"""S589 — سقفِ تازهٔ ۹۰-کندلی (پایهٔ منجمد S526) × گیتِ حجمِ نسبیِ هم‌اسلات RVOL_slot ≥ 1.0.

پیش‌ثبت: results/S589_PREREG_VOLUME_CONFIRMED_FRESH_HIGH.md (کامیت 85459a43، قبل از این کد).
هارنس عیناً tools/s1520_informed_fresh_high_runner.py (که خود عیناً s526 بود)؛
تنها تغییر: گیت ρ → گیت RVOL_slot (حجم / میانهٔ ۳۰ کندلِ قبلیِ همان ساعتِ روز، shift(1)).
حالت‌ها: gated (RVOL≥1.0) | counter (RVOL<1.0) — برای ابطال‌گر P2.
نول شرطی‌شده در فضای درفت>0 (همان S526/S1520) — تا lift با پایه هم‌مقیاس باشد.
لایه‌های S526/S1520 دست‌نخورده می‌مانند؛ فقط از قواعد کامیت‌شده‌شان ارث می‌بریم.
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

OUT = 'results/_s589'
CARDS = ['XAUUSD_H8', 'XAUUSD_H4', 'XAUUSD_H12']
N_TRIALS = 6
LOOKBACK = 90       # منجمد S526
RVOL_THR = 1.0      # متعارف «above-median volume» — قفل در پیش‌ثبت
SLOT_WIN = 30       # ۳۰ رخداد قبلی همان اسلات (≈۹۰ کندل H8)
SLOT_MINP = 20


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


def rvol_slot(df):
    """حجم نسبی هم‌اسلات: volume[t] / median(volume of previous SLOT_WIN bars
    sharing the same hour-of-day). فقط گذشته (shift(1) درون گروه)."""
    v = df['volume'].astype(float)
    hour = df['dt'].dt.hour
    ref = v.groupby(hour).transform(
        lambda s: s.shift(1).rolling(SLOT_WIN, min_periods=SLOT_MINP).median())
    return (v / ref.replace(0, np.nan))


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
        assert 'volume' in df.columns, 'BUG-NOVOLUME: volume column missing'
        return df

    L.load = load_full

    def signals(df):
        base = fresh_high(df)
        rv = rvol_slot(df)
        ok = rv.notna()
        g = (rv >= RVOL_THR) if mode == 'gated' else (rv < RVOL_THR)
        sig = base & g & ok
        base_ok = base & ok
        print(f'  gate pass-rate: {int(sig.sum())}/{int(base_ok.sum())} '
              f'({100.0 * sig.sum() / max(1, base_ok.sum()):.1f}%) mode={mode} '
              f'| rvol median at events={float(rv[base_ok].median()):.3f}', flush=True)
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

    print(f'S589 volume-confirmed fresh-high(90) x RVOL_slot>={RVOL_THR} [{mode}] | '
          f'sl_k={L.SL_K} rr={L.RR} side=long | conditioned null (drift>0) k={NM.K} '
          f'n_trials={N_TRIALS}', flush=True)
    for card in cards:
        try:
            r = MTF.run_card(card, L, NM)
        except Exception as e:
            print(f'{card}: ERROR {e}', flush=True)
            continue
        r['lookback'] = LOOKBACK
        r['rvol_thr'] = RVOL_THR
        r['slot_win'] = SLOT_WIN
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
