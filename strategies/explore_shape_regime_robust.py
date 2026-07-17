"""
explore_shape_regime_robust.py — آخرین آزمونِ سختگیرانه: رژیمِ بصری با انتخابِ دو-پنجره‌ای
================================================================================
> قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت): معیارِ موفقیت فقط و فقط **سودِ خالص** است،
> نه Win-Rate. تعریفِ سودِ خالص = جمعِ سودِ XAUUSD + EURUSD (دو دارایی).

هدف: آیا رژیمِ بصری (خوشهٔ شکل) یک لبهٔ زمان‌بندیِ *واقعی و پایدار* دارد که در
هر دو نیمه سود بدهد؟ سختگیری‌ها:
  • انتخابِ خوشه فقط اگر در دو پنجرهٔ اخیرِ (کوتاه + بلند) هم‌جهت و قوی باشد.
  • خروجِ زمان‌محورِ خالص (hold) — بدونِ TP/SL که لبهٔ drift را می‌پوشانند.
  • تست روی M15 و M30.
هر جفت (asset, TF) هزینهٔ واقعیِ خودش را دارد. both-halves اجباری برای پذیرش.

نسخهٔ بهینه‌شده (کم‌مصرف): z-score برداری + کشِ KMeans برای هر (asset,W,K) —
از فریز شدنِ سندباکس جلوگیری می‌کند.
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
    """z-score هر پنجرهٔ W-کندلی — برداری (بدون حلقهٔ پایتون)."""
    n = len(close)
    # ماتریسِ لغزان: sliding_window_view سریع و کم‌حافظه
    from numpy.lib.stride_tricks import sliding_window_view
    win = sliding_window_view(close, W)          # (n-W+1, W)
    mu = win.mean(axis=1, keepdims=True)
    sd = win.std(axis=1, keepdims=True)
    sd[sd < 1e-12] = 1.0
    X = (win - mu) / sd
    idxs = np.arange(W - 1, n)
    return X.astype(np.float32), idxs


# کشِ (df, close, pip, lab_full) برای هر (asset, W, K)
_CACHE = {}


def prep(asset, W, K):
    key = (asset, W, K)
    if key in _CACHE:
        return _CACHE[key]
    from sklearn.cluster import KMeans
    cfg = SE.ASSETS[asset]
    df = SE.load_data(cfg['file']); close = df['close'].values.astype(np.float64)
    pip = cfg['pip']; n = len(close)
    X, idxs = zscore_windows(close, W)
    lab = KMeans(n_clusters=K, n_init=3, random_state=42).fit_predict(X)
    lab_full = np.full(n, -1, int); lab_full[idxs] = lab
    _CACHE[key] = (df, close, pip, n, lab_full)
    return _CACHE[key]


def run(asset, W, K, hold, lb_short, lb_long, sl, min_sharpe, min_mean_pip):
    df, close, pip, n, lab_full = prep(asset, W, K)
    half = n // 2
    fwd = np.full(n, np.nan); fwd[:n - hold] = (close[hold:] - close[:n - hold]) / pip

    long_sig = np.zeros(n, bool); short_sig = np.zeros(n, bool)
    step = 2000
    first = lb_long + hold + 100

    def edge(lo, hi):
        d = {}
        seg_lab = lab_full[lo:hi]; seg_fwd = fwd[lo:hi]
        for c in range(K):
            fr = seg_fwd[seg_lab == c]; fr = fr[~np.isnan(fr)]
            if len(fr) >= 60:
                mean = fr.mean(); sd = fr.std(ddof=1)
                sh = mean / sd * np.sqrt(len(fr)) if sd > 0 else 0
                d[c] = (mean, sh)
        return d

    for start in range(first, n, step):
        end = min(start + step, n)
        eS = edge(max(0, start - lb_short), start - hold)
        eL = edge(max(0, start - lb_long), start - hold)
        for i in range(start, end):
            c = lab_full[i]
            if c < 0 or c not in eS or c not in eL:
                continue
            mS, shS = eS[c]; mL, shL = eL[c]
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
    print("  آزمونِ سختگیرانهٔ رژیمِ بصری (انتخابِ دو-پنجره‌ای، خروجِ زمان‌محور) — نسخهٔ بهینه")
    print("  قانونِ ۱: فقط سودِ خالص (XAUUSD+EURUSD). both-halves اجباری.")
    print("#" * 100)
    combos = []
    for asset in ['XAUUSD', 'XAUUSD_M30']:
        sl_grid = [120] if asset == 'XAUUSD' else [200]
        hold_grid = [24, 48] if asset == 'XAUUSD' else [48, 96]
        for W in [16, 32]:
            for K in [10, 14]:
                # پیش‌محاسبهٔ KMeans یک‌بار برای این (asset,W,K)
                prep(asset, W, K)
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
                sys.stdout.flush()
    combos.sort(key=lambda x: -x[0])
    print("\n  ── ۵ بهترین (فارغ از both) ──")
    for net, both, tag, r in combos[:5]:
        print(f"  {tag}: net={net:+.0f}$ both={'✅' if both else '❌'} "
              f"H1={r['s1']['net_profit']:+.0f} H2={r['s2']['net_profit']:+.0f}")
    print("#" * 100)
