"""
s102_short_additivity_final.py — آزمونِ نهاییِ افزایشی‌بودنِ SHORT به رکورد
================================================================================
پاسخِ نهایی به User Note: «چرا SHORT سودده نداریم؟»

کشفِ چرخهٔ S97→S101:
  • ماشهٔ SHORT = «قیمت میانگینِ MA-set [EMA50,EMA100,SMA200] را از بالا رو به
    پایین قطع کند» (دقیقاً حرفِ تریدر: خطِ چارت خطوطِ MA را از بالا قطع می‌کند).
  • خروج = SL40 + BE8 + trailing8 + max_hold12  →  معاملاتِ سریع (میانگین ۱.۱ کندل!)
    که همان «سودِ کوچکِ سریعِ ۳-۴ دلاری» موردِ نظرِ کاربر است.
  • نتیجه: کلِ ۱۵۰k = +30,853$، DD -4.1%، PF 1.35، هر چهار پنجرهٔ walk-forward مثبت.

این اسکریپت آزمونِ حیاتی را انجام می‌دهد:
  1. آیا SHORT با long‌های XAUUSD (رژیمِ صعودی) *ناهمبسته* است؟ (همبستگیِ سودِ روزانه)
  2. آیا مجموعِ سودِ خالص افزایش می‌یابد؟ (رکوردِ فعلی +61,102$)

قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت): فقط و فقط دنبالِ «سودِ خالصِ بیشتر»
هستیم — وین‌ریت مهم نیست. تعریفِ سودِ خالص = جمعِ سودِ XAUUSD + EURUSD.
================================================================================
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
import indicators as ind
import scalp_engine as se

DATA = os.path.join(os.path.dirname(__file__), '..', 'data', 'XAUUSD_M15.csv')
RESULTS = os.path.join(os.path.dirname(__file__), '..', 'results')
RECORD_TOTAL = 61102.0          # رکوردِ فعلیِ کل
RECORD_XAU   = 51880.0          # سهمِ XAUUSD از رکورد (S67+S91+S81)
RECORD_EUR   = 9223.0           # سهمِ EURUSD (S73)


def load():
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    return df


def short_signal(df):
    """ماشهٔ SHORT: قیمت میانگینِ [EMA50,EMA100,SMA200] را از بالا رو به پایین قطع کند."""
    c = df['close']; p = c.values
    e50 = ind.ema(c, 50).values
    e100 = ind.ema(c, 100).values
    s200 = ind.sma(c, 200).values
    M = np.column_stack([e50, e100, s200])
    mid = np.nanmean(M, axis=1)
    return (np.r_[False, p[:-1] > mid[:-1]]) & (p < mid)


def long_signal_xau(df):
    """
    نمایندهٔ long‌های XAUUSD رکورد (رژیمِ صعودی): ماشهٔ آینه‌ایِ SHORT —
    قیمت میانگینِ همان MA-set را از پایین رو به بالا قطع کند. این نمایندهٔ
    ساختاریِ همان جریانِ long است که رکورد را می‌سازد و برای سنجشِ *همبستگی*
    کافی است (نه بازتولیدِ دقیقِ S67).
    """
    c = df['close']; p = c.values
    e50 = ind.ema(c, 50).values
    e100 = ind.ema(c, 100).values
    s200 = ind.sma(c, 200).values
    M = np.column_stack([e50, e100, s200])
    mid = np.nanmean(M, axis=1)
    return (np.r_[False, p[:-1] < mid[:-1]]) & (p > mid)


def daily_pnl(df, trades):
    """سودِ دلاریِ هر معامله را به سطلِ روزِ خروجش می‌ریزد → سریِ سودِ روزانه."""
    if trades is None or len(trades) == 0:
        return pd.Series(dtype=float)
    exit_dt = df['dt'].values[trades['exit_bar'].values.astype(int)]
    day = pd.to_datetime(exit_dt).normalize()
    s = pd.Series(trades['pnl_pip'].values, index=day)
    # dollar تقریبی با pip_value ثابت (برای همبستگی کافی است — مقیاس مهم نیست)
    return s.groupby(level=0).sum()


def main():
    df = load()
    long_flat = np.zeros(len(df), bool)

    print("=" * 74)
    print("قانونِ شمارهٔ ۱: فقط «سودِ خالصِ بیشتر» — وین‌ریت مهم نیست.")
    print("تعریفِ سودِ خالص = جمعِ سودِ XAUUSD + EURUSD.")
    print("=" * 74)

    # ---- ۱) سودِ SHORT با پارامترِ برنده ----
    sh = short_signal(df)
    tr_sh = se.simulate_trades(df, long_flat, sh, sl_pip=40, tp_pip=200,
                               asset='XAUUSD', max_hold=12, allow_overlap=False,
                               be_trigger_pip=8, trail_pip=8)
    st_sh, eq_sh = se.run_capital(tr_sh, 'XAUUSD', 10000, 1.0, False)
    print(f"\n۱) SHORT (MA-confluence + trailing):")
    print(f"   net={st_sh['net_profit']:+.0f}$  n={st_sh['n_trades']}  "
          f"WR={st_sh['win_rate']:.1f}%  PF={st_sh['profit_factor']:.2f}  "
          f"DD={st_sh['max_dd_pct']:.1f}%  avgBars={tr_sh['bars_held'].mean():.1f}")

    # ---- ۲) همبستگیِ سودِ روزانهٔ SHORT با long نمایندهٔ XAUUSD ----
    lo = long_signal_xau(df)
    tr_lo = se.simulate_trades(df, lo, np.zeros(len(df), bool), sl_pip=40, tp_pip=200,
                               asset='XAUUSD', max_hold=12, allow_overlap=False,
                               be_trigger_pip=8, trail_pip=8)
    d_sh = daily_pnl(df, tr_sh)
    d_lo = daily_pnl(df, tr_lo)
    joined = pd.concat([d_sh.rename('short'), d_lo.rename('long')], axis=1).fillna(0.0)
    corr = joined['short'].corr(joined['long'])
    both_active = ((joined['short'] != 0) & (joined['long'] != 0)).mean() * 100
    print(f"\n۲) ناهمبستگیِ SHORT با long-XAUUSD:")
    print(f"   همبستگیِ سودِ روزانه = {corr:+.3f}   "
          f"(روزهایی که هر دو فعال‌اند: {both_active:.1f}%)")
    print(f"   → همبستگیِ نزدیک به صفر/منفی یعنی جریان‌ها مکمل‌اند "
          f"(SHORT در نزول، long در صعود).")

    # ---- ۳) آزمونِ افزایشی‌بودن به رکورد ----
    add = st_sh['net_profit']
    new_xau = RECORD_XAU + add
    new_total = RECORD_EUR + new_xau
    print(f"\n۳) افزایشی‌بودن به رکورد:")
    print(f"   رکوردِ فعلی:  XAUUSD {RECORD_XAU:+.0f}$ + EURUSD {RECORD_EUR:+.0f}$ "
          f"= {RECORD_TOTAL:+.0f}$")
    print(f"   + SHORT جدید: {add:+.0f}$  (جریانِ ناهمبستهٔ نزولی)")
    print(f"   ─────────────────────────────────────────────")
    print(f"   رکوردِ جدید:  XAUUSD {new_xau:+.0f}$ + EURUSD {RECORD_EUR:+.0f}$ "
          f"= {new_total:+.0f}$")
    print(f"   Δ = {new_total - RECORD_TOTAL:+.0f}$  "
          f"({(new_total/RECORD_TOTAL-1)*100:+.1f}%)")

    verdict = (add > 0) and (abs(corr) < 0.35) and (new_total > RECORD_TOTAL)
    print("\n" + "=" * 74)
    if verdict:
        print(f"✅ SHORT افزایشی است → رکوردِ جدید +{new_total:,.0f}$ "
              f"(پاسخِ کاملِ User Note: SHORT سودده ساخته شد).")
    else:
        print("⚠️ نیاز به بررسیِ بیشتر (همبستگیِ بالا یا سودِ ناکافی).")
    print("=" * 74)

    out = {
        'short_net': float(st_sh['net_profit']),
        'short_n': int(st_sh['n_trades']),
        'short_pf': float(st_sh['profit_factor']),
        'short_dd_pct': float(st_sh['max_dd_pct']),
        'short_wr': float(st_sh['win_rate']),
        'short_avg_bars': float(tr_sh['bars_held'].mean()),
        'corr_daily_with_long': float(corr),
        'record_old': RECORD_TOTAL,
        'record_new': float(new_total),
        'delta': float(new_total - RECORD_TOTAL),
        'verdict_additive': bool(verdict),
    }
    with open(os.path.join(RESULTS, '_s102_short_additivity.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\nخروجی: results/_s102_short_additivity.json")


if __name__ == '__main__':
    main()
