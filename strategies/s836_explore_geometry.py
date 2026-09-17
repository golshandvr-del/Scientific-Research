# -*- coding: utf-8 -*-
"""S836 — کاوشِ ۲: هندسه‌ی سلولِ aligned N=10 k=0.5 G∈{120,180} — RR×hold (۱۲ سلول) — فقط ۶۰٪ اکتشاف"""
import sys, os
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se
K_NULL=80; SEED=836002; R1_END=1356998400; R2_END=1451606400; PIP=se.ASSETS['XAUUSD']['pip']
def pf_of(p):
    w=p[p>0].sum(); lo_=-p[p<0].sum(); return w/lo_ if lo_>0 else np.inf
def info_null(df,sig,slp,tpp,hold,rng):
    wrs=[]
    for _ in range(K_NULL):
        dirs=rng.integers(0,2,size=len(sig)).astype(bool)
        lm=np.zeros(len(df),bool); lm[sig[dirs]]=True; sm=np.zeros(len(df),bool); sm[sig[~dirs]]=True
        t=se.simulate_trades(df,lm,sm,sl_pip=slp,tp_pip=tpp,asset='XAUUSD',max_hold=hold,allow_overlap=False)
        if len(t): wrs.append((t['pnl_pip'].values>0).mean()*100)
    return float(np.mean(wrs)),float(np.std(wrs))
d=fd.load_fast('XAUUSD','H1'); assert 'mt5_full' in d['src']
df=fd.as_dataframe(d); df=df.iloc[:int(len(df)*0.6)].reset_index(drop=True)
t=df['time'].values.astype(np.int64); o=df['open'].values; c=df['close'].values; h=df['high'].values; l=df['low'].values; n=len(df)
day=t//86400; first=np.concatenate([[True],day[1:]!=day[:-1]]); last=np.concatenate([day[1:]!=day[:-1],[True]])
fidx=np.where(first)[0]; lidx=np.where(last)[0]; D=len(fidx)
dclose=c[lidx]; ID=dclose-o[fidx]
sigma=pd.Series(np.array([h[a:b+1].max()-l[a:b+1].min() for a,b in zip(fidx,lidx)])).rolling(20).median().values
ss_=np.full(n,np.nan); ss_[lidx]=sigma
print(f'explore bars={n:,} src={d["src"]}',flush=True)
rng=np.random.default_rng(SEED)
z=pd.Series(ID).rolling(10).sum().values/(sigma*np.sqrt(10)); base=(np.abs(z)>0.5)&np.isfinite(z); base[:260]=False
for G in (120,180):
    drift=np.full(D,np.nan); drift[G:]=dclose[G:]-dclose[:-G]
    gl=base&(z>0)&(drift>0); gs=base&(z<0)&(drift<0)
    ls=np.zeros(n,bool); ssg=np.zeros(n,bool)
    dl=np.where(gl)[0]; ds=np.where(gs)[0]; dl=dl[dl<D-1]; ds=ds[ds<D-1]; ls[lidx[dl]]=True; ssg[lidx[ds]]=True
    for slm in (1.0,1.5):
        slp=np.clip(np.nan_to_num(ss_,nan=1.0)*slm/PIP,8,5000)
        for RR in (1.3,2.0):
            tpp=slp*RR
            for HOLD in (72,120):
                if slm==1.5 and HOLD==120: continue
                tdf=se.simulate_trades(df,ls,ssg,sl_pip=slp,tp_pip=tpp,asset='XAUUSD',max_hold=HOLD,allow_overlap=False)
                pnl=tdf['pnl_pip'].values; eb=tdf['entry_bar'].values; sb=tdf['signal_bar'].values.astype(int)
                wr=(pnl>0).mean()*100; nm,nsd=info_null(df,sb,slp,tpp,HOLD,rng)
                lift=wr-nm; zz=lift/nsd; pw=lift*np.sqrt(len(pnl)); te=t[eb]
                lo=lambda m:(pnl[m]>0).mean()*100-nm if m.sum()>=15 else np.nan
                l1,l2,l3=lo(te<R1_END),lo((te>=R1_END)&(te<R2_END)),lo(te>=R2_END)
                isl=tdf['direction'].values=='long'
                print(f'  G={G} slm={slm} RR={RR} hold={HOLD}: n={len(pnl):4,} WR={wr:5.2f}% null={nm:5.2f}%±{nsd:.2f} INFOlift={lift:+6.2f}pp z={zz:+4.1f} pw={pw:4.0f} PF={pf_of(pnl):.3f} [L={pf_of(pnl[isl]):.2f} S={pf_of(pnl[~isl]):.2f}] exp={pnl.mean():+7.2f} [R1={l1:+5.1f} R2={l2:+5.1f} R3={l3:+5.1f}]',flush=True)
print('\n[S836 explore-2 complete]',flush=True)
