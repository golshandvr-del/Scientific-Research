"""
explore_gold_m5_breakout.py — اکتشافِ لبهٔ Momentum-Breakout روی XAUUSD M5 (User Note 2)
================================================================================
> # قانونِ شمارهٔ ۱ پروژه: هدف فقط «سودِ خالصِ بیشتر» — نه WR.
> **تعریفِ رسمیِ سودِ خالص = XAUUSD + EURUSD.**

درسِ اکتشافِ قبل (explore_gold_m5_scalp): ورودِ کورکورانه در هر کندلِ یک ساعت →
هزاران معامله × هزینه → همه منفی. drift خام (~۱bps) با اسپرد محو می‌شود (درسِ L44).

فرضیهٔ نو (کیفیت > کمیت): طلا در بازهٔ M5 (۲۰۲۳–۲۰۲۶) به‌شدت روندیِ صعودی بوده
(autocorrِ بازده≈۰ ولی روندِ سطحِ قیمت قوی). یک **breakout در جهتِ روندِ کلان**
که با نوسانِ کافی همراه باشد، باید ادامه (momentum) داشته باشد. این انتخابی‌تر است:
  • فیلترِ روندِ کلان: close > EMA_slow (فقط Long در روندِ صعودی — با روندِ داده هم‌سو).
  • ماشه: شکستِ سقفِ N کندلِ اخیر (Donchian upper breakout).
  • فیلترِ نوسان: رنجِ کندلِ شکست ≥ ضریبی از ATR (حرکتِ واقعی، نه نویز).
  • خروج: SL/TP بر حسبِ pip (جارو) + خروجِ زمان‌محور.
کاملاً forward-safe: سیگنال روی close کندل، ورود روی open کندلِ بعد (موتورِ نو).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from engine import scalp_engine as SE

SE.ASSETS['XAUUSD_M5'] = dict(file='data/XAUUSD_M5.csv', pip=0.10, contract=100.0,
                              pip_value=10.0, spread_pip=2.0, comm=7.0, slip_pip=0.5)
ASSET = 'XAUUSD_M5'


def ema(x, span):
    return pd.Series(x).ewm(span=span, adjust=False).mean().values


def atr(df, period=14):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).rolling(period).mean().values


def build_signals(df, don_n, ema_slow, atr_mult):
    c = df['close'].values
    h = df['high'].values
    e_slow = ema(c, ema_slow)
    a = atr(df)
    # سقفِ Donchian از N کندلِ گذشته (شاملِ خودِ کندل نیست → forward-safe)
    don_up = pd.Series(h).rolling(don_n).max().shift(1).values
    rng = (df['high'].values - df['low'].values)
    long_sig = (
        (c > don_up) &                      # شکستِ سقفِ اخیر
        (c > e_slow) &                      # روندِ کلانِ صعودی
        (rng >= atr_mult * a)               # نوسانِ کافی
    )
    long_sig = np.nan_to_num(long_sig, nan=0).astype(bool)
    return long_sig


def main():
    df = SE.load_data(SE.ASSETS[ASSET]['file'])
    n = len(df)
    half = n // 2
    print("=" * 96)
    print("  اکتشافِ Momentum-Breakout روی XAUUSD M5 — موتورِ نو (IS نیمهٔ اول / OOS نیمهٔ دوم)")
    print(f"  کندل‌ها={n}  اسپرد={SE.ASSETS[ASSET]['spread_pip']}pip  comm={SE.ASSETS[ASSET]['comm']}$/لات")
    print("=" * 96)

    best = []
    for don_n in (12, 24, 48):
        for ema_slow in (100, 200, 400):
            for atr_mult in (1.0, 1.5, 2.0):
                long_sig = build_signals(df, don_n, ema_slow, atr_mult)
                for sl in (20, 30, 40):
                    for tp in (30, 50, 80):
                        short = np.zeros(n, bool)
                        tr = SE.simulate_trades(df, long_sig, short, sl, tp, ASSET, max_hold=24)
                        if len(tr) < 200:
                            continue
                        tr_is = tr[tr['entry_bar'] < half]
                        tr_oos = tr[tr['entry_bar'] >= half]
                        if len(tr_is) < 60 or len(tr_oos) < 60:
                            continue
                        s_is, _ = SE.run_capital(tr_is, ASSET)
                        s_oos, _ = SE.run_capital(tr_oos, ASSET)
                        s_all, _ = SE.run_capital(tr, ASSET)
                        if s_is['net_profit'] > 0 and s_oos['net_profit'] > 0:
                            best.append((s_all['net_profit'], don_n, ema_slow, atr_mult, sl, tp,
                                         s_is['net_profit'], s_oos['net_profit'],
                                         s_all['n_trades'], s_all['win_rate'],
                                         s_all['profit_factor'], s_all['max_dd_pct']))

    best.sort(reverse=True)
    print(f"\n  === لبه‌های دو-نیمه-مثبت (پایدار) — {len(best)} ترکیب ===")
    if not best:
        print("   هیچ ترکیبِ دو-نیمه-مثبتی یافت نشد.")
    print(f"  {'netAll':>8} {'don':>4}{'ema':>5}{'atrM':>5}{'SL':>4}{'TP':>4} | {'IS':>7} {'OOS':>7} | {'n':>5}{'WR':>5}{'PF':>5}{'DD%':>6}")
    for r in best[:20]:
        netA, don_n, ema_slow, atr_mult, sl, tp, isp, oosp, ntr, wr, pf, dd = r
        print(f"  {netA:+8.0f} {don_n:>4}{ema_slow:>5}{atr_mult:>5.1f}{sl:>4}{tp:>4} | "
              f"{isp:+7.0f} {oosp:+7.0f} | {ntr:>5}{wr:>5.0f}{pf:>5.2f}{dd:>6.1f}")
    print("=" * 96)


if __name__ == '__main__':
    main()
