"""
s82_visual_shape_router.py — استراتژیِ S82: مسیریابِ «الگوی بصریِ روند» (Visual-Shape Router)
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.** WR صرفاً یک عددِ
> گزارشی است؛ تعدادِ معامله در روز و Profit Factor هم هدف نیستند. **ما دنبالِ پول
> هستیم، نه آمارِ زیبا.** تنها تابعِ هدف: سودِ خالصِ تجمعیِ پس از اسپرد/کمیسیون.
> **تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.**

--------------------------------------------------------------------------------
ایده (پاسخِ مستقیم به User Note این دور):
  «داده‌ها را به الگوی بصری تبدیل کن؛ مهم‌تر از استراتژی، تقسیمِ داده به بخش‌های مشابه.»

  ۱) هر کندل را با «شکلِ اخیرِ منحنیِ close» (پنجرهٔ W کندلی، z-score نرمال‌شده)
     نمایندگی می‌کنیم ⇒ داده به «الگوی بصری» تبدیل شد (مستقل از سطح/مقیاس).
  ۲) KMeans شکل‌های مشابه را در K خوشه تقسیم می‌کند ⇒ «تقسیمِ داده به بخش‌های مشابه».
  ۳) هر خوشه = یک «رژیمِ بصری». برای هرکدام لبهٔ آتی را روی IS می‌سنجیم و فقط
     خوشه‌های دارای لبهٔ جهت‌دارِ قوی و پایدار را به معامله تبدیل می‌کنیم:
        - خوشهٔ صعودی (mean_fwd > +آستانه) ⇒ Long
        - خوشهٔ نزولی (mean_fwd < −آستانه) ⇒ Short
        - بقیه ⇒ خنثی (بدونِ معامله) — دقیقاً حالتِ «خنثی»یِ سایت.

اعتبارسنجی (بدونِ نشتِ آینده):
  • KMeans و انتخابِ خوشه‌ها فقط روی نیمهٔ اول (IS) آموزش می‌بینند.
  • برچسبِ خوشه با predict روی همهٔ داده (فقط از شکلِ گذشته؛ بدونِ نگاه به آینده).
  • ورود در open کندلِ بعد؛ SL/TP بر حسبِ pip؛ موتورِ سرمایه‌محورِ scalp_engine.
  • سودِ خالصِ کل و تفکیکِ دو-نیمه گزارش می‌شود؛ baselineِ buy&hold مقایسه می‌شود.
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


def build_shape_signals(asset, W=16, K=12, hold=32,
                        long_mean_th=4.0, short_mean_th=4.0,
                        min_t=3.0, min_n=200, verbose=True):
    """
    ساخت سیگنال‌های Long/Short بر پایهٔ خوشه‌بندیِ شکلِ بصری.
    آموزش KMeans + انتخاب خوشه‌ها فقط روی نیمهٔ اول (IS).
    """
    from sklearn.cluster import KMeans
    cfg = SE.ASSETS[asset]
    df = SE.load_data(cfg['file'])
    close = df['close'].values.astype(np.float64)
    pip = cfg['pip']
    n = len(close)
    half = n // 2

    X, idxs = zscore_windows(close, W)
    is_mask = idxs < half
    km = KMeans(n_clusters=K, n_init=10, random_state=42)
    km.fit(X[is_mask])
    labels = km.predict(X)

    # لبهٔ آتیِ hold-کندلیِ هر خوشه، فقط روی IS (بدونِ نشت)
    fwd = np.full(len(idxs), np.nan)
    for r, i in enumerate(idxs):
        if i + hold < n:
            fwd[r] = (close[i + hold] - close[i]) / pip

    long_clusters, short_clusters = [], []
    detail = []
    for c in range(K):
        m = (labels == c) & is_mask
        fr = fwd[m]
        fr = fr[~np.isnan(fr)]
        if len(fr) < min_n:
            detail.append((c, len(fr), 0.0, 0.0, 'skip(n)'))
            continue
        mean = fr.mean()
        se = fr.std(ddof=1) / np.sqrt(len(fr))
        t = mean / se if se > 0 else 0.0
        tag = 'neutral'
        if t >= min_t and mean >= long_mean_th:
            long_clusters.append(c); tag = 'LONG'
        elif t <= -min_t and mean <= -short_mean_th:
            short_clusters.append(c); tag = 'SHORT'
        detail.append((c, len(fr), t, mean, tag))

    # نگاشتِ برچسب به آرایهٔ هم‌طولِ df (کندل‌های ابتداییِ کمتر از W: خنثی)
    lab_full = np.full(n, -1, dtype=int)
    lab_full[idxs] = labels
    long_sig = np.isin(lab_full, long_clusters)
    short_sig = np.isin(lab_full, short_clusters)

    if verbose:
        print(f"\n  [{asset}] W={W} K={K} hold={hold} — انتخابِ خوشه‌ها روی IS:")
        for c, nn, t, mean, tag in detail:
            mark = '➜' if tag in ('LONG', 'SHORT') else ' '
            print(f"   {mark} clu {c:>2}: n_IS={nn:>6} t={t:+5.1f} mean={mean:+6.1f}pip  [{tag}]")
        print(f"   LONG خوشه‌ها: {long_clusters}  |  SHORT خوشه‌ها: {short_clusters}")

    return df, long_sig, short_sig, close, pip, half, (long_clusters, short_clusters)


def run(asset, W=16, K=12, hold=32, sl_pip=120, tp_pip=400,
        long_mean_th=4.0, short_mean_th=6.0, min_t=3.0,
        compounding=False, verbose=True):
    df, long_sig, short_sig, close, pip, half, clusters = build_shape_signals(
        asset, W=W, K=K, hold=hold, long_mean_th=long_mean_th,
        short_mean_th=short_mean_th, min_t=min_t, verbose=verbose)

    tr = SE.simulate_trades(df, long_sig, short_sig, sl_pip, tp_pip, asset, max_hold=hold)
    if len(tr) == 0:
        if verbose:
            print("   (هیچ معامله‌ای تولید نشد)")
        return None

    # فقط OOS (نیمهٔ دوم) برای ادعای سودِ قابلِ‌اتکا؛ و کل برای گزارش
    s_all, eq = SE.run_capital(tr, asset, compounding=compounding)
    tr1 = tr[tr['entry_bar'] < half]
    tr2 = tr[tr['entry_bar'] >= half]
    s1, _ = SE.run_capital(tr1, asset, compounding=compounding)
    s2, _ = SE.run_capital(tr2, asset, compounding=compounding)

    if verbose:
        print(f"\n   {SE.summary_line(asset+'-ALL', s_all)}")
        print(f"   {SE.summary_line(asset+'-IS ', s1)}")
        print(f"   {SE.summary_line(asset+'-OOS', s2)}")
        both = s1['net_profit'] > 0 and s2['net_profit'] > 0
        print(f"   both_halves_positive = {'✅' if both else '❌'}")
    return dict(asset=asset, s_all=s_all, s1=s1, s2=s2, tr=tr, eq=eq,
                clusters=clusters, W=W, K=K, hold=hold, sl=sl_pip, tp=tp_pip)


if __name__ == '__main__':
    print("#" * 100)
    print("  S82 — Visual-Shape Router: خوشه‌بندیِ شکلِ بصری ➜ معامله (User Note: تقسیمِ داده)")
    print("#" * 100)

    # XAUUSD: خوشه‌های صعودی لبهٔ بزرگ داشتند (تا +17pip، t=+11). SL/TP رژیم-swing.
    res_gold = run('XAUUSD', W=16, K=12, hold=32, sl_pip=120, tp_pip=400,
                   long_mean_th=4.0, short_mean_th=8.0, min_t=3.0)

    print("\n" + "#" * 100)
    if res_gold:
        s = res_gold['s_all']
        print(f"  XAUUSD Visual-Shape: net={s['net_profit']:+.0f}$  "
              f"IS={res_gold['s1']['net_profit']:+.0f}  OOS={res_gold['s2']['net_profit']:+.0f}")
    print("#" * 100)
