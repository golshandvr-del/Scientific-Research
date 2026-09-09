# -*- coding: utf-8 -*-
"""
S835 — کاوشِ ۲: افق/هندسه‌ی ماندگاریِ بازدهِ درون‌روزیِ N روزه (ID-momentum) — فقط ۶۰٪ اکتشاف
ON در طلا ساختاراً مرده (کاوش ۱) ⇒ لایه به ID-momentum تقلیل یافت. شبکه‌ی کوچک: N×hold×RR = 12 سلول.
"""
import sys, os
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se
K_NULL=80; SEED=835002; R1_END=1356998400; R2_END=1451606400; PIP=se.ASSETS['XAUUSD']['pip']
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
ID=c[lidx]-o[fidx]
sigma=pd.Series(np.array([h[a:b+1].max()-l[a:b+1].min() for a,b in zip(fidx,lidx)])).rolling(20).median().values
ss_=np.full(n,np.nan); ss_[lidx]=sigma; slp=np.clip(np.nan_to_num(ss_,nan=1.0)/PIP,8,5000)
print(f'explore bars={n:,} src={d["src"]}',flush=True)
rng=np.random.default_rng(SEED)
for N in (8,10,13):
    zid=pd.Series(ID).rolling(N).sum().values/(sigma*np.sqrt(N))
    ev=(np.abs(zid)>0.5)&np.isfinite(zid); ev[:60]=False
    ls=np.zeros(n,bool); ssg=np.zeros(n,bool)
    dl=np.where(ev&(zid>0))[0]; ds=np.where(ev&(zid<0))[0]; dl=dl[dl<D-1]; ds=ds[ds<D-1]
    ls[lidx[dl]]=True; ssg[lidx[ds]]=True
    for RR in (1.3,2.0):
        tpp=slp*RR
        for HOLD in (72,120):
            tdf=se.simulate_trades(df,ls,ssg,sl_pip=slp,tp_pip=tpp,asset='XAUUSD',max_hold=HOLD,allow_overlap=False)
            pnl=tdf['pnl_pip'].values; eb=tdf['entry_bar'].values; sb=tdf['signal_bar'].values.astype(int)
            wr=(pnl>0).mean()*100; nm,nsd=info_null(df,sb,slp,tpp,HOLD,rng)
            lift=wr-nm; z=lift/nsd; pw=lift*np.sqrt(len(pnl)); te=t[eb]
            lo=lambda m:(pnl[m]>0).mean()*100-nm if m.sum()>=15 else np.nan
            l1,l2,l3=lo(te<R1_END),lo((te>=R1_END)&(te<R2_END)),lo(te>=R2_END)
            isl=tdf['direction'].values=='long'
            print(f'  N={N:2d} RR={RR} hold={HOLD}: n={len(pnl):4,} WR={wr:5.2f}% null={nm:5.2f}%±{nsd:.2f} INFOlift={lift:+6.2f}pp z={z:+4.1f} pw={pw:4.0f} PF={pf_of(pnl):.3f} [L={pf_of(pnl[isl]):.2f} S={pf_of(pnl[~isl]):.2f}] exp={pnl.mean():+7.2f} [R1={l1:+5.1f} R2={l2:+5.1f} R3={l3:+5.1f}]',flush=True)
print('\n[S835 explore-2 complete]',flush=True)
