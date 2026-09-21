# -*- coding: utf-8 -*-
"""S932 — رکوردِ تازهٔ کف (پایهٔ منجمد S1511) × گیتِ کندلِ مطلع ρ≥0.618 (اهرمِ منجمد S1520).

پیش‌ثبت: results/S932_PREREG_informed_fresh_floor.md (کامیت eb24a222، قبل از این کد).
هارنس عیناً tools/s1520_informed_fresh_high_runner.py؛ تنها تغییر: تابعِ رویداد (fresh_high → fresh_floor از S1511).
حالت‌ها: base (گیت خاموش — گاردِ G0: باید S1511-H6 را بازتولید کند) | gated (ρ≥0.618) | counter (ρ<0.618).
نول شرطی‌شده در فضای درفت>0 (همان S1511/S526) — تا lift گیت‌شده با پایه هم‌مقیاس باشد.
داده: فقط data/mt5_full (گاردِ E-16).
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

OUT = 'results/_s932'
TFS_ALL = ['M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20', 'M30',
           'H1', 'H2', 'H3', 'H4', 'H6', 'H8', 'H12', 'D1', 'W1', 'MN1']
N_TRIALS = 114      # تجمعیِ بلوک S930–S939 (19×2 × 3 لایه)
LOOKBACK = 90       # منجمد S526/S1511
RHO_THR = 0.618     # منجمد S965/S1520
SEED = 20260905


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


def fresh_floor(df):
    """عیناً S1511.sig_fresh: low > max(low[t−90..t−1])، لبهٔ تازه، درفت>0."""
    lo = df['low']
    ff = _b(lo > lo.rolling(LOOKBACK).max().shift(1))
    return ff & ~ff.shift(1, fill_value=False) & drift_mask(df)


def rho(df):
    rng = (df['high'] - df['low']).replace(0, np.nan)
    return ((df['close'] - df['open']) / rng).fillna(0.0)


def verify_signals(n=6000, seed=3):
    rng = np.random.default_rng(seed)
    c = 1800 + np.cumsum(rng.normal(0, 3, n))
    o = np.concatenate([[c[0]], c[:-1]])
    h = np.maximum(o, c) + np.abs(rng.normal(0, 2, n))
    l = np.minimum(o, c) - np.abs(rng.normal(0, 2, n))
    z = rng.choice(n, 20, replace=False); h[z] = l[z] = o[z] = c[z]
    df = pd.DataFrame(dict(open=o, high=h, low=l, close=c))
    # مرجعِ مستقل با حلقه
    ref = np.zeros(n, bool)
    for i in range(LOOKBACK, n):
        st = l[i] > l[i - LOOKBACK:i].max()
        st_prev = l[i - 1] > l[i - 1 - LOOKBACK:i - 1].max() if i - 1 >= LOOKBACK else False
        dr = c[i - 1] - c[i - LOOKBACK] > 0
        ref[i] = st and (not st_prev) and dr
    got = fresh_floor(df).to_numpy()
    diff = int(np.sum(ref != got))
    r = rho(df).to_numpy()
    ok_rho = np.all(np.isfinite(r)) and np.all(r[z] == 0.0) and np.all(np.abs(r) <= 1.0 + 1e-12)
    print(f'  fresh_floor vs loop-reference diffs={diff}  events={int(got.sum())}  rho finite/zero-range ok={bool(ok_rho)}')
    return diff == 0 and bool(ok_rho)


def main():
    args = sys.argv[1:]
    if args and args[0] == 'verify':
        sys.exit(0 if verify_signals() else 1)
    mode = args[0] if args and args[0] in ('base', 'gated', 'counter') else 'gated'
    tfs = [a for a in args if a in TFS_ALL] or TFS_ALL
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

    def signals(df):
        base = fresh_floor(df)
        if mode == 'base':
            sig = base
        else:
            r = rho(df)
            g = (r >= RHO_THR) if mode == 'gated' else (r < RHO_THR)
            sig = base & g
        print(f'  gate pass-rate: {int(sig.sum())}/{int(base.sum())} '
              f'({100.0 * sig.sum() / max(1, base.sum()):.1f}%) mode={mode}', flush=True)
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

    def perm_cond(L_, df, sl_abs, ps, n_sig, k=NM.K, seed=SEED):
        rng = np.random.default_rng(seed)
        n = len(df)
        m = drift_mask(df).to_numpy()
        valid = np.where(m[200:n - 2])[0] + 200
        # کارت‌های ریز (M1..M5): K=2000 با شبیه‌سازِ pandas بسیار سنگین است؛ K=500 (کفِ پیش‌ثبتِ بلوک)
        kk = 500 if n > 1_000_000 else k
        wrs = []
        for _ in range(kk):
            pos = rng.choice(valid, size=min(n_sig, len(valid)), replace=False)
            sig = pd.Series(False, index=df.index)
            sig.iloc[np.sort(pos)] = True
            tr = L_.simulate_trades(df, sig, sl_abs, L_.RR, True, ps)
            if len(tr) >= 30:
                wrs.append(100.0 * float((tr['outcome'] == 'win').mean()))
        a = np.asarray(wrs, float)
        if a.size == 0:
            return dict(mean=None, sd=None, max=None, min=None, p95=None, k=0)
        return dict(mean=float(a.mean()), sd=float(a.std(ddof=1)) if a.size > 1 else None,
                    max=float(a.max()), min=float(a.min()),
                    p95=float(np.percentile(a, 95)), k=int(len(a)))

    NM.uncond_baseline = uncond_cond
    NM.perm_baseline = perm_cond

    print(f'S932 informed fresh-floor({LOOKBACK}) x rho>={RHO_THR} [{mode}] | sl_k={L.SL_K} rr={L.RR} '
          f'side=long | conditioned null (drift>0) k={NM.K} n_trials={N_TRIALS} seed={SEED}', flush=True)
    for tf in tfs:
        card = f'XAUUSD_{tf}'
        try:
            r = MTF.run_card(card, L, NM)
        except Exception as e:
            print(f'{card}: ERROR {e}', flush=True)
            r = dict(card=card, verdict='ERROR', error=str(e))
        r['lookback'] = LOOKBACK; r['rho_thr'] = RHO_THR; r['mode'] = mode; r['seed'] = SEED
        with open(f'{OUT}/{card}_{mode}.json', 'w') as f:
            json.dump(r, f, ensure_ascii=False, default=str)
        print(f'{card} [{mode}]: span={r.get("span_years")}y n={r.get("n_trades")} '
              f'sl={r.get("sl_pip")}pip wr={r.get("wr")} be={r.get("be")} '
              f'lift={r.get("lift")} unc={r.get("uncond_wr")} pmax={r.get("perm_max")} '
              f'z={r.get("z")} rqs2={r.get("rqs2")} verdict={r.get("verdict")}', flush=True)


if __name__ == '__main__':
    main()
