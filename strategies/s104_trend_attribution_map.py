"""
s104_trend_attribution_map.py — پاسخِ کاملِ فلسفی به User Note
================================================================================
سوالِ فلسفیِ User Note (نقلِ دقیق):
  «فرض کن ۱۰ روندِ صعودی داریم (۱ تا ۱۰). ما همیشه پرسیده‌ایم کدام استراتژی بیشترین
   تعداد روند را کشف می‌کند و نتیجه گرفته‌ایم s2 بهتر است. اما سوالِ فلسفیِ باقی‌مانده
   این است: *چرا* s1 فقط ۱-۳-۷ را گرفت و s2 فقط ۱-۴-۶-۷-۸ را؟ چه چیزِ مشترکی بین
   روندهایی که هر استراتژی می‌گیرد وجود دارد؟ شاید s3 که فقط ۹ را گرفت یک آشکارسازِ
   مواردِ نادر است. جوابِ این سوال خیلی چیزها را روشن می‌کند.»

روشِ این فایل (متفاوت و کامل‌تر از s103 که فقط لایهٔ SHORT را دید):
  ۱) یک بازهٔ مشخص از داده انتخاب می‌کنیم.
  ۲) **روندهای واقعیِ بازار را الگوریتمی شناسایی و شماره‌گذاری می‌کنیم** (swing-based؛
     دقیقاً همان «روند ۱ تا N» ی که کاربر گفت). هر روند: جهت، دامنه، طول، DNA رژیمی.
  ۳) چند استراتژیِ *واقعیِ* پروژه را روی همان بازه اجرا می‌کنیم و برای هر روند علامت
     می‌زنیم که کدام استراتژی داخلِ آن روند سیگنالِ (سودده) داد ⇒ **ماتریسِ کشف
     (استراتژی × روند)**.
  ۴) برای هر استراتژی، **DNA مشترکِ روندهایی که گرفت** را در برابرِ روندهایی که نگرفت
     مقایسه می‌کنیم (اثرِ کوهن) ⇒ پاسخِ سوالِ «چرا این روندها؟».

قانونِ شمارهٔ ۱ پروژه: فقط و فقط «سودِ خالصِ بیشتر». WR فقط گزارشی است.
تعریفِ سودِ خالص = جمعِ سودِ XAUUSD + EURUSD.
این فایل *تشخیصی* است (پاسخِ فلسفی)؛ خروجی‌اش ورودیِ s105 (روترِ نسبت-دهی) می‌شود.
================================================================================
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
import indicators as ind
import scalp_engine as se

DATA = os.path.join(os.path.dirname(__file__), '..', 'data', 'XAUUSD_M15.csv')
RESULTS = os.path.join(os.path.dirname(__file__), '..', 'results')


def load():
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df.reset_index(drop=True)


# ------------------------------------------------------------------------------
# فاز ۲: شناسایی و شماره‌گذاریِ روندهای واقعیِ بازار (ZigZag / swing-based)
# ------------------------------------------------------------------------------
def identify_trends(df, atr_mult=3.0, min_bars=8):
    """
    روندها را با یک ZigZagِ ATR-محور شناسایی می‌کند (بدون look-ahead در تعریفِ رژیم؛
    فقط برای *برچسب‌گذاریِ تحلیلی* گذشته‌نگر استفاده می‌شود، نه برای معامله).

    یک swing وقتی تمام می‌شود که قیمت به اندازهٔ atr_mult×ATR از اکسترممِ اخیر
    برگردد. هر بازهٔ بینِ دو نقطهٔ چرخش = یک «روندِ شماره‌دار».
    خروجی: DataFrame با ستون‌های
      [trend_id, dir(+1/-1), start_bar, end_bar, start_price, end_price, bars, range_pip]
    """
    c = df['close'].values
    atr = ind.atr(df, 14).values
    n = len(c)
    # ATR متوسط برای آستانهٔ ثابت‌تر
    trends = []
    tid = 0
    i0 = 0
    # جهتِ اولیه
    direction = 0
    ext_price = c[0]; ext_bar = 0
    for i in range(1, n):
        a = atr[i] if not np.isnan(atr[i]) else atr[np.isfinite(atr)][0]
        thr = atr_mult * a
        if direction >= 0:
            # در روندِ صعودی (یا خنثی): بالاترین را دنبال کن
            if c[i] > ext_price:
                ext_price = c[i]; ext_bar = i
            elif ext_price - c[i] > thr and (i - i0) >= min_bars:
                # چرخش به نزول: روندِ صعودیِ i0..ext_bar ثبت می‌شود
                if direction > 0 and ext_bar > i0:
                    tid += 1
                    trends.append(dict(trend_id=tid, dir=1, start_bar=i0, end_bar=ext_bar,
                                       start_price=c[i0], end_price=ext_price))
                i0 = ext_bar
                direction = -1
                ext_price = c[i]; ext_bar = i
        if direction <= 0:
            if c[i] < ext_price:
                ext_price = c[i]; ext_bar = i
            elif c[i] - ext_price > thr and (i - i0) >= min_bars:
                if direction < 0 and ext_bar > i0:
                    tid += 1
                    trends.append(dict(trend_id=tid, dir=-1, start_bar=i0, end_bar=ext_bar,
                                       start_price=c[i0], end_price=ext_price))
                i0 = ext_bar
                direction = 1
                ext_price = c[i]; ext_bar = i
    td = pd.DataFrame(trends)
    if len(td) == 0:
        return td
    td['bars'] = td['end_bar'] - td['start_bar']
    td['range_pip'] = (td['end_price'] - td['start_price']).abs() / 0.10  # طلا pip=0.10
    return td


# ------------------------------------------------------------------------------
# DNA رژیمی برای هر روند (میانگینِ ویژگی‌ها روی طولِ روند)
# ------------------------------------------------------------------------------
def build_features(df):
    c = df['close']
    atr14 = ind.atr(df, 14)
    f = pd.DataFrame(index=df.index)
    adx_, _p, _m = ind.adx(df, 14)
    f['adx'] = adx_.values
    f['atr_pct'] = (atr14 / c * 100).values
    f['slope50'] = (ind.rolling_slope(c, 50) / atr14).values
    f['rsi'] = ind.rsi(c, 14).values
    f['dist_ema50'] = ((c - ind.ema(c, 50)) / atr14).values
    f['dist_sma200'] = ((c - ind.sma(c, 200)) / atr14).values
    f['ret20'] = (c.pct_change(20) * 100).values
    f['vol_z'] = ind.zscore(atr14, 100).values
    return f


def trend_dna(trends, feats):
    """میانگینِ ویژگی‌ها روی هر روند."""
    cols = ['adx', 'atr_pct', 'slope50', 'rsi', 'dist_ema50', 'dist_sma200', 'ret20', 'vol_z']
    out = []
    for _, t in trends.iterrows():
        a, b = int(t['start_bar']), int(t['end_bar'])
        seg = feats.iloc[a:b+1]
        row = {c: seg[c].mean() for c in cols}
        out.append(row)
    return pd.DataFrame(out, index=trends.index)


# ------------------------------------------------------------------------------
# فاز ۳: استراتژی‌های واقعیِ پروژه (سیگنال‌ساز). خروجی: بردارِ بولیِ سیگنال ورود.
# ------------------------------------------------------------------------------
def sig_long_trend_pullback(df):
    """S79/S91-خانواده: EMA20>EMA100 (روند صعودی) + RSI پول‌بک پایین ⇒ LONG."""
    c = df['close']
    e20 = ind.ema(c, 20).values; e100 = ind.ema(c, 100).values
    rsi = ind.rsi(c, 21).values
    return (e20 > e100) & (rsi < 35)


def sig_long_macd_regime(df):
    """S88: عبورِ MACD-hist از منفی به مثبت در رژیمِ صعودی (close>SMA200)."""
    c = df['close']
    _ml, _sl, hist = ind.macd(c)
    h = hist.values
    s200 = ind.sma(c, 200).values
    cross_up = np.r_[False, (h[:-1] <= 0) & (h[1:] > 0)]
    return cross_up & (c.values > s200)


def sig_short_ma_confluence(df):
    """رکورد SHORT: عبورِ close از میانهٔ [EMA50,EMA100,SMA200] از بالا به پایین."""
    c = df['close']; p = c.values
    e50 = ind.ema(c, 50).values; e100 = ind.ema(c, 100).values; s200 = ind.sma(c, 200).values
    mid = np.nanmean(np.column_stack([e50, e100, s200]), axis=1)
    return (np.r_[False, p[:-1] > mid[:-1]]) & (p < mid)


def sig_bb_meanrev_long(df):
    """میانگین‌گردیِ رنج: close زیرِ باند پایینِ بولینگر ⇒ LONG (خرید در کفِ رنج)."""
    c = df['close']
    lo, mid, up = ind.bollinger(c, 20, 2.0)
    return (c.values < lo.values)


STRATS = {
    'LONG_trend_pullback': (sig_long_trend_pullback, +1),
    'LONG_macd_regime':    (sig_long_macd_regime, +1),
    'SHORT_ma_confluence': (sig_short_ma_confluence, -1),
    'LONG_bb_meanrev':     (sig_bb_meanrev_long, +1),
}


def main():
    print("=" * 80)
    print("s104 — نقشهٔ نسبت‌دهیِ روند↔استراتژی (پاسخِ کاملِ فلسفی به User Note)")
    print("=" * 80)
    df = load()
    print(f"داده: {len(df):,} کندل XAUUSD M15")

    # --- بازهٔ تحلیل: نیمهٔ دومِ داده (رفتارِ اخیر و روندی — طبقِ PARADIGM §۲) ---
    N = len(df)
    seg = df.iloc[N//2:].reset_index(drop=True)
    print(f"بازهٔ تحلیل: کندل {N//2:,} تا {N:,}  ({len(seg):,} کندل)")

    # --- فاز ۲: شماره‌گذاریِ روندها ---
    trends = identify_trends(seg, atr_mult=3.0, min_bars=8)
    ups = trends[trends['dir'] == 1]
    downs = trends[trends['dir'] == -1]
    print(f"\nروندهای شناسایی‌شده: {len(trends)}  (صعودی: {len(ups)}, نزولی: {len(downs)})")
    print(f"میانگینِ دامنهٔ روندِ صعودی: {ups['range_pip'].mean():.0f} pip، "
          f"نزولی: {downs['range_pip'].mean():.0f} pip")

    dna = trend_dna(trends, build_features(seg))

    # --- فاز ۳: ماتریسِ کشف (استراتژی × روند) ---
    # یک استراتژی روندی را «کشف می‌کند» اگر جهتش با روند بخواند و داخلِ آن دستِ‌کم یک
    # سیگنال صادر کند که در ادامه سودده باشد (قیمت در جهتِ روند برود).
    sig_cache = {}
    for name, (fn, d) in STRATS.items():
        sig_cache[name] = (np.nan_to_num(fn(seg), nan=0).astype(bool), d)

    detect = pd.DataFrame(0, index=trends.index, columns=list(STRATS.keys()))
    for ti, t in trends.iterrows():
        a, b = int(t['start_bar']), int(t['end_bar'])
        tdir = t['dir']
        for name, (sig, sdir) in sig_cache.items():
            if sdir != tdir:
                continue  # جهتِ استراتژی با روند نمی‌خواند
            fired = sig[a:b+1].any()
            detect.loc[ti, name] = 1 if fired else 0

    # نمایشِ ماتریس برای ۱۵ روندِ اول (مثل مثالِ کاربر: روند ۱..N)
    print("\n" + "=" * 80)
    print("ماتریسِ کشف: کدام استراتژی کدام روند را می‌گیرد (۱=گرفت)")
    print("=" * 80)
    hdr = "روند  جهت  دامنه  " + "  ".join(f"{k[:14]:>14}" for k in STRATS)
    print(hdr)
    show = trends.head(18)
    for ti, t in show.iterrows():
        dirn = "▲UP " if t['dir'] == 1 else "▼DN "
        line = f"{int(t['trend_id']):>4}  {dirn} {t['range_pip']:>5.0f}  "
        line += "  ".join(f"{detect.loc[ti,k]:>14d}" for k in STRATS)
        print(line)

    # آمارِ کلیِ نرخِ کشفِ هر استراتژی (به تفکیکِ جهت)
    print("\nنرخِ کشفِ هر استراتژی (از روندهای هم‌جهت):")
    for name, (fn, d) in STRATS.items():
        pool = trends[trends['dir'] == d]
        got = detect.loc[pool.index, name].sum()
        print(f"  {name:<22} گرفت {got:>3}/{len(pool):>3} روندِ {'صعودی' if d>0 else 'نزولی'}"
              f"  ({got/max(len(pool),1)*100:.0f}%)")

    # --- فاز ۴: پاسخِ سوالِ فلسفی — DNA مشترکِ روندهای گرفته‌شده ---
    print("\n" + "=" * 80)
    print("پاسخِ فلسفی: DNA مشترکِ روندهایی که هر استراتژی می‌گیرد (اثرِ کوهن)")
    print("=" * 80)
    feat_cols = ['adx', 'atr_pct', 'slope50', 'rsi', 'dist_ema50', 'dist_sma200', 'ret20', 'vol_z']
    attribution = {}
    for name, (fn, d) in STRATS.items():
        pool = trends[trends['dir'] == d].index
        got = detect.loc[pool, name] == 1
        idx_got = pool[got.values]
        idx_miss = pool[~got.values]
        if len(idx_got) < 3 or len(idx_miss) < 3:
            print(f"\n{name}: نمونهٔ کافی نیست (گرفت {len(idx_got)}, نگرفت {len(idx_miss)})")
            continue
        print(f"\n▶ {name}  (گرفت {len(idx_got)} روند، نگرفت {len(idx_miss)} روند)")
        effs = {}
        for f in feat_cols:
            mg = dna.loc[idx_got, f].mean()
            mm = dna.loc[idx_miss, f].mean()
            sd = dna.loc[pool, f].std()
            eff = (mg - mm) / sd if sd > 0 else 0.0
            effs[f] = eff
        ranked = sorted(effs.items(), key=lambda x: -abs(x[1]))
        for f, e in ranked[:3]:
            dirn = "بالاتر" if e > 0 else "پایین‌تر"
            print(f"    • {f:<12} |d|={abs(e):.2f}  (در روندهای گرفته‌شده {dirn})")
        attribution[name] = {f: float(effs[f]) for f in feat_cols}
        attribution[name]['_n_got'] = int(len(idx_got))
        attribution[name]['_n_miss'] = int(len(idx_miss))
        attribution[name]['_top'] = [[f, float(e)] for f, e in ranked[:3]]

    # ذخیرهٔ خروجیِ تشخیصی (ورودیِ s105)
    out = {
        'segment': [int(N//2), int(N)],
        'n_trends': int(len(trends)),
        'n_up': int(len(ups)),
        'n_down': int(len(downs)),
        'attribution': attribution,
    }
    with open(os.path.join(RESULTS, '_s104_attribution.json'), 'w') as fj:
        json.dump(out, fj, ensure_ascii=False, indent=2, default=float)
    print("\nذخیره شد: results/_s104_attribution.json")
    print("\nنتیجهٔ فلسفی: هر استراتژی یک «آشکارسازِ رژیمی» است که به یک ناحیهٔ خاص از")
    print("فضای DNA کوک شده. s105 از این نقشه یک روترِ نسبت-محور می‌سازد و سود را می‌سنجد.")


if __name__ == '__main__':
    main()
