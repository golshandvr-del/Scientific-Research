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
import scalp_engine as se

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
    ZigZag استانداردِ مبتنی بر آستانهٔ دلاری (روی close، با ثبتِ اکسترممِ واقعی).

    منطق: یک اکسترممِ جاری نگه می‌داریم. تا وقتی قیمت در جهتِ فعلی پیش می‌رود،
    اکسترمم را به‌روز می‌کنیم. به‌محضِ آنکه قیمت از اکسترممِ جاری به اندازهٔ
    threshold در خلافِ جهت برگردد، یک pivot تأیید می‌شود و جهت عوض می‌شود.
    این تضمین می‌کند روندها چندکندلی و معنادارند (نه یک‌کندلیِ intrabar).

    خروجی: فهرستِ روندها dict(dir, i_start, i_end, p_start, p_end, move_usd).
    """
    n = len(close)
    if n < 3:
        return []
    pivots = []  # (index, price, type)  type: 'H' or 'L'
    direction = 0            # +1 = در حالِ ساختنِ سقف، -1 = در حالِ ساختنِ کف
    ext_idx = 0
    ext_price = close[0]

    for i in range(1, n):
        price = close[i]
        if direction >= 0:
            # جهتِ صعودی (یا نامعلوم): بالاترین close را دنبال کن
            if price > ext_price:
                ext_price = price; ext_idx = i
            # برگشتِ ≥ threshold از سقف ⇒ سقف تأیید شد
            if ext_price - price >= threshold_usd:
                pivots.append((ext_idx, ext_price, 'H'))
                direction = -1
                ext_price = price; ext_idx = i
        if direction <= 0:
            if price < ext_price:
                ext_price = price; ext_idx = i
            if price - ext_price >= threshold_usd:
                pivots.append((ext_idx, ext_price, 'L'))
                direction = 1
                ext_price = price; ext_idx = i

    # از دنبالهٔ pivotها روندها را بساز
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
def score_trade_vs_trend(trend, entry_bar, exit_bar, close):
    """
    معیارِ نوِ User Note — امتیازِ دقتِ زمان‌بندیِ یک *معاملهٔ واقعی* در برابرِ یک روند.

    ورودی: یک روند + معاملهٔ واقعیِ استراتژی (entry_bar از سیگنال، exit_bar از موتورِ
    TP/SL/trailing/max_hold — یعنی جایی که استراتژی *واقعاً* بست).

    سه امتیاز (۰ تا ۱۰۰):
      start_score : دقتِ کشفِ نقطهٔ «شروع». ۱۰۰ = ورود دقیقاً روی کفِ واقعیِ روند.
                    هرچه دیرتر (کسرِ کمتری از روند باقی مانده) ⇒ امتیازِ کمتر.
                    = ۱۰۰ × (کسرِ دامنه که هنگامِ ورود هنوز مانده بود).
      end_score   : دقتِ کشفِ نقطهٔ «پایان». ۱۰۰ = خروج دقیقاً روی سقفِ واقعیِ روند.
                    = ۱۰۰ × (۱ − |قیمتِ خروج − سقفِ روند| / دامنه).
      captured_pct: درصدِ دامنهٔ روند که معامله واقعاً گرفت (بینِ قیمتِ ورود و خروج).

    برای روندِ صعودی: کف = p_start، سقف = p_end (خرید).
    برای روندِ نزولی: سقف = p_start، کف = p_end (فروش) — «شروع» = بالا، «پایان» = پایین.
    """
    rng = abs(trend['p_end'] - trend['p_start'])
    if rng <= 0:
        return None
    up = (trend['dir'] == 'up')
    c_in = close[entry_bar]
    c_out = close[exit_bar]
    if up:
        remaining_at_entry = (trend['p_end'] - c_in) / rng
        end_closeness = 1.0 - abs(trend['p_end'] - c_out) / rng
        captured = (c_out - c_in) / rng
    else:
        remaining_at_entry = (c_in - trend['p_end']) / rng
        end_closeness = 1.0 - abs(trend['p_end'] - c_out) / rng
        captured = (c_in - c_out) / rng
    return dict(start=float(np.clip(remaining_at_entry, 0, 1) * 100),
                end=float(np.clip(end_closeness, 0, 1) * 100),
                captured=float(np.clip(captured, -1, 1) * 100))


def attribute_trades_to_trend(trend, trades, tol_frac=0.25):
    """
    معاملاتِ (واقعیِ) یک استراتژی را که *درونِ محدودهٔ روند* آغاز شده‌اند پیدا می‌کند.
    یک معامله به روند نسبت داده می‌شود اگر entry_bar آن در بازهٔ
    [i_start - tol, i_end] باشد (tol = کسری از طولِ روند، حداقل ۲ کندل).
    خروجی: فهرستِ (entry_bar, exit_bar) معاملاتِ مرتبط، مرتب بر اساسِ entry.
    """
    i0, i1 = trend['i_start'], trend['i_end']
    dur = max(1, i1 - i0)
    tol = int(np.clip(round(dur * tol_frac), 2, 20))
    lo, hi = max(0, i0 - tol), i1 + tol
    rel = [(int(r['entry_bar']), int(r['exit_bar']))
           for _, r in trades.iterrows()
           if lo <= int(r['entry_bar']) <= hi]
    rel.sort()
    return rel


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


def simulate_brain(seg, sig, direction, sl_pip, tp_pip, max_hold,
                   be_trigger_pip=None, trail_pip=None):
    """معاملاتِ واقعیِ یک مغز را با موتورِ scalp_engine شبیه‌سازی می‌کند."""
    n = len(seg)
    long_sig = sig if direction == 'long' else np.zeros(n, bool)
    short_sig = sig if direction == 'short' else np.zeros(n, bool)
    tr = se.simulate_trades(seg, long_sig, short_sig, sl_pip=sl_pip, tp_pip=tp_pip,
                            asset='XAUUSD', max_hold=max_hold, allow_overlap=False,
                            be_trigger_pip=be_trigger_pip, trail_pip=trail_pip)
    return tr if tr is not None else pd.DataFrame(columns=['entry_bar', 'exit_bar'])


def run_for_direction(df, seg, trends, sigs, dna, target_dir):
    """اجرا و امتیازدهی برای یک جهت (up یا down) با معاملاتِ *واقعیِ* موتور."""
    dir_trends = [t for t in trends if t['dir'] == target_dir][:50]
    close = seg['close'].values

    # مغزها با پارامترهای واقعیِ رکورد (pip؛ pip=0.10$ ⇒ ۱۰pip=۱$):
    #   LONG swing (S81): SL=120pip, TP=1200pip (R:R≈1:10), نگهداریِ بلند.
    #   SCALP (S91): SL=80pip, TP=120pip, نگهداریِ کوتاه.
    #   SHORT (رکورد recent3y): SL=60, BE=6, trail=6, max_hold=8.
    if target_dir == 'up':
        brain_trades = {
            'LONG_midcross': simulate_brain(seg, sigs['LONG_midcross'], 'long',
                                            sl_pip=120, tp_pip=1200, max_hold=288),
            'SCALP_long':    simulate_brain(seg, sigs['SCALP_long'], 'long',
                                            sl_pip=80, tp_pip=120, max_hold=32),
        }
    else:
        brain_trades = {
            'SHORT_midcross': simulate_brain(seg, sigs['SHORT_midcross'], 'short',
                                             sl_pip=60, tp_pip=600, max_hold=8,
                                             be_trigger_pip=6, trail_pip=6),
        }

    rows = []
    for idx, t in enumerate(dir_trends, 1):
        i0 = t['i_start']
        row = dict(num=idx, dir=target_dir, i_start=t['i_start'], i_end=t['i_end'],
                   move_usd=round(t['move_usd'], 2),
                   len_bars=t['i_end'] - t['i_start'],
                   p_start=round(t['p_start'], 1), p_end=round(t['p_end'], 1),
                   adx=round(float(dna['adx'][i0]), 1) if not np.isnan(dna['adx'][i0]) else None,
                   rsi=round(float(dna['rsi'][i0]), 1) if not np.isnan(dna['rsi'][i0]) else None,
                   dist200=round(float(dna['dist200'][i0]), 2) if not np.isnan(dna['dist200'][i0]) else None,
                   detected_by=[], scores={})
        for name, trades in brain_trades.items():
            rel = attribute_trades_to_trend(t, trades)
            if not rel:
                continue
            # اولین معاملهٔ مرتبط = تخمینِ شروع؛ خروجِ آخرین معامله = تخمینِ پایان
            entry_bar = rel[0][0]
            exit_bar = rel[-1][1]
            sc = score_trade_vs_trend(t, entry_bar, exit_bar, close)
            if sc is None:
                continue
            row['detected_by'].append(name)
            row['scores'][name] = dict(start=round(sc['start'], 1),
                                       end=round(sc['end'], 1),
                                       captured=round(sc['captured'], 1),
                                       n_trades=len(rel))
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
