# -*- coding: utf-8 -*-
"""
S641 — QqeSaturation — فازِ اکتشاف (مسیرِ C، فقط نیمهٔ اولِ داده)
==================================================================
فرضیه: عبورِ QQE (RSI(14) هموارشده با EMA(5)) از آستانهٔ اشباع → ادامهٔ حرکت.
الهام: الگویِ «اشباع → ادامه»ی S382 (تنها الگوی تکرارشونده در ACCEPTهای پروژه)
ولی با حافظهٔ نمایی به‌جای مستطیلی. خانوادهٔ QQE در ۶۲۶ سندِ پیشین بکر است.

قیود: TP=SL (RR=1)، SL=1.5×ATR(100)median، max_hold=64، نولِ هم‌جهتِ کور.
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
                   'results', '_s641_explore')
os.makedirs(OUT, exist_ok=True)

PIP = 0.1
MAX_HOLD = 64
TFS = ['M15','M30','H1','H2','H3','H4','H6','H8','H12','D1']  # طبق S383: ریزتر از M15 مرده است؛ M15/M30 برای مستندسازی
UP_TH = [55, 60, 65, 70]
DN_TH = [45, 40, 35, 30]

def stats(tr):
    if tr is None or not len(tr): return 0, 0.0, 0.0
    p = tr['pnl_pip'].values
    return len(p), 100.0*(p>0).mean(), float(p.mean())

def run_tf(tf):
    t0=time.time()
    d = fd.load_fast('XAUUSD', tf); df_all = fd.as_dataframe(d)
    half = len(df_all)//2
    df = df_all.iloc[:half].reset_index(drop=True)
    q = ib.compute('qqe', df).values
    pq = np.roll(q,1); pq[0]=q[0]
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
        sig = (q>th)&(pq<=th)
        n,wr,ep = stats(se.simulate_trades(df,sig,zeros,sl_pip=sl,tp_pip=tp,asset='XAUUSD',max_hold=MAX_HOLD))
        lift=wr-wrbL
        cells.append({'side':'long','th':th,'n':n,'wr':round(wr,2),'blind':round(wrbL,2),
                      'lift':round(lift,2),'exp_pip':round(ep,2),
                      'lsn':round(lift*np.sqrt(max(n,0)),1)})
    for th in DN_TH:
        sig = (q<th)&(pq>=th)
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
        print(f"[S641] {tf}: sl={r['sl_pip']} cost%={r['cost_to_sl_pct']} "
              f"best={best['side']}@{best['th']} lift={best['lift']:+} n={best['n']} lsn={best['lsn']}", flush=True)
    print('[S641] ALL DONE', flush=True)
