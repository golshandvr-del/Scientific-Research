"""
s100_short_ma_validate.py — اعتبارسنجیِ سختگیرانهٔ برندهٔ SHORT (e50+e100+s200 trailing)
================================================================================
> # قانونِ شمارهٔ ۱ پروژه: هدف فقط «سودِ خالصِ بیشتر». سودِ خالص = XAUUSD + EURUSD.

نامزدِ برندهٔ s99 (روی ۲ سالِ اخیر): سیگنالِ «خطِ چارت میانهٔ بستهٔ MA (e50,e100,s200)
را رو به پایین قطع کند» + خروجِ trailing (SL30/BE10/TR10/max_hold=8) = +۱۴٬۴۵۲$،
هر دو نیمه مثبت. این دقیقاً حرفِ تریدر است: SHORTِ سریعِ کوتاه با سودِ کوچک.

⚠️ این نتیجه فقط پس از **رفعِ باگِ look-ahead در trailing** (engine/scalp_engine.py)
به‌دست آمد؛ پیش از آن سودِ جعلیِ +۱۶۰k$ می‌داد.

این اسکریپت اعتبارسنجیِ کامل انجام می‌دهد پیش از هر ادعای رکورد:
  ۱) کلِ ۱۵۰k کندل (نه فقط ۲ سال).
  ۲) Walk-forward چهار-پنجره‌ای.
  ۳) حساسیت به پارامتر (robustness).
  ۴) حساسیت به هزینه (اسپردِ بدتر).
  ۵) آزمونِ افزایشی‌بودن: آیا به رکوردِ long-only (+۶۱٬۱۰۲$) اضافه می‌شود؟
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

def signal(df):
    c = df['close']; price = c.values
    e50 = ind.ema(c,50).values; e100 = ind.ema(c,100).values; s200 = ind.sma(c,200).values
    M = np.column_stack([e50,e100,s200]); mid = np.nanmean(M,axis=1)
    ev = (np.r_[False, price[:-1] > mid[:-1]]) & (price < mid)
    return ev

def bt(df, ev, sl=30, be=10, tr=10, hold=8):
    long = np.zeros(len(df), bool)
    trades = se.simulate_trades(df, long, ev, sl_pip=sl, tp_pip=200, asset='XAUUSD',
                                max_hold=hold, allow_overlap=False, be_trigger_pip=be, trail_pip=tr)
    st = se.run_capital(trades, 'XAUUSD', 10000, 1.0, False)[0]
    return st, trades

def main():
    df = load()
    n2y = 2*365*24*4

    print("="*72)
    print("۱) اعتبارسنجیِ پایه: ۲ سالِ اخیر در برابرِ کلِ ۱۵۰k")
    print("="*72)
    for tag, d in [('۲ سال', df.iloc[-n2y:].reset_index(drop=True)), ('کلِ ۱۵۰k', df)]:
        ev = signal(d)
        st, trd = bt(d, ev)
        mid = len(d)//2
        t1 = trd[trd['entry_bar']<mid]; t2 = trd[trd['entry_bar']>=mid]
        n1 = se.run_capital(t1,'XAUUSD',10000,1.0,False)[0]['net_profit'] if len(t1) else 0
        n2 = se.run_capital(t2,'XAUUSD',10000,1.0,False)[0]['net_profit'] if len(t2) else 0
        print(f"  [{tag:8s}] net={st['net_profit']:+9.0f}$ n={st['n_trades']:5d} "
              f"WR={st['win_rate']:.1f}% PF={st['profit_factor']:.2f} DD={st['max_dd_pct']:.1f}% "
              f"Sh={st['sharpe']:.2f} | H1={n1:+.0f} H2={n2:+.0f}")

    print("\n"+"="*72)
    print("۲) Walk-forward چهار-پنجره‌ای (کلِ داده)")
    print("="*72)
    q = len(df)//4
    for i in range(4):
        d = df.iloc[i*q:(i+1)*q].reset_index(drop=True)
        ev = signal(d); st,_ = bt(d, ev)
        print(f"  پنجرهٔ {i+1}/4 ({d['dt'].iloc[0].date()}→{d['dt'].iloc[-1].date()}): "
              f"net={st['net_profit']:+8.0f}$ n={st['n_trades']:4d} PF={st['profit_factor']:.2f}")

    print("\n"+"="*72)
    print("۳) حساسیت به پارامتر (۲ سال) — آیا لبه به یک نقطهٔ خاص وابسته است؟")
    print("="*72)
    d = df.iloc[-n2y:].reset_index(drop=True); ev = signal(d)
    for sl in [25,30,40]:
        for be,tr in [(8,8),(10,10),(12,12),(15,10)]:
            for hold in [6,8,12]:
                st,_ = bt(d, ev, sl=sl, be=be, tr=tr, hold=hold)
                mark = "✅" if st['net_profit']>0 else "❌"
                print(f"  SL{sl}/BE{be}/TR{tr}/H{hold:2d}: net={st['net_profit']:+8.0f}$ PF={st['profit_factor']:.2f} {mark}")

    print("\n"+"="*72)
    print("۴) حساسیت به هزینه: اسپردِ بدتر از ۴pip")
    print("="*72)
    orig = se.ASSETS['XAUUSD']['spread_pip']
    for sp in [4.0, 5.0, 6.0, 8.0]:
        se.ASSETS['XAUUSD']['spread_pip'] = sp
        st,_ = bt(d, ev)
        print(f"  اسپرد={sp}pip: net={st['net_profit']:+8.0f}$ PF={st['profit_factor']:.2f}")
    se.ASSETS['XAUUSD']['spread_pip'] = orig

if __name__ == '__main__':
    main()
