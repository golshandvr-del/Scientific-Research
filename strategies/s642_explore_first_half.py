# -*- coding: utf-8 -*-
"""
S642 — BopPressure — فازِ اکتشاف (مسیرِ C، فقط نیمهٔ اولِ داده)
================================================================
فرضیه: BOP(14) = SMA14((close-open)/(high-low)) — توازنِ پایدارِ فشارِ
خریدار/فروشنده درونِ کندل. عبور از آستانهٔ مثبت/منفی = فشارِ غالبِ پایدار →
ادامهٔ حرکت. خانواده در همهٔ PREREGهای S500–S980 و ۶۳۰+ سندِ نتایج بکر است.

درس‌های دکاد: فقط TFهای درشت (S383)؛ نولِ هم‌جهتِ کور (S385)؛ RR=1.
نیمهٔ دوم هرگز لمس نمی‌شود.
"""
import json, os, sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import indicator_bank as ib
from engine import scalp_engine as se
from tools import s434_fast_data as fd

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'results', '_s642_explore')
os.makedirs(OUT, exist_ok=True)

PIP = 0.1
MAX_HOLD = 64
TFS = ['M15','M30','H1','H2','H3','H4','H6','H8','H12','D1']
UP_TH = [0.10, 0.15, 0.20, 0.25]     # کراسِ رو به بالا → لانگ
DN_TH = [-0.10, -0.15, -0.20, -0.25] # کراسِ رو به پایین → شورت

def stats(tr):
    if tr is None or not len(tr): return 0, 0.0, 0.0
    p = tr['pnl_pip'].values
    return len(p), 100.0*(p>0).mean(), float(p.mean())

def run_tf(tf):
    t0=time.time()
    d = fd.load_fast('XAUUSD', tf); df_all = fd.as_dataframe(d)
    half = len(df_all)//2
    df = df_all.iloc[:half].reset_index(drop=True)
    b = ib.compute('bop', df).values
    pb = np.roll(b,1); pb[0]=b[0]
    h,l,c = df['high'].values, df['low'].values, df['close'].values
    pc = np.roll(c,1); pc[0]=c[0]
    tr_ = np.maximum(h-l, np.maximum(abs(h-pc), abs(l-pc)))
    slb = float(np.nanmedian(pd.Series(tr_).rolling(100).mean().values))/PIP
    sl = max(1.0, round(1.5*slb,1)); tp = sl
    zeros = np.zeros(len(df),bool); ones = np.ones(len(df),bool)
    _,wrbL,_ = stats(se.simulate_trades(df,ones,zeros,sl_pip=sl,tp_pip=tp,asset='XAUUSD',max_hold=MAX_HOLD))
    _,wrbS,_ = stats(se.simulate_trades(df,zeros,ones,sl_pip=sl,tp_pip=tp,asset='XAUUSD',max_hold=MAX_HOLD))
    cells=[]
    for th in UP_TH:
        sig = (b>th)&(pb<=th)
        n,wr,ep = stats(se.simulate_trades(df,sig,zeros,sl_pip=sl,tp_pip=tp,asset='XAUUSD',max_hold=MAX_HOLD))
        lift=wr-wrbL
        cells.append({'side':'long','th':th,'n':n,'wr':round(wr,2),'blind':round(wrbL,2),
                      'lift':round(lift,2),'exp_pip':round(ep,2),
                      'lsn':round(lift*np.sqrt(max(n,0)),1)})
    for th in DN_TH:
        sig = (b<th)&(pb>=th)
        n,wr,ep = stats(se.simulate_trades(df,zeros,sig,sl_pip=sl,tp_pip=tp,asset='XAUUSD',max_hold=MAX_HOLD))
        lift=wr-wrbS
        cells.append({'side':'short','th':th,'n':n,'wr':round(wr,2),'blind':round(wrbS,2),
                      'lift':round(lift,2),'exp_pip':round(ep,2),
                      'lsn':round(lift*np.sqrt(max(n,0)),1)})
    return {'tf':tf,'n_bars_first_half':int(half),'sl_pip':sl,
            'cost_to_sl_pct':round(100*3.3/sl,1),
            'blind_long':round(wrbL,2),'blind_short':round(wrbS,2),
            'elapsed_s':round(time.time()-t0,1),'cells':cells}

if __name__=='__main__':
    only = sys.argv[1:] if len(sys.argv)>1 else TFS
    for tf in only:
        r = run_tf(tf)
        with open(os.path.join(OUT,f'{tf}.json'),'w') as f:
            json.dump(r,f,ensure_ascii=False,indent=1)
        best = max(r['cells'], key=lambda c:c['lsn'])
        print(f"[S642] {tf}: sl={r['sl_pip']} cost%={r['cost_to_sl_pct']} "
              f"best={best['side']}@{best['th']} lift={best['lift']:+} n={best['n']} lsn={best['lsn']}", flush=True)
    print('[S642] ALL DONE', flush=True)
