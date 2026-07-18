"""
s116_trend_timing_scorecard.py — پاسخِ عملیِ User Note (کارتِ امتیازِ زمان‌بندیِ روند)
================================================================================
> # قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.**
> تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.
================================================================================

سوالِ فلسفیِ User Note (بُعدِ نو که هرگز تست نشده):
  «تا الان فقط پرسیده‌ایم "آیا استراتژی داخلِ روند سیگنال داد یا نه؟" (باینری).
   اما یک بُعدِ مهم باقی مانده: *دقتِ زمان‌بندی*. یک استراتژی ممکن است یک روند را
   کشف کند اما دیر وارد شود (نصفِ روند را از دست بدهد) یا دیر خارج شود (سود را پس
   بدهد). باید معیاری داشته باشیم که نقاطِ "شروع" و "پایانِ" کشف‌شده چقدر به نقاطِ
   شروع/پایانِ *واقعیِ* روند نزدیک‌اند. هرکدام یک امتیاز داشته باشند.»

پروتکلِ دقیقِ خواسته‌شده در User Note:
  ۱) یک بازهٔ کوتاه از دادهٔ واقعی انتخاب کن که دقیقاً ~۵۰ روندِ صعودی داشته باشد.
  ۲) هر روندِ صعودی باید حداقل ۸ دلار جابجاییِ قیمتِ طلا داشته باشد (زیرِ ۸$ نادیده).
  ۳) روندها را شماره‌گذاری کن؛ برای هر شماره، طولِ روند را به دلار ثبت کن.
  ۴) استراتژی را تست کن؛ ببین کدام روندها کشف می‌شوند و کدام نه.
     (روندهای کوتاه باید توسطِ مغزِ اسکالپ کشف شوند.)
  ۵) معیارِ نو: امتیازِ دقتِ کشفِ نقطهٔ "شروع" و نقطهٔ "پایان" را حساب کن.
  ۶) بفهم چرا هرکدام کشف/کشف‌نشده — DNA رژیمی.
  ۷) همین فرایند را برای روندهای نزولی تکرار کن.

روشِ شناساییِ روندِ واقعی: ZigZag مبتنی بر آستانهٔ دلاری (سوئینگ‌های تأییدشده).
  این «حقیقتِ زمینیِ» روندهاست (بدونِ نگاه به هیچ استراتژی).

سیگنال‌های تست‌شده (سه مغزِ واقعیِ سایت/رکورد):
  • LONG  (mid-cross): قیمت میانگینِ [EMA50,EMA100,SMA200] را رو به بالا قطع کند.
  • SHORT (mid-cross): همان میانگین را رو به پایین قطع کند (لایهٔ SHORTِ رکورد).
  • SCALP (M5→نمایندهٔ M15 اینجا): EMA20>EMA100 & RSI(21)<35 (مغزِ اسکالپِ S91).

توجه: این فایل *تشخیصی* است (پاسخِ فلسفی + معیارِ نوِ زمان‌بندی). سودِ خالصِ رکورد را
تغییر نمی‌دهد مگر آنکه معیارِ نو یک ضعفِ قابلِ‌اصلاح را آشکار کند و اصلاحش سود را بالا ببرد.
================================================================================
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np
import pandas as pd
import indicators as ind

DATA = os.path.join(os.path.dirname(__file__), '..', 'data', 'XAUUSD_M15.csv')
RESULTS = os.path.join(os.path.dirname(__file__), '..', 'results')
MIN_MOVE_USD = 8.0   # حداقل جابجاییِ روند (خواستهٔ User Note)


def load():
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    return df.reset_index(drop=True)


# ==============================================================================
# ۱) شناساییِ روندهای واقعی با ZigZag (حقیقتِ زمینی)
# ==============================================================================
def zigzag_trends(close, high, low, threshold_usd):
    """
    ZigZag ساده مبتنی بر آستانهٔ دلاری.
    یک روند صعودی = از یک کفِ تأییدشده تا سقفِ تأییدشدهٔ بعدی که ≥ threshold باشد.
    خروجی: فهرستِ روندها هرکدام dict(dir, i_start, i_end, p_start, p_end, move_usd).
    نقاطِ اکسترمم بر اساسِ high/low (کف=low، سقف=high) تعیین می‌شوند.
    """
    n = len(close)
    c = close
    # پیدا کردنِ نقاطِ چرخشِ ZigZag
    pivots = []  # (index, price, type)  type: 'H' or 'L'
    # از اولین کندل شروع؛ جهتِ اولیه را با اولین حرکتِ ≥ threshold تعیین می‌کنیم
    last_pivot_idx = 0
    last_pivot_price = c[0]
    direction = 0  # +1 up-leg در حال شکل‌گیری، -1 down-leg، 0 نامعلوم
    cur_ext_idx = 0
    cur_ext_price = c[0]

    for i in range(1, n):
        if direction >= 0:
            # در up-leg، بالاترین high را دنبال کن
            if high[i] > cur_ext_price:
                cur_ext_price = high[i]; cur_ext_idx = i
            # آیا از سقفِ فعلی به اندازهٔ threshold برگشته؟ ⇒ تأییدِ یک سقف
            if cur_ext_price - low[i] >= threshold_usd and direction > 0:
                pivots.append((cur_ext_idx, cur_ext_price, 'H'))
                direction = -1
                last_pivot_idx = cur_ext_idx; last_pivot_price = cur_ext_price
                cur_ext_price = low[i]; cur_ext_idx = i
            elif direction == 0 and cur_ext_price - low[i] >= threshold_usd:
                # اولین سقف تأیید شد
                pivots.append((cur_ext_idx, cur_ext_price, 'H'))
                direction = -1
                last_pivot_idx = cur_ext_idx; last_pivot_price = cur_ext_price
                cur_ext_price = low[i]; cur_ext_idx = i
        if direction <= 0:
            if low[i] < cur_ext_price:
                cur_ext_price = low[i]; cur_ext_idx = i
            if high[i] - cur_ext_price >= threshold_usd and direction < 0:
                pivots.append((cur_ext_idx, cur_ext_price, 'L'))
                direction = 1
                last_pivot_idx = cur_ext_idx; last_pivot_price = cur_ext_price
                cur_ext_price = high[i]; cur_ext_idx = i
            elif direction == 0 and high[i] - cur_ext_price >= threshold_usd:
                pivots.append((cur_ext_idx, cur_ext_price, 'L'))
                direction = 1
                last_pivot_idx = cur_ext_idx; last_pivot_price = cur_ext_price
                cur_ext_price = high[i]; cur_ext_idx = i

    # از دنبالهٔ pivotها روندها را بساز (هر جفتِ متوالیِ L→H = صعودی، H→L = نزولی)
    trends = []
    for k in range(1, len(pivots)):
        i0, p0, t0 = pivots[k - 1]
        i1, p1, t1 = pivots[k]
        if i1 <= i0:
            continue
        move = p1 - p0
        if t0 == 'L' and t1 == 'H' and move >= threshold_usd:
            trends.append(dict(dir='up', i_start=i0, i_end=i1,
                               p_start=p0, p_end=p1, move_usd=float(move)))
        elif t0 == 'H' and t1 == 'L' and (-move) >= threshold_usd:
            trends.append(dict(dir='down', i_start=i0, i_end=i1,
                               p_start=p0, p_end=p1, move_usd=float(-move)))
    return trends


# ==============================================================================
# ۲) سیگنال‌های سه مغزِ واقعی
# ==============================================================================
def build_signals(df):
    c = df['close']; p = c.values
    e20 = ind.ema(c, 20).values
    e50 = ind.ema(c, 50).values
    e100 = ind.ema(c, 100).values
    s200 = ind.sma(c, 200).values
    rsi21 = ind.rsi(c, 21).values
    mid = np.nanmean(np.column_stack([e50, e100, s200]), axis=1)

    long_cross = (np.r_[False, p[:-1] < mid[:-1]]) & (p > mid)
    short_cross = (np.r_[False, p[:-1] > mid[:-1]]) & (p < mid)
    scalp_long = (e20 > e100) & (rsi21 < 35)
    # فقط لبهٔ ورودِ اسکالپ (گذر از False به True) تا با کندلِ ورود هم‌تراز شود
    scalp_edge = scalp_long & (~np.r_[False, scalp_long[:-1]])

    return dict(LONG_midcross=long_cross,
                SHORT_midcross=short_cross,
                SCALP_long=scalp_edge)


# ==============================================================================
# ۳) امتیازِ دقتِ زمان‌بندی (معیارِ نوِ User Note)
# ==============================================================================
def timing_scores(trend, sig_bars, tol_bars=8):
    """
    برای یک روند و مجموعه‌کندل‌هایی که یک استراتژی سیگنال داده، محاسبه می‌کند:

      detected       : آیا حداقل یک سیگنال در پنجرهٔ روند (با تحملِ tol_bars) هست؟
      entry_bar      : اولین سیگنالِ مرتبط با این روند.
      start_score    : دقتِ کشفِ نقطهٔ شروع (۱۰۰ = دقیقاً روی کفِ روند؛ کاهش هرچه دیرتر).
                       بر حسبِ درصدِ دامنهٔ روند که در لحظهٔ ورود «باقی مانده» بود.
      end_score      : دقتِ کشفِ نقطهٔ پایان — اینجا با «آخرین سیگنالِ داخلِ روند»
                       به‌عنوان تخمینِ پایان سنجیده می‌شود (چقدر نزدیک به سقفِ واقعی).
      captured_pct   : درصدِ دامنهٔ روند که بینِ اولین و آخرین سیگنال پوشش داده شد.

    منطق (برای روندِ صعودی):
      دامنه = p_end - p_start (بر حسبِ $). اگر استراتژی در کندلِ b وارد شود، قیمتِ
      ورود ≈ close[b]. کسرِ روند که «هنوز مانده» = (p_end - close[b]) / range.
      start_score = ۱۰۰ × کسرِ باقی‌مانده در لحظهٔ اولین سیگنال (زودتر = بهتر).
      end_score   = ۱۰۰ × (۱ − |p_end - close[last_sig]| / range)  (نزدیک‌تر به سقف = بهتر).
    """
    i0, i1 = trend['i_start'], trend['i_end']
    rng = abs(trend['p_end'] - trend['p_start'])
    if rng <= 0:
        return None
    lo = max(0, i0 - tol_bars)
    hi = i1 + tol_bars
    rel = [b for b in sig_bars if lo <= b <= hi]
    if not rel:
        return dict(detected=False, entry_bar=None, start_score=0.0,
                    end_score=0.0, captured_pct=0.0, n_sig=0)
    return dict(detected=True, entry_bar=int(rel[0]), last_bar=int(rel[-1]),
                n_sig=len(rel), _range=rng, _trend=trend, _rel=rel)


def finalize_scores(sc, close):
    """محاسبهٔ start/end/captured با استفاده از close واقعی در کندل‌های سیگنال."""
    if not sc.get('detected'):
        return sc
    t = sc['_trend']; rng = sc['_range']
    up = (t['dir'] == 'up')
    first_b = sc['entry_bar']; last_b = sc['last_bar']
    c_first = close[first_b]; c_last = close[last_b]
    if up:
        remaining_at_entry = (t['p_end'] - c_first) / rng      # هرچه بیشتر، زودتر وارد شده
        end_closeness = 1.0 - abs(t['p_end'] - c_last) / rng   # هرچه نزدیک‌تر به سقف
    else:
        remaining_at_entry = (c_first - t['p_end']) / rng
        end_closeness = 1.0 - abs(t['p_end'] - c_last) / rng
    start_score = float(np.clip(remaining_at_entry, 0, 1) * 100)
    end_score = float(np.clip(end_closeness, 0, 1) * 100)
    captured = float(np.clip(abs(c_last - c_first) / rng, 0, 1) * 100)
    sc['start_score'] = start_score
    sc['end_score'] = end_score
    sc['captured_pct'] = captured
    # پاک‌سازیِ فیلدهای داخلی برای JSON
    for k in ('_range', '_trend', '_rel'):
        sc.pop(k, None)
    return sc


# ==============================================================================
# ۴) DNA رژیمی برای تحلیلِ چرایی
# ==============================================================================
def regime_dna(df):
    c = df['close']
    adx14 = ind.adx(df, 14)[0].values
    atr14 = ind.atr(df, 14).values
    rsi14 = ind.rsi(c, 14).values
    slope50 = ind.rolling_slope(c, 50).values
    e50 = ind.ema(c, 50).values; s200 = ind.sma(c, 200).values
    dist200 = (c.values - s200) / s200 * 100
    return dict(adx=adx14, atr=atr14, rsi=rsi14, slope50=slope50, dist200=dist200)


def find_window_with_n_trends(df, target_dir, target_n=50, win=5000):
    """
    پنجره‌ای پیدا کن که ~target_n روندِ در جهتِ target_dir (≥MIN_MOVE) داشته باشد.
    پنجره را از انتها به عقب می‌لغزانیم تا نزدیک‌ترین شمارش را بگیریم.
    """
    n = len(df)
    best = None
    for start in range(n - win, 0, -win // 2):
        seg = df.iloc[start:start + win].reset_index(drop=True)
        tr = zigzag_trends(seg['close'].values, seg['high'].values,
                           seg['low'].values, MIN_MOVE_USD)
        cnt = sum(1 for t in tr if t['dir'] == target_dir)
        if best is None or abs(cnt - target_n) < abs(best[1] - target_n):
            best = (start, cnt)
        if cnt >= target_n:
            # پنجره را کوچک کن تا دقیقاً ~target_n برسد
            return start, win, tr
    start = best[0]
    seg = df.iloc[start:start + win].reset_index(drop=True)
    tr = zigzag_trends(seg['close'].values, seg['high'].values,
                       seg['low'].values, MIN_MOVE_USD)
    return start, win, tr


def run_for_direction(df, seg, trends, sigs, dna, target_dir):
    """اجرا و امتیازدهی برای یک جهت (up یا down)."""
    dir_trends = [t for t in trends if t['dir'] == target_dir]
    # فقط ~۵۰ روندِ اول را نگه دار
    dir_trends = dir_trends[:50]
    close = seg['close'].values

    # کدام مغزها برای این جهت مرتبط‌اند
    if target_dir == 'up':
        brains = {'LONG_midcross': sigs['LONG_midcross'],
                  'SCALP_long': sigs['SCALP_long']}
    else:
        brains = {'SHORT_midcross': sigs['SHORT_midcross']}

    brain_bars = {name: list(np.where(sig)[0]) for name, sig in brains.items()}

    rows = []
    for idx, t in enumerate(dir_trends, 1):
        row = dict(num=idx, dir=target_dir, i_start=t['i_start'], i_end=t['i_end'],
                   move_usd=round(t['move_usd'], 2),
                   len_bars=t['i_end'] - t['i_start'],
                   p_start=round(t['p_start'], 1), p_end=round(t['p_end'], 1))
        # DNA در نقطهٔ شروعِ روند
        i0 = t['i_start']
        row['adx'] = round(float(dna['adx'][i0]), 1) if not np.isnan(dna['adx'][i0]) else None
        row['rsi'] = round(float(dna['rsi'][i0]), 1) if not np.isnan(dna['rsi'][i0]) else None
        row['dist200'] = round(float(dna['dist200'][i0]), 2) if not np.isnan(dna['dist200'][i0]) else None
        row['detected_by'] = []
        row['scores'] = {}
        for name, bars in brain_bars.items():
            sc = timing_scores(t, bars)
            sc = finalize_scores(sc, close)
            if sc.get('detected'):
                row['detected_by'].append(name)
                row['scores'][name] = dict(
                    start=round(sc['start_score'], 1),
                    end=round(sc['end_score'], 1),
                    captured=round(sc['captured_pct'], 1),
                    n_sig=sc['n_sig'])
        row['detected'] = len(row['detected_by']) > 0
        rows.append(row)
    return rows


def summarize(rows, label):
    det = [r for r in rows if r['detected']]
    miss = [r for r in rows if not r['detected']]
    n = len(rows)
    print(f"\n{'='*80}\n{label}: {n} روند  |  کشف‌شده {len(det)} ({len(det)/max(n,1)*100:.0f}%)  |  کشف‌نشده {len(miss)}")
    # میانگینِ امتیازها
    all_start = []; all_end = []; all_cap = []
    for r in det:
        for name, s in r['scores'].items():
            all_start.append(s['start']); all_end.append(s['end']); all_cap.append(s['captured'])
    if all_start:
        print(f"  میانگینِ امتیازِ شروع = {np.mean(all_start):.1f}/100  |  "
              f"امتیازِ پایان = {np.mean(all_end):.1f}/100  |  پوشش = {np.mean(all_cap):.1f}%")
    # DNA مقایسه (چرایی)
    def avg(lst, key):
        v = [r[key] for r in lst if r[key] is not None]
        return np.mean(v) if v else float('nan')
    print(f"  DNA کشف‌شده : ADX={avg(det,'adx'):.1f}  RSI={avg(det,'rsi'):.1f}  dist200={avg(det,'dist200'):.2f}%  طول={avg(det,'len_bars'):.0f}کندل  حرکت={avg(det,'move_usd'):.1f}$")
    print(f"  DNA کشف‌نشده: ADX={avg(miss,'adx'):.1f}  RSI={avg(miss,'rsi'):.1f}  dist200={avg(miss,'dist200'):.2f}%  طول={avg(miss,'len_bars'):.0f}کندل  حرکت={avg(miss,'move_usd'):.1f}$")
    return dict(n=n, detected=len(det), missed=len(miss),
                mean_start=float(np.mean(all_start)) if all_start else 0.0,
                mean_end=float(np.mean(all_end)) if all_end else 0.0,
                mean_captured=float(np.mean(all_cap)) if all_cap else 0.0,
                dna_det=dict(adx=avg(det,'adx'), rsi=avg(det,'rsi'), dist200=avg(det,'dist200'),
                             len_bars=avg(det,'len_bars'), move=avg(det,'move_usd')),
                dna_miss=dict(adx=avg(miss,'adx'), rsi=avg(miss,'rsi'), dist200=avg(miss,'dist200'),
                              len_bars=avg(miss,'len_bars'), move=avg(miss,'move_usd')))


def main():
    print("=" * 80)
    print("s116 — کارتِ امتیازِ زمان‌بندیِ روند (پاسخِ عملیِ User Note)")
    print("=" * 80)
    df = load()
    print(f"کلِ داده: {len(df)} کندل  |  آستانهٔ روند: ≥{MIN_MOVE_USD}$")

    out = {'min_move_usd': MIN_MOVE_USD}

    for target_dir, label in [('up', 'صعودی'), ('down', 'نزولی')]:
        start, win, _ = find_window_with_n_trends(df, target_dir, 50, 5000)
        seg = df.iloc[start:start + win].reset_index(drop=True)
        trends = zigzag_trends(seg['close'].values, seg['high'].values,
                               seg['low'].values, MIN_MOVE_USD)
        sigs = build_signals(seg)
        dna = regime_dna(seg)
        rows = run_for_direction(df, seg, trends, sigs, dna, target_dir)
        t0 = seg['dt'].iloc[0].strftime('%Y-%m-%d')
        t1 = seg['dt'].iloc[min(win, len(seg)) - 1].strftime('%Y-%m-%d')
        print(f"\n### روندهای {label} — پنجره [{start}:{start+win}] ({t0} → {t1})")
        # چاپِ جدولِ روندها
        print(f"{'#':>3} {'طول$':>7} {'کندل':>5} {'ADX':>5} {'RSI':>5} {'کشف':>6}  امتیازها(start/end/cap)")
        for r in rows:
            det = ','.join(r['detected_by']) if r['detected'] else '—'
            sc_str = ''
            for name, s in r['scores'].items():
                sc_str += f"[{name.split('_')[0]}:{s['start']:.0f}/{s['end']:.0f}/{s['captured']:.0f}]"
            adx = f"{r['adx']:.0f}" if r['adx'] is not None else '-'
            rsi = f"{r['rsi']:.0f}" if r['rsi'] is not None else '-'
            print(f"{r['num']:>3} {r['move_usd']:>7.1f} {r['len_bars']:>5} {adx:>5} {rsi:>5} {det[:14]:>14}  {sc_str}")
        summ = summarize(rows, f"جمع‌بندیِ {label}")
        out[target_dir] = dict(window=[int(start), int(start + win)],
                               date=[t0, t1], rows=rows, summary=summ)

    with open(os.path.join(RESULTS, '_s116_timing.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print("\n✅ ذخیره شد: results/_s116_timing.json")


if __name__ == '__main__':
    main()
