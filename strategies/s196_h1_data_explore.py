"""
s196_h1_data_explore.py — «بگذار داده حرف بزند» روی XAUUSD H1 (پاسخِ User Note: تایم‌فریمِ هدف H1)
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه: هدف فقط «سودِ خالصِ بیشتر» است — نه WR (کفِ WR≥40٪).
> تعریفِ رسمیِ سودِ خالص = XAUUSD + EURUSD.

انگیزه (User Note این نشست):
  «ما استراتژی‌ها را فقط روی یک تایم‌فریم (M15) تست کرده‌ایم. شاید روی H1 که داده‌اش
   موجود است بازدهیِ خوبی داشته باشند. اول داده‌های تایم‌فریمِ هدف (H1) را بررسی کن و
   بگذار داده حرف بزند.»

این اسکریپت هیچ معامله‌ای نمی‌زند؛ فقط ساختارِ آماریِ خامِ XAUUSD H1 را استخراج می‌کند
تا بفهمیم کدام لایه‌ها *پتانسیلِ* کار روی H1 دارند (قبل از صرفِ بودجهٔ بک‌تست):
  1) پوششِ زمانی، تعداد کندل، بازهٔ قیمت.
  2) ATRِ H1 در مقابلِ M15 (برای بازتنظیمِ TP/SL و max_hold مخصوصِ H1).
  3) Drift ساعتی (میانگینِ بازده هر ساعتِ UTC + t-stat) → آیا S139 Overnight زنده است؟
  4) Drift روزِ هفته (Monday effect و بقیه) → آیا S140 Monday زنده است؟
  5) Drift روزِ تقویمیِ ماه (turn-of-month / mid-month / end-of-month) → S141/S142/S144.
  6) بایاسِ کلیِ long/short و اتوکورلیشنِ بازده (روند در برابر بازگشت‌به‌میانگین).
================================================================================
"""
import os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

DATA_H1 = os.path.join(ROOT, 'data', 'XAUUSD_H1.csv')
DATA_M15 = os.path.join(ROOT, 'data', 'XAUUSD_M15.csv')
PIP = 0.10  # اندازهٔ pip موتور برای طلا


def tstat(x):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    if len(x) < 2 or x.std() == 0:
        return 0.0
    return x.mean() / (x.std() / np.sqrt(len(x)))


def load(path):
    df = pd.read_csv(path)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    return df


