# -*- coding: utf-8 -*-
"""
S633b — پالایش خانوادهٔ run (ادامهٔ دنبالهٔ HA) — «فقط نیمهٔ نخست»
====================================================================
① همسایه‌های m∈{3,4,5,6,7,8} روی H4/H6/H8/H12 — فلات یا قله؟
② پایداری تقویمی سلول‌های نامزد
③ برآورد استخر چندکارتی (pooled n و لیفت وزنی)
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'research', 's633_explore')

def wrn(t, side):
    t=t[t['direction']==side]
    if len(t)==0: return None,0,None
    return round(100*float((t['outcome']=='win').mean()),2), len(t), round(float(t['pnl_pip'].mean()),3)

res={}
trades_store={}
for TF in ['H4','H6','H8','H12']:
    d=fd.load_fast('XAUUSD',TF)
    df=fd.as_dataframe(d)
    df=df.iloc[:len(df)//2].reset_index(drop=True)
    o,h,l,c=df['open'].values,df['high'].values,df['low'].values,df['close'].values
    nb=len(df)
    ha_c=(o+h+l+c)/4.0
    ha_o=np.empty(nb); ha_o[0]=(o[0]+c[0])/2.0
    for i in range(1,nb): ha_o[i]=(ha_o[i-1]+ha_c[i-1])/2.0
    bull=ha_c>ha_o
    run=np.zeros(nb,dtype=int); run[0]=1 if bull[0] else -1
    for i in range(1,nb):
        run[i]=(run[i-1]+1 if run[i-1]>0 else 1) if bull[i] else (run[i-1]-1 if run[i-1]<0 else -1)
    tr_=np.maximum(h-l,np.maximum(abs(h-np.roll(c,1)),abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
    sl=float(np.nanmedian(pd.Series(tr_).rolling(100).mean().values[100:]))*1.5/0.1
    empty=pd.Series(False,index=df.index)
    def base(side):
        vals=[]
        for stride in (3,7,13):
            b=pd.Series(False,index=df.index); b.iloc[::stride]=True
            lo_,hi_=(b,empty) if side=='long' else (empty,b)
            t=se.simulate_trades(df,lo_,hi_,sl_pip=sl,tp_pip=sl,asset='XAUUSD',max_hold=64,allow_overlap=False)
            w,_,_=wrn(t,side)
            if w is not None: vals.append(w)
        return max(vals) if vals else None
    bl,bs=base('long'),base('short')
    cells={}
    for m in [3,4,5,6,7,8]:
        lo=pd.Series(run==m,index=df.index); hi=pd.Series(run==-m,index=df.index)
        t=se.simulate_trades(df,lo,hi,sl_pip=sl,tp_pip=sl,asset='XAUUSD',max_hold=64,allow_overlap=False)
        lw,ln,lp=wrn(t,'long'); sw,sn,sp=wrn(t,'short')
        cells[f'm{m}']=dict(long=dict(n=ln,wr=lw,lift=None if lw is None else round(lw-bl,2),pnl=lp),
                            short=dict(n=sn,wr=sw,lift=None if sw is None else round(sw-bs,2),pnl=sp))
        # ذخیرهٔ معاملات برای تقویم
        t=t.copy(); t['year']=pd.to_datetime(df['time'].iloc[t['entry_bar'].values].values,unit='s').year
        trades_store[(TF,m)]=t
    res[TF]=dict(sl_pip=round(sl,1),base_long=bl,base_short=bs,cells=cells)
    print(f'== {TF} baseL={bl} baseS={bs} ==', flush=True)
    for m in [3,4,5,6,7,8]:
        cc=cells[f'm{m}']
        print(f"  m{m}: L n{cc['long']['n']} lift{cc['long']['lift']} pnl{cc['long']['pnl']} | S n{cc['short']['n']} lift{cc['short']['lift']} pnl{cc['short']['pnl']}", flush=True)

# تقویم برای سلول‌های نامزد
cand=[('H4',8),('H6',5),('H8',5),('H12',5),('H6',6),('H4',7)]
cal={}
print('=== calendar (pnl_pip sum per year, all trades both sides) ===', flush=True)
for key in cand:
    t=trades_store[key]
    byy={int(y):dict(n=len(g),wr=round(100*float((g['outcome']=='win').mean()),1),pnl=round(float(g['pnl_pip'].sum()),0)) for y,g in t.groupby('year')}
    cal[f'{key[0]}_m{key[1]}']=byy
    pos=sum(1 for v in byy.values() if v['pnl']>0)
    print(f'  {key}: {pos}/{len(byy)} yrs pnl+ | {byy}', flush=True)

with open(f'{OUT}/s633b_refine.json','w') as f:
    json.dump(dict(grid=res,calendar=cal),f,ensure_ascii=False,indent=1)
print('saved -> s633b_refine.json')
