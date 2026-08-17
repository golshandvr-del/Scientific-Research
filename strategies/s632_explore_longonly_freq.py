# -*- coding: utf-8 -*-
"""
S632 — اکتشاف لانگ‌تنهای پرتناوب — «فقط نیمهٔ نخست» (قانون بهبود)
===================================================================
قضیهٔ S630/S631: مهارت لانگِ IBS در روند صعودی طلا دو بار منتقل شد (+1.4 → +6.25pp)
اما توان آماری ناکافی است (n=124 → z=1.4 < 3.09). نیاز: n≈600+ با لیفت ≥5pp.
راه‌ها (بهبودهای چندگانهٔ هم‌زمان):
  ① آستانهٔ بازتر / k کوچک‌تر → سیگنال بیشتر در H1
  ② ادغام چند-TF (M30+H1+H2) — الگوی multicard آرشیو
  ③ سیگنال سطحی به‌جای عبوری (state-based با فاصلهٔ حداقلی) → تناوب بالاتر
همه لانگ‌تنها، همه پشت گیت close>SMA144، همه SL=TP (قانون بودجه).
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'research', 's630_explore')

def wrn(t):
    t = t[t['direction']=='long']
    if len(t)==0: return None,0,None
    return round(100*float((t['outcome']=='win').mean()),2), len(t), round(float(t['pnl_pip'].mean()),3)

def prep(TF):
    d = fd.load_fast('XAUUSD', TF)
    df = fd.as_dataframe(d)
    df = df.iloc[:len(df)//2].reset_index(drop=True)   # فقط نیمهٔ اول
    h,l,c = df['high'].values, df['low'].values, df['close'].values
    rng = h-l
    ibs = np.where(rng>0,(c-l)/np.where(rng>0,rng,1.0),0.5)
    tr_ = np.maximum(h-l, np.maximum(abs(h-np.roll(c,1)), abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
    atr = pd.Series(tr_).rolling(100).mean().values
    sl = float(np.nanmedian(atr))*1.5/0.1
    up = (pd.Series(c) > pd.Series(c).rolling(144).mean()).fillna(False)
    return df, ibs, sl, up

def base_long(df, up, sl, stride=7):
    b = pd.Series(False, index=df.index); b.iloc[::stride]=True
    sig=(b&up).fillna(False); empty=pd.Series(False,index=df.index)
    t=se.simulate_trades(df,sig,empty,sl_pip=sl,tp_pip=sl,asset='XAUUSD',max_hold=64,allow_overlap=False)
    w,n,_=wrn(t); return w

res={}
for TF in ['M30','H1','H2']:
    df, ibs, sl, up = prep(TF)
    empty=pd.Series(False,index=df.index)
    bw = base_long(df, up, sl)
    res[TF]={'base_long':bw,'sl_pip':round(sl,1),'cells':{}}
    for k in [2,3,5]:
        ibs_k = pd.Series(ibs).rolling(k).mean()
        for thr in [0.20,0.235,0.28,0.32]:
            # ① عبوری (crossing)
            cross=((ibs_k.shift(1)>=thr)&(ibs_k<thr)&up).fillna(False)
            t=se.simulate_trades(df,cross,empty,sl_pip=sl,tp_pip=sl,asset='XAUUSD',max_hold=64,allow_overlap=False)
            w,n,p=wrn(t)
            lift=None if (w is None or bw is None) else round(w-bw,2)
            pw = None if (lift is None or n==0) else round(lift*np.sqrt(n),1)
            res[TF]['cells'][f'cross_k{k}_t{thr}']=dict(n=n,wr=w,lift=lift,pnl=p,power=pw)
            # ③ سطحی (state) — allow_overlap=False خودش فاصله می‌سازد
            state=((ibs_k<thr)&up).fillna(False)
            t=se.simulate_trades(df,state,empty,sl_pip=sl,tp_pip=sl,asset='XAUUSD',max_hold=64,allow_overlap=False)
            w,n,p=wrn(t)
            lift=None if (w is None or bw is None) else round(w-bw,2)
            pw = None if (lift is None or n==0) else round(lift*np.sqrt(n),1)
            res[TF]['cells'][f'state_k{k}_t{thr}']=dict(n=n,wr=w,lift=lift,pnl=p,power=pw)
    # چاپ برترین‌ها
    top=sorted(res[TF]['cells'].items(), key=lambda kv:-(kv[1]['power'] or -999))[:5]
    print(f"== {TF} base={bw} sl={sl:.0f} ==", flush=True)
    for name,c in top: print('  ',name,c, flush=True)

with open(f'{OUT}/s632_longonly_freq.json','w') as f:
    json.dump(res,f,ensure_ascii=False,indent=1)
print('saved -> s632_longonly_freq.json')
