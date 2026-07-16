"""
تلاش نهایی استراتژی ۲۰: بررسی مرز WR-فرکانس-سودآوری.
دو ایده باقی‌مانده + اسکن گسترده روی (ch_mult, tp_cap, sl) برای یافتن هر نقطه‌ای
که هم‌زمان WR>=60 و exp>0 و tpd>=3 باشد (شرط کامل کاربر).
"""
import sys, os
import numpy as np
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.indicators import atr
from engine.backtest import load_data
from strategies.s20_squeeze_chandelier import build_signals
from strategies.s20b_sweep import backtest_chandelier_cap


def main():
    df = load_data()
    n_days = (df['dt'].iloc[-1]-df['dt'].iloc[0]).days
    a = atr(df, 14).values

    # برای فرکانس بالا، min_squeeze_len کوچک (سیگنال بیشتر)
    fire, direction = build_signals(df, min_squeeze_len=2)
    print(f"سیگنال fire (len>=2): {fire.sum()} (~{fire.sum()/n_days:.2f}/روز)\n")

    print("اسکن کامل: دنبال WR>=60 و exp>0 و tpd>=3 هم‌زمان")
    print(f"{'ch':>4}{'sl':>5}{'tpcap':>7}{'be':>5}{'n':>7}{'WR%':>8}{'exp$':>9}{'tpd':>7}  flag")
    found = []
    for ch in [1.0, 1.5, 2.0, 3.0, 5.0]:
        for sl in [1.0, 1.5, 2.0, 2.5, 3.0]:
            for tpcap in [None, 0.5, 0.8, 1.0, 1.5, 2.0]:
                for be in [None, 0.5, 1.0]:
                    kw = dict(ch_mult=ch, init_sl_mult=sl)
                    if tpcap: kw['tp_cap_mult'] = tpcap
                    if be: kw['be_trigger_mult'] = be
                    st, _ = backtest_chandelier_cap(df, fire, direction, a, **kw)
                    if st['n_trades'] == 0: continue
                    tpd = st['n_trades']/n_days
                    ok = st['win_rate'] >= 60 and st['expectancy'] > 0 and tpd >= 3
                    ok_soft = st['win_rate'] >= 60 and st['expectancy'] > 0
                    flag = ""
                    if ok: flag = "*** ALL"
                    elif ok_soft: flag = "WR60+exp>0"
                    if ok or ok_soft:
                        found.append((ch, sl, tpcap, be, st, tpd))
                        print(f"{ch:>4}{sl:>5}{str(tpcap):>7}{str(be):>5}"
                              f"{st['n_trades']:>7}{st['win_rate']:>8.2f}"
                              f"{st['expectancy']:>9.3f}{tpd:>7.2f}  {flag}")
    if not found:
        print("\n>>> هیچ ترکیبی WR>=60% را با expectancy>0 برآورده نکرد.")
        # بهترین WR با exp>0 را گزارش کن
        best = None
        for ch in [1.0,1.5,2.0,3.0,5.0]:
            for sl in [1.0,1.5,2.0,2.5,3.0]:
                for tpcap in [None,0.5,0.8,1.0,1.5,2.0]:
                    kw = dict(ch_mult=ch, init_sl_mult=sl)
                    if tpcap: kw['tp_cap_mult']=tpcap
                    st,_ = backtest_chandelier_cap(df, fire, direction, a, **kw)
                    if st['n_trades']==0 or st['expectancy']<=0: continue
                    if best is None or st['win_rate']>best[0]:
                        best=(st['win_rate'], ch, sl, tpcap, st)
        if best:
            wr,ch,sl,tpcap,st = best
            print(f"بهترین WR در میان سودآورها: WR={wr:.2f}% "
                  f"(ch={ch}, sl={sl}, tpcap={tpcap}) exp={st['expectancy']:.3f}$ "
                  f"n={st['n_trades']} tpd={st['n_trades']/n_days:.2f}")


if __name__ == '__main__':
    main()
