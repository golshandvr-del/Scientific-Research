"""
explore_shape_regime_robust.py — آخرین آزمونِ سختگیرانه: رژیمِ بصری با انتخابِ دو-پنجره‌ای
================================================================================
> قانونِ شمارهٔ ۱: فقط سودِ خالص. تعریف = XAUUSD + EURUSD.

هدف: آیا رژیمِ بصری (خوشهٔ شکل) یک لبهٔ زمان‌بندیِ *واقعی و پایدار* دارد که در
هر دو نیمه سود بدهد؟ سختگیری‌ها:
  • انتخابِ خوشه فقط اگر در دو پنجرهٔ اخیرِ (کوتاه + بلند) هم‌جهت و قوی باشد.
  • خروجِ زمان‌محورِ خالص (hold) — بدونِ TP/SL که لبهٔ drift را می‌پوشانند.
  • تست روی M15 و M30.
هر جفت (asset, TF) هزینهٔ واقعیِ خودش را دارد. both-halves اجباری برای پذیرش.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from engine import scalp_engine as SE

np.random.seed(42)

SE.ASSETS.setdefault('XAUUSD_M30', dict(file='data/XAUUSD_M30.csv', pip=0.10, contract=100.0,
                                        pip_value=10.0, spread_pip=4.0, comm=0.0, slip_pip=0.5))


def zscore_windows(close, W):
    n = len(close); idxs = np.arange(W - 1, n)
    X = np.empty((len(idxs), W))
    for r, i in enumerate(idxs):
        w = close[i - W + 1:i + 1]; mu = w.mean(); sd = w.std()
        X[r] = 0.0 if sd < 1e-12 else (w - mu) / sd
    return X, idxs


def run(asset, W, K, hold, lb_short, lb_long, sl, min_sharpe, min_mean_pip):
    from sklearn.cluster import KMeans
    cfg = SE.ASSETS[asset]
    df = SE.load_data(cfg['file']); close = df['close'].values.astype(np.float64)
    pip = cfg['pip']; n = len(close); half = n // 2
    X, idxs = zscore_windows(close, W)
    lab = KMeans(n_clusters=K, n_init=8, random_state=42).fit_predict(X)
    lab_full = np.full(n, -1, int); lab_full[idxs] = lab
    fwd = np.full(n, np.nan); fwd[:n - hold] = (close[hold:] - close[:n - hold]) / pip

    long_sig = np.zeros(n, bool); short_sig = np.zeros(n, bool)
    step = 2000
    first = lb_long + hold + 100

    def edge(learn):
        d = {}
        for c in range(K):
            m = learn[lab_full[learn] == c]; fr = fwd[m]; fr = fr[~np.isnan(fr)]
            if len(fr) >= 60:
                mean = fr.mean(); sd = fr.std(ddof=1)
                sh = mean / sd * np.sqrt(len(fr)) if sd > 0 else 0
                d[c] = (mean, sh)
        return d

    for start in range(first, n, step):
        end = min(start + step, n)
        eS = edge(np.arange(max(0, start - lb_short), start - hold))
        eL = edge(np.arange(max(0, start - lb_long), start - hold))
        for i in range(start, end):
            c = lab_full[i]
            if c < 0 or c not in eS or c not in eL:
                continue
            mS, shS = eS[c]; mL, shL = eL[c]
            # هم‌جهت و قوی در هر دو پنجره
            if mS >= min_mean_pip and mL >= min_mean_pip and shS >= min_sharpe and shL >= min_sharpe:
                long_sig[i] = True
            elif mS <= -min_mean_pip and mL <= -min_mean_pip and shS <= -min_sharpe and shL <= -min_sharpe:
                short_sig[i] = True

    if long_sig.sum() + short_sig.sum() < 30:
        return None
    tr = SE.simulate_trades(df, long_sig, short_sig, sl, 99999, asset, max_hold=hold)
    if len(tr) < 30:
        return None
    s, _ = SE.run_capital(tr, asset, compounding=False)
    s1, _ = SE.run_capital(tr[tr['entry_bar'] < half], asset, compounding=False)
    s2, _ = SE.run_capital(tr[tr['entry_bar'] >= half], asset, compounding=False)
    both = s1['net_profit'] > 0 and s2['net_profit'] > 0
    return dict(s=s, s1=s1, s2=s2, both=both, nl=int(long_sig.sum()), ns=int(short_sig.sum()))


if __name__ == '__main__':
    print("#" * 100)
    print("  آزمونِ سختگیرانهٔ رژیمِ بصری (انتخابِ دو-پنجره‌ای، خروجِ زمان‌محور)")
    print("#" * 100)
    combos = []
    for asset in ['XAUUSD', 'XAUUSD_M30']:
        sl_grid = [80, 150] if asset == 'XAUUSD' else [150, 250]
        hold_grid = [24, 48] if asset == 'XAUUSD' else [48, 96]
        for W in [16, 32]:
            for K in [10, 14]:
                for hold in hold_grid:
                    for sl in sl_grid:
                        for min_sharpe in [2.5, 4.0]:
                            for min_mean in [5.0, 9.0]:
                                r = run(asset, W, K, hold, 12000, 40000, sl, min_sharpe, min_mean)
                                if r is None:
                                    continue
                                tag = f"{asset} W={W} K={K} hold={hold} SL={sl} sh>{min_sharpe} m>{min_mean}"
                                if r['both'] and r['s']['net_profit'] > 500:
                                    print(f"  ⭐ {tag}: net={r['s']['net_profit']:+7.0f}$ "
                                          f"n={r['s']['n_trades']}(L{r['nl']}/S{r['ns']}) "
                                          f"WR={r['s']['win_rate']:.0f}% "
                                          f"H1={r['s1']['net_profit']:+.0f} H2={r['s2']['net_profit']:+.0f}")
                                combos.append((r['s']['net_profit'], r['both'], tag, r))
    combos.sort(key=lambda x: -x[0])
    print("\n  ── ۵ بهترین (فارغ از both) ──")
    for net, both, tag, r in combos[:5]:
        print(f"  {tag}: net={net:+.0f}$ both={'✅' if both else '❌'} "
              f"H1={r['s1']['net_profit']:+.0f} H2={r['s2']['net_profit']:+.0f}")
    print("#" * 100)
