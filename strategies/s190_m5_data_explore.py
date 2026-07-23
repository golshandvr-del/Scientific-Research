# -*- coding: utf-8 -*-
"""
s190_m5_data_explore.py — مرحلهٔ ۱ User Note: «بذار داده XAUUSD M5 حرف بزنه»
================================================================================
> # 🎯 قانونِ #۱: هدف = سودِ خالصِ بیشتر (XAUUSD+EURUSD). WR≥۴۰٪ فقط کفِ پذیرش.

پیش از هر تستِ استراتژی، ابتدا شخصیتِ آماریِ دادهٔ M5 طلا را می‌شناسیم تا بفهمیم
کدام SL/TP و کدام ساعت/رژیم برای این تایم‌فریم طبیعی است (پاسخِ صریحِ User Note:
«ابتدا داده‌های تایم‌فریم هدف را بررسی کن و بگذار داده حرف بزند»).

خروجی‌های تحلیلی:
  ۱) پوششِ زمانی، تعداد کندل، بازهٔ قیمت.
  ۲) توزیعِ حرکتِ هر کندل بر حسبِ pip (طلا pip=0.10$): میانه، صدک‌ها ⇒ مقیاسِ طبیعیِ SL/TP روی M5.
  ۳) ATR(14) روی M5 بر حسبِ pip در مقایسه با M15 (چقدر ریزتر است؟).
  ۴) بازدهیِ میانگینِ درون-کندلی بر حسبِ ساعتِ روز (بایاسِ زمانی روی M5).
  ۵) بازدهیِ روزانهٔ متوسط بر حسبِ روزِ هفته و روزِ ماه (آیا درفت‌های تقویمیِ M15 روی M5 هم دیده می‌شوند؟).
  ۶) نرخِ برخوردِ SL-قبل-از-TP برای چند جفتِ SL/TP نمونه (به‌صورتِ خام، بدونِ سیگنال) ⇒
     حدسِ اولیهٔ WR طبیعیِ هر نسبتِ R:R روی M5.
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from engine import indicators as ind

DATA = os.path.join(ROOT, 'data')
RESULTS = os.path.join(ROOT, 'results')
PIP = 0.10  # طلا


def load(tf):
    df = pd.read_csv(os.path.join(DATA, tf + '.csv'))
    df.columns = [c.lower() for c in df.columns]
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df.reset_index(drop=True)


def atr_pip(df, n=14):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).rolling(n).mean().values / PIP


def main():
    out = {}
    df5 = load('XAUUSD_M5')
    df15 = load('XAUUSD_M15')

    # فقط بازهٔ مشترک برای مقایسهٔ عادلانه
    start = max(df5['dt'].iloc[0], df15['dt'].iloc[0])
    end = min(df5['dt'].iloc[-1], df15['dt'].iloc[-1])
    df5c = df5[(df5['dt'] >= start) & (df5['dt'] <= end)].reset_index(drop=True)
    df15c = df15[(df15['dt'] >= start) & (df15['dt'] <= end)].reset_index(drop=True)

    print("=" * 90)
    print("S190 — کاوشِ اکتشافیِ دادهٔ XAUUSD M5 (مرحلهٔ ۱ User Note)")
    print("=" * 90)
    print(f"\n[۱] پوشش زمانی: {df5['dt'].iloc[0]} → {df5['dt'].iloc[-1]}")
    print(f"    تعداد کندل M5 (کل): {len(df5):,} | بازهٔ مشترک با M15: {start.date()}→{end.date()}")
    print(f"    قیمت: {df5['low'].min():.1f} → {df5['high'].max():.1f}")
    out['coverage'] = dict(first=str(df5['dt'].iloc[0]), last=str(df5['dt'].iloc[-1]),
                           n=len(df5), price_lo=float(df5['low'].min()), price_hi=float(df5['high'].max()))

    # [۲] حرکتِ درون-کندلی بر حسبِ pip
    rng5 = (df5['high'] - df5['low']).values / PIP
    body5 = np.abs(df5['close'] - df5['open']).values / PIP
    pct = [10, 25, 50, 75, 90, 95, 99]
    rng_pct = {p: float(np.percentile(rng5, p)) for p in pct}
    print(f"\n[۲] دامنهٔ هر کندلِ M5 بر حسبِ pip (طلا، pip=0.10$):")
    print("    صدک‌های high-low: " + ", ".join(f"P{p}={rng_pct[p]:.0f}" for p in pct))
    print(f"    میانهٔ بدنه: {np.median(body5):.0f} pip | میانگین دامنه: {rng5.mean():.0f} pip")
    out['candle_range_pip'] = dict(percentiles=rng_pct, median_body=float(np.median(body5)),
                                   mean_range=float(rng5.mean()))

    # [۳] ATR مقایسه M5 vs M15
    a5 = atr_pip(df5c); a15 = atr_pip(df15c)
    print(f"\n[۳] ATR(14) بر حسبِ pip (بازهٔ مشترک):")
    print(f"    M5:  میانه={np.nanmedian(a5):.0f} pip  میانگین={np.nanmean(a5):.0f}")
    print(f"    M15: میانه={np.nanmedian(a15):.0f} pip  میانگین={np.nanmean(a15):.0f}")
    print(f"    نسبت M15/M5 ≈ {np.nanmedian(a15)/np.nanmedian(a5):.2f}  (انتظار ~√3≈1.73 اگر random-walk)")
    out['atr'] = dict(m5_median=float(np.nanmedian(a5)), m15_median=float(np.nanmedian(a15)),
                      ratio=float(np.nanmedian(a15)/np.nanmedian(a5)))

    # [۴] بازدهیِ میانگینِ درون-کندلی بر حسبِ ساعت (close-open) بر حسبِ pip
    df5['hour'] = df5['dt'].dt.hour
    df5['ret_pip'] = (df5['close'] - df5['open']) / PIP
    hourly = df5.groupby('hour')['ret_pip'].agg(['mean', 'count'])
    print(f"\n[۴] بایاسِ ساعتیِ M5 (میانگینِ close-open هر کندل بر حسبِ pip):")
    top = hourly['mean'].sort_values(ascending=False)
    print("    ۵ ساعتِ صعودی‌ترین: " + ", ".join(f"h{h}={v:+.2f}" for h, v in top.head(5).items()))
    print("    ۵ ساعتِ نزولی‌ترین: " + ", ".join(f"h{h}={v:+.2f}" for h, v in top.tail(5).items()))
    out['hourly_bias'] = {int(h): float(v) for h, v in hourly['mean'].items()}

    # [۵] بازدهیِ روزانهٔ متوسط بر حسبِ روزِ هفته و روزِ ماه
    daily = df5.groupby(df5['dt'].dt.normalize()).agg(
        o=('open', 'first'), c=('close', 'last')).reset_index()
    daily['ret_pip'] = (daily['c'] - daily['o']) / PIP
    daily['dow'] = daily['dt'].dt.dayofweek
    daily['dom'] = daily['dt'].dt.day
    dow = daily.groupby('dow')['ret_pip'].mean()
    print(f"\n[۵] بازدهیِ روزانهٔ متوسط (open→close روز) بر حسبِ روزِ هفته (pip):")
    print("    " + ", ".join(f"{['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][d]}={v:+.0f}" for d, v in dow.items()))
    dom = daily.groupby('dom')['ret_pip'].mean()
    top_dom = dom.sort_values(ascending=False).head(6)
    print(f"    ۶ روزِ قوی‌ترین ماه: " + ", ".join(f"d{d}={v:+.0f}" for d, v in top_dom.items()))
    out['dow_bias'] = {int(d): float(v) for d, v in dow.items()}
    out['dom_bias_top'] = {int(d): float(v) for d, v in top_dom.items()}

    # [۶] نرخِ برخوردِ خامِ SL-قبل-از-TP برای چند R:R (بدونِ سیگنال، ورود روی هر کندل)
    print(f"\n[۶] WR خامِ نظری روی M5 (ورودِ long روی open هر کندل، بدونِ فیلتر):")
    o = df5['open'].values; h = df5['high'].values; l = df5['low'].values
    n = len(df5)
    for sl, tp, mh in [(50, 50, 36), (80, 120, 72), (100, 200, 96), (150, 300, 96), (150, 500, 144)]:
        wins = 0; total = 0
        step = 20  # نمونه‌گیری برای سرعت
        for i in range(0, n - mh, step):
            entry = o[i + 1] if i + 1 < n else o[i]
            slp = entry - sl * PIP; tpp = entry + tp * PIP
            res = None
            for j in range(i + 1, min(i + 1 + mh, n)):
                if l[j] <= slp: res = 0; break
                if h[j] >= tpp: res = 1; break
            if res is not None:
                wins += res; total += 1
        wr = wins / total * 100 if total else 0
        print(f"    SL{sl}/TP{tp} mh{mh}: WR_خام≈{wr:.1f}%  (نمونه n={total})")
        out.setdefault('raw_wr', {})[f'sl{sl}_tp{tp}_mh{mh}'] = dict(wr=wr, n=total)

    with open(os.path.join(RESULTS, '_s190_m5_explore.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\n✅ ذخیره شد: results/_s190_m5_explore.json")
    print("=" * 90)


if __name__ == '__main__':
    main()
