"""
explore_eurusd_dom_deepdive.py — کالبدشکافیِ بُعدِ «روزِ تقویمیِ ماه» در EURUSD
================================================================================
> قانونِ #۱: تنها معیار «سودِ خالص = XAUUSD + EURUSD» است، نه Win-Rate.

اسکنِ اولیه (explore_eurusd_calendar_dimensions) نشان داد قوی‌ترین رویدادهای
both-halves-positive و کشف‌نشدهٔ EURUSD اینها هستند:
    dom=20 → t=+9.78, mean=+2.24pip, both ✓  (قوی‌ترین — درست مثلِ طلا!)
    dom=3  → t=+5.50, mean=+1.47pip, both ✓
    dom=9  → t=+3.54, both ✓

این فایل عمیق‌تر می‌سنجد (پیش از ساختِ استراتژی):
  ۱) پایداریِ ۴-چارکیِ هر روز و خوشهٔ آن‌ها (نه آرتیفکت).
  ۲) کدام ساعاتِ روز drift را حمل می‌کنند (برای پنجرهٔ ساعتی).
  ۳) هم‌پوشانی با S73 (ساعتِ ۰) — باید متعامد باشد.

نکتهٔ نبوغ: dom=20 در *هر دو* داراییِ طلا و EURUSD قوی‌ترین است ⇒ یک اثرِ
جهانیِ بین‌دارایی (بازموازنه‌سازیِ نهادیِ میانهٔ ماه)، نه آرتیفکتِ یک دارایی.
================================================================================
"""
import os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

DATA = os.path.join(ROOT, 'data', 'EURUSD_M15.csv')
PIP = 0.0001
FWD = 16


def load():
    df = pd.read_csv(DATA)
    dt = pd.to_datetime(df['time'], unit='s', utc=True)
    df['hour'] = dt.dt.hour
    df['dow'] = dt.dt.dayofweek
    df['dom'] = dt.dt.day
    df['close'] = df['close'].astype(float)
    return df.reset_index(drop=True)


def fwd_ret(df, fwd=FWD):
    c = df['close'].values; n = len(c)
    out = np.full(n, np.nan)
    out[:n-fwd] = (c[fwd:] - c[:n-fwd]) / PIP
    return out


def quartile_test(mask, ret, n):
    """میانگینِ pip در هر ۴ چارکِ داده."""
    edges = np.linspace(0, n, 5, dtype=int)
    res = []
    for k in range(4):
        m = mask.copy()
        m[:edges[k]] = False
        m[edges[k+1]:] = False
        m = m & ~np.isnan(ret)
        x = ret[m]
        res.append(round(x.mean(), 2) if len(x) else 0.0)
    return res


def tstat(mask, ret):
    m = mask & ~np.isnan(ret)
    x = ret[m]
    if len(x) < 30:
        return 0, 0, 0
    mean = x.mean()
    t = mean / (x.std(ddof=1) / np.sqrt(len(x))) if x.std() > 0 else 0.0
    return len(x), mean, t


def main():
    df = load()
    n = len(df)
    ret = fwd_ret(df)
    dom = df['dom'].values
    hour = df['hour'].values
    print(f"داده: {n} کندلِ EURUSD M15\n")

    CAND = [3, 9, 20]
    print(f"{'='*70}\n۱) پایداریِ ۴-چارکیِ روزهای کاندید و خوشهٔ آن‌ها\n{'='*70}")
    for d in CAND:
        q = quartile_test(np.isin(dom, [d]), ret, n)
        nn, mean, t = tstat(np.isin(dom, [d]), ret)
        allpos = all(v > 0 for v in q)
        print(f"dom={d:>2}: t={t:+.2f} mean={mean:+.2f}  quartiles={q}  {'✅ هر۴ مثبت' if allpos else '❌'}")

    cl = np.isin(dom, CAND)
    q = quartile_test(cl, ret, n)
    nn, mean, t = tstat(cl, ret)
    allpos = all(v > 0 for v in q)
    print(f"\nخوشهٔ {CAND}: t={t:+.2f} mean={mean:+.2f} N={nn}  quartiles={q}  {'✅' if allpos else '❌'}")

    print(f"\n{'='*70}\n۲) کدام ساعات drift را حمل می‌کنند؟ (روی خوشهٔ {CAND})\n{'='*70}")
    print(f"{'hour':>5}{'n':>8}{'mean_pip':>11}{'t':>9}")
    strong_hours = []
    for h in range(24):
        m = cl & (hour == h)
        nn, mean, t = tstat(m, ret)
        if nn > 50 and t >= 2.0:
            strong_hours.append(h)
            print(f"{h:>5}{nn:>8}{mean:>11.2f}{t:>9.2f}   <== قوی")
        elif nn > 50 and abs(t) >= 3.0:
            print(f"{h:>5}{nn:>8}{mean:>11.2f}{t:>9.2f}")
    print(f"\nساعاتِ قوی (t≥2): {strong_hours}")

    # پنجرهٔ محافظه‌کارانه: بازهٔ پیوستهٔ سشنِ لندن+US که بیشترِ drift آنجاست
    print(f"\n{'='*70}\n۳) هم‌پوشانی با S73 (ساعتِ ۰) — باید متعامد باشد\n{'='*70}")
    m0 = cl & (hour == 0)
    nn0, mean0, t0 = tstat(m0, ret)
    print(f"سهمِ ساعتِ ۰ از خوشه: N={nn0} ({100*nn0/max(cl.sum(),1):.1f}% کلِ خوشه)")
    print(f"⇒ اگر پنجرهٔ ساعتی ساعتِ ۰ را حذف کند، با S73 متعامد می‌ماند.")

    # پیشنهادِ پنجرهٔ نهایی: ساعاتِ لندن+US بدونِ ساعتِ ۰
    london_us = [h for h in strong_hours if h != 0]
    print(f"\nپنجرهٔ پیشنهادیِ نهایی (بدونِ ساعتِ ۰): {london_us if london_us else 'کلِ روز جز ۰'}")


if __name__ == '__main__':
    main()
