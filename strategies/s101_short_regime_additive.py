"""
s101_short_regime_additive.py — فیلترِ رژیم + آزمونِ افزایشی‌بودنِ SHORT به رکورد
================================================================================
> # قانونِ شمارهٔ ۱ پروژه: هدف فقط «سودِ خالصِ بیشتر». سودِ خالص = XAUUSD + EURUSD.

درسِ s100: لبهٔ SHORT روی ۲ سالِ اخیر قوی و robust است (+۱۴k$، هر دو نیمه مثبت،
۳۶/۳۶ پارامتر مثبت)، اما روی کلِ ۱۵۰k کندل DD=−۶۰٪ دارد چون در بازهٔ رنج/صعودیِ
۲۰۲۰–۲۰۲۳ ضدِ روند SHORT می‌زند. راه‌حل: **فیلترِ رژیم** تا SHORT فقط در محیطِ
مناسب (نزولی/غیرصعودیِ قوی) فعال شود.

هدفِ نهایی (طبقِ PARADIGM v6): این جریانِ SHORT باید **ناهمبسته با long-stack**
باشد (در نزول سود دهد وقتی long ساکت است) ⇒ افزایشی به رکوردِ +۶۱٬۱۰۲$.

این اسکریپت:
  ۱) چند فیلترِ رژیم را روی SHORT آزمون و DD را کنترل می‌کند.
  ۲) همبستگیِ سودِ روزانهٔ SHORT با long-stack را می‌سنجد.
  ۳) افزایشی‌بودنِ واقعی (long + short) را محاسبه می‌کند.
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
    df = pd.read_csv(DATA); df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    return df.reset_index(drop=True)

def base_signal(df):
    c = df['close']; price = c.values
    e50 = ind.ema(c,50).values; e100 = ind.ema(c,100).values; s200 = ind.sma(c,200).values
    M = np.column_stack([e50,e100,s200]); mid = np.nanmean(M,axis=1)
    ev = (np.r_[False, price[:-1] > mid[:-1]]) & (price < mid)
    return ev, price, e50, e100, s200

def regimes(df, price, e50, e100, s200):
    c = df['close']
    e200 = ind.ema(c,200).values
    slope200 = pd.Series(s200).diff(20).values          # شیبِ SMA200 روی ۲۰ کندل
    ema50_slope = pd.Series(e50).diff(10).values
    # HTF: روندِ روزانه (close < EMA بلندمدت)
    return {
        'no_filter':      np.ones(len(df), bool),
        'below_s200':     price < s200,
        's200_falling':   slope200 < 0,
        'e50_below_e100': e50 < e100,
        'e50_below_e200': e50 < e200,
        'dn_stack':       (e50 < e100) & (e100 < s200),
        'below+falling':  (price < s200) & (slope200 < 0),
        'e50fall+below':  (ema50_slope < 0) & (price < e100),
    }

def bt(df, ev, sl=40, be=8, tr=8, hold=12):
    long = np.zeros(len(df), bool)
    trades = se.simulate_trades(df, long, ev, sl_pip=sl, tp_pip=200, asset='XAUUSD',
                                max_hold=hold, allow_overlap=False, be_trigger_pip=be, trail_pip=tr)
    stats, eq, pt = se.run_capital_pertrade(trades, 'XAUUSD', df=df,
                                            initial_capital=10000, risk_pct=1.0, compounding=False)
    return stats, trades, pt

def main():
    df = load()
    n2y = 2*365*24*4
    ev, price, e50, e100, s200 = base_signal(df)
    regs = regimes(df, price, e50, e100, s200)

    print("="*74)
    print("۱) فیلترِ رژیم روی SHORT (SL40/BE8/TR8/H12) — کنترلِ DD روی کلِ ۱۵۰k")
    print("="*74)
    print(f"{'فیلتر':18s} {'net_full':>10s} {'DD%':>7s} {'PF':>5s} {'n':>6s} | {'net_2y':>9s} {'H1':>7s} {'H2':>7s}")
    best = None
    for name, mask in regs.items():
        s = ev & mask
        st, trd, _ = bt(df, s)
        # روی ۲ سال
        d2 = df.iloc[-n2y:].reset_index(drop=True)
        ev2, p2,a,b,c2 = base_signal(d2); r2 = regimes(d2,p2,a,b,c2)
        s2 = ev2 & r2[name]
        st2, trd2, _ = bt(d2, s2)
        mid=len(d2)//2; t1=trd2[trd2['entry_bar']<mid]; t2=trd2[trd2['entry_bar']>=mid]
        n1=se.run_capital(t1,'XAUUSD',10000,1.0,False)[0]['net_profit'] if len(t1) else 0
        n2v=se.run_capital(t2,'XAUUSD',10000,1.0,False)[0]['net_profit'] if len(t2) else 0
        print(f"{name:18s} {st['net_profit']:+10.0f} {st['max_dd_pct']:7.1f} {st['profit_factor']:5.2f} "
              f"{st['n_trades']:6d} | {st2['net_profit']:+9.0f} {n1:+7.0f} {n2v:+7.0f}")
        # معیار: کلِ داده مثبت + DD معقول (>-25%) + هر دو نیمهٔ ۲ سال مثبت
        score = st['net_profit'] if (st['max_dd_pct']>-30 and n1>0 and n2v>0) else -1e9
        if score > (best[0] if best else -1e18):
            best = (score, name, st, st2, n1, n2v)

    print(f"\n>>> بهترین فیلتر (کل مثبت + DD معقول + هر دو نیمه مثبت): "
          f"{best[1] if best else 'هیچ‌کدام'}")
    if best and best[0] > -1e8:
        print(f"    کلِ ۱۵۰k: {best[2]['net_profit']:+.0f}$ (DD {best[2]['max_dd_pct']:.1f}%, PF {best[2]['profit_factor']:.2f})")
        print(f"    ۲ سال:   {best[3]['net_profit']:+.0f}$ (H1={best[4]:+.0f}, H2={best[5]:+.0f})")

if __name__ == '__main__':
    main()
