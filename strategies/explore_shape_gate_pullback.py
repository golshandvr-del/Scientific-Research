"""
explore_shape_gate_pullback.py — آیا «گیتِ شکلِ بصری» یک trend-pullbackِ M15 را بهبود می‌دهد؟
================================================================================
> قانونِ شمارهٔ ۱: فقط سودِ خالص. تعریف = XAUUSD + EURUSD.

منطق:
  پایه = trend-pullbackِ کلاسیک روی XAUUSD M15 (EMA20>EMA100 + RSI<th، Long، TP>SL).
  گیت  = فقط وقتی وارد شو که «شکلِ بصریِ اخیر» (خوشهٔ z-scoreِ پنجرهٔ W) در پنجرهٔ
         اخیرِ گذشته لبهٔ صعودیِ مثبت داشته باشد (walk-forward، بدونِ نشت).

هدف: اگر گیت سودِ خالص را بالا ببرد و both-halves مثبت بماند ⇒ ارتقای لایهٔ M15
(جایگزینِ S67؛ نه افزودن ⇒ بدونِ double-count).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from engine import scalp_engine as SE

np.random.seed(42)


def ema(x, s): return pd.Series(x).ewm(span=s, adjust=False).mean().values
def rsi(x, p=14):
    d = np.diff(x, prepend=x[0]); up = np.where(d > 0, d, 0); dn = np.where(d < 0, -d, 0)
    ru = pd.Series(up).ewm(alpha=1/p, adjust=False).mean().values
    rd = pd.Series(dn).ewm(alpha=1/p, adjust=False).mean().values
    return 100 - 100 / (1 + ru / (rd + 1e-12))


def zscore_windows(close, W):
    n = len(close); idxs = np.arange(W - 1, n)
    X = np.empty((len(idxs), W))
    for r, i in enumerate(idxs):
        w = close[i - W + 1:i + 1]; mu = w.mean(); sd = w.std()
        X[r] = 0.0 if sd < 1e-12 else (w - mu) / sd
    return X, idxs


def shape_bull_gate(close, pip, n, W, K, hold, lookback, step, gate_th):
    """آرایهٔ بولین: True اگر خوشهٔ کندلِ i در پنجرهٔ اخیرِ گذشته لبهٔ صعودی≥gate_th داشت."""
    from sklearn.cluster import KMeans
    X, idxs = zscore_windows(close, W)
    lab = KMeans(n_clusters=K, n_init=10, random_state=42).fit_predict(X)
    lab_full = np.full(n, -1, int); lab_full[idxs] = lab
    fwd = np.full(n, np.nan); fwd[:n - hold] = (close[hold:] - close[:n - hold]) / pip
    gate = np.zeros(n, bool)
    first = lookback + hold + 100
    for start in range(first, n, step):
        end = min(start + step, n)
        learn = np.arange(max(0, start - lookback), start - hold)
        if len(learn) < 500:
            continue
        edges = {}
        for c in range(K):
            m = learn[lab_full[learn] == c]; fr = fwd[m]; fr = fr[~np.isnan(fr)]
            if len(fr) >= 60:
                edges[c] = fr.mean()
        for i in range(start, end):
            c = lab_full[i]
            if c >= 0 and edges.get(c, -1e9) >= gate_th:
                gate[i] = True
    return gate, first


def main():
    asset = 'XAUUSD'
    df = SE.load_data(SE.ASSETS[asset]['file'])
    close = df['close'].values.astype(np.float64)
    pip = SE.ASSETS[asset]['pip']
    n = len(close); half = n // 2

    ef = ema(close, 20); es = ema(close, 100)
    uptrend = ef > es

    print("#" * 100)
    print("  گیتِ شکلِ بصری روی trend-pullbackِ M15 — پایه در برابر گیت‌شده")
    print("#" * 100)

    # پیش‌محاسبهٔ گیت‌ها (گران‌ترین بخش) برای چند تنظیم
    gates = {}
    for (W, K, hold, gate_th) in [(16, 12, 32, 3.0), (16, 12, 32, 6.0),
                                  (32, 12, 32, 3.0), (16, 10, 48, 6.0)]:
        g, first = shape_bull_gate(close, pip, n, W, K, hold, 24000, 2000, gate_th)
        gates[(W, K, hold, gate_th)] = (g, first)
        print(f"  گیت {W,K,hold,gate_th}: فعال روی {g.sum()} کندل (از {first})")

    for rsi_th in (35, 40, 45):
        r = rsi(close, 14); dip = r < rsi_th
        base_long = np.nan_to_num(uptrend & dip).astype(bool)
        short = np.zeros(n, bool)
        for sl in (80, 120):
            for tp in (300, 500):
                # پایه
                tr = SE.simulate_trades(df, base_long, short, sl, tp, asset, max_hold=48)
                if len(tr) < 50:
                    continue
                sb, _ = SE.run_capital(tr, asset, compounding=False)
                sb1, _ = SE.run_capital(tr[tr['entry_bar'] < half], asset, compounding=False)
                sb2, _ = SE.run_capital(tr[tr['entry_bar'] >= half], asset, compounding=False)
                bboth = sb1['net_profit'] > 0 and sb2['net_profit'] > 0
                print(f"\n  RSI<{rsi_th} SL={sl} TP={tp}  پایه: net={sb['net_profit']:+7.0f}$ "
                      f"n={sb['n_trades']} both={'✅' if bboth else '❌'} "
                      f"H1={sb1['net_profit']:+.0f} H2={sb2['net_profit']:+.0f}")
                # گیت‌شده
                for key, (g, first) in gates.items():
                    lg = base_long & g
                    if lg.sum() < 50:
                        continue
                    trg = SE.simulate_trades(df, lg, short, sl, tp, asset, max_hold=48)
                    if len(trg) < 30:
                        continue
                    sg, _ = SE.run_capital(trg, asset, compounding=False)
                    sg1, _ = SE.run_capital(trg[trg['entry_bar'] < half], asset, compounding=False)
                    sg2, _ = SE.run_capital(trg[trg['entry_bar'] >= half], asset, compounding=False)
                    gboth = sg1['net_profit'] > 0 and sg2['net_profit'] > 0
                    delta = sg['net_profit'] - sb['net_profit']
                    mark = '⭐' if (gboth and sg['net_profit'] > sb['net_profit']) else '  '
                    print(f"    {mark} گیت{key}: net={sg['net_profit']:+7.0f}$ (Δ{delta:+6.0f}) "
                          f"n={sg['n_trades']} both={'✅' if gboth else '❌'} "
                          f"H1={sg1['net_profit']:+.0f} H2={sg2['net_profit']:+.0f}")


if __name__ == '__main__':
    main()
