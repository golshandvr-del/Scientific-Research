"""
s111_coverage_vs_winrate_paradox.py — پاسخِ علمی به پارادوکسِ User note2
================================================================================
پارادوکسِ کاربر (User note2):
  «تو می‌گویی ما تقریباً همهٔ روندها را با استراتژی‌هامان کشف می‌کنیم.
   پس چرا WR ما پایین است؟!»

این تناقضِ ظاهری کلیدِ کلِ پروژه است. فرضیهٔ ما برای پاسخ:

  «کشفِ روند» (coverage) و «Win-Rate» دو چیزِ کاملاً متفاوت‌اند که در دو
  «سطحِ اندازه‌گیریِ متفاوت» زندگی می‌کنند:

  • coverage در سطحِ *رویداد* است: «آیا در طولِ روندِ شمارهٔ ۷ حداقل یک بار
    وارد شدیم؟» — یک روندِ بزرگ ده‌ها ورود دارد، کافی است یکی سود کند تا
    بگوییم «روند را کشف کردیم».
  • WR در سطحِ *ورودِ منفرد* است: «از هر ۱۰۰ ورود، چند تا سود کردند؟»
    اکثرِ ورودها در نویزِ داخلِ روند استاپ می‌خورند؛ فقط چند ورود سودِ بزرگ
    می‌گیرند. پس WR پایین می‌ماند حتی وقتی coverage بالاست.

  ⇒ WR پایین + coverage بالا = «چند بردِ بزرگ، بسیار باختِ کوچک». این دقیقاً
    یک سیستمِ «تعقیبِ روند با R:R بالا» است. WR پایین یک *باگ* نیست، یک
    *ویژگیِ ساختاری* است. سودِ خالص از (میانگینِ برد × نرخِ برد) می‌آید، نه
    از نرخِ برد به‌تنهایی.

این اسکریپت این را روی ۳ سالِ اخیرِ طلا (طبق User note2) عدداً اندازه می‌گیرد:
  1. روندهای واقعیِ طلا را شماره‌گذاری می‌کند (swing-based).
  2. coverage روند را می‌سنجد (چند درصدِ روندها لمس می‌شوند).
  3. WR در سطحِ ورود را می‌سنجد.
  4. توزیعِ pnl را کالبدشکافی می‌کند تا شکافِ coverage↔WR را نشان دهد.

قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود):
  از این پس فقط و فقط دنبالِ «سودِ خالصِ بیشتر» هستیم — WR مهم نیست.
  تعریفِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.
================================================================================
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
import indicators as ind
import scalp_engine as se

DATA = os.path.join(os.path.dirname(__file__), '..', 'data', 'XAUUSD_M15.csv')
RESULTS = os.path.join(os.path.dirname(__file__), '..', 'results')
YEARS_RECENT = 3          # طبق User note2: تمرکز بر ۳ سالِ اخیر


def load_recent():
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    cut = df['dt'].max() - pd.Timedelta(days=365 * YEARS_RECENT)
    df = df[df['dt'] >= cut].reset_index(drop=True)
    return df


def label_swings(df, atr_mult=3.0, atr_period=14):
    """
    روندهای واقعی را با الگوریتمِ ZigZag مبتنی بر ATR شماره‌گذاری می‌کند.
    یک swing وقتی «تمام» می‌شود که قیمت به اندازهٔ atr_mult*ATR در جهتِ مخالف
    برگردد. هر swing یک «روندِ شماره‌گذاری‌شده» است (دقیقاً مثالِ کاربر: ۱..۱۰).
    خروجی: لیستِ روندها با (start_bar, end_bar, direction, size_pip).
    """
    high = df['high'].values; low = df['low'].values; close = df['close'].values
    atr = ind.atr(df, atr_period).values
    PIP_XAU = se.ASSETS['XAUUSD']['pip']
    n = len(df)
    trends = []
    # نقطهٔ شروع
    piv_idx = 0
    piv_price = close[0]
    direction = 0  # 0 نامشخص، +1 صعودی، -1 نزولی
    ext_idx = 0
    ext_price = close[0]
    for i in range(1, n):
        a = atr[i] if not np.isnan(atr[i]) else atr[np.isfinite(atr)][0]
        thr = atr_mult * a
        if direction >= 0:
            # در روندِ صعودی یا نامشخص: extremum را به‌روز کن
            if high[i] > ext_price:
                ext_price = high[i]; ext_idx = i
            # آیا به اندازهٔ آستانه برگشت؟ ⇒ پایانِ روندِ صعودی
            if ext_price - low[i] > thr and direction >= 0:
                if direction > 0:
                    trends.append({'start': piv_idx, 'end': ext_idx, 'dir': +1,
                                   'size_pip': (ext_price - piv_price) / PIP_XAU})
                # شروعِ روندِ نزولی
                piv_idx = ext_idx; piv_price = ext_price
                direction = -1
                ext_price = low[i]; ext_idx = i
        if direction <= 0:
            if low[i] < ext_price:
                ext_price = low[i]; ext_idx = i
            if high[i] - ext_price > thr and direction <= 0:
                if direction < 0:
                    trends.append({'start': piv_idx, 'end': ext_idx, 'dir': -1,
                                   'size_pip': (piv_price - ext_price) / PIP_XAU})
                piv_idx = ext_idx; piv_price = ext_price
                direction = +1
                ext_price = high[i]; ext_idx = i
    return trends


def short_signal(df):
    c = df['close']; p = c.values
    e50 = ind.ema(c, 50).values; e100 = ind.ema(c, 100).values; s200 = ind.sma(c, 200).values
    mid = np.nanmean(np.column_stack([e50, e100, s200]), axis=1)
    return (np.r_[False, p[:-1] > mid[:-1]]) & (p < mid)


def long_signal(df):
    c = df['close']; p = c.values
    e50 = ind.ema(c, 50).values; e100 = ind.ema(c, 100).values; s200 = ind.sma(c, 200).values
    mid = np.nanmean(np.column_stack([e50, e100, s200]), axis=1)
    return (np.r_[False, p[:-1] < mid[:-1]]) & (p > mid)


def trend_coverage(trades, trends, direction):
    """چند درصد از روندهای هم‌جهت حداقل یک ورودِ سودده در بازه‌شان داشتند."""
    dir_trends = [t for t in trends if t['dir'] == direction]
    if not dir_trends:
        return 0.0, 0, 0
    eb = trades['entry_bar'].values
    pn = trades['pnl_pip'].values
    covered = 0
    for t in dir_trends:
        lo, hi = t['start'], t['end']
        mask = (eb >= lo) & (eb <= hi) & (pn > 0)
        if mask.any():
            covered += 1
    return covered / len(dir_trends) * 100.0, covered, len(dir_trends)


def main():
    print("=" * 80)
    print("s111 — پارادوکسِ «coverage بالا ولی WR پایین» (پاسخِ علمی به User note2)")
    print("=" * 80)
    df = load_recent()
    print(f"داده: {len(df)} کندلِ ۳ سالِ اخیر  ({df['dt'].min().date()} → {df['dt'].max().date()})\n")

    # 1) شماره‌گذاریِ روندهای واقعی
    trends = label_swings(df, atr_mult=3.0)
    up = [t for t in trends if t['dir'] == +1]
    dn = [t for t in trends if t['dir'] == -1]
    print(f"روندهای واقعیِ کشف‌شده (ZigZag، ATR×3):  {len(trends)} روند "
          f"({len(up)} صعودی، {len(dn)} نزولی)")
    print(f"  میانهٔ اندازهٔ روندِ صعودی: {np.median([t['size_pip'] for t in up]):.0f} pip"
          f"   نزولی: {np.median([t['size_pip'] for t in dn]):.0f} pip\n")

    # 2) اجرای دو لایهٔ برندهٔ واقعی: SHORT (trailing) و LONG (mirror)
    results = {}
    for name, sig, dirn, params in [
        ('LONG (تعقیبِ روند)', long_signal(df), +1,
         dict(sl_pip=40, tp_pip=120, max_hold=48, be_trigger_pip=None, trail_pip=None)),
        ('SHORT (اسکالپِ trailing)', short_signal(df), -1,
         dict(sl_pip=40, tp_pip=200, max_hold=12, be_trigger_pip=8, trail_pip=8)),
    ]:
        long_sig = sig if dirn > 0 else np.zeros(len(df), bool)
        short_sig = sig if dirn < 0 else np.zeros(len(df), bool)
        trades = se.simulate_trades(df, long_sig, short_sig, asset='XAUUSD', **params)
        if trades is None or len(trades) == 0:
            print(f"[{name}] هیچ معامله‌ای تولید نشد."); continue
        pnls = trades['pnl_pip'].values
        wins = pnls[pnls > 0]; losses = pnls[pnls <= 0]
        wr = len(wins) / len(pnls) * 100.0
        avg_win = wins.mean() if len(wins) else 0.0
        avg_loss = losses.mean() if len(losses) else 0.0
        net_pip = pnls.sum()
        cov_pct, cov_n, cov_tot = trend_coverage(trades, trends, dirn)

        print("─" * 80)
        print(f"▶ لایهٔ: {name}")
        print(f"    تعدادِ ورود (کندل-به-کندل):  {len(trades)}")
        print(f"    coverage روند (سطحِ رویداد): {cov_pct:.0f}%  ({cov_n}/{cov_tot} روندِ هم‌جهت لمس شد)")
        print(f"    WR (سطحِ ورودِ منفرد):        {wr:.1f}%")
        print(f"    میانگینِ برد: {avg_win:+.1f} pip    میانگینِ باخت: {avg_loss:+.1f} pip"
              f"    R:R = {abs(avg_win/avg_loss) if avg_loss else 0:.2f}")
        print(f"    سودِ خالص (pip):  {net_pip:+.0f}")
        print(f"    ⇒ شکاف: coverage={cov_pct:.0f}% ولی WR={wr:.1f}%  →  اختلافِ {cov_pct-wr:.0f} واحد!")
        results[name] = dict(n_entries=len(trades), coverage_pct=round(cov_pct, 1),
                             covered=cov_n, dir_trends=cov_tot, win_rate=round(wr, 1),
                             avg_win_pip=round(avg_win, 2), avg_loss_pip=round(avg_loss, 2),
                             net_pip=round(net_pip, 1))

    # 3) پاسخِ فلسفی
    print("\n" + "=" * 80)
    print("پاسخِ فلسفی به User note2:")
    print("=" * 80)
    print("""
