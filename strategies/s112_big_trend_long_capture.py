"""
s112_big_trend_long_capture.py — تبدیلِ کشفِ s111 به سود (شکار روندهای بزرگِ صعودی)
================================================================================
کشفِ s111 (پاسخ به پارادوکسِ User note2):
  • در ۳ سالِ اخیر، ماشهٔ LONGِ mid-cross فقط ۱۶٪ روندهای صعودی را لمس می‌کند و
    خالصِ منفی می‌دهد (-9,451 pip، WR=25٪) — چون بیش‌ازحد در پول‌بک‌های نویزی
    شلیک می‌کند.
  • اما طلا در ۳ سالِ اخیر یک روندِ صعودیِ تاریخی داشته. پس LONG *باید* سودده
    باشد. مشکل «ماشهٔ بد» است، نه جهت.

فرضیهٔ این اسکریپت (طبق نتیجهٔ فلسفیِ s111):
  برای بالا بردنِ سودِ خالص، WR را هدف نمی‌گیریم؛ در عوض:
    (الف) فقط واردِ روندهای بزرگِ صعودی می‌شویم (فیلترِ قدرتِ روند)،
    (ب) اجازه می‌دهیم بردها بدوند (TP بزرگ یا trailing گشاد)،
    (ج) باختِ منفرد را کوچک نگه می‌داریم (SL تنگ).
  این باید coverageِ روندهای بزرگ را بالا ببرد و از نویز دوری کند.

جاروب می‌کنیم: فیلترهای قدرتِ روند × پروفایل‌های خروج، روی ۳ سالِ اخیر،
با آزمونِ both-halves (نیمهٔ اول و دومِ همین ۳ سال هر دو باید مثبت باشند).

⚠️ توجهِ افزایشی‌بودن: این یک لایهٔ LONGِ XAUUSD است و ممکن است با S67/S91
(long‌های موجودِ رکورد) هم‌بسته باشد. اگر لایهٔ برنده‌ای پیدا شد، در گامِ بعد
باید ناهمبستگی‌اش با رکورد سنجیده شود (این اسکریپت فقط سوددهیِ مستقل را می‌سنجد).

قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود):
  فقط و فقط دنبالِ «سودِ خالصِ بیشتر» هستیم — WR مهم نیست.
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
YEARS_RECENT = 3


def load_recent():
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    cut = df['dt'].max() - pd.Timedelta(days=365 * YEARS_RECENT)
    return df[df['dt'] >= cut].reset_index(drop=True)


def net_usd(df, long_sig, params):
    """سودِ خالصِ دلاری با موتورِ سرمایه‌محور (هم‌گام با سایت/رکورد)."""
    short_sig = np.zeros(len(df), bool)
    trades = se.simulate_trades(df, long_sig, short_sig, asset='XAUUSD', **params)
    if trades is None or len(trades) == 0:
        return 0.0, 0, 0.0, trades
    stats, _ = se.run_capital(trades, asset='XAUUSD')
    return stats['net_profit'], stats['n_trades'], stats['win_rate'], trades


def build_signals(df):
    """ماشهٔ پایه = mid-cross رو به بالا؛ سپس با فیلترهای قدرتِ روند غربال می‌شود."""
    c = df['close']; p = c.values
    e50 = ind.ema(c, 50).values; e100 = ind.ema(c, 100).values; s200 = ind.sma(c, 200).values
    mid = np.nanmean(np.column_stack([e50, e100, s200]), axis=1)
    base_cross = (np.r_[False, p[:-1] < mid[:-1]]) & (p > mid)

    adx = ind.adx(df, 14)[0].values if isinstance(ind.adx(df, 14), tuple) else ind.adx(df, 14).values
    dist200 = (p - s200) / s200 * 100.0          # فاصلهٔ درصدی از SMA200
    slope50 = ind.rolling_slope(c, 50).values
    stacked_up = (e50 > e100) & (e100 > s200)    # چیدمانِ صعودیِ MA

    filters = {
        'base_only':      base_cross,
        'adx>20':         base_cross & (adx > 20),
        'adx>25':         base_cross & (adx > 25),
        'above_sma200':   base_cross & (p > s200),
        'dist200>1%':     base_cross & (dist200 > 1.0),
        'stacked_up':     base_cross & stacked_up,
        'stacked+adx20':  base_cross & stacked_up & (adx > 20),
        'slope50>0':      base_cross & (slope50 > 0),
        'stacked+slope':  base_cross & stacked_up & (slope50 > 0),
    }
    return filters


def main():
    print("=" * 80)
    print("s112 — شکارِ روندهای بزرگِ صعودی (تبدیلِ کشفِ s111 به سود، ۳ سالِ اخیر)")
    print("=" * 80)
    df = load_recent()
    mid = len(df) // 2
    h1, h2 = df.iloc[:mid].reset_index(drop=True), df.iloc[mid:].reset_index(drop=True)
    print(f"داده: {len(df)} کندل  ({df['dt'].min().date()} → {df['dt'].max().date()})")
    print(f"نیمهٔ اول: {len(h1)} کندل   نیمهٔ دوم: {len(h2)} کندل\n")

    # پروفایل‌های خروج: از «بردِ دونده» تا «اسکالپِ تنگ»
    exits = {
        'run_TP200_SL40':      dict(sl_pip=40, tp_pip=200, max_hold=96, be_trigger_pip=None, trail_pip=None),
        'run_TP300_SL50':      dict(sl_pip=50, tp_pip=300, max_hold=192, be_trigger_pip=None, trail_pip=None),
        'trailBE_wide':        dict(sl_pip=50, tp_pip=400, max_hold=192, be_trigger_pip=30, trail_pip=40),
        'trailBE_med':         dict(sl_pip=40, tp_pip=300, max_hold=96, be_trigger_pip=20, trail_pip=25),
    }

    filters_full = build_signals(df)
    filters_h1 = build_signals(h1)
    filters_h2 = build_signals(h2)

    rows = []
    for fname in filters_full:
        for ename, ep in exits.items():
            net_f, n_f, wr_f, _ = net_usd(df, filters_full[fname], ep)
            net1, n1, _, _ = net_usd(h1, filters_h1[fname], ep)
            net2, n2, _, _ = net_usd(h2, filters_h2[fname], ep)
            both_pos = net1 > 0 and net2 > 0
            rows.append(dict(filt=fname, exit=ename, net_full=net_f, n=n_f, wr=wr_f,
                             h1=net1, h2=net2, both=both_pos))

    rows.sort(key=lambda r: r['net_full'], reverse=True)
    print(f"{'فیلتر':<16}{'خروج':<18}{'net_full':>10}{'n':>6}{'WR':>6}{'h1':>9}{'h2':>9}{'both':>6}")
    print("─" * 82)
    for r in rows[:15]:
        flag = '✅' if r['both'] else '  '
        print(f"{r['filt']:<16}{r['exit']:<18}{r['net_full']:>10,.0f}{r['n']:>6}"
              f"{r['wr']:>5.0f}%{r['h1']:>9,.0f}{r['h2']:>9,.0f}{flag:>6}")

    # بهترین لایهٔ both-halves مثبت
    winners = [r for r in rows if r['both'] and r['net_full'] > 0]
    print("\n" + "=" * 80)
    if winners:
        w = winners[0]
        print(f"✅ بهترین لایهٔ both-halves مثبت:")
        print(f"   فیلتر={w['filt']}  خروج={w['exit']}")
        print(f"   سودِ خالص (۳ سالِ اخیر) = ${w['net_full']:,.0f}   n={w['n']}   WR={w['wr']:.0f}%")
        print(f"   h1=${w['h1']:,.0f}  h2=${w['h2']:,.0f}  (هر دو مثبت)")
        print("\n   گامِ بعد: آزمونِ ناهمبستگی با رکوردِ فعلی برای سنجشِ افزایشی‌بودن.")
    else:
        print("❌ هیچ لایهٔ LONGی با both-halves مثبت یافت نشد.")
    print("=" * 80)

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, '_s112_big_trend.json'), 'w') as f:
        json.dump({'window': f'{YEARS_RECENT}y_recent', 'n_bars': len(df),
                   'top': rows[:15], 'best_both': winners[0] if winners else None},
                  f, ensure_ascii=False, indent=2, default=float)
    print(f"\nذخیره شد: results/_s112_big_trend.json")


if __name__ == '__main__':
    main()
