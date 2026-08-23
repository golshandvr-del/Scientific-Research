# -*- coding: utf-8 -*-
"""
S636 — ترکیب متعامد: IBS-لانگ × پنجرهٔ ساعتی — «فقط نیمهٔ نخست»
==================================================================
دو اثر مستقلِ اندازه‌گیری‌شده:
  الف) لانگ-MR (IBS state <0.28, k5, گیت SMA144): ~+2..3pp پایدار در ۳ hold-out
  ب) رانش ساعتی: لانگ عصر (15..23) مثبت، لانگ صبح (03..09) سمی
فرضیه: حذف ساعات سمی از سیگنال IBS باید لیفت را جمع‌پذیر بالا ببرد.
خط پایه: بی‌قیدِ همان گیتِ مرکب (ساعت×SMA) — تفکیک کامل آلفا از بتا.
پنجره‌ها: باندهای یکنواخت، بدون گیلاس‌چینی تک‌ساعته.
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'research', 's636_explore')
os.makedirs(OUT, exist_ok=True)

d=fd.load_fast('XAUUSD','H1'); df=fd.as_dataframe(d)
df=df.iloc[:len(df)//2].reset_index(drop=True)
h,l,c=df['high'].values,df['low'].values,df['close'].values
rng=h-l
ibs=np.where(rng>0,(c-l)/np.where(rng>0,rng,1.0),0.5)
ibs5=pd.Series(ibs).rolling(5).mean()
tr_=np.maximum(h-l,np.maximum(abs(h-np.roll(c,1)),abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
sl=float(np.nanmedian(pd.Series(tr_).rolling(100).mean().values[100:]))*1.5/0.1
cs=pd.Series(c)
up=(cs>cs.rolling(144).mean()).fillna(False)
hours=pd.to_datetime(df['time'].values,unit='s').hour
empty=pd.Series(False,index=df.index)
ibs_low=(ibs5<0.28).fillna(False)

def wrn(t):
    t=t[t['direction']=='long']
    if len(t)==0: return None,0,None
    return 100*float((t['outcome']=='win').mean()), len(t), float(t['pnl_pip'].mean())

def base_gated(gate):
    vals=[]
    for stride in (3,7,13):
        b=pd.Series(False,index=df.index); b.iloc[::stride]=True
        sig=(b&gate).fillna(False)
        t=se.simulate_trades(df,sig,empty,sl_pip=sl,tp_pip=sl,asset='XAUUSD',max_hold=64,allow_overlap=False)
        w,_,_=wrn(t)
        if w is not None: vals.append(w)
    return max(vals) if vals else None

windows={
  'all24':      list(range(24)),
  'no_morning': [x for x in range(24) if x not in (3,4,5,6,7,8,9)],
  'afternoon+': list(range(12,24)),
  'evening':    list(range(15,24)),
  'late_eve':   list(range(18,24)),
}
res={}
for wname,hrs in windows.items():
    inwin=pd.Series(np.isin(hours,hrs),index=df.index)
    gate=(up&inwin).fillna(False)
    bw=base_gated(gate)
    sig=(ibs_low&gate).fillna(False)
    t=se.simulate_trades(df,sig,empty,sl_pip=sl,tp_pip=sl,asset='XAUUSD',max_hold=64,allow_overlap=False)
    w,n,p=wrn(t)
    if w is None: continue
    lift=w-bw; z=lift/(100*np.sqrt(0.25/n))
    res[wname]=dict(n=n,wr=round(w,2),base=round(bw,2),lift=round(lift,2),pnl=round(p,3),
                    z=round(z,2),power=round(lift*np.sqrt(n),1))
    print(f'{wname}: n={n} wr={w:.2f} base={bw:.2f} lift={lift:+.2f} pnl={p:+.2f} z={z:+.2f}', flush=True)

# نیز بدون گیت SMA (فقط ساعت) — آیا SMA لازم است؟
print('--- without SMA gate ---', flush=True)
for wname,hrs in windows.items():
    inwin=pd.Series(np.isin(hours,hrs),index=df.index)
    bw=base_gated(inwin)
    sig=(ibs_low&inwin).fillna(False)
    t=se.simulate_trades(df,sig,empty,sl_pip=sl,tp_pip=sl,asset='XAUUSD',max_hold=64,allow_overlap=False)
    w,n,p=wrn(t)
    if w is None: continue
    lift=w-bw; z=lift/(100*np.sqrt(0.25/n))
    res[f'noSMA_{wname}']=dict(n=n,wr=round(w,2),base=round(bw,2),lift=round(lift,2),pnl=round(p,3),
                               z=round(z,2),power=round(lift*np.sqrt(n),1))
    print(f'noSMA_{wname}: n={n} wr={w:.2f} base={bw:.2f} lift={lift:+.2f} pnl={p:+.2f} z={z:+.2f}', flush=True)

with open(f'{OUT}/ibs_hour_combo.json','w') as f:
    json.dump(dict(sl_pip=round(sl,1),cells=res),f,ensure_ascii=False,indent=1)
print('saved -> ibs_hour_combo.json')