شکافِ عددیِ بالا تناقض را حل می‌کند:

  • coverage بالاست چون یک روندِ بزرگ ده‌ها فرصتِ ورود می‌سازد؛ کافی است یکی
    از آن ورودها سود کند تا بگوییم «روند کشف شد». پس در سطحِ رویداد، بله ما
    تقریباً همهٔ روندهای بزرگ را لمس می‌کنیم.

  • اما WR در سطحِ *هر ورودِ منفرد* سنجیده می‌شود. داخلِ همان روندِ بزرگ،
    ده‌ها ورودِ نویزی هم داریم که استاپ می‌خورند. نسبتِ (ورودِ سودده / کلِ ورود)
    پایین است، چون بازار حتی در یک روندِ قوی، ۶۰-۷۰٪ زمان را در پول‌بک و
    نویزِ خلافِ جهت می‌گذراند.

  ⇒ WR پایین یک نقص نیست؛ امضای یک سیستمِ «چند بردِ بزرگ، بسیار باختِ کوچک»
    است (R:R>1). سودِ خالص = نرخِ برد × میانگینِ برد − نرخِ باخت × میانگینِ باخت.
    وقتی میانگینِ برد چند برابرِ میانگینِ باخت است، سیستم حتی با WR=۳۵٪ سودده
    می‌ماند. این دقیقاً چیزی است که قانونِ شمارهٔ ۱ پروژه می‌گوید: WR بی‌ربط
    است؛ فقط سودِ خالص مهم است.

  نتیجهٔ عملی برای طراحی: برای بالا بردنِ سودِ خالص نباید WR را بالا ببریم؛
    باید (الف) میانگینِ برد را بزرگ‌تر کنیم (اجازه دهیم بردها بدوند) و
    (ب) باختِ منفرد را کوچک نگه داریم (استاپِ تنگ / خروجِ سریع). این همان
    کاری است که لایهٔ SHORTِ trailing انجام می‌دهد.
""")

    os.makedirs(RESULTS, exist_ok=True)
    out = os.path.join(RESULTS, '_s111_paradox.json')
    with open(out, 'w') as f:
        json.dump({'window': f'{YEARS_RECENT}y_recent',
                   'n_bars': len(df),
                   'n_trends_total': len(trends),
                   'n_up': len(up), 'n_dn': len(dn),
                   'layers': results}, f, ensure_ascii=False, indent=2)
    print(f"ذخیره شد: {out}")


if __name__ == '__main__':
    main()
