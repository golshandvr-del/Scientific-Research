"""
s97_short_ma_confluence.py — استراتژیِ SHORT با ترکیبِ MA (پاسخِ User Note)
================================================================================
> # قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدف فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.**
> **تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.**

انگیزه (User Note): «چرا SHORT سودده نداریم؟ تریدر گفت با ترکیبِ MA (20ema، 50sma،
200sma، 50ema) در تایم‌فریمِ پایین: وقتی خطِ چارت خطوطِ MA را از بالا قطع می‌کند و
MAها فشرده می‌شوند و تثبیت می‌شود ⇒ روندِ نزولی. حتی SHORTهای کوچکِ ۳–۴ pip کافی‌اند.»

کشفِ اکتشافی (explore_short_ma_confluence.py) روی ۲ سالِ اخیر:
  رویدادِ «قطعِ رو به پایینِ MAها + فشردگی» یک drift نزولیِ **کوتاه‌مدت** می‌سازد
  (HZ=4: fwd −5.3pip، t=−1.76) اما در افقِ بلند به mean-reversion برمی‌گردد
  (HZ=48: +8pip). ⇒ SHORT باید **سریع، TP کوچک، max_hold کوتاه** باشد — دقیقاً
  حرفِ تریدر.

این اسکریپت این شهود را به سودِ خالصِ واقعی (موتورِ scalp_engine، اسپردِ ۴pip طلا،
اسلیپیج، ۱۰k$/۱٪) تبدیل و جاروبِ TP/SL/hold انجام می‌دهد. روی ۲ سالِ اخیر + کلِ داده.
================================================================================
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np
import pandas as pd
import indicators as ind
import scalp_engine as se

DATA = os.path.join(os.path.dirname(__file__), '..', 'data', 'XAUUSD_M15.csv')

def load():
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    return df.reset_index(drop=True)

def build_signals(df):
    """سیگنالِ SHORT: خطِ چارت بستهٔ MAها را از بالا به پایین قطع کند + شیبِ نزولی."""
    c = df['close']
    price = c.values
    ema20 = ind.ema(c, 20).values
    ema50 = ind.ema(c, 50).values
    sma50 = ind.sma(c, 50).values
    sma200 = ind.sma(c, 200).values
    atr = ind.atr(df, 14).values

    ma_stack = np.column_stack([ema20, ema50, sma50, sma200])
    ma_top = np.nanmax(ma_stack, axis=1)
    ma_bot = np.nanmin(ma_stack, axis=1)
    ma_mid = np.nanmean(ma_stack, axis=1)

    ribbon_w = (ma_top - ma_bot)
    rw = pd.Series(ribbon_w)
    ribbon_w_z = ((rw - rw.rolling(100).mean()) / (rw.rolling(100).std() + 1e-12)).values
    ema20_slope = pd.Series(ema20).diff().values

    prev_above_mid = np.r_[False, price[:-1] > ma_mid[:-1]]
    # سیگنالِ پایه: قطعِ میانهٔ بسته رو به پایین + شیبِ نزولیِ ema20
    base = prev_above_mid & (price < ma_mid) & (ema20_slope < 0)
    return {
        'base': base,
        'squeeze': ribbon_w_z < 0,
        'below200': price < sma200,
        'strong': (ribbon_w_z < 0) & (ema20 < ema50),   # فشرده + ترتیبِ نزولیِ کوتاه
    }, atr

def run_variant(df, short_sig, sl, tp, hold, label, halves=True):
    long_sig = np.zeros(len(df), dtype=bool)
    trades = se.simulate_trades(df, long_sig, short_sig, sl_pip=sl, tp_pip=tp,
                                asset='XAUUSD', max_hold=hold, allow_overlap=False)
    if len(trades) == 0:
        print(f"  {label}: بدون معامله")
        return None
    stats, eq = se.run_capital(trades, 'XAUUSD', initial_capital=10000, risk_pct=1.0, compounding=False)
    extra = ""
    if halves and len(trades) > 4:
        mid = len(df)//2
        t1 = trades[trades['entry_bar'] < mid]; t2 = trades[trades['entry_bar'] >= mid]
        n1 = se.run_capital(t1,'XAUUSD',10000,1.0,False)[0]['net_profit'] if len(t1) else 0
        n2 = se.run_capital(t2,'XAUUSD',10000,1.0,False)[0]['net_profit'] if len(t2) else 0
        extra = f"  H1={n1:+.0f} H2={n2:+.0f}"
    print(f"  {label:32s} SL{sl:.0f}/TP{tp:.0f}/H{hold:2d}: "
          f"net={stats['net_profit']:+8.0f}$ n={stats['n_trades']:4d} "
          f"WR={stats['win_rate']:4.1f}% PF={stats['profit_factor']:.2f}{extra}")
    return stats

def main():
    df_full = load()
    n_2y = 2*365*24*4
    df_2y = df_full.iloc[-n_2y:].reset_index(drop=True)

    for tag, df in [('۲ سالِ اخیر', df_2y), ('کلِ ۱۵۰k', df_full)]:
        print(f"\n{'='*70}\nبازه: {tag}  ({len(df)} کندل)\n{'='*70}")
        sig, atr = build_signals(df)

        # جاروبِ TP/SL/hold — SHORTِ کوتاه (حرفِ تریدر: TP کوچک، سریع)
        print("\n[A] سیگنالِ پایه (cross-mid-down):")
        for sl, tp, hold in [(15,10,4),(20,15,6),(25,20,8),(30,30,12),(40,40,16)]:
            run_variant(df, sig['base'], sl, tp, hold, 'base')

        print("\n[B] پایه + فشردگی (squeeze):")
        s = sig['base'] & sig['squeeze']
        for sl, tp, hold in [(15,10,4),(20,15,6),(25,20,8),(30,30,12),(40,40,16)]:
            run_variant(df, s, sl, tp, hold, 'base+squeeze')

        print("\n[C] پایه + فشردگی + ترتیبِ نزولی (strong):")
        s = sig['base'] & sig['strong']
        for sl, tp, hold in [(15,10,4),(20,15,6),(25,20,8),(30,30,12),(40,40,16)]:
            run_variant(df, s, sl, tp, hold, 'strong')

        print("\n[D] پایه + زیرِ sma200 (رژیمِ نزولیِ کلان):")
        s = sig['base'] & sig['below200']
        for sl, tp, hold in [(15,10,4),(20,15,6),(25,20,8),(30,30,12),(40,40,16)]:
            run_variant(df, s, sl, tp, hold, 'base+below200')

if __name__ == '__main__':
    main()
