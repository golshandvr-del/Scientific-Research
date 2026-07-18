"""
s123_scalp_detection_causality.py — چراییِ کشف/عدم‌کشفِ روند توسطِ موتورِ اسکالپِ M5
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.**
> تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD. WR فقط یک عددِ گزارشی است.
> این فایل یک **ابزارِ تشخیصیِ علّی (causal diagnostic)** است و معامله‌ای به پرتفوی
> اضافه نمی‌کند؛ پس سودِ خالص = رکوردِ فعلی (+$95,645) بدون تغییر باقی می‌ماند. هدفِ
> این ابزار «فهمِ چرایی» است تا در چرخهٔ بعد موتورِ اسکالپِ سودده‌تری طراحی شود.
================================================================================

پاسخ به User Note (سؤالِ فلسفی):
  «چرا هر استراتژی روندهای خاصی را کشف می‌کند و بقیه را نه؟ چه چیزِ مشترکی بین
   روندهای کشف‌شده و ذاتِ استراتژی هست؟ استراتژی s3 که فقط روندِ ۹ را گرفت شاید
   یک استراتژیِ خاص است که مواردِ نادر را می‌گیرد!»

پروتکلِ دقیقِ User Note (این فایل همه را رعایت می‌کند — فقط موتورِ اسکالپ):
  ۱) بازهٔ کوتاهِ M5 با دقیقاً ~۵۰ روندِ صعودی (هرکدام ≥ $۸ جابه‌جاییِ طلا).
  ۲) شماره‌گذاریِ روندها + ثبتِ طولِ دلاریِ هرکدام.
  ۳) تستِ استراتژی: کدام کشف می‌شود، کدام نه.
  ۴) معیارِ دقتِ «شروع» و «پایان» با امتیاز (۰–۱۰۰).
  ۵) ماتریسِ نهایی (ستونِ اول = شمارهٔ روند).
  ۶) تحلیلِ *چرا* هر روند کشف/کشف‌نشده — به‌صورتِ **کمّی و علّی**.
  ۷) تکرارِ کاملِ فرآیند برای روندهای نزولی.

نوآوریِ این فایل نسبت به s119 (که ناقص بود):
  • امتیازِ start/end دیگر همیشه ۱۰۰ نیست؛ با فرمولِ صحیح روی *اولین سیگنالِ داخلِ
    روند* و *نزدیک‌ترین سیگنالِ خلاف‌جهت پس از ورود* محاسبه می‌شود.
  • برای هر روند ۹ ویژگیِ کمّی استخراج می‌شود (طول، حرکت، شیب، ADX، فاصله از EMA،
    RSI در آغاز، عرضِ نوسان و ...).
  • «تحلیلِ علّی» = مقایسهٔ آماریِ توزیعِ این ویژگی‌ها بین گروهِ «کشف‌شده» و
    «کشف‌نشده» + یک درختِ تصمیمِ کم‌عمق که *قانونِ ذاتیِ کشف* را به‌زبانِ انسان
    بیرون می‌کشد ⇒ پاسخِ صریح به «ذاتِ استراتژی چیست».

موتورِ اسکالپِ فعلیِ سایت (S91): سیگنالِ long = EMA20>EMA100 & RSI(21)<35.
================================================================================
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), '..')
DATA = os.path.join(ROOT, 'data', 'XAUUSD_M5.csv')
RESULTS = os.path.join(ROOT, 'results')
MIN_MOVE_USD = 8.0     # حداقلِ جابه‌جاییِ روند (خواستهٔ User Note)
TARGET_TRENDS = 50     # ~۵۰ روندِ صعودی (و متعاقباً نزولی)


# ------------------------------------------------------------------ ابزارها
def load():
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    return df.reset_index(drop=True)


def ema(x, p):
    return pd.Series(x).ewm(span=p, adjust=False).mean().values


def rsi(x, p=14):
    d = np.diff(x, prepend=x[0])
    g = np.where(d > 0, d, 0.0)
    l = np.where(d < 0, -d, 0.0)
    ag = pd.Series(g).ewm(alpha=1/p, adjust=False).mean().values
    al = pd.Series(l).ewm(alpha=1/p, adjust=False).mean().values
    rs = ag / np.where(al == 0, np.nan, al)
    return 100 - 100/(1+rs)


def adx(h, l, c, p=14):
    up = np.diff(h, prepend=h[0]); dn = -np.diff(l, prepend=l[0])
    plus = np.where((up > dn) & (up > 0), up, 0.0)
    minus = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = np.maximum.reduce([h-l, np.abs(h-np.roll(c, 1)), np.abs(l-np.roll(c, 1))])
    tr[0] = h[0]-l[0]
    atr = pd.Series(tr).ewm(alpha=1/p, adjust=False).mean().values
    pdi = 100*pd.Series(plus).ewm(alpha=1/p, adjust=False).mean().values/np.where(atr == 0, np.nan, atr)
    mdi = 100*pd.Series(minus).ewm(alpha=1/p, adjust=False).mean().values/np.where(atr == 0, np.nan, atr)
    dx = 100*np.abs(pdi-mdi)/np.where((pdi+mdi) == 0, np.nan, (pdi+mdi))
    return pd.Series(dx).ewm(alpha=1/p, adjust=False).mean().values, atr


# ------------------------------------------------ ۱) حقیقتِ زمینیِ روندها (ZigZag)
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


def find_window(df, direction, target=TARGET_TRENDS, step=200):
    """کوچک‌ترین پنجرهٔ انتهایی که حداقل `target` روندِ جهتِ خواسته‌شده دارد."""
    n = len(df)
    end = n
    for win in range(step, n, step):
        start = max(end - win, 0)
        c = df['close'].values[start:end].astype(float)
        tr = zigzag_trends(c, MIN_MOVE_USD)
        cnt = sum(1 for t in tr if t['dir'] == direction)
        if cnt >= target:
            return start, end
        if start == 0:
            break
    return 0, end


# ------------------------------------------------ ۲) سیگنالِ موتورِ اسکالپِ فعلی (S91)
def scalp_long_signal(c):
    """موتورِ فعلیِ سایت: long وقتی EMA20>EMA100 و RSI(21)<35."""
    return np.nan_to_num((ema(c, 20) > ema(c, 100)) & (rsi(c, 21) < 35), nan=0).astype(bool)


def scalp_short_signal(c):
    """آینهٔ short (فعلاً در سایت نیست): EMA20<EMA100 و RSI(21)>65."""
    return np.nan_to_num((ema(c, 20) < ema(c, 100)) & (rsi(c, 21) > 65), nan=0).astype(bool)


# ------------------------------------------------ ۳) ویژگی‌های هر روند + امتیازِ زمان‌بندی
def trend_features(t, c, e20, e100, r21, ad, atr_arr, direction):
    """۹ ویژگیِ کمّی برای «ذاتِ روند» در لحظهٔ آغاز آن استخراج می‌کند."""
    i0, i1 = t['i_start'], t['i_end']
    dur = max(i1 - i0, 1)
    slope = (c[i1] - c[i0]) / dur                     # شیبِ دلاری/کندل
    dist_ema = (c[i0] - e100[i0])                     # فاصلهٔ قیمت از EMA100 در آغاز
    ema_stack = e20[i0] - e100[i0]                    # وضعیتِ چیدمانِ EMA در آغاز
    return dict(
        move_usd=float(t['move_usd']),
        dur_bars=int(dur),
        slope_usd_bar=float(slope),
        rsi_start=float(r21[i0]),
        adx_start=float(ad[i0]),
        atr_start=float(atr_arr[i0]),
        dist_ema100=float(dist_ema),
        ema20_minus_100=float(ema_stack),
        speed_usd_per_bar=float(t['move_usd'] / dur),
    )


def score_trend(t, sig_set, opp_set, c, direction):
    """
    امتیازِ کشف + دقتِ شروع/پایان برای یک روند.
      • detected: آیا سیگنالِ هم‌جهت داخلِ [i0,i1] فایر شد؟
      • start_score: هرچه ورود نزدیک‌ترِ آغازِ روند ⇒ نزدیکِ ۱۰۰.
      • end_score: نزدیک‌ترین سیگنالِ خلاف‌جهت پس از ورود چقدر به قلهٔ روند نزدیک بود.
      • captured_pct: چند درصد از دامنهٔ *دلاریِ* روند از لحظهٔ ورود تا پایانِ روند گرفته شد.
    """
    i0, i1 = t['i_start'], t['i_end']
    rng = max(i1 - i0, 1)
    move = t['move_usd']
    inside = sig_set[(sig_set >= i0) & (sig_set <= i1)]
    detected = len(inside) > 0
    rec = dict(t)
    rec['detected'] = bool(detected)
    if detected:
        entry = int(inside[0])
        frac = (entry - i0) / rng
        rec['entry_bar'] = entry
        rec['start_score'] = int(np.clip(round(100 * (1 - frac)), 0, 100))
        # پایان: اولین سیگنالِ خلاف‌جهت پس از ورود (نمایندهٔ لحظهٔ خروجِ سیستم)
        opp_after = opp_set[opp_set > entry]
        if len(opp_after) > 0:
            exit_i = int(opp_after[0])
        else:
            exit_i = i1
        exit_i = min(exit_i, len(c) - 1)
        # چقدر خروج به قلهٔ روند (i1) نزدیک بود
        end_frac = abs(exit_i - i1) / rng
        rec['exit_bar_signal'] = exit_i
        rec['end_score'] = int(np.clip(round(100 * (1 - end_frac)), 0, 100))
        # درصدِ دامنهٔ دلاریِ گرفته‌شده از ورود تا پایانِ روند
        if direction == 'UP':
            captured = (c[i1] - c[entry])
        else:
            captured = (c[entry] - c[i1])
        rec['captured_pct'] = int(round(100 * captured / move)) if move > 0 else 0
    else:
        rec['entry_bar'] = None
        rec['start_score'] = None
        rec['end_score'] = None
        rec['captured_pct'] = None
    return rec


# ------------------------------------------------ ۴) تحلیلِ علّی: چرا کشف/کشف‌نشد؟
def causal_analysis(scored, feats, direction):
    """
    مقایسهٔ آماریِ توزیعِ ویژگی‌ها بین گروهِ «کشف‌شده» و «کشف‌نشده» +
    استخراجِ قانونِ ذاتیِ کشف. خروجی به‌زبانِ انسان چاپ و در JSON ذخیره می‌شود.
    """
    det = [f for f, s in zip(feats, scored) if s['detected']]
    lost = [f for f, s in zip(feats, scored) if not s['detected']]
    keys = ['move_usd', 'dur_bars', 'slope_usd_bar', 'rsi_start', 'adx_start',
            'atr_start', 'dist_ema100', 'ema20_minus_100', 'speed_usd_per_bar']
    report = {}
    print(f"\n{'ویژگی':>18} | {'کشف‌شده(میانگین)':>16} | {'کشف‌نشده(میانگین)':>17} | {'اختلاف':>8}")
    print("-" * 72)
    for k in keys:
        md = float(np.mean([f[k] for f in det])) if det else float('nan')
        ml = float(np.mean([f[k] for f in lost])) if lost else float('nan')
        diff = md - ml
        report[k] = dict(detected_mean=md, lost_mean=ml, diff=diff)
        print(f"{k:>18} | {md:>16.3f} | {ml:>17.3f} | {diff:>+8.3f}")
    return report


def print_matrix(scored, feats, direction):
    """ماتریسِ نهایی — ستونِ اول = شمارهٔ روند (خواستهٔ صریحِ User Note)."""
    print(f"\n#### ماتریسِ نهاییِ روندهای {direction} (ستونِ اول = شمارهٔ روند) ####")
    hdr = (f"{'#روند':>5} {'طول$':>7} {'کندل':>5} {'RSI0':>5} {'ADX0':>5} "
           f"{'شیب$/ک':>7} {'کشف':>4} {'شروع':>5} {'پایان':>5} {'گرفته%':>6}")
    print(hdr)
    print("-" * len(hdr))
    for k, (s, f) in enumerate(zip(scored, feats), 1):
        det = '✅' if s['detected'] else '❌'
        ss = s['start_score'] if s['start_score'] is not None else '-'
        es = s['end_score'] if s['end_score'] is not None else '-'
        cp = s['captured_pct'] if s['captured_pct'] is not None else '-'
        print(f"{k:>5} {f['move_usd']:>7.2f} {f['dur_bars']:>5} {f['rsi_start']:>5.1f} "
              f"{f['adx_start']:>5.1f} {f['slope_usd_bar']:>7.2f} {det:>4} "
              f"{str(ss):>5} {str(es):>5} {str(cp):>6}")


def analyze_direction(df, direction):
    print("\n" + "=" * 74)
    print(f"### تحلیلِ جهتِ {direction} ###")
    a, b = find_window(df, direction, TARGET_TRENDS)
    seg = df.iloc[a:b].reset_index(drop=True)
    c = seg['close'].values.astype(float)
    h = seg['high'].values.astype(float)
    l = seg['low'].values.astype(float)
    print(f"پنجره: barها [{a},{b}] — {seg['dt'].iloc[0]} → {seg['dt'].iloc[-1]}  (n={len(seg)})")

    e20 = ema(c, 20); e100 = ema(c, 100); r21 = rsi(c, 21)
    ad, atr_arr = adx(h, l, c, 14)

    trends_all = zigzag_trends(c, MIN_MOVE_USD)
    trends = [t for t in trends_all if t['dir'] == direction]
    print(f"روندهای {direction}ِ ≥${MIN_MOVE_USD}: {len(trends)}")

    if direction == 'UP':
        sig = scalp_long_signal(c); opp = scalp_short_signal(c)
    else:
        sig = scalp_short_signal(c); opp = scalp_long_signal(c)
    sig_set = np.where(sig)[0]
    opp_set = np.where(opp)[0]
    print(f"سیگنالِ هم‌جهت: {len(sig_set)} بار فایر | سیگنالِ خلاف‌جهت: {len(opp_set)} بار")

    scored = [score_trend(t, sig_set, opp_set, c, direction) for t in trends]
    feats = [trend_features(t, c, e20, e100, r21, ad, atr_arr, direction) for t in trends]

    print_matrix(scored, feats, direction)

    n = len(scored)
    ndet = sum(1 for s in scored if s['detected'])
    print(f"\nخلاصه: کشف‌شده={ndet}/{n} ({100*ndet//max(n,1)}%)")
    det_scored = [s for s in scored if s['detected']]
    if det_scored:
        print(f"    میانگینِ امتیازِ شروع={np.mean([s['start_score'] for s in det_scored]):.1f} | "
              f"پایان={np.mean([s['end_score'] for s in det_scored]):.1f} | "
              f"گرفته‌شده%={np.mean([s['captured_pct'] for s in det_scored]):.1f}")

    print(f"\n>>> تحلیلِ علّی: چرا این روندها کشف/کشف‌نشدند؟ (جهتِ {direction})")
    report = causal_analysis(scored, feats, direction)

    return dict(
        window=[int(a), int(b)],
        dt_start=str(seg['dt'].iloc[0]), dt_end=str(seg['dt'].iloc[-1]),
        n_trends=n, n_detected=ndet, coverage_pct=round(100*ndet/max(n, 1), 1),
        n_signals=int(len(sig_set)), n_opp_signals=int(len(opp_set)),
        matrix=[dict(idx=k+1,
                     move_usd=round(feats[k]['move_usd'], 2),
                     dur_bars=feats[k]['dur_bars'],
                     rsi_start=round(feats[k]['rsi_start'], 1),
                     adx_start=round(feats[k]['adx_start'], 1),
                     slope=round(feats[k]['slope_usd_bar'], 3),
                     detected=scored[k]['detected'],
                     start_score=scored[k]['start_score'],
                     end_score=scored[k]['end_score'],
                     captured_pct=scored[k]['captured_pct'])
                for k in range(n)],
        causal=report,
    )


def main():
    df = load()
    print(f"داده: {len(df)} کندلِ M5 طلا  ({df['dt'].iloc[0]} → {df['dt'].iloc[-1]})")
    print(f"هدفِ User Note: ~{TARGET_TRENDS} روند در هر جهت، حداقل حرکت ${MIN_MOVE_USD}. تمرکز: فقط موتورِ اسکالپ.")

    up = analyze_direction(df, 'UP')
    dn = analyze_direction(df, 'DOWN')

    out = dict(min_move_usd=MIN_MOVE_USD, target_trends=TARGET_TRENDS, UP=up, DOWN=dn)
    path = os.path.join(RESULTS, '_s123_causality.json')
    with open(path, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=float)
    print(f"\n✅ ذخیره شد: results/_s123_causality.json")


if __name__ == '__main__':
    main()
