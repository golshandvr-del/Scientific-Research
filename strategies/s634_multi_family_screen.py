# -*- coding: utf-8 -*-
"""
S634 — غربال منصفانهٔ چند خانوادهٔ متعامد — «فقط نیمهٔ نخست»
==============================================================
قاعدهٔ S633: تا z منصفانهٔ درون‌نمونه ≥3 نشود، hold-out سوزانده نمی‌شود.
خانواده‌ها (همه بکر یا کم‌کاوش در آرشیو):
  F1) PSAR flip (0 نتیجه در آرشیو): فلیپ پارابولیک SAR به‌عنوان سیگنال ادامه
  F2) ساعتِ روز (time-of-day drift): ورود لانگ در ساعت شروع لندن/NY (رانش سکولار+نقدینگی)
  F3) روز هفته: لانگ در روزهای خاص (اثر تقویمی — DNA برندهٔ S312/S432)
  F4) دنبالهٔ کندل واقعی (نه HA): n کندل هم‌جهت متوالی + کندل بزرگ (follow-through)
هر خانواده: پارامترهای اندک و یکنواخت، خط پایهٔ سخت‌ترین stride، بدون گیلاس‌چینی.
سنجهٔ گزارش: z_fair = lift/sd_perm_approx با sd=100*sqrt(0.25/n).
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'research', 's634_explore')
os.makedirs(OUT, exist_ok=True)

def prep(TF):
    d=fd.load_fast('XAUUSD',TF); df=fd.as_dataframe(d)
    df=df.iloc[:len(df)//2].reset_index(drop=True)
    h,l,c=df['high'].values,df['low'].values,df['close'].values
    tr_=np.maximum(h-l,np.maximum(abs(h-np.roll(c,1)),abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
    sl=float(np.nanmedian(pd.Series(tr_).rolling(100).mean().values[100:]))*1.5/0.1
    return df,sl

def wrn(t,side):
    t=t[t['direction']==side]
    if len(t)==0: return None,0,None
    return 100*float((t['outcome']=='win').mean()), len(t), float(t['pnl_pip'].mean())

def base(df,sl,side='long'):
    vals=[]; empty=pd.Series(False,index=df.index)
    for stride in (3,7,13):
        b=pd.Series(False,index=df.index); b.iloc[::stride]=True
        lo_,hi_=(b,empty) if side=='long' else (empty,b)
        t=se.simulate_trades(df,lo_,hi_,sl_pip=sl,tp_pip=sl,asset='XAUUSD',max_hold=64,allow_overlap=False)
        w,_,_=wrn(t,side)
        if w is not None: vals.append(w)
    return max(vals) if vals else None

def score(df,sl,sig,side,bw,label,res_list):
    empty=pd.Series(False,index=df.index)
    lo_,hi_=(sig,empty) if side=='long' else (empty,sig)
    t=se.simulate_trades(df,lo_.fillna(False),hi_.fillna(False),sl_pip=sl,tp_pip=sl,
                         asset='XAUUSD',max_hold=64,allow_overlap=False)
    w,n,p=wrn(t,side)
    if w is None or n<30: return
    lift=w-bw; z=lift/(100*np.sqrt(0.25/n))
    res_list.append(dict(label=label,side=side,n=n,wr=round(w,2),lift=round(lift,2),
                         pnl=round(p,3),z_fair=round(z,2)))

def psar(h,l,af0=0.02,afmax=0.2):
    n=len(h); ps=np.zeros(n); bull=True; af=af0; ep=h[0]; ps[0]=l[0]
    for i in range(1,n):
        ps[i]=ps[i-1]+af*(ep-ps[i-1])
        if bull:
            if l[i]<ps[i]: bull=False; ps[i]=ep; ep=l[i]; af=af0
            else:
                if h[i]>ep: ep=h[i]; af=min(afmax,af+af0)
                ps[i]=min(ps[i],l[i-1],l[i-2] if i>1 else l[i-1])
        else:
            if h[i]>ps[i]: bull=True; ps[i]=ep; ep=h[i]; af=af0
            else:
                if l[i]<ep: ep=l[i]; af=min(afmax,af+af0)
                ps[i]=max(ps[i],h[i-1],h[i-2] if i>1 else h[i-1])
    return ps

results=[]
# ---------- F1: PSAR flip (H4/H6/H8) ----------
for TF in ['H4','H6','H8']:
    df,sl=prep(TF)
    h,l,c=df['high'].values,df['low'].values,df['close'].values
    ps=psar(h,l)
    bull=c>ps
    flip_up=pd.Series(bull & ~np.roll(bull,1),index=df.index); flip_up.iloc[0]=False
    flip_dn=pd.Series(~bull & np.roll(bull,1),index=df.index); flip_dn.iloc[0]=False
    bl=base(df,sl,'long'); bs=base(df,sl,'short')
    score(df,sl,flip_up,'long',bl,f'F1_psar_{TF}',results)
    score(df,sl,flip_dn,'short',bs,f'F1_psar_{TF}',results)

# ---------- F2: ساعت روز (H1) — لانگ در آغاز کندل‌های ساعت خاص ----------
df,sl=prep('H1')
hours=pd.to_datetime(df['time'].values,unit='s').hour
bl=base(df,sl,'long')
for hr in [1,7,8,12,13,14,15,16]:
    sig=pd.Series(hours==hr,index=df.index)
    score(df,sl,sig,'long',bl,f'F2_hour{hr:02d}_H1',results)

# ---------- F3: روز هفته (H4) — لانگ در روز خاص ----------
df,sl=prep('H4')
dow=pd.to_datetime(df['time'].values,unit='s').dayofweek
hours4=pd.to_datetime(df['time'].values,unit='s').hour
bl=base(df,sl,'long')
for dwi,dname in [(0,'Mon'),(1,'Tue'),(2,'Wed'),(3,'Thu'),(4,'Fri')]:
    sig=pd.Series((dow==dwi)&(hours4<4),index=df.index)  # اولین کندل روز
    score(df,sl,sig,'long',bl,f'F3_{dname}_H4',results)

# ---------- F4: دنبالهٔ کندل واقعی + کندل بزرگ (H2/H4) ----------
for TF in ['H2','H4']:
    df,sl=prep(TF)
    o,h,l,c=df['open'].values,df['high'].values,df['low'].values,df['close'].values
    up_c=c>o
    runl=np.zeros(len(df),dtype=int); runl[0]=1 if up_c[0] else -1
    for i in range(1,len(df)):
        runl[i]=(runl[i-1]+1 if runl[i-1]>0 else 1) if up_c[i] else (runl[i-1]-1 if runl[i-1]<0 else -1)
    rng=h-l
    big=pd.Series(rng>pd.Series(rng).rolling(50).mean().values*1.5,index=df.index)
    bl=base(df,sl,'long'); bs=base(df,sl,'short')
    for m in [3,4,5]:
        score(df,sl,pd.Series(runl==m,index=df.index)&big,'long',bl,f'F4_run{m}big_{TF}',results)
        score(df,sl,pd.Series(runl==-m,index=df.index)&big,'short',bs,f'F4_run{m}big_{TF}',results)

results.sort(key=lambda r:-r['z_fair'])
for r in results: print(r, flush=True)
with open(f'{OUT}/multi_family_screen.json','w') as f:
    json.dump(results,f,ensure_ascii=False,indent=1)
print('saved -> multi_family_screen.json')
