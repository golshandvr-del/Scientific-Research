# -*- coding: utf-8 -*-
"""
S643 — EngulfEvent — فازِ اکتشاف (مسیرِ C، فقط نیمهٔ اولِ داده)
===============================================================
فرضیه: کندلِ پوشا (Engulfing) = رویدادِ گسستهٔ تغییرِ کنترل درونِ دو کندل.
دو گونه آزموده می‌شود — هر دو با تعریفِ بانکِ اندیکاتور (cdl_engulf_bull/bear):
  • plain  : پوشای خام
  • strong : پوشا + بدنهٔ کندلِ پوشاننده ≥ 1.5× بدنهٔ کندلِ قبلی (فیلترِ قدرت)
دو حالتِ جهت:
  • cont   : پوشای صعودی → لانگ، پوشای نزولی → شورت (ادامه)
  • fade   : برعکس (محوِ رویداد) — تا قانونِ جهت از داده استخراج شود، نه از ادبیات
خانواده در همهٔ PREREGهای S500–S980 بکر است (grep = 0).

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
                   'results', '_s643_explore')
os.makedirs(OUT, exist_ok=True)

PIP = 0.1
MAX_HOLD = 64
TFS = ['M15','M30','H1','H2','H3','H4','H6','H8','H12','D1']
STRONG_K = 1.5

def stats(tr):
    if tr is None or not len(tr): return 0, 0.0, 0.0
    p = tr['pnl_pip'].values
    return len(p), 100.0*(p>0).mean(), float(p.mean())

def run_tf(tf):
    t0=time.time()
    d = fd.load_fast('XAUUSD', tf); df_all = fd.as_dataframe(d)
    half = len(df_all)//2
    df = df_all.iloc[:half].reset_index(drop=True)
    bull = np.asarray(ib.compute('cdl_engulf_bull', df)) > 0
    bear = np.asarray(ib.compute('cdl_engulf_bear', df)) != 0  # bank returns -100 for bear
    o,h,l,c = df['open'].values, df['high'].values, df['low'].values, df['close'].values
    body = np.abs(c-o); pbody = np.roll(body,1); pbody[0]=body[0]
    strong = body >= STRONG_K*np.maximum(pbody, 1e-9)
    pc = np.roll(c,1); pc[0]=c[0]
    tr_ = np.maximum(h-l, np.maximum(abs(h-pc), abs(l-pc)))
    slb = float(np.nanmedian(pd.Series(tr_).rolling(100).mean().values))/PIP
    sl = max(1.0, round(1.5*slb,1)); tp = sl
    zeros = np.zeros(len(df),bool); ones = np.ones(len(df),bool)
    _,wrbL,_ = stats(se.simulate_trades(df,ones,zeros,sl_pip=sl,tp_pip=tp,asset='XAUUSD',max_hold=MAX_HOLD))
    _,wrbS,_ = stats(se.simulate_trades(df,zeros,ones,sl_pip=sl,tp_pip=tp,asset='XAUUSD',max_hold=MAX_HOLD))
    cells=[]
    for variant, bu, be in [('plain', bull, bear), ('strong', bull&strong, bear&strong)]:
        for mode in ('cont','fade'):
            ls, ss = (bu, be) if mode=='cont' else (be, bu)
            for side, sig, zero, wrb in (('long', ls, zeros, wrbL), ('short', ss, zeros, wrbS)):
                if side=='long':
                    tr = se.simulate_trades(df,sig,zero,sl_pip=sl,tp_pip=tp,asset='XAUUSD',max_hold=MAX_HOLD)
                else:
                    tr = se.simulate_trades(df,zero,sig,sl_pip=sl,tp_pip=tp,asset='XAUUSD',max_hold=MAX_HOLD)
                n,wr,ep = stats(tr); lift = wr-wrb
                cells.append({'variant':variant,'mode':mode,'side':side,'n':n,
                              'wr':round(wr,2),'blind':round(wrb,2),'lift':round(lift,2),
                              'exp_pip':round(ep,2),'lsn':round(lift*np.sqrt(max(n,0)),1)})
    res = {'tf':tf,'src':d.get('src'),'bars_first_half':int(half),'sl_pip':sl,
           'cost_to_sl_pct':round(100*3.3/sl,1),'blind_long_wr':round(wrbL,2),
           'blind_short_wr':round(wrbS,2),'n_bull_events':int(bull.sum()),
           'n_bear_events':int(bear.sum()),'cells':cells,'sec':round(time.time()-t0,1)}
    json.dump(res, open(os.path.join(OUT,f'{tf}.json'),'w'), ensure_ascii=False, indent=1)
    return res

if __name__=='__main__':
    for tf in TFS:
        try:
            r = run_tf(tf)
        except Exception as e:
            print(f'[S643] {tf}: ERROR {e}', flush=True); continue
        best = max(r['cells'], key=lambda c:c['lsn'])
        print(f"[S643] {tf}: sl={r['sl_pip']} cost%={r['cost_to_sl_pct']} "
              f"best={best['variant']}/{best['mode']}/{best['side']} lift={best['lift']:+} "
              f"n={best['n']} lsn={best['lsn']} ({r['sec']}s)", flush=True)
    print('[S643] ALL DONE', flush=True)
