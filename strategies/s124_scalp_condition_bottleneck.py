"""
s124_scalp_condition_bottleneck.py — کدام شرطِ موتورِ اسکالپ «گلوگاه» است؟
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.**
> تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD. WR فقط گزارشی است.
> این فایل یک **ابزارِ تشخیصی** است؛ معامله‌ای اضافه نمی‌کند ⇒ سودِ خالص = +$95,645
> بدون تغییر.
================================================================================

انگیزه (ادامهٔ پاسخِ فلسفیِ User Note):
  s123 نشان داد بزرگ‌ترین تفاوتِ بین روندِ «کشف‌شده» و «کشف‌نشده» در متغیرِ
  `ema20_minus_100` است (کشف‌شده +۱.۸، کشف‌نشده −۵.۴). یعنی «ذاتِ استراتژیِ فعلی»
  یک ماشهٔ pullback است، نه ماشهٔ آغازِ روند. این فایل به‌صورتِ **تجزیه‌ای** ثابت
  می‌کند کدام یک از دو شرطِ موتور (EMA20>EMA100  یا  RSI21<35) گلوگاهِ واقعی است:
  برای هر روندِ صعودی می‌سنجیم آیا در بازهٔ آن روند:
    (الف) شرطِ EMA به‌تنهایی برقرار شده؟
    (ب) شرطِ RSI به‌تنهایی برقرار شده؟
    (ج) هر دو هم‌زمان (=سیگنالِ واقعی)؟
  نسبتِ این سه، گلوگاه را لخت می‌کند و مسیرِ طراحیِ موتورِ سودده‌ترِ بعد را می‌سازد.
================================================================================
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), '..')
DATA = os.path.join(ROOT, 'data', 'XAUUSD_M5.csv')
RESULTS = os.path.join(ROOT, 'results')
MIN_MOVE_USD = 8.0
TARGET = 50


def load():
    df = pd.read_csv(DATA); df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    return df.reset_index(drop=True)


def ema(x, p): return pd.Series(x).ewm(span=p, adjust=False).mean().values
def rsi(x, p=14):
    d = np.diff(x, prepend=x[0]); g = np.where(d > 0, d, 0.0); l = np.where(d < 0, -d, 0.0)
    ag = pd.Series(g).ewm(alpha=1/p, adjust=False).mean().values
    al = pd.Series(l).ewm(alpha=1/p, adjust=False).mean().values
    rs = ag/np.where(al == 0, np.nan, al); return 100-100/(1+rs)


def zigzag_trends(close, thr):
    n = len(close)
    if n < 3: return []
    piv = []; direction = 0; ei = 0; ep = close[0]
    for i in range(1, n):
        p = close[i]
        if direction >= 0:
            if p > ep: ep = p; ei = i
            if ep - p >= thr: piv.append((ei, ep, 'H')); direction = -1; ep = p; ei = i
        if direction <= 0:
            if p < ep: ep = p; ei = i
            if p - ep >= thr: piv.append((ei, ep, 'L')); direction = +1; ep = p; ei = i
    tr = []
    for k in range(1, len(piv)):
        i0, p0, t0 = piv[k-1]; i1, p1, t1 = piv[k]
        if i1 <= i0: continue
        mv = p1-p0
        if t0 == 'L' and t1 == 'H' and mv >= thr:
            tr.append(dict(dir='UP', i_start=i0, i_end=i1, move_usd=mv))
        elif t0 == 'H' and t1 == 'L' and -mv >= thr:
            tr.append(dict(dir='DOWN', i_start=i0, i_end=i1, move_usd=-mv))
    return tr


def find_window(df, direction, target=TARGET, step=200):
    n = len(df); end = n
    for win in range(step, n, step):
        start = max(end-win, 0)
        c = df['close'].values[start:end].astype(float)
        cnt = sum(1 for t in zigzag_trends(c, MIN_MOVE_USD) if t['dir'] == direction)
        if cnt >= target: return start, end
        if start == 0: break
    return 0, end


def analyze(df, direction):
    a, b = find_window(df, direction, TARGET)
    seg = df.iloc[a:b].reset_index(drop=True)
    c = seg['close'].values.astype(float)
    e20 = ema(c, 20); e100 = ema(c, 100); r = rsi(c, 21)
    if direction == 'UP':
        cond_ema = e20 > e100
        cond_rsi = r < 35
    else:
        cond_ema = e20 < e100
        cond_rsi = r > 65
    both = cond_ema & cond_rsi
    trends = [t for t in zigzag_trends(c, MIN_MOVE_USD) if t['dir'] == direction]

    n = len(trends)
    only_ema = only_rsi = hit_both = neither = 0
    for t in trends:
        i0, i1 = t['i_start'], t['i_end']
        e = cond_ema[i0:i1+1].any()
        rr = cond_rsi[i0:i1+1].any()
        bb = both[i0:i1+1].any()
        if bb: hit_both += 1
        elif e and not rr: only_ema += 1
        elif rr and not e: only_rsi += 1
        elif e and rr and not bb: only_ema += 0  # هر دو جدا ولی نه هم‌زمان
        else: neither += 1
    print(f"\n### {direction} — تجزیهٔ گلوگاهِ شرط (n={n} روند) ###")
    print(f"  شرطِ EMA در بازهٔ روند برقرار شد:  {sum(cond_ema[t['i_start']:t['i_end']+1].any() for t in trends)}/{n}")
    print(f"  شرطِ RSI در بازهٔ روند برقرار شد:  {sum(cond_rsi[t['i_start']:t['i_end']+1].any() for t in trends)}/{n}")
    print(f"  هر دو هم‌زمان (=سیگنالِ واقعی):     {hit_both}/{n}  ⇒ پوششِ واقعی {100*hit_both//max(n,1)}%")
    # نرخِ فعال‌بودنِ هر شرط روی کلِ کندل‌ها
    print(f"  ٪کندل‌هایی که شرطِ EMA فعال است: {100*cond_ema.mean():.1f}%")
    print(f"  ٪کندل‌هایی که شرطِ RSI فعال است: {100*cond_rsi.mean():.1f}%")
    print(f"  ٪کندل‌هایی که هر دو فعال‌اند:     {100*both.mean():.1f}%")
    return dict(direction=direction, n=n,
                ema_in_trend=int(sum(cond_ema[t['i_start']:t['i_end']+1].any() for t in trends)),
                rsi_in_trend=int(sum(cond_rsi[t['i_start']:t['i_end']+1].any() for t in trends)),
                both_in_trend=int(hit_both),
                pct_ema_active=round(100*float(cond_ema.mean()), 2),
                pct_rsi_active=round(100*float(cond_rsi.mean()), 2),
                pct_both_active=round(100*float(both.mean()), 2))


def main():
    df = load()
    print(f"داده: {len(df)} کندلِ M5 طلا")
    up = analyze(df, 'UP')
    dn = analyze(df, 'DOWN')
    print("\n" + "="*66)
    print("نتیجه‌گیریِ گلوگاه:")
    print("  اگر EMA-in-trend بالا ولی both-in-trend پایین باشد ⇒ گلوگاه = شرطِ RSI")
    print("  (RSI<35 در آغازِ روندِ صعودیِ M5 نادر است ⇒ ماشه عملاً pullback-only می‌شود).")
    out = dict(UP=up, DOWN=dn)
    with open(os.path.join(RESULTS, '_s124_bottleneck.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("\n✅ ذخیره شد: results/_s124_bottleneck.json")


if __name__ == '__main__':
    main()
