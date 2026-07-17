"""
explore_visual_shape_clusters.py — اکتشافِ «الگوهای بصریِ روند» با خوشه‌بندیِ شکلِ کندل‌ها
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.** WR صرفاً یک عددِ
> گزارشی است؛ تعدادِ معامله در روز و Profit Factor هم هدف نیستند. **ما دنبالِ پول
> هستیم، نه آمارِ زیبا.** تنها تابعِ هدف: سودِ خالصِ تجمعیِ پس از اسپرد/کمیسیون.
> **تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.**

--------------------------------------------------------------------------------
انگیزه (User Note این دور):
  «داشتیم روی الگوهای بصریِ روندها و شکلِ کندل‌ها کار می‌کردیم. اگر می‌توانستیم
   داده‌های پوشهٔ data را به صورتِ الگوی بصری در بیاوریم خیلی خوب می‌شد ... مهم‌تر
   از استراتژی، تقسیمِ داده‌ها به چند بخشِ مشابه است.»

ایدهٔ نو (که هیچ‌یک از ۸۱ استراتژیِ قبلی نکرده‌اند):
  به‌جای اندیکاتورهای اسکالرِ رژیم (ADX/ER/Hurst)، **خودِ منحنیِ قیمت** را به یک
  «شکلِ بصری» تبدیل می‌کنیم و شکل‌های مشابه را خوشه‌بندی می‌کنیم:

  ۱) پنجرهٔ متحرکِ W-کندلی از close را برمی‌داریم (شکلِ اخیرِ روند = «آنچه چشم می‌بیند»).
  ۲) هر پنجره را **نرمال‌سازیِ z-score** می‌کنیم ⇒ مستقل از سطح/مقیاسِ قیمت
     (فقط «شکل» می‌ماند؛ دقیقاً همان «تبدیلِ داده به الگوی بصری»).
  ۳) با KMeans پنجره‌ها را به K خوشهٔ «بصریِ مشابه» تقسیم می‌کنیم
     (این همان «تقسیمِ داده به چند بخشِ مشابه» است).
  ۴) برای هر خوشه، **بازدهِ آتیِ** k کندل بعد را می‌سنجیم (بدونِ نشتِ آینده):
     میانگین، t-stat، پایداریِ دو-نیمه. خوشه‌های دارای لبهٔ جهت‌دارِ پایدار = «الگوی
     بصریِ سودده».

اعتبارسنجی: بدونِ look-ahead (شکل فقط از کندلِ i و قبل‌تر؛ بازدهِ آتی shift-safe).
این اسکریپت فقط «کشف» است؛ تبدیل به معامله در فایلِ استراتژیِ جداگانه انجام می‌شود.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from engine import scalp_engine as SE

np.random.seed(42)


def zscore_windows(close, W, stride=1):
    """
    ساختِ ماتریسِ پنجره‌های نرمال‌شده (شکل‌ها).
    برای هر i، پنجرهٔ close[i-W+1 .. i] را می‌گیریم و z-score می‌کنیم.
    خروجی: X (n_windows × W)، idx (اندیسِ کندلِ پایانیِ هر پنجره = «حالا»).
    """
    n = len(close)
    idxs = np.arange(W - 1, n, stride)
    X = np.empty((len(idxs), W), dtype=np.float64)
    for r, i in enumerate(idxs):
        w = close[i - W + 1: i + 1]
        mu = w.mean()
        sd = w.std()
        if sd < 1e-12:
            X[r] = 0.0
        else:
            X[r] = (w - mu) / sd
    return X, idxs


def forward_return_pips(close, idxs, k, pip):
    """
    بازدهِ آتیِ k کندل بعد بر حسبِ pip، از close[i] تا close[i+k].
    forward-safe: تصمیم روی کندلِ i؛ نتیجه از i+1..i+k (اینجا close[i+k]-close[i]).
    """
    n = len(close)
    out = np.full(len(idxs), np.nan)
    for r, i in enumerate(idxs):
        if i + k < n:
            out[r] = (close[i + k] - close[i]) / pip
    return out


def tstat(x):
    x = x[~np.isnan(x)]
    if len(x) < 2:
        return 0.0, 0.0, 0
    m = x.mean()
    se = x.std(ddof=1) / np.sqrt(len(x))
    return (m / se if se > 0 else 0.0), m, len(x)


def explore_asset(asset, W=32, K=12, ks=(4, 8, 16, 32), stride=1):
    from sklearn.cluster import KMeans
    cfg = SE.ASSETS[asset]
    df = SE.load_data(cfg['file'])
    close = df['close'].values.astype(np.float64)
    pip = cfg['pip']
    n = len(close)
    half = n // 2

    print(f"\n{'='*100}")
    print(f"  {asset}  (n={n})  W={W}  K={K}  — خوشه‌بندیِ شکلِ بصری")
    print(f"{'='*100}")

    X, idxs = zscore_windows(close, W, stride)
    # آموزشِ KMeans فقط روی نیمهٔ اول (IS) برای جلوگیری از نشت؛ سپس برچسب روی همه
    is_mask = idxs < half
    km = KMeans(n_clusters=K, n_init=10, random_state=42)
    km.fit(X[is_mask])
    labels = km.predict(X)

    print(f"\n  {'clu':>3} {'n':>7} {'share':>6} | " +
          " | ".join([f"k={k}: t/mean" for k in ks]))
    rows = []
    for c in range(K):
        m = labels == c
        cnt = int(m.sum())
        share = cnt / len(labels) * 100
        cell = []
        edge_info = {}
        for k in ks:
            fr = forward_return_pips(close, idxs[m], k, pip)
            t, mean, nn = tstat(fr)
            edge_info[k] = (t, mean, nn)
            cell.append(f"{t:+5.1f}/{mean:+6.1f}")
        rows.append((c, cnt, share, edge_info))
        print(f"  {c:>3} {cnt:>7} {share:>5.1f}% | " + " | ".join(cell))

    # خوشه‌های دارای لبهٔ قوی (|t|>=3 در حداقل یک افق)، و پایداریِ دو-نیمه
    print(f"\n  --- خوشه‌های دارای لبهٔ قوی و پایداریِ دو-نیمه ---")
    strong = []
    for c, cnt, share, edge_info in rows:
        for k in ks:
            t, mean, nn = edge_info[k]
            if abs(t) >= 3.0 and nn >= 100:
                # پایداریِ دو-نیمه (IS/OOS)
                m = labels == c
                i_c = idxs[m]
                fr = forward_return_pips(close, i_c, k, pip)
                fr1 = fr[i_c < half]
                fr2 = fr[i_c >= half]
                m1 = np.nanmean(fr1) if np.sum(~np.isnan(fr1)) else 0
                m2 = np.nanmean(fr2) if np.sum(~np.isnan(fr2)) else 0
                same_sign = (m1 > 0 and m2 > 0) or (m1 < 0 and m2 < 0)
                flag = "✅پایدار" if same_sign else "⚠️ناپایدار"
                strong.append((c, k, t, mean, m1, m2, same_sign, cnt))
                print(f"  clu {c:>2} k={k:>2}: t={t:+5.1f} mean={mean:+6.1f}pip "
                      f"IS={m1:+6.1f} OOS={m2:+6.1f} {flag}  (n={cnt})")
    return strong


if __name__ == '__main__':
    print("#" * 100)
    print("  اکتشافِ الگوهای بصری با خوشه‌بندیِ شکلِ کندل‌ها (User Note: تقسیمِ داده به بخش‌های مشابه)")
    print("#" * 100)
    for asset in ['XAUUSD', 'EURUSD']:
        for W in [16, 32, 48]:
            explore_asset(asset, W=W, K=12, ks=(4, 8, 16, 32))
    print("\n" + "#" * 100)
    print("  پایان اکتشاف. خوشه‌های ✅پایدار کاندیدِ تبدیل به معامله‌اند.")
    print("#" * 100)
