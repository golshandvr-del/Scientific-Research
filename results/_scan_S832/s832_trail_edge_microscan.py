import sys, os
sys.path.insert(0, '/home/user/webapp')
import numpy as np
from tools import s434_fast_data as fd
from engine import scalp_engine as se
SPLIT_IDX=54798; WARMUP=600; HALF=SPLIT_IDX//2
d=fd.load_fast('XAUUSD','H1'); df=fd.as_dataframe(d).iloc[:SPLIT_IDX].reset_index(drop=True)
t=df['time'].values.astype(np.int64); c=df['close'].values; h=df['high'].values; l=df['low'].values
hour=(t//3600)%24; day=t//86400
prev_c=np.concatenate([[c[0]],c[:-1]])
tr=np.maximum(h-l,np.maximum(np.abs(h-prev_c),np.abs(l-prev_c)))
atr=np.empty_like(tr); atr[0]=tr[0]; a=1/34
for i in range(1,len(tr)): atr[i]=atr[i-1]+a*(tr[i]-atr[i-1])
atr_pip=atr/se.ASSETS['XAUUSD']['pip']; n=len(df)
e=np.empty_like(c); e[0]=c[0]; kk=2/301
for i in range(1,n): e[i]=e[i-1]+kk*(c[i]-e[i-1])
above=c>e
rhi=np.full(n,np.nan); rlo=np.full(n,np.nan)
for dd in np.unique(day):
    m=(day==dd)&(hour<=6)
    if m.sum()<5: continue
    md=(day==dd)&(hour>=7); rhi[md]=h[m].max(); rlo[md]=l[m].min()
in_win=(hour>=7)&(hour<=16)
bu=in_win&np.isfinite(rhi)&(c>rhi); bd=in_win&np.isfinite(rlo)&(c<rlo)
first=np.zeros(n,bool); seen=set()
for i in range(n):
    if (bu[i] or bd[i]) and day[i] not in seen: first[i]=True; seen.add(day[i])
ls=first&bu&above; ss=first&bd&~bu&~above
ls[:WARMUP]=False; ss[:WARMUP]=False
MED=float(np.median(atr_pip[WARMUP:]))
slp=np.clip(atr_pip*2.1,8,5000); tpp=slp*6.0
def pf_of(p):
    w=p[p>0].sum(); lo_=-p[p<0].sum(); return w/lo_ if lo_>0 else np.inf
for tf_ in (0.2,0.3,0.4,0.5,0.6):
    tdf=se.simulate_trades(df,ls,ss,sl_pip=slp,tp_pip=tpp,asset='XAUUSD',max_hold=55,allow_overlap=False,trail_pip=float(MED*tf_))
    p=tdf['pnl_pip'].values; eb=tdf['entry_bar'].values
    wr=(p>0).mean()*100
    print(f'trail={tf_}: n={len(tdf):5,} WR={wr:5.2f}% exp={p.mean():+6.2f}pip PF={pf_of(p):.3f} [E1={pf_of(p[eb<HALF]):.3f} E2={pf_of(p[eb>=HALF]):.3f}]',flush=True)
