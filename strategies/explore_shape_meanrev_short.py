"""
explore_shape_meanrev_short.py — شکارِ یک جریانِ «ضدِروند/بازگشتِ کوتاه» متنوع‌ساز
================================================================================
> قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت): معیارِ موفقیت فقط و فقط **سودِ خالص** است،
> نه Win-Rate. تعریفِ سودِ خالص = جمعِ سودِ XAUUSD + EURUSD (دو دارایی).

انگیزه (کشفِ L؟): کلِ پرتفویِ رکورد (S67/S79/S81/S73) روی طلا ۹۸٪ long است. هر
لایهٔ long دیگر با آن هم‌بسته و دابل-کانت می‌شود. چیزی که واقعاً به سودِ خالص
اضافه می‌کند، یک جریانِ **کم‌هم‌بسته/منفی-هم‌بسته** است: یک لایهٔ mean-reversion که
وقتی طلا ناگهانی جهش می‌کند و برمی‌گردد سود می‌دهد (short روی جهش‌های بیش‌کشیده).

ایدهٔ بصری: خوشه‌بندیِ شکلِ پنجره‌ها؛ خوشه‌هایی که «جهشِ عمودیِ اخیر» را نشان می‌دهند
(z-score انتهای پنجره بسیار بالا) کاندیدِ بازگشت‌اند. به‌جای انتخابِ جهت از drift،
مستقیماً خوشه‌های «بیش‌کشیده» را short و «بیش‌فروخته» را long (mean-reversion) می‌کنیم
و شرطِ both-halves + هزینهٔ واقعی را اعمال می‌کنیم.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from engine import scalp_engine as SE

np.random.seed(42)

_CACHE = {}


def zscore_windows(close, W):
    from numpy.lib.stride_tricks import sliding_window_view
    win = sliding_window_view(close, W)
    mu = win.mean(axis=1, keepdims=True)
    sd = win.std(axis=1, keepdims=True)
    sd[sd < 1e-12] = 1.0
    X = (win - mu) / sd
    return X.astype(np.float32), np.arange(W - 1, len(close))


def prep(asset, W, K):
    key = (asset, W, K)
    if key in _CACHE:
        return _CACHE[key]
    from sklearn.cluster import KMeans
    cfg = SE.ASSETS[asset]
    df = SE.load_data(cfg['file']); close = df['close'].values.astype(np.float64)
    pip = cfg['pip']; n = len(close)
    X, idxs = zscore_windows(close, W)
    km = KMeans(n_clusters=K, n_init=3, random_state=42).fit(X)
    lab = km.predict(X)
    lab_full = np.full(n, -1, int); lab_full[idxs] = lab
    # میانگینِ «کششِ انتهایی» هر خوشه: مقدارِ z در آخرین کندلِ پنجره (شکلِ بصری)
    last_z = X[:, -1]
    stretch = {c: float(last_z[lab == c].mean()) for c in range(K)}
    _CACHE[key] = (df, close, pip, n, lab_full, stretch)
    return _CACHE[key]


def run_meanrev(asset, W, K, hold, sl, tp, lb, min_t):
    """
    خوشه‌ها بر اساسِ «کششِ انتهاییِ» بصری‌شان طبقه‌بندی می‌شوند؛ اما جهتِ معامله
    از لبهٔ فوروارد در پنجرهٔ اخیر گرفته می‌شود (mean-reversion یعنی خوشهٔ بیش‌کشیده
    باید لبهٔ فورواردِ منفی داشته باشد تا short مجاز شود). این هم‌بستگی با long-stack
    را می‌شکند چون فقط short/بازگشت را می‌گیریم.
    """
    df, close, pip, n, lab_full, stretch = prep(asset, W, K)
    half = n // 2
    fwd = np.full(n, np.nan); fwd[:n - hold] = (close[hold:] - close[:n - hold]) / pip

    long_sig = np.zeros(n, bool); short_sig = np.zeros(n, bool)
    step = 2000; first = lb + hold + 100

    def edge(lo, hi):
        d = {}
        sl_ = lab_full[lo:hi]; sf = fwd[lo:hi]
        for c in range(K):
            fr = sf[sl_ == c]; fr = fr[~np.isnan(fr)]
            if len(fr) >= 50:
                m = fr.mean(); sd = fr.std(ddof=1)
                t = m / sd * np.sqrt(len(fr)) if sd > 0 else 0
                d[c] = (m, t)
        return d

    for start in range(first, n, step):
        end = min(start + step, n)
        e = edge(max(0, start - lb), start - hold)
        for i in range(start, end):
            c = lab_full[i]
            if c < 0 or c not in e:
                continue
            m, t = e[c]
            # فقط SHORT: خوشهٔ بیش‌کشیده (stretch بالا) با لبهٔ فورواردِ منفیِ معنادار
            if stretch[c] > 0.4 and t <= -min_t:
                short_sig[i] = True
            # فقط LONG-بازگشتی: خوشهٔ بیش‌فروخته (stretch پایین) با لبهٔ مثبتِ معنادار
            elif stretch[c] < -0.4 and t >= min_t:
                long_sig[i] = True

    if long_sig.sum() + short_sig.sum() < 30:
        return None
    tr = SE.simulate_trades(df, long_sig, short_sig, sl, tp, asset, max_hold=hold)
    if len(tr) < 30:
        return None
    s, _ = SE.run_capital(tr, asset, compounding=False)
    s1, _ = SE.run_capital(tr[tr['entry_bar'] < half], asset, compounding=False)
    s2, _ = SE.run_capital(tr[tr['entry_bar'] >= half], asset, compounding=False)
    both = s1['net_profit'] > 0 and s2['net_profit'] > 0
    return dict(s=s, s1=s1, s2=s2, both=both,
                nl=int(long_sig.sum()), ns=int(short_sig.sum()))


if __name__ == '__main__':
    print("#" * 100)
    print("  شکارِ جریانِ متنوع‌سازِ mean-reversion (short/بازگشت) — کم‌هم‌بسته با long-stack")
    print("  قانونِ ۱: فقط سودِ خالص (XAUUSD+EURUSD). both-halves اجباری.")
    print("#" * 100)
    combos = []
    asset = 'XAUUSD'
    for W in [16, 24, 32]:
        for K in [10, 14, 20]:
            prep(asset, W, K)
            for hold in [8, 16, 24]:
                for sl in [80, 120]:
                    for tp in [40, 80, 150]:
                        for min_t in [2.0, 3.0]:
                            r = run_meanrev(asset, W, K, hold, sl, tp, 12000, min_t)
                            if r is None:
                                continue
                            tag = f"W={W} K={K} hold={hold} SL={sl} TP={tp} t>{min_t}"
                            if r['both'] and r['s']['net_profit'] > 300:
                                print(f"  ⭐ {tag}: net={r['s']['net_profit']:+7.0f}$ "
                                      f"n={r['s']['n_trades']}(L{r['nl']}/S{r['ns']}) "
                                      f"WR={r['s']['win_rate']:.0f}% "
                                      f"H1={r['s1']['net_profit']:+.0f} H2={r['s2']['net_profit']:+.0f}")
                            combos.append((r['s']['net_profit'], r['both'], tag, r))
            sys.stdout.flush()
    combos.sort(key=lambda x: -x[0])
    print("\n  ── ۸ بهترین (فارغ از both) ──")
    for net, both, tag, r in combos[:8]:
        print(f"  {tag}: net={net:+.0f}$ both={'✅' if both else '❌'} "
              f"S-share={r['ns']/(r['nl']+r['ns'])*100:.0f}% "
              f"H1={r['s1']['net_profit']:+.0f} H2={r['s2']['net_profit']:+.0f}")
    print("#" * 100)
