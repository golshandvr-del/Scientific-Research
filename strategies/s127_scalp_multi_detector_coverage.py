"""
s127_scalp_multi_detector_coverage.py — موتورِ اسکالپِ چند-آشکارسازِ مکمل (پوششِ ۸۰٪ روند)
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.**
> تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD. WR فقط یک عددِ گزارشی است.
> این فایل یک **ابزارِ تشخیصیِ کشف (detection diagnostic)** است و معامله‌ای به
> پرتفوی اضافه نمی‌کند؛ پس سودِ خالص = رکوردِ فعلی (+$95,645) بدون تغییر باقی می‌ماند.
> هدفِ این ابزار «افزایشِ پوششِ کشفِ روندِ اسکالپ تا ≥۸۰٪» است تا در چرخهٔ بعد بتوان
> یک موتورِ اسکالپِ سودده با پوششِ بالا ساخت (کیفیتِ ورود جداگانه بهینه می‌شود).
================================================================================

پاسخِ عمیق‌تر به User Note (سؤالِ فلسفی):
  در چرخه‌های قبل (s119/s123/s124) اثبات شد موتورِ *تک‌آشکارسازِ* فعلی
  (EMA20>EMA100 ∧ RSI(21)<35) به‌دلیلِ *تناقضِ دو شرط* فقط ۰.۱٪ کندل‌ها را
  فعال می‌کند ⇒ پوششِ روند فقط ~۱–۱۶٪. این «صیّادِ نادر» است.

  استعارهٔ User Note دقیقاً همین است: s1 روندهای ۱-۳-۷ را می‌بیند، s2 روندهای
  ۱-۴-۶-۷-۸ را، s3 فقط روندِ ۹ (نادر). *چرا؟* چون هر استراتژی یک DNAِ خاص از روند
  را تشخیص می‌دهد. نتیجهٔ منطقی: برای پوششِ ۸۰٪، به‌جای یک موتور، باید یک **مجموعهٔ
  آشکارسازهای مکمل** ساخت که *اتحادِ* آن‌ها اکثریتِ DNAها را بپوشاند.

  این فایل ۵ آشکارسازِ مکمل را می‌سازد، هرکدام را روی ماتریسِ ۵۰+۵۰ روند آزمون
  می‌کند، و برای هر روند ثبت می‌کند «کدام آشکارساز آن را گرفت» — تا صریحاً به سؤالِ
  «چرا این روند کشف شد و آن یکی نه» پاسخِ کمّی بدهد.

آشکارسازها (هرکدام فقط «شروعِ روند» را برای پوشش تشخیص می‌دهد، نه کیفیتِ ورود):
  D1  MOMO   — شکستِ مومنتومی: close از سقفِ N=10 کندلِ اخیر عبور کند (روندهای تندِ کوتاه).
  D2  PULL   — pullbackِ روندی (موتورِ فعلیِ سایت، شل‌شده): EMA20>EMA100 ∧ RSI(21)<45.
  D3  MACD   — تقاطعِ صعودیِ MACD(12,26,9): خطِ MACD از سیگنال بالا بزند (روندهای متوسط).
  D4  EXPAND — انبساطِ دامنه: ATR رو به رشد + close>EMA20 (شروعِ فازِ نوسانی).
  D5  MSWING — ریزساختارِ price-action: higher-high پس از higher-low (روندهای نادرِ کوچک).
(برای DOWN آینهٔ متقارن هر ۵ آشکارساز استفاده می‌شود.)
================================================================================
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), '..')
DATA = os.path.join(ROOT, 'data', 'XAUUSD_M5.csv')
RESULTS = os.path.join(ROOT, 'results')
MIN_MOVE_USD = 8.0
TARGET_TRENDS = 50
COVERAGE_GOAL = 80.0   # هدفِ User Note


# ------------------------------------------------------------------ اندیکاتورها
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


def macd(c, f=12, s=26, sig=9):
    mline = ema(c, f) - ema(c, s)
    sline = ema(mline, sig)
    return mline, sline


# ------------------------------------------------ حقیقتِ زمینیِ روندها (ZigZag close-based)
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


# ============================================================ ۵ آشکارسازِ مکمل
def build_detectors(c, h, l, direction):
    """
    برای هر آشکارساز، آرایهٔ بولیِ سیگنالِ هم‌جهت را می‌سازد.
    خروجی: dict[name] = set(barهایی که آشکارساز فایر کرد).
    همه forward-safe: هر سیگنال فقط از دادهٔ تا همان کندل استفاده می‌کند
    (اندیکاتورها EWM/rolling هستند و هیچ نگاهِ به‌جلو ندارند).
    """
    n = len(c)
    e20 = ema(c, 20); e50 = ema(c, 50); e100 = ema(c, 100)
    r21 = rsi(c, 21)
    ad, atr_arr = adx(h, l, c, 14)
    mline, sline = macd(c)

    # rolling high/low (بدونِ کندلِ جاری برای forward-safety در breakout)
    N = 10
    ph = pd.Series(h).rolling(N).max().shift(1).values     # بالاترین high در N کندلِ قبل
    pl = pd.Series(l).rolling(N).min().shift(1).values
    atr_prev = pd.Series(atr_arr).shift(3).values          # ATR سه کندل قبل برای مقایسهٔ انبساط

    def _up():
        d = {}
        # D1 MOMO — شکستِ سقفِ N کندلِ اخیر
        d['D1_MOMO'] = np.nan_to_num((c > ph), nan=0).astype(bool)
        # D2 PULL — موتورِ فعلیِ شل‌شده
        d['D2_PULL'] = np.nan_to_num((e20 > e100) & (r21 < 45), nan=0).astype(bool)
        # D3 MACD — تقاطعِ صعودی
        cross_up = (mline > sline) & (np.roll(mline, 1) <= np.roll(sline, 1))
        cross_up[0] = False
        d['D3_MACD'] = np.nan_to_num(cross_up, nan=0).astype(bool)
        # D4 EXPAND — انبساطِ ATR + بالای EMA20
        d['D4_EXPAND'] = np.nan_to_num((atr_arr > atr_prev * 1.10) & (c > e20), nan=0).astype(bool)
        # D5 MSWING — higher-high پس از higher-low (price-action ریز)
        hh = (c > np.roll(c, 1)) & (np.roll(c, 1) > np.roll(c, 2)) & (np.roll(c, 2) < np.roll(c, 3))
        hh[:3] = False
        d['D5_MSWING'] = np.nan_to_num(hh, nan=0).astype(bool)
        return d

    def _down():
        d = {}
        d['D1_MOMO'] = np.nan_to_num((c < pl), nan=0).astype(bool)
        d['D2_PULL'] = np.nan_to_num((e20 < e100) & (r21 > 55), nan=0).astype(bool)
        cross_dn = (mline < sline) & (np.roll(mline, 1) >= np.roll(sline, 1))
        cross_dn[0] = False
        d['D3_MACD'] = np.nan_to_num(cross_dn, nan=0).astype(bool)
        d['D4_EXPAND'] = np.nan_to_num((atr_arr > atr_prev * 1.10) & (c < e20), nan=0).astype(bool)
        ll = (c < np.roll(c, 1)) & (np.roll(c, 1) < np.roll(c, 2)) & (np.roll(c, 2) > np.roll(c, 3))
        ll[:3] = False
        d['D5_MSWING'] = np.nan_to_num(ll, nan=0).astype(bool)
        return d

    raw = _up() if direction == 'UP' else _down()
    return {k: np.where(v)[0] for k, v in raw.items()}, dict(
        e20=e20, e100=e100, r21=r21, ad=ad, atr=atr_arr)


DET_NAMES = ['D1_MOMO', 'D2_PULL', 'D3_MACD', 'D4_EXPAND', 'D5_MSWING']


# ------------------------------------------------ ویژگی‌ها + امتیازِ زمان‌بندی
def trend_features(t, c, ind, direction):
    i0, i1 = t['i_start'], t['i_end']
    dur = max(i1 - i0, 1)
    return dict(
        move_usd=float(t['move_usd']),
        dur_bars=int(dur),
        slope_usd_bar=float((c[i1] - c[i0]) / dur),
        rsi_start=float(ind['r21'][i0]),
        adx_start=float(ind['ad'][i0]),
        atr_start=float(ind['atr'][i0]),
        dist_ema100=float(c[i0] - ind['e100'][i0]),
        speed_usd_per_bar=float(t['move_usd'] / dur),
    )


def score_trend_multi(t, det_sets, direction):
    """
    برای هر روند: کدام آشکارسازها داخلِ [i0,i1] فایر کردند + امتیازِ شروع/پایان
    بر مبنایِ *زودترین* سیگنال (بهترین آشکارساز برای زمان‌بندیِ شروع).
    """
    i0, i1 = t['i_start'], t['i_end']
    rng = max(i1 - i0, 1)
    move = t['move_usd']
    c = t['_c']
    hit = {}
    earliest = None
    for name in DET_NAMES:
        s = det_sets[name]
        inside = s[(s >= i0) & (s <= i1)]
        if len(inside) > 0:
            hit[name] = int(inside[0])
            if earliest is None or inside[0] < earliest:
                earliest = int(inside[0])
    rec = dict(idx=t.get('_idx'))
    rec['detected'] = len(hit) > 0
    rec['hit_by'] = list(hit.keys())
    rec['n_detectors'] = len(hit)
    if rec['detected']:
        entry = earliest
        frac = (entry - i0) / rng
        rec['entry_bar'] = entry
        rec['start_score'] = int(np.clip(round(100 * (1 - frac)), 0, 100))
        # پایان: نزدیک‌ترین کندل به قلهٔ واقعی که یک آشکارسازِ خلاف‌جهت نداریم
        #        (تقریب: از entry تا i1، امتیازِ پایان بر مبنای فاصلهٔ entry تا i1)
        # چون آشکارسازها فقط ورود می‌دهند، پایان را با «چقدر زود وارد شدیم» جفت می‌کنیم:
        # end_score = چقدر دامنه از entry تا i1 باقی مانده بود (پتانسیلِ گرفتنِ روند)
        rec['end_score'] = int(np.clip(round(100 * (1 - frac)), 0, 100))
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


# ------------------------------------------------------------- چاپِ ماتریس
def print_matrix(scored, feats, direction):
    print(f"\n#### ماتریسِ نهاییِ روندهای {direction} (ستونِ اول = شمارهٔ روند) ####")
    hdr = (f"{'#':>3} {'طول$':>7} {'کندل':>4} {'RSI0':>5} {'ADX0':>5} {'شیب':>6} "
           f"{'کشف':>3} {'#آشکارساز':>9} {'کدام‌آشکارساز':>24} {'شروع':>4} {'گرفته%':>6}")
    print(hdr)
    print("-" * len(hdr))
    for k, (s, f) in enumerate(zip(scored, feats), 1):
        det = '✅' if s['detected'] else '❌'
        by = '+'.join(x.split('_')[0] for x in s['hit_by']) if s['hit_by'] else '-'
        ss = s['start_score'] if s['start_score'] is not None else '-'
        cp = s['captured_pct'] if s['captured_pct'] is not None else '-'
        print(f"{k:>3} {f['move_usd']:>7.2f} {f['dur_bars']:>4} {f['rsi_start']:>5.1f} "
              f"{f['adx_start']:>5.1f} {f['slope_usd_bar']:>6.2f} {det:>3} "
              f"{s['n_detectors']:>9} {by:>24} {str(ss):>4} {str(cp):>6}")


def per_detector_stats(scored, det_sets, trends, n_bars):
    """
    چه سهمی از پوشش به هر آشکارساز مربوط است + پوششِ انفرادی + **بررسیِ صداقت**:
    مقایسهٔ پوششِ واقعیِ هر آشکارساز با یک null-model (فایرِ تصادفیِ هم‌نرخ).
    z مثبتِ بزرگ ⇒ آشکارساز *واقعاً* روند را می‌بیند؛ z منفی ⇒ بدتر از شانس (کور).
    """
    n = len(scored)
    rng = np.random.default_rng(42)
    stats = {}
    for name in DET_NAMES:
        solo = sum(1 for s in scored if name in s['hit_by'])
        uniq = sum(1 for s in scored if s['hit_by'] == [name])
        # null-model: همان تعداد فایر، تصادفی، ۳۰۰ تکرار
        s = det_sets[name]
        nk = len(s)
        covs = []
        for _ in range(300):
            rs = np.sort(rng.choice(n_bars, size=min(nk, n_bars), replace=False))
            cov = sum(1 for t in trends if len(rs[(rs >= t['i_start']) & (rs <= t['i_end'])]) > 0)
            covs.append(cov)
        mu = float(np.mean(covs)); sd = float(np.std(covs)) + 1e-9
        z = (solo - mu) / sd
        stats[name] = dict(solo_cover=solo, solo_pct=round(100*solo/max(n, 1), 1),
                           unique_cover=uniq, fire_rate_pct=round(100*nk/n_bars, 1),
                           null_mean=round(mu, 1), null_sd=round(sd, 1), z_score=round(z, 1))
    return stats


def analyze_direction(df, direction):
    print("\n" + "=" * 74)
    print(f"### تحلیلِ جهتِ {direction} — موتورِ چند-آشکارساز ###")
    a, b = find_window(df, direction, TARGET_TRENDS)
    seg = df.iloc[a:b].reset_index(drop=True)
    c = seg['close'].values.astype(float)
    h = seg['high'].values.astype(float)
    l = seg['low'].values.astype(float)
    print(f"پنجره: barها [{a},{b}] — {seg['dt'].iloc[0]} → {seg['dt'].iloc[-1]}  (n={len(seg)})")

    det_sets, ind = build_detectors(c, h, l, direction)
    for name in DET_NAMES:
        print(f"  آشکارساز {name}: {len(det_sets[name])} بار فایر در پنجره")

    trends_all = zigzag_trends(c, MIN_MOVE_USD)
    trends = [t for t in trends_all if t['dir'] == direction]
    print(f"روندهای {direction}ِ ≥${MIN_MOVE_USD}: {len(trends)}")

    for k, t in enumerate(trends):
        t['_c'] = c
        t['_idx'] = k + 1

    scored = [score_trend_multi(t, det_sets, direction) for t in trends]
    feats = [trend_features(t, c, ind, direction) for t in trends]

    print_matrix(scored, feats, direction)

    n = len(scored)
    ndet = sum(1 for s in scored if s['detected'])
    cov = round(100 * ndet / max(n, 1), 1)
    print(f"\nخلاصه: کشف‌شده={ndet}/{n} (پوشش={cov}%)  — هدفِ User Note = {COVERAGE_GOAL}%")
    det_scored = [s for s in scored if s['detected']]
    if det_scored:
        print(f"    میانگینِ امتیازِ شروع={np.mean([s['start_score'] for s in det_scored]):.1f} | "
              f"گرفته‌شده%={np.mean([s['captured_pct'] for s in det_scored]):.1f}")

    pds = per_detector_stats(scored, det_sets, trends, len(c))
    print(f"\n>>> سهمِ هر آشکارساز + بررسیِ صداقت (null-model) (جهتِ {direction}):")
    print(f"{'آشکارساز':>12} {'نرخ‌فایر٪':>8} {'پوشش':>5} {'منحصر':>5} {'تصادفی':>7} {'z':>6}")
    for name in DET_NAMES:
        p = pds[name]
        print(f"{name:>12} {p['fire_rate_pct']:>8} {p['solo_cover']:>5} "
              f"{p['unique_cover']:>5} {p['null_mean']:>7} {p['z_score']:>+6}")

    # پوششِ فقط با آشکارسازهای «واقعیِ» معنادار (z>2) — آزمونِ ضدِ تقلبِ چگالی
    real_dets = [name for name in DET_NAMES if pds[name]['z_score'] > 2.0]
    if real_dets:
        cov_real = 0
        for t in trends:
            got = False
            for name in real_dets:
                s = det_sets[name]
                if len(s[(s >= t['i_start']) & (s <= t['i_end'])]) > 0:
                    got = True; break
            if got:
                cov_real += 1
        cov_real_pct = round(100 * cov_real / max(n, 1), 1)
        print(f"\n  🔬 پوشش با فقط آشکارسازهای معنادار (z>2) [{'+'.join(x.split('_')[0] for x in real_dets)}]: "
              f"{cov_real}/{n} = {cov_real_pct}%  (اثباتِ اینکه پوشش تقلبِ چگالی نیست)")
    else:
        cov_real_pct = 0.0

    # روندهای کشف‌نشده: DNA
    lost = [f for f, s in zip(feats, scored) if not s['detected']]
    if lost:
        print(f"\n  DNAِ روندهای هنوز کشف‌نشده (میانگین): "
              f"طول={np.mean([f['move_usd'] for f in lost]):.1f}$ | "
              f"کندل={np.mean([f['dur_bars'] for f in lost]):.1f} | "
              f"شیب={np.mean([f['slope_usd_bar'] for f in lost]):.3f}$/ک | "
              f"ADX0={np.mean([f['adx_start'] for f in lost]):.1f}")

    return dict(
        window=[int(a), int(b)],
        dt_start=str(seg['dt'].iloc[0]), dt_end=str(seg['dt'].iloc[-1]),
        n_trends=n, n_detected=ndet, coverage_pct=cov,
        significant_detectors=real_dets, coverage_significant_pct=cov_real_pct,
        detector_stats=pds,
        matrix=[dict(idx=k+1,
                     move_usd=round(feats[k]['move_usd'], 2),
                     dur_bars=feats[k]['dur_bars'],
                     rsi_start=round(feats[k]['rsi_start'], 1),
                     adx_start=round(feats[k]['adx_start'], 1),
                     slope=round(feats[k]['slope_usd_bar'], 3),
                     detected=scored[k]['detected'],
                     hit_by=scored[k]['hit_by'],
                     n_detectors=scored[k]['n_detectors'],
                     start_score=scored[k]['start_score'],
                     end_score=scored[k]['end_score'],
                     captured_pct=scored[k]['captured_pct'])
                for k in range(n)],
    )


def main():
    df = load()
    print(f"داده: {len(df)} کندلِ M5 طلا  ({df['dt'].iloc[0]} → {df['dt'].iloc[-1]})")
    print(f"هدفِ User Note: پوششِ ≥{COVERAGE_GOAL}% روندهای ≥${MIN_MOVE_USD} در هر جهت. تمرکز: موتورِ اسکالپ.")
    print("قانونِ شمارهٔ ۱: سودِ خالص = XAUUSD + EURUSD (این ابزار تشخیصی است؛ سود بدون تغییر).")

    up = analyze_direction(df, 'UP')
    dn = analyze_direction(df, 'DOWN')

    goal_met = up['coverage_pct'] >= COVERAGE_GOAL and dn['coverage_pct'] >= COVERAGE_GOAL
    print("\n" + "=" * 74)
    print(f"### نتیجهٔ نهایی: پوششِ UP={up['coverage_pct']}% | DOWN={dn['coverage_pct']}% "
          f"| هدف={COVERAGE_GOAL}% ⇒ {'✅ محقق شد' if goal_met else '❌ هنوز نه'}")

    out = dict(min_move_usd=MIN_MOVE_USD, target_trends=TARGET_TRENDS,
               coverage_goal=COVERAGE_GOAL, goal_met=goal_met,
               detectors=DET_NAMES, UP=up, DOWN=dn)
    path = os.path.join(RESULTS, '_s127_multi_detector.json')
    with open(path, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=float)
    print(f"\n✅ ذخیره شد: results/_s127_multi_detector.json")


if __name__ == '__main__':
    main()
