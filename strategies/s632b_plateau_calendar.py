# -*- coding: utf-8 -*-
"""
S632b — آزمون فلات سه‌بعدی + پایداری تقویمی — «فقط نیمهٔ نخست»
=================================================================
نامزد: H1 لانگ‌تنها، state mean(IBS,k)<thr، گیت close>SMA144.
① شبکهٔ ریز thr∈{0.25..0.31} × k∈{4,5,6} — قله یا فلات؟
② حساسیت گیت SMA∈{89,144,233} روی سلول مرکزی
③ پایداری تقویمی: WR و pnl سال‌به‌سال برای سلول مرکزی
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'research', 's630_explore')

d = fd.load_fast('XAUUSD','H1')
df = fd.as_dataframe(d)
df = df.iloc[:len(df)//2].reset_index(drop=True)
h,l,c = df['high'].values, df['low'].values, df['close'].values
rng=h-l
ibs = np.where(rng>0,(c-l)/np.where(rng>0,rng,1.0),0.5)
tr_ = np.maximum(h-l, np.maximum(abs(h-np.roll(c,1)), abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
sl = float(np.nanmedian(pd.Series(tr_).rolling(100).mean().values[100:]))*1.5/0.1
cs=pd.Series(c); empty=pd.Series(False,index=df.index)

def run(sig):
    t=se.simulate_trades(df,sig.fillna(False),empty,sl_pip=sl,tp_pip=sl,asset='XAUUSD',max_hold=64,allow_overlap=False)
    t=t[t['direction']=='long']
    if len(t)==0: return None
    return t

def base(up, stride=7):
    b=pd.Series(False,index=df.index); b.iloc[::stride]=True
    t=run(b&up)
    return round(100*float((t['outcome']=='win').mean()),2)

res={'sl_pip':round(sl,1)}
# ① شبکهٔ ریز thr×k با گیت SMA144
up144=(cs>cs.rolling(144).mean()).fillna(False)
bw144=base(up144)
grid={}
for k in [4,5,6]:
    ik=pd.Series(ibs).rolling(k).mean()
    for thr in [0.25,0.26,0.27,0.28,0.29,0.30,0.31]:
        t=run((ik<thr)&up144)
        if t is None: continue
        w=round(100*float((t['outcome']=='win').mean()),2); n=len(t)
        grid[f'k{k}_t{thr}']=dict(n=n,wr=w,lift=round(w-bw144,2),pnl=round(float(t['pnl_pip'].mean()),3))
res['grid']=grid; res['base144']=bw144
print('=== fine grid (base=%.2f) ===' % bw144, flush=True)
for k in [4,5,6]:
    row=' | '.join(f"t{thr}: L{grid[f'k{k}_t{thr}']['lift']:+.1f} n{grid[f'k{k}_t{thr}']['n']}" for thr in [0.25,0.26,0.27,0.28,0.29,0.30,0.31] if f'k{k}_t{thr}' in grid)
    print(f'k={k}: {row}', flush=True)

# ② حساسیت SMA روی سلول مرکزی k5 t0.28
ik5=pd.Series(ibs).rolling(5).mean()
sma_sens={}
for P in [89,144,233]:
    up=(cs>cs.rolling(P).mean()).fillna(False)
    bw=base(up)
    t=run((ik5<0.28)&up)
    w=round(100*float((t['outcome']=='win').mean()),2); n=len(t)
    sma_sens[f'SMA{P}']=dict(n=n,wr=w,base=bw,lift=round(w-bw,2),pnl=round(float(t['pnl_pip'].mean()),3))
    print(f'SMA{P}:', sma_sens[f'SMA{P}'], flush=True)
res['sma_sens']=sma_sens

# ③ پایداری تقویمی سلول مرکزی (SMA144, k5, t0.28)
t=run((ik5<0.28)&up144)
t=t.copy()
t['year']=pd.to_datetime(df['time'].iloc[t['entry_bar'].values].values, unit='s').year
cal={}
for y,g in t.groupby('year'):
    cal[int(y)]=dict(n=len(g), wr=round(100*float((g['outcome']=='win').mean()),2),
                     pnl=round(float(g['pnl_pip'].sum()),1))
res['calendar']=cal
print('=== calendar ===', flush=True)
for y in sorted(cal): print(f'  {y}: {cal[y]}', flush=True)

with open(f'{OUT}/s632b_plateau_calendar.json','w') as f:
    json.dump(res,f,ensure_ascii=False,indent=1)
print('saved -> s632b_plateau_calendar.json')
