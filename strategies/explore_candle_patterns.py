"""
explore_candle_patterns.py — اکتشافِ آماریِ الگوهای بصری/کندلی روی XAUUSD (User Note)
================================================================================
قانونِ شمارهٔ ۱ پروژه (تکرارِ الزامی): هدفِ پروژه **فقط و فقط «سودِ خالصِ بیشتر»**
است — نه Win-Rate. WR صرفاً یک عددِ گزارشی است. تعریفِ فعلیِ «سودِ خالص» = مجموعِ
سودِ خالصِ دو دارایی: XAUUSD + EURUSD. **ما دنبالِ پول هستیم، نه آمارِ زیبا.**

--------------------------------------------------------------------------------
انگیزه (User Note جدید — صحبتِ تریدر):
  تریدر گفت «من با چشمم شکلِ بازار را می‌فهمم» و اشاره کرد به:
    • شکلِ کندل‌ها: shooting star, hammer, engulfing, doji, ...
    • الگوهای هندسی: double top/bottom (دو قله)، پروانه/harmonic، ذوزنقه.
    • الگوهای شکلیِ تکرارشونده در XAUUSD.
  سوال‌های علمیِ صریح: آیا واقعاً وجود دارند؟ کجا؟ در بازارِ رنج؟ روندی؟ همه‌جا؟
  در چه تایم‌فریمی؟

  ⚠️ هیچ استراتژیِ قبلیِ پروژه (S1..S73) الگوهای کندلی/شکلی را تست نکرده — این مسیر
  کاملاً بکر است. این اسکریپت **فرض نمی‌کند** الگوها کار می‌کنند؛ می‌گذارد داده
  حرف بزند: هر الگو را کمی‌سازی و بازدهِ آتیِ شرطی‌اش را در برابرِ baseline و به
  تفکیکِ رژیم (روند/رنج/نوسان) می‌سنجد.

روش‌شناسی (بدونِ نشتِ آینده):
  • همهٔ فیچرهای الگو فقط از کندلِ i و قبل‌تر ساخته می‌شوند.
  • «بازدهِ آتی» = بازدهِ close[i+k]/close[i] برای افق‌های k∈{1,2,4,8,16}.
  • برای هر الگو: میانگینِ بازدهِ آتیِ شرطی، t-stat در برابرِ صفر، و lift نسبت به
    baselineِ بی‌قید (میانگینِ بازدهِ آتیِ کلِ بازار). t-stat بزرگ ⇒ لبهٔ واقعی.
  • رژیم‌بندی: ADX (روندی/رنج) و ATR-percentile (پرنوسان/کم‌نوسان) ⇒ پاسخ به «کجا».
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from backtest import load_data
import indicators as ind
import warnings; warnings.filterwarnings('ignore')

HORIZONS = [1, 2, 4, 8, 16]     # افق‌های بازدهِ آتی (کندل)


def add_context(df):
    """اندیکاتورهای زمینه‌ای برای رژیم‌بندی + نرمال‌سازی."""
    df = df.copy()
    df['atr'] = ind.atr(df, 14)
    adx_val, _, _ = ind.adx(df, 14)
    df['adx'] = adx_val
    df['body'] = (df['close'] - df['open'])
    df['range'] = (df['high'] - df['low']).replace(0, np.nan)
    df['upper_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
    df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
    df['body_abs'] = df['body'].abs()
    # میانگینِ بدنهٔ اخیر برای نرمال‌سازیِ نسبی
    df['body_ma'] = df['body_abs'].rolling(20).mean()
    df['range_ma'] = df['range'].rolling(20).mean()
    # رژیمِ نوسان: صدکِ ATR در پنجرهٔ متحرک
    df['atr_pct'] = df['atr'].rolling(500, min_periods=100).apply(
        lambda x: (x[-1] >= np.nanpercentile(x, 66)) * 1.0 + (x[-1] <= np.nanpercentile(x, 33)) * -1.0,
        raw=True)
    return df


def candle_patterns(df):
    """کمی‌سازیِ الگوهای کلاسیکِ کندلی (بولین، همه بدونِ نشتِ آینده)."""
    o, h, l, c = df['open'], df['high'], df['low'], df['close']
    body = c - o
    body_abs = body.abs()
    rng = (h - l).replace(0, np.nan)
    up_wick = h - np.maximum(o, c)
    lo_wick = np.minimum(o, c) - l
    body_ma = df['body_ma']
    prev_o, prev_c = o.shift(1), c.shift(1)
    prev_body = prev_c - prev_o

    pat = {}
    # --- Doji: بدنهٔ خیلی کوچک نسبت به رنج ---
    pat['doji'] = (body_abs <= 0.1 * rng)
    # --- Hammer: سایهٔ پایینیِ بلند، بدنهٔ کوچک بالا، سایهٔ بالاییِ کوچک ---
    pat['hammer'] = (lo_wick >= 2.0 * body_abs) & (up_wick <= 0.5 * body_abs) & (body_abs > 0)
    # --- Shooting Star: سایهٔ بالاییِ بلند، بدنهٔ کوچک پایین ---
    pat['shooting_star'] = (up_wick >= 2.0 * body_abs) & (lo_wick <= 0.5 * body_abs) & (body_abs > 0)
    # --- Bullish Engulfing: کندلِ سبزِ بزرگ که بدنهٔ قرمزِ قبلی را می‌بلعد ---
    pat['bull_engulf'] = (prev_body < 0) & (body > 0) & (c >= prev_o) & (o <= prev_c)
    # --- Bearish Engulfing ---
    pat['bear_engulf'] = (prev_body > 0) & (body < 0) & (c <= prev_o) & (o >= prev_c)
    # --- Marubozu صعودی: بدنهٔ بزرگ بدونِ سایه (مومنتوم قوی) ---
    pat['bull_marubozu'] = (body > 0) & (body_abs >= 1.5 * body_ma) & (up_wick + lo_wick <= 0.2 * body_abs)
    pat['bear_marubozu'] = (body < 0) & (body_abs >= 1.5 * body_ma) & (up_wick + lo_wick <= 0.2 * body_abs)
    # --- Pin bar bullish (رد قیمتِ پایین) / bearish (رد قیمتِ بالا) ---
    pat['pin_bull'] = (lo_wick >= 0.6 * rng) & (body_abs <= 0.3 * rng)
    pat['pin_bear'] = (up_wick >= 0.6 * rng) & (body_abs <= 0.3 * rng)
    # --- Inside bar (فشردگی): رنجِ کندلِ i داخلِ کندلِ i-1 ---
    pat['inside_bar'] = (h <= h.shift(1)) & (l >= l.shift(1))
    # --- Outside bar (گسترش) ---
    pat['outside_bar'] = (h > h.shift(1)) & (l < l.shift(1))
    return pat


def eval_pattern(df, mask, direction_hint):
    """
    بازدهِ آتیِ شرطیِ یک الگو را در برابرِ baseline می‌سنجد.
    direction_hint: +1 اگر الگو صعودی فرض شود، -1 اگر نزولی (برای علامتِ بازده).
    خروجی: دیکشنری آمار به تفکیکِ افق و رژیم.
    """
    c = df['close'].values
    n = len(df)
    mask = mask.fillna(False).values if hasattr(mask, 'fillna') else np.asarray(mask)
    out = {}
    for k in HORIZONS:
        fut = np.full(n, np.nan)
        fut[:n-k] = (c[k:] / c[:n-k] - 1.0) * 10000.0   # بازدهِ آتی به bps
        fut = fut * direction_hint                        # هم‌جهت با فرضِ الگو
        idx = mask & ~np.isnan(fut)
        base = ~np.isnan(fut)
        sig = fut[idx]
        allret = fut[base]
        if len(sig) < 30:
            out[k] = None
            continue
        mean = sig.mean()
        base_mean = allret.mean()
        t = mean / (sig.std(ddof=1) / np.sqrt(len(sig))) if sig.std() > 0 else 0.0
        wr = (sig > 0).mean() * 100
        out[k] = {'n': int(len(sig)), 'mean_bps': mean, 'base_bps': base_mean,
                  'lift_bps': mean - base_mean, 't': t, 'wr': wr}
    return out


def print_pattern_report(name, direction_hint, results):
    dh = '↑' if direction_hint > 0 else '↓'
    print(f"\n  ▸ {name} (فرضِ جهت {dh})")
    print(f"    {'k':>3} {'n':>6} {'mean_bps':>9} {'base':>7} {'lift':>7} {'t':>7} {'WR%':>6}")
    for k in HORIZONS:
        r = results[k]
        if r is None:
            print(f"    {k:>3}    n<30 (نادر)")
            continue
        flag = '  <<<' if abs(r['t']) >= 3 and r['lift_bps'] * direction_hint > 0 else ''
        print(f"    {k:>3} {r['n']:>6} {r['mean_bps']:>9.2f} {r['base_bps']:>7.2f} "
              f"{r['lift_bps']:>7.2f} {r['t']:>7.2f} {r['wr']:>6.1f}{flag}")


def analyze_asset(path, asset_name):
    print("\n" + "=" * 78)
    print(f"  دارایی: {asset_name}  ({path})")
    print("=" * 78)
    df = load_data(path)
    df['hour'] = df['dt'].dt.hour
    df = add_context(df)
    pats = candle_patterns(df)

    # جهتِ فرضیِ هر الگو (طبقِ ادبیاتِ کلاسیک)
    hints = {
        'doji': 0, 'hammer': +1, 'shooting_star': -1, 'bull_engulf': +1,
        'bear_engulf': -1, 'bull_marubozu': +1, 'bear_marubozu': -1,
        'pin_bull': +1, 'pin_bear': -1, 'inside_bar': 0, 'outside_bar': 0,
    }

    print(f"\n  کلِ کندل‌ها: {len(df):,}")
    print("  --- فراوانیِ الگوها ---")
    for name, mask in pats.items():
        cnt = int(mask.fillna(False).sum())
        print(f"    {name:>16}: {cnt:>6}  ({cnt/len(df)*100:.2f}%)")

    print("\n  ================= بازدهِ آتیِ شرطیِ کلِ بازار =================")
    for name, mask in pats.items():
        dh = hints[name]
        if dh == 0:
            # الگوهای بی‌جهت را در هر دو جهت گزارش می‌کنیم (اینجا مومنتوم=+1)
            res = eval_pattern(df, mask, +1)
            print_pattern_report(f"{name} [as-momentum +1]", +1, res)
        else:
            res = eval_pattern(df, mask, dh)
            print_pattern_report(name, dh, res)

    # ---------------- رژیم‌بندی: پاسخ به «کجا؟» ----------------
    print("\n  ================= تفکیکِ رژیم (پاسخ به «کجا؟») =================")
    trend = df['adx'] >= 25          # روندی
    rng_regime = df['adx'] < 20      # رنج
    hivol = df['atr_pct'] > 0        # پرنوسان
    lovol = df['atr_pct'] < 0        # کم‌نوسان

    # فقط الگوهای جهت‌دارِ پرتکرار را در رژیم‌ها می‌سنجیم
    focus = ['hammer', 'shooting_star', 'bull_engulf', 'bear_engulf',
             'pin_bull', 'pin_bear', 'bull_marubozu', 'bear_marubozu']
    regimes = {'TREND(adx>=25)': trend, 'RANGE(adx<20)': rng_regime,
               'HIVOL': hivol, 'LOVOL': lovol}
    for name in focus:
        dh = hints[name]
        print(f"\n  ▸ {name} (جهت {'↑' if dh>0 else '↓'}) — بازدهِ آتیِ افق k=4 در رژیم‌ها:")
        for rn, rmask in regimes.items():
            res = eval_pattern(df, pats[name] & rmask, dh)
            r = res[4]
            if r is None:
                print(f"      {rn:>16}: n<30 (نادر)")
            else:
                flag = '  <<< لبه' if abs(r['t']) >= 3 and r['lift_bps'] > 0 else ''
                print(f"      {rn:>16}: n={r['n']:>5} mean={r['mean_bps']:>7.2f}bps "
                      f"lift={r['lift_bps']:>7.2f} t={r['t']:>6.2f} WR={r['wr']:.1f}%{flag}")


if __name__ == '__main__':
    analyze_asset('data/XAUUSD_M15.csv', 'XAUUSD M15')
    print("\n\n########## تکرار برای تایم‌فریمِ بالاتر (H1) — پاسخ به «چه تایم‌فریمی؟» ##########")
    analyze_asset('data/XAUUSD_H1.csv', 'XAUUSD H1')
