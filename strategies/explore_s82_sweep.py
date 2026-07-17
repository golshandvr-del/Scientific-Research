"""
explore_s82_sweep.py — جاروی پارامترهای Rolling Visual-Shape Router برای پایداریِ دو-نیمه
================================================================================
معیار: سودِ خالص + both_halves_positive (طبقِ استانداردِ S67/S81).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from engine import scalp_engine as SE

np.random.seed(42)


def zscore_windows(close, W):
    n = len(close)
    idxs = np.arange(W - 1, n)
    X = np.empty((len(idxs), W), dtype=np.float64)
    for r, i in enumerate(idxs):
        w = close[i - W + 1: i + 1]
        mu = w.mean(); sd = w.std()
        X[r] = 0.0 if sd < 1e-12 else (w - mu) / sd
    return X, idxs


def prep(asset, W, K):
    from sklearn.cluster import KMeans
    cfg = SE.ASSETS[asset]
    df = SE.load_data(cfg['file'])
    close = df['close'].values.astype(np.float64)
    pip = cfg['pip']
    n = len(close)
    X, idxs = zscore_windows(close, W)
    km = KMeans(n_clusters=K, n_init=10, random_state=42)
    lab = km.fit_predict(X)
    lab_full = np.full(n, -1, dtype=int); lab_full[idxs] = lab
    return df, close, pip, n, lab_full


def signals(close, pip, n, lab_full, K, hold, lookback, step,
            long_th, short_th, min_t, min_n):
    fwd = np.full(n, np.nan)
    fwd[:n - hold] = (close[hold:] - close[:n - hold]) / pip
    long_sig = np.zeros(n, bool); short_sig = np.zeros(n, bool)
    first = lookback + hold + 100
    for start in range(first, n, step):
        end = min(start + step, n)
        lb0 = max(0, start - lookback)
        learn_idx = np.arange(lb0, start - hold)
        if len(learn_idx) < 500:
            continue
        edges = {}
        for c in range(K):
            m = learn_idx[lab_full[learn_idx] == c]
            fr = fwd[m]; fr = fr[~np.isnan(fr)]
            if len(fr) >= min_n:
                mean = fr.mean()
                se = fr.std(ddof=1) / np.sqrt(len(fr))
                t = mean / se if se > 0 else 0.0
                edges[c] = (mean, t)
        for i in range(start, end):
            c = lab_full[i]
            if c < 0 or c not in edges:
                continue
            mean, t = edges[c]
            if mean >= long_th and t >= min_t:
                long_sig[i] = True
            elif mean <= -short_th and t <= -min_t:
                short_sig[i] = True
    return long_sig, short_sig


def evaluate(asset, df, close, n, long_sig, short_sig, sl, tp, hold):
    half = n // 2
    tr = SE.simulate_trades(df, long_sig, short_sig, sl, tp, asset, max_hold=hold)
    if len(tr) < 30:
        return None
    s, _ = SE.run_capital(tr, asset, compounding=False)
    tr1 = tr[tr['entry_bar'] < half]; tr2 = tr[tr['entry_bar'] >= half]
    s1, _ = SE.run_capital(tr1, asset, compounding=False)
    s2, _ = SE.run_capital(tr2, asset, compounding=False)
    both = s1['net_profit'] > 0 and s2['net_profit'] > 0
    return dict(s=s, s1=s1, s2=s2, both=both, sl=sl, tp=tp, hold=hold)


if __name__ == '__main__':
    asset = 'XAUUSD'
    print("#" * 100)
    print(f"  جاروی S82 روی {asset} — هدف: both_halves_positive + سودِ خالصِ بالا")
    print("#" * 100)
    best_overall = None
    for W in [16, 32]:
        for K in [10, 16]:
            df, close, pip, n, lab_full = prep(asset, W, K)
            for hold in [16, 32, 48]:
                for long_th in [6.0, 9.0, 12.0]:
                    ls, ss = signals(close, pip, n, lab_full, K, hold,
                                     lookback=24000, step=2000,
                                     long_th=long_th, short_th=99999,
                                     min_t=4.0, min_n=60)
                    if ls.sum() < 50:
                        continue
                    for sl in [60, 100, 150]:
                        for tp in [200, 400, 800]:
                            r = evaluate(asset, df, close, n, ls, ss, sl, tp, hold)
                            if r is None:
                                continue
                            r.update(W=W, K=K, long_th=long_th)
                            if r['both'] and r['s']['net_profit'] > 0:
                                print(f"  ✅ W={W} K={K} hold={hold} lth={long_th} "
                                      f"SL={sl} TP={tp}: net={r['s']['net_profit']:+7.0f}$ "
                                      f"n={r['s']['n_trades']:4d} WR={r['s']['win_rate']:4.1f}% "
                                      f"PF={r['s']['profit_factor']:.2f} DD={r['s']['max_dd_pct']:5.1f}% "
                                      f"H1={r['s1']['net_profit']:+6.0f} H2={r['s2']['net_profit']:+6.0f}")
                            if best_overall is None or r['s']['net_profit'] > best_overall['s']['net_profit']:
                                best_overall = r
    print("\n  ── بهترین (فارغ از both) ──")
    if best_overall:
        b = best_overall
        print(f"  W={b['W']} K={b['K']} hold={b['hold']} lth={b['long_th']} "
              f"SL={b['sl']} TP={b['tp']}: net={b['s']['net_profit']:+.0f}$ "
              f"both={'✅' if b['both'] else '❌'} "
              f"H1={b['s1']['net_profit']:+.0f} H2={b['s2']['net_profit']:+.0f}")
    print("#" * 100)
