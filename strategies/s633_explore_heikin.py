# -*- coding: utf-8 -*-
"""
S633 — اکتشاف Heikin-Ashi فلیپ/ادامهٔ روند — «فقط نیمهٔ نخست»
================================================================
ایدهٔ بکر (۰ نتیجه در آرشیو ۶۲۶تایی): فلیپ رنگ HA پس از دنبالهٔ مخالف طول ≥m
= سیگنال ازسرگیری روند. DNA برندگان آرشیو: ادامهٔ حرکت هم‌جهت با رانش.
دو خانوادهٔ سیگنال:
  flip: رنگ HA از نزولی→صعودی پس از m کندل نزولی متوالی (لانگ) و بالعکس (شورت)
  run : ادامهٔ دنباله — ورود پس از m کندل هم‌رنگ متوالی (momentum)
هندسه: SL=TP=1.5×medATR100 (متقارن). گیت اختیاری بعداً.
TFها: M30..H12 (درس S630: دقیقه‌ای‌ها را اسپرد می‌بلعد).
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'research', 's633_explore')
os.makedirs(OUT, exist_ok=True)

def wrn(t, side):
    t = t[t['direction']==side]
    if len(t)==0: return None,0,None
    return round(100*float((t['outcome']=='win').mean()),2), len(t), round(float(t['pnl_pip'].mean()),3)

all_res={}
for TF in ['M30','H1','H2','H3','H4','H6','H8','H12']:
    try:
        d = fd.load_fast('XAUUSD', TF)
    except Exception as e:
        print(TF,'load fail',e); continue
    df = fd.as_dataframe(d)
    df = df.iloc[:len(df)//2].reset_index(drop=True)
    o,h,l,c = df['open'].values, df['high'].values, df['low'].values, df['close'].values
    n_b=len(df)
    # Heikin-Ashi
    ha_c = (o+h+l+c)/4.0
    ha_o = np.empty(n_b); ha_o[0]=(o[0]+c[0])/2.0
    for i in range(1,n_b): ha_o[i]=(ha_o[i-1]+ha_c[i-1])/2.0
    bull = ha_c > ha_o
    # ATR/هندسه
    tr_=np.maximum(h-l,np.maximum(abs(h-np.roll(c,1)),abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
    sl=float(np.nanmedian(pd.Series(tr_).rolling(100).mean().values[100:]))*1.5/0.1
    empty=pd.Series(False,index=df.index)

    # خط پایهٔ بی‌قید هر سمت مستقل (سخت‌ترین stride)
    def base(side):
        vals=[]
        for stride in (3,7,13):
            b=pd.Series(False,index=df.index); b.iloc[::stride]=True
            lo_,hi_=(b,empty) if side=='long' else (empty,b)
            t=se.simulate_trades(df,lo_,hi_,sl_pip=sl,tp_pip=sl,asset='XAUUSD',max_hold=64,allow_overlap=False)
            w,_,_=wrn(t,side)
            if w is not None: vals.append(w)
        return max(vals) if vals else None
    bl, bs = base('long'), base('short')

    # دنبالهٔ رنگ
    run = np.zeros(n_b, dtype=int)  # طول دنبالهٔ هم‌رنگ منتهی به i (علامت‌دار)
    run[0] = 1 if bull[0] else -1
    for i in range(1,n_b):
        if bull[i]: run[i] = run[i-1]+1 if run[i-1]>0 else 1
        else:       run[i] = run[i-1]-1 if run[i-1]<0 else -1

    cells={}
    for m in [2,3,5,8]:
        # flip: کندل i صعودی شد پس از دنبالهٔ نزولی ≥m
        lo_flip = pd.Series((run==1) & (np.roll(run,1)<=-m), index=df.index); lo_flip.iloc[0]=False
        hi_flip = pd.Series((run==-1) & (np.roll(run,1)>=m), index=df.index); hi_flip.iloc[0]=False
        # run: دنبالهٔ هم‌رنگ دقیقاً به طول m رسید (momentum)
        lo_run = pd.Series(run==m, index=df.index)
        hi_run = pd.Series(run==-m, index=df.index)
        for fam,(lo,hi) in {'flip':(lo_flip,hi_flip),'run':(lo_run,hi_run)}.items():
            t=se.simulate_trades(df,lo.fillna(False),hi.fillna(False),sl_pip=sl,tp_pip=sl,
                                 asset='XAUUSD',max_hold=64,allow_overlap=False)
            lw,ln,lp=wrn(t,'long'); sw,sn,sp=wrn(t,'short')
            cells[f'{fam}_m{m}']=dict(
                long=dict(n=ln,wr=lw,base=bl,lift=None if(lw is None or bl is None) else round(lw-bl,2),pnl=lp),
                short=dict(n=sn,wr=sw,base=bs,lift=None if(sw is None or bs is None) else round(sw-bs,2),pnl=sp))
    all_res[TF]=dict(sl_pip=round(sl,1),base_long=bl,base_short=bs,cells=cells)
    # چاپ بهترین سلول‌ها بر اساس power لانگ
    def pw(cell):
        L=cell['long']
        return (L['lift'] or -99)*np.sqrt(L['n']) if L['n'] else -999
    top=sorted(cells.items(), key=lambda kv:-pw(kv[1]))[:3]
    print(f'== {TF} sl={sl:.0f} baseL={bl} baseS={bs} ==', flush=True)
    for name,cell in top:
        print(f"  {name}: L{cell['long']} | S{cell['short']}", flush=True)

with open(f'{OUT}/heikin_scan.json','w') as f:
    json.dump(all_res,f,ensure_ascii=False,indent=1)
print('saved -> heikin_scan.json')
