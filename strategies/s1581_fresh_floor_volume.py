# -*- coding: utf-8 -*-
"""S1581 — کفِ تازهٔ ۹۰ (S1511، منجمد) × گیتِ حجمِ نسبیِ هم‌اسلات RVOL_slot≥1.0 (S589، منجمد) · XAUUSD · H6/H8/H4

پیش‌ثبت: results/S1581_PREREG_VOLUME_CONFIRMED_FRESH_FLOOR.md (کامیت c5663c08، قبل از این کد).
هارنس عیناً strategies/s1511_fresh_floor.py (← S526/S382)؛ تنها تغییر: افزودنِ گیت RVOL به سیگنال.
حالت‌ها: gated (RVOL≥1) | counter (RVOL<1) | ungated (=S1511 خام روی همین داده، P1).
داده: data/mt5_full فقط (هارد-گارد). فقط اکتشاف — هیچ استقراری.
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

OUT = 'results/_s1581'
TFS = ['H6', 'H8', 'H4']
CARDS = [f'XAUUSD_{tf}' for tf in TFS]
N_TRIALS = 3
LOOKBACK = 90          # منجمد S950/S523/S526/S1511
SEED = 20260905        # همان S1511 (هم‌مقیاسی نول)
RVOL_THR, SLOT_WIN, SLOT_MINP = 1.0, 30, 20   # منجمد S589


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


def rvol_slot(df):
    v = df['volume'].astype(float)
    hour = df['dt'].dt.hour
    ref = v.groupby(hour).transform(
        lambda s: s.shift(1).rolling(SLOT_WIN, min_periods=SLOT_MINP).median())
    return v / ref.replace(0, np.nan)


def make_signals(mode):
    def signals(df):
        base = sig_fresh(df)
        rv = rvol_slot(df)
        ok = rv.notna()
        if mode == 'gated':
            sig = base & ok & (rv >= RVOL_THR)
        elif mode == 'counter':
            sig = base & ok & (rv < RVOL_THR)
        else:
            sig = base & ok
        b = base & ok
        print(f'  [{mode}] events={int(b.sum())} pass={int((b & (rv >= RVOL_THR)).sum())} '
              f'pass_rate={100.0 * (b & (rv >= RVOL_THR)).sum() / max(1, b.sum()):.1f}% '
              f'rvol_median_at_events={float(rv[b].median()):.3f} n_sig={int(sig.sum())}', flush=True)
        return sig
    return signals


def main():
    mode = 'gated'
    stress = False
    args = []
    for a in sys.argv[1:]:
        if a in ('gated', 'counter', 'ungated'):
            mode = a
        elif a == '--stress':
            stress = True
        else:
            args.append(a)
    cards = args or CARDS
    os.makedirs(OUT, exist_ok=True)
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')
    NM = _mod('tools/s382_null_model.py', '_nm')
    MTF = _mod('tools/s382_mtf_runner.py', '_mtf')
    n_trials = 50 if stress else N_TRIALS
    MTF.N_TRIALS = n_trials
    MTF.SEED = SEED
    NM.SEED = SEED

    def load_full(card):
        path = f'data/mt5_full/{card}.csv'
        assert 'mt5_full' in path and os.path.exists(path), f'E-16 GUARD: {path}'
        df = pd.read_csv(path)
        df['dt'] = pd.to_datetime(df['time'], unit='s')
        span = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days / 365.25
        assert span > 12.0, f'BUG-DATASETDRIFT {card}: {span:.2f}y'
        assert 'volume' in df.columns, 'BUG-NOVOLUME'
        return df

    L.load = load_full
    L.signals = make_signals(mode)

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

    print(f'S1581 fresh-floor(90) x RVOL_slot>={RVOL_THR} [{mode}] | sl_k={L.SL_K} rr={L.RR} side=long | '
          f'conditioned null (drift>0) k={NM.K} seed={SEED} n_trials={n_trials}', flush=True)
    for card in cards:
        try:
            r = MTF.run_card(card, L, NM)
        except Exception as e:
            print(f'{card}: ERROR {e}', flush=True)
            continue
        r.update(lookback=LOOKBACK, rvol_thr=RVOL_THR, slot_win=SLOT_WIN, mode=mode, stress=stress)
        fn = f'{OUT}/{card}_{mode}{"_stress50" if stress else ""}.json'
        with open(fn, 'w') as f:
            json.dump(r, f, ensure_ascii=False, default=str)
        print(f'{card} [{mode}]: span={r.get("span_years")}y n={r.get("n_trades")} '
              f'sl={r.get("sl_pip")}pip wr={r.get("wr")} be={r.get("be")} '
              f'lift={r.get("lift")} unc={r.get("uncond_wr")} pmax={r.get("perm_max")} '
              f'z={r.get("z")} rqs2={r.get("rqs2")} verdict={r.get("verdict")}', flush=True)
        print(f'  saved -> {fn}', flush=True)


if __name__ == '__main__':
    main()
