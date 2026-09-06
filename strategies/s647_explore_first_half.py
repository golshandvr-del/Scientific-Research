# -*- coding: utf-8 -*-
"""
S647 — AoZeroCrossDrift — فازِ اکتشاف (مسیرِ C، فقط نیمهٔ اولِ داده)
====================================================================
فرضیه (Bill Williams، Awesome Oscillator = SMA5(mid) − SMA34(mid)): گذرِ AO از صفر
رویدادِ گسستهٔ تغییرِ تعادلِ مومنتوم است. با درسِ S646 (تلهٔ رژیمِ دوسویه) و الگویِ
لایه‌های ACCEPT موازی (S604/S919/S966: گیتِ درفتِ ۶۰ روزِ تقویمی)، دو گونه بررسی می‌شود:
  • plain   : هر گذر (↑ → لانگ، ↓ → شورت)
  • aligned : گذر فقط هم‌راستا با درفتِ ۶۰ روزِ تقویمی (close[t−1] − close[t−1−60d])
  • counter : گذرِ خلافِ درفت (فقط برای تشخیص؛ پیش‌ثبت نمی‌شود)
دو حالت cont/fade. دو هندسه: RR=1 (استانداردِ دکاد) و RR=1.618 (TP=1.618×SL؛ به ارث از S919).
خانوادهٔ AO در S500–S980 بکر است (grep = 0). نیمهٔ دوم هرگز لمس نمی‌شود.
"""
import json, os, sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import indicator_bank as ib
from engine import scalp_engine as se
from tools import s434_fast_data as fd

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'results', '_s647_explore')
os.makedirs(OUT, exist_ok=True)

PIP = 0.1
MAX_HOLD = 64
TFS = ['M15','M30','H1','H2','H3','H4','H6','H8','H12','D1']
DRIFT_SEC = 60*86400
RRS = [1.0, 1.618]

def stats(tr):
    if tr is None or not len(tr): return 0, 0.0, 0.0
    p = tr['pnl_pip'].values
    return len(p), 100.0*(p>0).mean(), float(p.mean())

def run_tf(tf):
    t0=time.time()
    d = fd.load_fast('XAUUSD', tf); df_all = fd.as_dataframe(d)
    half = len(df_all)//2
    df = df_all.iloc[:half].reset_index(drop=True)
    o,h,l,c = df['open'].values, df['high'].values, df['low'].values, df['close'].values
    t = df['time'].values.astype(np.int64)
    ao = ib.compute('ao', df).values
    pao = np.roll(ao,1); pao[0] = np.nan
    with np.errstate(invalid='ignore'):
        up = np.nan_to_num((pao <= 0) & (ao > 0), nan=False).astype(bool)
        dn = np.nan_to_num((pao >= 0) & (ao < 0), nan=False).astype(bool)
    # درفتِ ۶۰ روزِ تقویمی، علّی: close[t-1] - close[idx(time[t-1]-60d)]
    pc1 = np.roll(c,1); pc1[0]=c[0]
    pt1 = np.roll(t,1); pt1[0]=t[0]
    j = np.searchsorted(t, pt1 - DRIFT_SEC, side='left')
    drift = pc1 - c[np.clip(j,0,len(c)-1)]
    drift[j <= 0] = 0.0
    dpos = drift > 0; dneg = drift < 0
    variants = [('plain', up, dn), ('aligned', up & dpos, dn & dneg), ('counter', up & dneg, dn & dpos)]
    pc = np.roll(c,1); pc[0]=c[0]
    tr_ = np.maximum(h-l, np.maximum(abs(h-pc), abs(l-pc)))
    slb = float(np.nanmedian(pd.Series(tr_).rolling(100).mean().values))/PIP
    sl = max(1.0, round(1.5*slb,1))
    zeros = np.zeros(len(df),bool); ones = np.ones(len(df),bool)
    cells=[]
    for rr in RRS:
        tp = round(rr*sl,1)
        _,wrbL,_ = stats(se.simulate_trades(df,ones,zeros,sl_pip=sl,tp_pip=tp,asset='XAUUSD',max_hold=MAX_HOLD))
        _,wrbS,_ = stats(se.simulate_trades(df,zeros,ones,sl_pip=sl,tp_pip=tp,asset='XAUUSD',max_hold=MAX_HOLD))
        for variant, bu, be in variants:
            for mode in ('cont','fade'):
                ls, ss = (bu, be) if mode=='cont' else (be, bu)
                for side, sig, wrb in (('long', ls, wrbL), ('short', ss, wrbS)):
                    if side=='long':
                        tr = se.simulate_trades(df,sig,zeros,sl_pip=sl,tp_pip=tp,asset='XAUUSD',max_hold=MAX_HOLD)
                    else:
                        tr = se.simulate_trades(df,zeros,sig,sl_pip=sl,tp_pip=tp,asset='XAUUSD',max_hold=MAX_HOLD)
                    n,wr,ep = stats(tr); lift = wr-wrb
                    cells.append({'rr':rr,'variant':variant,'mode':mode,'side':side,'n':n,
                                  'wr':round(wr,2),'blind':round(wrb,2),'lift':round(lift,2),
                                  'exp_pip':round(ep,2),'lsn':round(lift*np.sqrt(max(n,0)),1)})
    res = {'tf':tf,'src':d.get('src'),'bars_first_half':int(half),'sl_pip':sl,
           'cost_to_sl_pct':round(100*3.3/sl,1),'n_up':int(up.sum()),'n_dn':int(dn.sum()),'n_aligned':int((variants[1][1]|variants[1][2]).sum()),'cells':cells,'sec':round(time.time()-t0,1)}
    json.dump(res, open(os.path.join(OUT,f'{tf}.json'),'w'), ensure_ascii=False, indent=1)
    return res

if __name__=='__main__':
    for tf in TFS:
        try:
            r = run_tf(tf)
        except Exception as e:
            print(f'[S647] {tf}: ERROR {e}', flush=True); continue
        best = max(r['cells'], key=lambda c:c['lsn'])
        print(f"[S647] {tf}: sl={r['sl_pip']} cost%={r['cost_to_sl_pct']} "
              f"best=rr{best['rr']}/{best['variant']}/{best['mode']}/{best['side']} lift={best['lift']:+} "
              f"n={best['n']} lsn={best['lsn']} ({r['sec']}s)", flush=True)
    print('[S647] ALL DONE', flush=True)
