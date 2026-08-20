# -*- coding: utf-8 -*-
"""
S635 — پروفایل کامل پنجره‌های رانش: ساعتِ لانگ + روزِ ماه — «فقط نیمهٔ نخست»
==============================================================================
① پروفایل ۲۴ساعتهٔ لانگ H1 (مکمل نقشهٔ شورت S634b)
② پروفایل روزِ ماه (1..31) لانگ H4 — خانوادهٔ تقویمی، پنجرهٔ متعامد با S312
خط پایهٔ سخت‌ترین، z_fair، بدون گیلاس‌چینی. قاعدهٔ S633: hold-out فقط با z≥3 و lift≥4pp.
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'research', 's635_explore')
os.makedirs(OUT, exist_ok=True)

def prep(TF):
    d=fd.load_fast('XAUUSD',TF); df=fd.as_dataframe(d)
    df=df.iloc[:len(df)//2].reset_index(drop=True)
    h,l,c=df['high'].values,df['low'].values,df['close'].values
    tr_=np.maximum(h-l,np.maximum(abs(h-np.roll(c,1)),abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
    sl=float(np.nanmedian(pd.Series(tr_).rolling(100).mean().values[100:]))*1.5/0.1
    return df,sl

def wrn(t):
    t=t[t['direction']=='long']
    if len(t)==0: return None,0,None
    return 100*float((t['outcome']=='win').mean()), len(t), float(t['pnl_pip'].mean())

def base_long(df,sl):
    vals=[]; empty=pd.Series(False,index=df.index)
    for stride in (3,7,13):
        b=pd.Series(False,index=df.index); b.iloc[::stride]=True
        t=se.simulate_trades(df,b,empty,sl_pip=sl,tp_pip=sl,asset='XAUUSD',max_hold=64,allow_overlap=False)
        w,_,_=wrn(t)
        if w is not None: vals.append(w)
    return max(vals)

res={}
# ① لانگ ۲۴ساعته H1
df,sl=prep('H1')
empty=pd.Series(False,index=df.index)
hours=pd.to_datetime(df['time'].values,unit='s').hour
bl=base_long(df,sl)
prof={}
print(f'=== LONG hourly H1 (base={bl:.2f}) ===', flush=True)
for hr in range(24):
    sig=pd.Series(hours==hr,index=df.index)
    t=se.simulate_trades(df,sig,empty,sl_pip=sl,tp_pip=sl,asset='XAUUSD',max_hold=64,allow_overlap=False)
    w,n,p=wrn(t)
    if w is None: continue
    lift=w-bl; z=lift/(100*np.sqrt(0.25/n))
    prof[hr]=dict(n=n,wr=round(w,2),lift=round(lift,2),pnl=round(p,3),z=round(z,2))
    print(f'h{hr:02d}: n={n} lift={lift:+.2f} pnl={p:+.2f} z={z:+.2f}', flush=True)
res['long_hourly_H1']=dict(base=round(bl,2),profile=prof)

# ② روزِ ماه، لانگ H4 (اولین کندل هر روز)
df,sl=prep('H4')
empty=pd.Series(False,index=df.index)
dtt=pd.to_datetime(df['time'].values,unit='s')
dom=dtt.day; hh=dtt.hour
bl=base_long(df,sl)
prof2={}
print(f'=== LONG day-of-month H4 first candle (base={bl:.2f}) ===', flush=True)
first=pd.Series(hh<4,index=df.index)
for dd in range(1,32):
    sig=(pd.Series(dom==dd,index=df.index)&first).fillna(False)
    t=se.simulate_trades(df,sig,empty,sl_pip=sl,tp_pip=sl,asset='XAUUSD',max_hold=64,allow_overlap=False)
    w,n,p=wrn(t)
    if w is None or n<40: continue
    lift=w-bl; z=lift/(100*np.sqrt(0.25/n))
    prof2[dd]=dict(n=n,wr=round(w,2),lift=round(lift,2),pnl=round(p,3),z=round(z,2))
    print(f'd{dd:02d}: n={n} lift={lift:+.2f} pnl={p:+.2f} z={z:+.2f}', flush=True)
res['long_dom_H4']=dict(base=round(bl,2),profile=prof2)

with open(f'{OUT}/drift_windows.json','w') as f:
    json.dump(res,f,ensure_ascii=False,indent=1)
print('saved -> drift_windows.json')
