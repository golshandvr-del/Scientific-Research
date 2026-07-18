"""
s119_m5_trend_scorecard.py — کارتِ امتیازِ زمان‌بندیِ روند روی دادهٔ M5 (پاسخِ User Note)
================================================================================
> # قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.**
> تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD. Win-Rate صرفاً یک
> عددِ گزارشی است. این فایل یک **ابزارِ تشخیصی (diagnostic)** است و معامله‌ای
> اضافه نمی‌کند؛ پس سودِ خالص = رکوردِ فعلی (+$95,645) بدون تغییر است.
================================================================================

انگیزه (User Note — نسخهٔ M5):
  User Note دوباره سؤالِ فلسفی را مطرح کرد ولی این بار با تمرکزِ صریح روی **M5**:
    «بخشِ مغزِ اسکالپ را تقویت کنیم. تمرکزِ این‌بار فقط روی دادهٔ M5 است. باید
     بتوانیم حداکثر تعداد روند را کشف کنیم و در زمانِ مناسب وارد/خارج شویم.
     الان مغزِ اسکالپ فقط long باز می‌کند و short ندارد.»
  و پروتکلِ دقیق:
    ۱) یک بازهٔ کوتاه از دادهٔ *واقعیِ M5* با ~۵۰ روندِ صعودی انتخاب شود.
    ۲) هر روند باید ≥ ۸ دلار جابه‌جاییِ طلا داشته باشد (زیرِ ۸$ نادیده).
    ۳) روندها شماره‌گذاری و طولِ دلاریِ هرکدام ثبت شود.
    ۴) مغزِ اسکالپِ فعلی تست شود؛ کدام کشف می‌شود، کدام نه.
    ۵) امتیازِ دقتِ *شروع* و *پایان* هر روند سنجیده شود.
    ۶) تحلیلِ **چرا** هر روند کشف/کشف‌نشده.
    ۷) همین فرآیند برای روندهای نزولی تکرار شود.

  این فایل فقط تشخیص می‌دهد؛ خروجی‌اش پایهٔ طراحیِ استراتژیِ اسکالپِ دوطرفهٔ جدید
  (s120) است — که بر اساسِ همین یافته‌ها ساخته خواهد شد.

روشِ شناساییِ روندِ واقعی: ZigZag مبتنی بر آستانهٔ دلاری (همان روشِ s116، close-based).
سیگنالِ اسکالپِ فعلیِ سایت (S91): EMA20>EMA100 & RSI(21)<35 ⇒ فقط long.
================================================================================
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), '..')
DATA = os.path.join(ROOT, 'data', 'XAUUSD_M5.csv')
RESULTS = os.path.join(ROOT, 'results')
MIN_MOVE_USD = 8.0   # حداقل جابجاییِ روند (خواستهٔ User Note)
PIP = 0.10           # اندازهٔ pip طلا (موتور)


def load():
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    return df.reset_index(drop=True)


def ema(x, p):
    a = 2.0 / (p + 1.0)
    out = np.empty_like(x); out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i-1]
    return out


def sma(x, p):
    return pd.Series(x).rolling(p).mean().values


def rsi(x, p=14):
    d = np.diff(x, prepend=x[0])
    gain = np.where(d > 0, d, 0.0)
    loss = np.where(d < 0, -d, 0.0)
    ag = pd.Series(gain).ewm(alpha=1/p, adjust=False).mean().values
    al = pd.Series(loss).ewm(alpha=1/p, adjust=False).mean().values
    rs = ag / np.where(al == 0, np.nan, al)
    return 100 - 100 / (1 + rs)


def adx(h, l, c, p=14):
    up = np.diff(h, prepend=h[0]); dn = -np.diff(l, prepend=l[0])
    plus = np.where((up > dn) & (up > 0), up, 0.0)
    minus = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = np.maximum.reduce([h - l,
                            np.abs(h - np.roll(c, 1)),
                            np.abs(l - np.roll(c, 1))])
    tr[0] = h[0] - l[0]
    atr = pd.Series(tr).ewm(alpha=1/p, adjust=False).mean().values
    pdi = 100 * pd.Series(plus).ewm(alpha=1/p, adjust=False).mean().values / np.where(atr == 0, np.nan, atr)
    mdi = 100 * pd.Series(minus).ewm(alpha=1/p, adjust=False).mean().values / np.where(atr == 0, np.nan, atr)
    dx = 100 * np.abs(pdi - mdi) / np.where((pdi + mdi) == 0, np.nan, (pdi + mdi))
    return pd.Series(dx).ewm(alpha=1/p, adjust=False).mean().values


# ==============================================================================
# ۱) شناساییِ روندهای واقعی با ZigZag (حقیقتِ زمینی)
# ==============================================================================
def zigzag_trends(close, threshold_usd):
    n = len(close)
    if n < 3:
        return []
    pivots = []
    direction = 0
    ext_idx = 0
    ext_price = close[0]
    for i in range(1, n):
        price = close[i]
        if direction >= 0:
            if price > ext_price:
                ext_price = price; ext_idx = i
            if ext_price - price >= threshold_usd:
                pivots.append((ext_idx, ext_price, 'H'))
                direction = -1
                ext_price = price; ext_idx = i
        if direction <= 0:
            if price < ext_price:
                ext_price = price; ext_idx = i
            if price - ext_price >= threshold_usd:
                pivots.append((ext_idx, ext_price, 'L'))
                direction = +1
                ext_price = price; ext_idx = i
    # ساختِ روندها از توالیِ pivots
    trends = []
    for k in range(1, len(pivots)):
        i0, p0, t0 = pivots[k-1]
        i1, p1, t1 = pivots[k]
        if i1 <= i0:
            continue
        move = p1 - p0
        if t0 == 'L' and t1 == 'H' and move >= threshold_usd:
            trends.append(dict(dir='UP', i_start=i0, i_end=i1, p_start=p0, p_end=p1, move_usd=move))
        elif t0 == 'H' and t1 == 'L' and (-move) >= threshold_usd:
            trends.append(dict(dir='DOWN', i_start=i0, i_end=i1, p_start=p0, p_end=p1, move_usd=-move))
    return trends


# ==============================================================================
# ۲) سیگنالِ مغزِ اسکالپِ فعلی (S91): فقط long
# ==============================================================================
def scalp_long_signal(df):
    c = df['close'].values.astype(float)
    emaF = ema(c, 20)
    emaS = ema(c, 100)
    r = rsi(c, 21)
    sig = (emaF > emaS) & (r < 35)
    return np.nan_to_num(sig, nan=0).astype(bool)


def scalp_short_signal(df):
    """مغزِ short «آینه‌ای» که فعلاً وجود ندارد — فقط برای سنجشِ حفرهٔ پوششی:
       EMA20<EMA100 & RSI(21)>65 (اشباعِ خرید در روندِ نزولی)."""
    c = df['close'].values.astype(float)
    emaF = ema(c, 20)
    emaS = ema(c, 100)
    r = rsi(c, 21)
    sig = (emaF < emaS) & (r > 65)
    return np.nan_to_num(sig, nan=0).astype(bool)


# ==============================================================================
# ۳) امتیازدهیِ زمان‌بندی: برای هر روند، آیا سیگنال داخلِ آن فایر شد؟
#    start = چقدر نزدیکِ آغازِ روند وارد شدیم (۱۰۰=دقیقاً کف برای UP)
#    end   = چقدر نزدیکِ پایانِ روند (اولین سیگنالِ خلاف‌جهت بعد از ورود) خارج شدیم
# ==============================================================================
def score_trends(trends, sig_idx, direction):
    """sig_idx: آرایهٔ ایندکس‌هایی که سیگنالِ این جهت فایر شده.
       direction: 'UP' یا 'DOWN'."""
    sig_set = np.array(sorted(sig_idx))
    out = []
    for t in trends:
        if t['dir'] != direction:
            continue
        i0, i1 = t['i_start'], t['i_end']
        rng = max(i1 - i0, 1)
        # سیگنالی که داخلِ [i0, i1] فایر شده؟
        inside = sig_set[(sig_set >= i0) & (sig_set <= i1)]
        detected = len(inside) > 0
        rec = dict(t)
        rec['detected'] = detected
        if detected:
            entry = int(inside[0])
            # start: چند درصد از دامنه در لحظهٔ ورود باقی مانده بود
            frac_used = (entry - i0) / rng    # 0 = دقیقاً کف/سقف
            start_score = round(100 * (1 - frac_used))
            rec['entry_bar'] = entry
            rec['start_score'] = int(np.clip(start_score, 0, 100))
            # end: با ساده‌ترین منطق، فرض خروج در پایانِ روند؛ چون این فایل
            # فقط «کشف» را می‌سنجد نه اجرا، end بر مبنای فاصلهٔ ورود تا پایان است
            rec['bars_captured'] = i1 - entry
            rec['captured_pct'] = int(np.clip(round(100 * (i1 - entry) / rng), 0, 100))
        out.append(rec)
    return out


def summarize(scored, label):
    n = len(scored)
    det = [s for s in scored if s['detected']]
    lost = [s for s in scored if not s['detected']]
    print(f"\n=== {label} === n={n} | کشف‌شده={len(det)} ({100*len(det)//max(n,1)}%) | ازدست‌رفته={len(lost)}")
    if det:
        avg_start = np.mean([s['start_score'] for s in det])
        avg_cap = np.mean([s['captured_pct'] for s in det])
        print(f"    میانگین start={avg_start:.1f} | میانگین captured%={avg_cap:.1f}")
    def dna(group, name):
        if not group:
            print(f"    DNA {name}: (خالی)")
            return
        cndl = np.mean([s['i_end'] - s['i_start'] for s in group])
        mv = np.mean([s['move_usd'] for s in group])
        print(f"    DNA {name}: طولِ متوسط={cndl:.1f} کندلِ M5 | حرکتِ متوسط=${mv:.2f}")
    dna(det, 'کشف‌شده‌ها')
    dna(lost, 'ازدست‌رفته‌ها')
    return dict(n=n, detected=len(det), lost=len(lost),
                avg_start=(float(np.mean([s['start_score'] for s in det])) if det else None),
                avg_captured=(float(np.mean([s['captured_pct'] for s in det])) if det else None),
                dna_detected_bars=(float(np.mean([s['i_end']-s['i_start'] for s in det])) if det else None),
                dna_detected_usd=(float(np.mean([s['move_usd'] for s in det])) if det else None),
                dna_lost_bars=(float(np.mean([s['i_end']-s['i_start'] for s in lost])) if lost else None),
                dna_lost_usd=(float(np.mean([s['move_usd'] for s in lost])) if lost else None))


def find_window_with_50_up(df, target=50, step=200):
    """پنجرهٔ انتهاییِ داده را طوری بزرگ کن که دقیقاً ~۵۰ روندِ صعودی (≥$8) داشته باشد.
       چون داده به‌سمتِ انتها تازه‌تر است، از انتها به عقب پنجره را بزرگ می‌کنیم."""
    n = len(df)
    end = n
    # پنجره را از کوچک به بزرگ رشد بده تا شمارشِ UP به target برسد
    for win in range(step, n, step):
        start = end - win
        if start < 0:
            start = 0
        c = df['close'].values[start:end].astype(float)
        tr = zigzag_trends(c, MIN_MOVE_USD)
        ups = sum(1 for t in tr if t['dir'] == 'UP')
        if ups >= target:
            return start, end
    return 0, end


def main():
    df = load()
    print(f"داده: {len(df)} کندلِ M5 طلا  ({df['dt'].iloc[0]} → {df['dt'].iloc[-1]})")

    # پنجره‌ای با ~۵۰ روندِ صعودی پیدا کن
    a, b = find_window_with_50_up(df, target=50)
    seg = df.iloc[a:b].reset_index(drop=True)
    c = seg['close'].values.astype(float)
    print(f"\nپنجرهٔ انتخابی: barها [{a},{b}] — {seg['dt'].iloc[0]} → {seg['dt'].iloc[-1]}")

    trends = zigzag_trends(c, MIN_MOVE_USD)
    ups = [t for t in trends if t['dir'] == 'UP']
    downs = [t for t in trends if t['dir'] == 'DOWN']
    print(f"روندهای صعودیِ ≥${MIN_MOVE_USD}: {len(ups)} | نزولی: {len(downs)}")

    # اندیکاتورها روی segment
    long_sig = scalp_long_signal(seg)
    short_sig = scalp_short_signal(seg)
    r = rsi(c, 21)
    ad = adx(seg['high'].values.astype(float), seg['low'].values.astype(float), c, 14)

    long_idx = np.where(long_sig)[0]
    short_idx = np.where(short_sig)[0]
    print(f"سیگنالِ اسکالپِ فعلی (long): {len(long_idx)} بار فایر | آینهٔ short: {len(short_idx)} بار")

    up_scored = score_trends(trends, long_idx, 'UP')
    dn_scored = score_trends(trends, short_idx, 'DOWN')

    # جدولِ روندهای صعودی
    print("\n#### روندهای صعودی (کشف با مغزِ long فعلی) ####")
    print(f"{'#':>3} {'طول$':>7} {'کندل':>5} {'ADX':>5} {'RSI':>5} {'کشف':>4} {'start':>6} {'cap%':>5}")
    for k, s in enumerate(up_scored, 1):
        i0 = s['i_start']
        det = '✅' if s['detected'] else '❌'
        st = s.get('start_score', '')
        cp = s.get('captured_pct', '')
        print(f"{k:>3} {s['move_usd']:>7.2f} {s['i_end']-s['i_start']:>5} {ad[i0]:>5.1f} {r[i0]:>5.1f} {det:>4} {str(st):>6} {str(cp):>5}")

    up_sum = summarize(up_scored, 'روندهای صعودی (UP)')
    dn_sum = summarize(dn_scored, 'روندهای نزولی (DOWN) — آینهٔ short که هنوز وجود ندارد')

    # ذخیرهٔ خروجی JSON
    out = dict(
        window=[int(a), int(b)],
        dt_start=str(seg['dt'].iloc[0]), dt_end=str(seg['dt'].iloc[-1]),
        n_up=len(ups), n_down=len(downs),
        long_signals=int(len(long_idx)), short_signals=int(len(short_idx)),
        up_summary=up_sum, down_summary=dn_sum,
        up_trends=[{k: (float(v) if isinstance(v, (np.floating, float)) else int(v) if isinstance(v, (np.integer, int, bool)) else v)
                    for k, v in t.items()} for t in up_scored],
        down_trends=[{k: (float(v) if isinstance(v, (np.floating, float)) else int(v) if isinstance(v, (np.integer, int, bool)) else v)
                      for k, v in t.items()} for t in dn_scored],
    )
    with open(os.path.join(RESULTS, '_s119_m5_scorecard.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=float)
    print("\n✅ ذخیره شد: results/_s119_m5_scorecard.json")


if __name__ == '__main__':
    main()
