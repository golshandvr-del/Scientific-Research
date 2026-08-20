# -*- coding: utf-8 -*-
"""
S634b — شورتِ ساعات لندن — سنجش مستقیم با خط پایهٔ شورت — «فقط نیمهٔ نخست»
=============================================================================
ناهنجاری S634: لانگ ساعت 07/08 UTC z=-3.1/-3.86. آیا شورت مستقیم مهارت دارد؟
① شورت هر ساعت 0..23 در H1 با خط پایهٔ شورتِ سخت‌ترین (stride 3/7/13)
② پروفایل کامل ساعت → فلات ساعتی یا قلهٔ تنها؟
③ تقویم سالانهٔ سلول‌های برتر
هندسه: SL=TP=1.5×medATR100 متقارن. بدون گیت اضافه — کمینهٔ پارامتر (DNA برندگان).
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'research', 's634_explore')

d=fd.load_fast('XAUUSD','H1'); df=fd.as_dataframe(d)
df=df.iloc[:len(df)//2].reset_index(drop=True)
h,l,c=df['high'].values,df['low'].values,df['close'].values
tr_=np.maximum(h-l,np.maximum(abs(h-np.roll(c,1)),abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
sl=float(np.nanmedian(pd.Series(tr_).rolling(100).mean().values[100:]))*1.5/0.1
hours=pd.to_datetime(df['time'].values,unit='s').hour
empty=pd.Series(False,index=df.index)

def wrn(t):
    t=t[t['direction']=='short']
    if len(t)==0: return None,0,None
    return 100*float((t['outcome']=='win').mean()), len(t), float(t['pnl_pip'].mean())

# خط پایهٔ شورت سخت‌ترین
bvals=[]
for stride in (3,7,13):
    b=pd.Series(False,index=df.index); b.iloc[::stride]=True
    t=se.simulate_trades(df,empty,b,sl_pip=sl,tp_pip=sl,asset='XAUUSD',max_hold=64,allow_overlap=False)
    w,_,_=wrn(t)
    if w is not None: bvals.append(w)
bs=max(bvals)
print(f'short base (hardest) = {bs:.2f} | sl={sl:.1f}', flush=True)

prof={}
for hr in range(24):
    sig=pd.Series(hours==hr,index=df.index)
    t=se.simulate_trades(df,empty,sig,sl_pip=sl,tp_pip=sl,asset='XAUUSD',max_hold=64,allow_overlap=False)
    w,n,p=wrn(t)
    if w is None: continue
    lift=w-bs; z=lift/(100*np.sqrt(0.25/n))
    prof[hr]=dict(n=n,wr=round(w,2),lift=round(lift,2),pnl=round(p,3),z=round(z,2))
    print(f'h{hr:02d}: n={n} wr={w:.2f} lift={lift:+.2f} pnl={p:+.3f} z={z:+.2f}', flush=True)

# تقویم سلول‌های |z| بزرگ
cal={}
for hr,v in prof.items():
    if abs(v['z'])>=2.5:
        sig=pd.Series(hours==hr,index=df.index)
        t=se.simulate_trades(df,empty,sig,sl_pip=sl,tp_pip=sl,asset='XAUUSD',max_hold=64,allow_overlap=False)
        t=t[t['direction']=='short'].copy()
        t['year']=pd.to_datetime(df['time'].iloc[t['entry_bar'].values].values,unit='s').year
        byy={int(y):dict(n=len(g),wr=round(100*float((g['outcome']=='win').mean()),1),
                         pnl=round(float(g['pnl_pip'].sum()),0)) for y,g in t.groupby('year')}
        pos=sum(1 for vv in byy.values() if vv['pnl']>0)
        cal[hr]=byy
        print(f'CAL h{hr:02d}: {pos}/{len(byy)} yrs+ | {byy}', flush=True)

with open(f'{OUT}/s634b_london_short.json','w') as f:
    json.dump(dict(sl_pip=round(sl,1),base_short=round(bs,2),profile=prof,calendar=cal),f,ensure_ascii=False,indent=1)
print('saved -> s634b_london_short.json')
