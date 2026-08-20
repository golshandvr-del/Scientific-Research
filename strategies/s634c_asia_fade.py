# -*- coding: utf-8 -*-
"""
S634c — محو رالی آسیا (Asia-fade) در ساعات لندن — «فقط نیمهٔ نخست»
====================================================================
فرضیه: مهارت شورت 07/08 UTC = محوِ حرکت سشن آسیا. شرطی‌سازی بر بازده آسیا
باید لیفت را از ~3.5 به بالای کف H3 (4pp) برساند.
شرط‌ها (بهبودهای چندگانهٔ هم‌زمان):
  asia_up:   بازده 00→07 مثبت (فقط محو رالی)
  asia_up_q: بازده آسیا در چارک بالای مثبت‌ها (رالی قوی)
  نیز پنجرهٔ ساعت {07},{08},{07,08},{06..09} — باند یکنواخت
خط پایه: شورت بی‌قیدِ «همان شرط» (گیت‌خورده) — تفکیک آلفا از بتا.
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
h,l,c,o=df['high'].values,df['low'].values,df['close'].values,df['open'].values
tr_=np.maximum(h-l,np.maximum(abs(h-np.roll(c,1)),abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
sl=float(np.nanmedian(pd.Series(tr_).rolling(100).mean().values[100:]))*1.5/0.1
dtt=pd.to_datetime(df['time'].values,unit='s')
hours=dtt.hour
empty=pd.Series(False,index=df.index)

# بازده آسیا: از close اولین کندل روز (00) تا open کندل جاری — علّی
day_id=(dtt.date)
day_ser=pd.Series(pd.factorize(day_id)[0],index=df.index)
c_ser=pd.Series(c,index=df.index)
open_of_day=c_ser.groupby(day_ser).transform('first')  # close کندل 00 (تقریب سطح شروع روز)
asia_ret=(pd.Series(o,index=df.index)-open_of_day)/open_of_day*10000  # به‌واحد bp

def wrn(t):
    t=t[t['direction']=='short']
    if len(t)==0: return None,0,None
    return 100*float((t['outcome']=='win').mean()), len(t), float(t['pnl_pip'].mean())

def base_gated(gate):
    vals=[]
    for stride in (3,7,13):
        b=pd.Series(False,index=df.index); b.iloc[::stride]=True
        sig=(b&gate).fillna(False)
        t=se.simulate_trades(df,empty,sig,sl_pip=sl,tp_pip=sl,asset='XAUUSD',max_hold=64,allow_overlap=False)
        w,_,_=wrn(t)
        if w is not None: vals.append(w)
    return max(vals) if vals else None

hour_windows={'h07':[7],'h08':[8],'h0708':[7,8],'h0609':[6,7,8,9]}
conds={
  'all':        pd.Series(True,index=df.index),
  'asia_up':    (asia_ret>0).fillna(False),
  'asia_up_med':(asia_ret>asia_ret[asia_ret>0].median()).fillna(False),
}
res={}
q75=asia_ret[asia_ret>0].quantile(0.75)
conds['asia_up_q75']=(asia_ret>q75).fillna(False)

for cname,cond in conds.items():
    bw=base_gated(cond)
    for wname,hrs in hour_windows.items():
        inwin=pd.Series(np.isin(hours,hrs),index=df.index)
        sig=(inwin&cond).fillna(False)
        t=se.simulate_trades(df,empty,sig,sl_pip=sl,tp_pip=sl,asset='XAUUSD',max_hold=64,allow_overlap=False)
        w,n,p=wrn(t)
        if w is None or n<50: continue
        lift=w-bw; z=lift/(100*np.sqrt(0.25/n))
        res[f'{cname}_{wname}']=dict(n=n,wr=round(w,2),base=round(bw,2),lift=round(lift,2),
                                     pnl=round(p,3),z=round(z,2))
        print(f'{cname}_{wname}: n={n} wr={w:.2f} base={bw:.2f} lift={lift:+.2f} pnl={p:+.2f} z={z:+.2f}', flush=True)

with open(f'{OUT}/s634c_asia_fade.json','w') as f:
    json.dump(dict(sl_pip=round(sl,1),cells=res),f,ensure_ascii=False,indent=1)
print('saved -> s634c_asia_fade.json')
