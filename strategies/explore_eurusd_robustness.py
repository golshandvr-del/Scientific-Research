"""
explore_eurusd_robustness.py — آزمونِ استحکامِ استراتژیِ drift ساعتی + انتخابِ نهایی
================================================================================
قانونِ #۱: فقط سودِ خالص (XAUUSD+EURUSD).

grid خروج نشان داد کلِ فضای پارامتر سودده و هر دو نیمه مثبت است ⇒ الگو ساختاری.
حالا استحکام را می‌سنجیم و پیکربندیِ نهاییِ robust را انتخاب می‌کنیم:
  A) اثرِ فیلترِ pullback (روشن/خاموش) روی سود و پایداری.
  B) افزودنِ Short ساعتِ 13 UTC به Long ساعتِ 0.
  C) حساسیت به پارامترِ لنگرِ (SL=12,TP=12,hold=6): جابه‌جاییِ ±.
  D) بررسیِ هزینه: با اسپردِ بدتر (1.5 pip) هنوز سودده می‌ماند؟
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from backtest import load_data, run_backtest
import indicators as ind
from capital_engine import run_capital_backtest
import warnings; warnings.filterwarnings('ignore')

PIP = 0.0001
CFG = dict(file='data/EURUSD_M15.csv', contract=100_000.0)
INITIAL_CAPITAL = 10_000.0; RISK_PCT = 1.0; COMMISSION = 7.0; EVAL_START = 24000

def sigs(df, pullback_lb=4, use_pullback=True):
    n = len(df)
    hour = pd.to_datetime(df['time'], unit='s').dt.hour.values
    c = df['close'].values
    ev = np.zeros(n, dtype=bool); ev[EVAL_START:] = True
    lb0 = np.zeros(n, dtype=bool); lb0[:-1] = (hour[1:]==0)&(hour[:-1]!=0)
    longs = lb0 & ev
    if use_pullback:
        prior = np.zeros(n); prior[pullback_lb:] = c[pullback_lb:]-c[:-pullback_lb]
        longs = longs & (prior < 0)
    lb13 = np.zeros(n, dtype=bool); lb13[:-1] = (hour[1:]==13)&(hour[:-1]!=13)
    shorts = lb13 & ev
    return longs, shorts

def bt(df, sig, direction, sl_pip, tp_pip, mh, spread):
    n=len(df)
    sl_series=np.full(n, sl_pip*PIP); tp_series=np.full(n, tp_pip*PIP)
    st,tr=run_backtest(df,sig,None,None,direction,spread=spread,max_hold=mh,
                       sl_series=sl_series,tp_series=tp_series)
    if len(tr)==0: return tr, np.array([])
    return tr, sl_series[tr['signal_bar'].values]

def capital(tr, sld):
    if len(tr)==0: return dict(net_profit=0,win_rate=0,profit_factor=0,max_dd_pct=0,sharpe=0,n_trades=0), 0,0
    order=tr['exit_bar'].values.argsort(); tr=tr.iloc[order].reset_index(drop=True); sld=sld[order]
    s,_=run_capital_backtest(tr,sld,None,INITIAL_CAPITAL,RISK_PCT,COMMISSION,False,CFG['contract'])
    mid=tr['exit_bar'].median(); m1=tr['exit_bar'].values<=mid
    def hn(mk):
        if mk.sum()==0: return 0.0
        x,_=run_capital_backtest(tr[mk].reset_index(drop=True),sld[mk],None,INITIAL_CAPITAL,RISK_PCT,COMMISSION,False,CFG['contract'])
        return x['net_profit']
    return s, hn(m1), hn(~m1)

def combo(df, sl_pip, tp_pip, mh, use_pullback, use_short, spread):
    longs, shorts = sigs(df, use_pullback=use_pullback)
    trL,slL = bt(df,longs,'long',sl_pip,tp_pip,mh,spread)
    frames=[trL]; sls=[slL]
    if use_short:
        trS,slS = bt(df,shorts,'short',sl_pip,tp_pip,mh,spread)
        frames.append(trS); sls.append(slS)
    all_tr=pd.concat([f for f in frames if len(f)],ignore_index=True)
    all_sl=np.concatenate([s for s in sls if len(s)]) if any(len(s) for s in sls) else np.array([])
    return capital(all_tr, all_sl)

def line(tag, s, h1, h2):
    bp = "✓both+" if (h1>0 and h2>0) else "✗"
    print(f"  {tag:<34} net={s['net_profit']:>7.0f}$  n={s['n_trades']:>4}  WR={s['win_rate']:>5.1f}%  "
          f"PF={s['profit_factor']:>4.2f}  DD={s['max_dd_pct']:>5.1f}%  Shrp={s['sharpe']:>4.2f}  "
          f"H1={h1:>6.0f} H2={h2:>6.0f} {bp}", flush=True)

def main():
    df = load_data(CFG['file'])
    print("=== A) اثرِ فیلترِ pullback (لنگر: SL12/TP12/hold6، Long-only، اسپرد 1pip) ===")
    for up in [True, False]:
        s,h1,h2 = combo(df,12,12,6,up,False,0.00010)
        line(f"pullback={up}", s,h1,h2)

    print("\n=== B) افزودنِ Short ساعت13 (لنگر، pullback=True) ===")
    for us in [False, True]:
        s,h1,h2 = combo(df,12,12,6,True,us,0.00010)
        line(f"use_short={us}", s,h1,h2)

    print("\n=== C) حساسیت به لنگر (Long-only، pullback=True، اسپرد1pip) ===")
    for sl_pip,tp_pip,mh in [(10,10,6),(12,12,6),(14,14,6),(12,12,4),(12,12,8),(12,10,6),(12,14,6)]:
        s,h1,h2 = combo(df,sl_pip,tp_pip,mh,True,False,0.00010)
        line(f"SL{sl_pip}/TP{tp_pip}/hold{mh}", s,h1,h2)

    print("\n=== D) استحکام به هزینه (لنگر، Long-only، pullback=True) ===")
    for sp,tag in [(0.00010,'spread=1.0pip'),(0.00013,'spread=1.3pip'),(0.00015,'spread=1.5pip')]:
        s,h1,h2 = combo(df,12,12,6,True,False,sp)
        line(tag, s,h1,h2)

    print("\nتمام.", flush=True)

if __name__ == '__main__':
    main()