def main():
    print("=" * 92)
    print("s196 — تحلیلِ اکتشافیِ XAUUSD H1: بگذار داده حرف بزند")
    print("=" * 92, flush=True)

    df = load(DATA_H1)
    n = len(df)
    print(f"\n[۱] پوششِ داده H1:")
    print(f"    کندل‌ها: {n:,}")
    print(f"    از {df['dt'].iloc[0]}  تا  {df['dt'].iloc[-1]}")
    print(f"    بازهٔ قیمت: {df['low'].min():.1f} – {df['high'].max():.1f} $")

    # بازدهِ هر کندل بر حسبِ pip (close-to-close)
    ret_pip = df['close'].diff() / PIP
    # حرکتِ درون‌کندلی (high-low) بر حسبِ pip ~ نماینده ATR
    range_pip = (df['high'] - df['low']) / PIP
    atr_h1 = range_pip.rolling(14).mean()

    # M15 برای مقایسهٔ ATR
    dfm = load(DATA_M15)
    range_m15 = (dfm['high'] - dfm['low']) / PIP
    atr_m15 = range_m15.rolling(14).mean()

    print(f"\n[۲] مقایسهٔ ATR (میانهٔ range بر حسبِ pip):")
    print(f"    H1  : میانهٔ range = {range_pip.median():.1f} pip   (ATR14 میانه = {atr_h1.median():.1f})")
    print(f"    M15 : میانهٔ range = {range_m15.median():.1f} pip   (ATR14 میانه = {atr_m15.median():.1f})")
    print(f"    نسبت H1/M15 ≈ {range_pip.median()/max(range_m15.median(),1e-9):.2f}×")
    print(f"    ⇒ درسِ کلیدی: TP/SLهای M15 روی H1 باید بزرگ‌تر شوند و max_hold کوچک‌تر")
    print(f"      (هر کندلِ H1 = ۴ کندلِ M15 ⇒ mh_H1 ≈ mh_M15 / 4).")

    hour = df['dt'].dt.hour.values
    dow = df['dt'].dt.dayofweek.values   # 0=Monday
    dom = df['dt'].dt.day.values
    days_in_month = df['dt'].dt.days_in_month.values

    r = ret_pip.values

    print(f"\n[۳] Drift ساعتی (میانگینِ بازدهِ close-to-close بر حسبِ pip، t-stat):")
    print(f"    {'ساعتUTC':>7}{'میانگین pip':>13}{'t':>8}{'n':>8}")
    hour_stats = []
    for h in range(24):
        m = hour == h
        seg = r[m]
        seg = seg[~np.isnan(seg)]
        t = tstat(seg)
        hour_stats.append((h, seg.mean() if len(seg) else 0, t, len(seg)))
        star = " ⭐" if abs(t) > 2.5 else ""
        print(f"    {h:>7}{seg.mean() if len(seg) else 0:>+13.2f}{t:>+8.1f}{len(seg):>8}{star}")

    # بهترین بازهٔ شبانه (drift مثبت پیوسته)
    top_hours = sorted(hour_stats, key=lambda x: -x[1])[:5]
    print(f"    بهترین ساعاتِ drift مثبت: {[h for h,_,_,_ in top_hours]}")

    print(f"\n[۴] Drift روزِ هفته (میانگینِ بازدهِ کندل‌های آن روز، pip، t-stat):")
    names = ['دوشنبه','سه‌شنبه','چهارشنبه','پنجشنبه','جمعه','شنبه','یکشنبه']
    for d in range(7):
        m = dow == d
        seg = r[m]; seg = seg[~np.isnan(seg)]
        if len(seg) == 0:
            continue
        t = tstat(seg)
        star = " ⭐" if abs(t) > 2.5 else ""
        print(f"    {names[d]:>9}: میانگین={seg.mean():+.3f}pip  t={t:+.1f}  n={len(seg)}{star}")

    print(f"\n[۵] Drift روزِ تقویمیِ ماه:")
    # ابتدای ماه (turn-of-month): روزهای 1-3 + آخرین روز
    tom = (dom <= 3) | (dom >= days_in_month - 1)
    mid = (dom >= 10) & (dom <= 20)
    eom = (dom >= days_in_month - 8) & (dom <= days_in_month - 5)
    for label, m in [('Turn-of-Month (۱-۳ و انتها)', tom),
                     ('Mid-Month (۱۰-۲۰)', mid),
                     ('End-of-Month Pre-End (۶-۸ روز مانده)', eom)]:
        seg = r[m]; seg = seg[~np.isnan(seg)]
        t = tstat(seg)
        star = " ⭐" if abs(t) > 2.5 else ""
        print(f"    {label:>34}: میانگین={seg.mean():+.3f}pip  t={t:+.1f}  n={len(seg)}{star}")

    print(f"\n[۶] بایاسِ کلی و اتوکورلیشن:")
    rr = r[~np.isnan(r)]
    print(f"    میانگینِ بازدهِ هر کندلِ H1 = {rr.mean():+.3f} pip (بایاسِ کلیِ {'صعودی' if rr.mean()>0 else 'نزولی'})")
    print(f"    t-stat کل = {tstat(rr):+.1f}  (n={len(rr)})")
    # اتوکورلیشنِ lag-1
    a = rr[:-1]; b = rr[1:]
    ac = np.corrcoef(a, b)[0, 1] if a.std() > 0 and b.std() > 0 else 0.0
    print(f"    اتوکورلیشنِ lag-1 = {ac:+.3f}  "
          f"({'روند-ادامه (momentum)' if ac>0.02 else 'بازگشت-به-میانگین' if ac<-0.02 else 'تصادفی/خنثی'})")

    print(f"\n{'='*92}")
    print("خلاصهٔ حکمِ اکتشافی (کدام لایه‌ها روی H1 پتانسیل دارند) در فایلِ MD ثبت می‌شود.")
    print("=" * 92, flush=True)


if __name__ == '__main__':
    main()
