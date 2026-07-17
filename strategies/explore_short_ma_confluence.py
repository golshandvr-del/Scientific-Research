"""
explore_short_ma_confluence.py — پاسخِ مستقیم به User Note (کشفِ SHORT سودده)
================================================================================
> # قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت)
> **هدف فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.**
> تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.

--------------------------------------------------------------------------------
انگیزه (نقلِ User Note):
  «چرا نمی‌توانیم معاملهٔ short سودده داشته باشیم؟ امروز بازار روند نزولیِ قوی
   ~30pip داشت اما ربات نتوانست تشخیص دهد. یک تریدر گفت با ترکیبِ ۵ MA در
   تایم‌فریمِ پایین می‌توان روندهای درست را کشف کرد — نه رفتارِ MAها نسبت به هم
   به‌تنهایی، بلکه رفتارِ *نمودار (خطِ چارت = MA با دورهٔ ۱)* نسبت به این MAها:
   وقتی خطِ چارت خطوطِ MA را از بالا قطع می‌کند و خطوطِ MA بهم نزدیک می‌شوند
   (فشردگی) و اگر تثبیت شود ⇒ روندِ نزولیِ قوی در راه است. اعداد: 20ema، 50sma،
   200sma، 50ema. با اعداد/تعداد/انواعِ مختلف MA امتحان کن؛ سیستمی بساز که روند
   را تشخیص دهد و با واقعیتِ روندِ بعدی مطابقت دهد و امتیاز بدهد.»

این اسکریپت مرحلهٔ اکتشاف است (بدون بک‌تستِ پول): آیا رویدادِ «قطعِ رو به پایینِ
خطِ چارت از میان بستهٔ MAها + فشردگیِ MAها» با drift نزولیِ آیندهٔ معنادار همراه
است؟ روی داده‌های ۲ سالِ اخیر (طبقِ User Note: «یک قدم به عقب، ۲ سالِ اخیر»).
================================================================================
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np
import pandas as pd
import indicators as ind

DATA = os.path.join(os.path.dirname(__file__), '..', 'data', 'XAUUSD_M15.csv')

def load():
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    return df.reset_index(drop=True)

def main():
    df = load()
    # ۲ سالِ اخیر: M15 ⇒ ~۲ سال ≈ 2*365*24*4 ≈ 70080 کندل. برش آخر.
    n_2y = 2 * 365 * 24 * 4
    df = df.iloc[-n_2y:].reset_index(drop=True)
    print(f"بازهٔ ۲ سالِ اخیر: {df['dt'].iloc[0]} → {df['dt'].iloc[-1]}  ({len(df)} کندل)")

    c = df['close']
    price = c.values

    # ---- MAهای موردِ اشارهٔ تریدر ----
    ema20 = ind.ema(c, 20).values
    ema50 = ind.ema(c, 50).values
    sma50 = ind.sma(c, 50).values
    sma200 = ind.sma(c, 200).values

    MAs = {'ema20': ema20, 'ema50': ema50, 'sma50': sma50, 'sma200': sma200}
    ma_stack = np.column_stack([ema20, ema50, sma50, sma200])
    ma_top = np.nanmax(ma_stack, axis=1)
    ma_bot = np.nanmin(ma_stack, axis=1)
    ma_mid = np.nanmean(ma_stack, axis=1)

    atr = ind.atr(df, 14).values

    # فشردگیِ MAها: پهنای بسته / ATR  (کوچک = فشرده)
    ribbon_w = (ma_top - ma_bot)
    ribbon_w_atr = ribbon_w / np.where(atr > 0, atr, np.nan)
    # z-score پهنا نسبت به ۱۰۰ کندلِ اخیر (منفی = فشرده‌تر از معمول)
    rw = pd.Series(ribbon_w)
    ribbon_w_z = ((rw - rw.rolling(100).mean()) / (rw.rolling(100).std() + 1e-12)).values

    # رویدادِ «قطعِ رو به پایین»: کندلِ قبل قیمت بالای همهٔ MAها بود، حالا زیرِ همه بست.
    above_all_prev = np.zeros(len(df), dtype=bool)
    below_all_now = price < ma_bot
    above_all = price > ma_top
    above_all_prev[1:] = above_all[:-1]
    cross_down = above_all_prev & below_all_now

    # نسخهٔ نرم‌تر: عبور از زیرِ میانهٔ بسته + شیبِ نزولیِ ema20
    ema20_slope = pd.Series(ema20).diff().values
    cross_mid_down = (np.r_[False, price[:-1] > ma_mid[:-1]]) & (price < ma_mid) & (ema20_slope < 0)

    print("\n=== فراوانیِ رویدادها در ۲ سالِ اخیر ===")
    print(f"قطعِ رو به پایینِ کلِ بسته (cross below all): {cross_down.sum()}")
    print(f"قطعِ میانهٔ بسته + شیبِ نزولی (soft):          {cross_mid_down.sum()}")

    # ---- سیستمِ امتیازدهی: آیا رویداد با drift نزولیِ آینده همراه است؟ ----
    # افقِ آینده (forward return) بر حسبِ pip طلا (pip=0.10). 
    for HZ in [4, 8, 16, 24, 48]:
        fwd = np.full(len(df), np.nan)
        for i in range(len(df) - HZ):
            fwd[i] = (price[i + HZ] - price[i]) / 0.10   # pip
        # میانگینِ forward return برای رویداد در برابر کل
        def stat(mask, name):
            m = mask & ~np.isnan(fwd)
            if m.sum() < 20:
                print(f"  [{name}] HZ={HZ}: n={m.sum()} (کم)")
                return
            ev = fwd[m]
            base = fwd[~np.isnan(fwd)]
            # t-stat اختلافِ میانگین از صفر
            t = ev.mean() / (ev.std() / np.sqrt(len(ev)) + 1e-12)
            win_dn = (ev < 0).mean() * 100
            print(f"  [{name}] HZ={HZ:2d}: n={m.sum():5d}  fwd_mean={ev.mean():+7.1f}pip  "
                  f"t={t:+5.2f}  P(down)={win_dn:4.1f}%  (base_mean={base.mean():+.1f}pip)")
        print(f"\n--- افقِ {HZ} کندل ({HZ*15}دقیقه) ---")
        stat(cross_down, 'cross_all_down')
        stat(cross_mid_down, 'cross_mid_down')
        # با فیلترِ فشردگی
        stat(cross_mid_down & (ribbon_w_z < 0), 'mid_down + squeeze')
        # با تأییدِ رژیمِ نزولی HTF (قیمت زیرِ sma200)
        stat(cross_mid_down & (price < sma200), 'mid_down + below_sma200')

if __name__ == '__main__':
    main()
