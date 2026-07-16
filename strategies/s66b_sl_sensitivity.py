"""S66b — تستِ حساسیت/overfitting برای اهرمِ SL تطبیقی.
گریدهای مختلفِ SL را امتحان می‌کنیم؛ اگر بیشترِ آن‌ها S65 (6082$) را بزنند،
بهبود ساختاری است نه overfit به یک گریدِ خاص."""
import sys, os
sys.path.insert(0, 'engine')
import numpy as np, pandas as pd
from backtest import load_data, run_backtest
import warnings; warnings.filterwarnings('ignore')

HZ=48; SPREAD=0.20; ER_TREND_THR=0.30; P_HI=0.66; P_MIN=0.58
STEP=6000; LOOKBACK=24000; EXP_MIN=0.10; MIN_N=15
W_MIN,W_MAX,W_BASE,W_SLOPE=0.5,2.0,1.0,1.2
TP_L=[0.8,1.0,1.3,1.6,2.0]; TP_S=[1.0,1.4,1.8,2.2,2.6]
SL_BASE_L=1.5; SL_BASE_S=1.7; BASE_S65=6082.0

z=np.load('results/_s61_cache.npz',allow_pickle=True)
pL,pS=z['pL'],z['pS']; up_reg,down_reg=z['up_reg'],z['down_reg']; er=z['er']; atrv=z['atrv']
df=load_data('data/XAUUSD_M15.csv'); n=len(df)
trendy=np.nan_to_num(er>=ER_TREND_THR,nan=False).astype(bool)
baseL=up_reg&~np.isnan(atrv)&(pL>=P_MIN); baseS=down_reg&~np.isnan(atrv)&(pS>=P_MIN)
def labs(d,b):
    p=pL if d=='long' else pS; ef=np.where(trendy,'trend','chop'); pw=np.where(p>=P_HI,'hi','lo')
    l=np.array([f'{a}_{c}' for a,c in zip(ef,pw)],dtype=object); l[~b]=''; return l
labL=labs('long',baseL); labS=labs('short',baseS); BUCKETS=['trend_hi','trend_lo','chop_hi','chop_lo']
def bt(d,bk,lo,hi,slm,tpm,bl):
    m=np.zeros(n,dtype=bool); seg=(bl==bk); m[lo:hi]=seg[lo:hi]
    if m.sum()<1: return None,0,0.0
    st,_=run_backtest(df,m,None,None,d,spread=SPREAD,max_hold=HZ,sl_series=slm*atrv,tp_series=tpm*atrv)
    return st['expectancy'],st['n_trades'],st['total_pnl']
def kw(e): return float(np.clip(W_BASE+W_SLOPE*(e-EXP_MIN),W_MIN,W_MAX))
em=np.zeros(n,dtype=bool); em[LOOKBACK:]=True
def build(d,bl,slc,tpc,base_sl):
    ent=np.zeros(n,dtype=bool); wt=np.ones(n); tpa=np.zeros(n); sla=np.zeros(n)
    base_tp=tpc[1]
    for start in range(LOOKBACK,n,STEP):
        end=min(start+STEP,n); lo=max(0,start-LOOKBACK); ch=[]
        for bk in BUCKETS:
            e0,nt0,_=bt(d,bk,lo,start,base_sl,base_tp,bl)
            if e0 is None or nt0<MIN_N or e0<EXP_MIN: continue
            bsl,btp,bp,be=base_sl,base_tp,-1e9,e0
            for s in slc:
                for t in tpc:
                    e,nt,pnl=bt(d,bk,lo,start,s,t,bl)
                    if e is not None and nt>=MIN_N and pnl>bp: bp,bsl,btp,be=pnl,s,t,e
            ch.append((bk,bsl,btp,kw(be)))
        for bk,s,t,w in ch:
            seg=(bl==bk); sel=np.zeros(n,dtype=bool); sel[start:end]=seg[start:end]
            ent|=sel; wt[sel]=w; tpa[sel]=t; sla[sel]=s
    return ent,wt,tpa,sla
def ev(d,ent,wt,tpa,sla,base_sl):
    s=ent&em; sl=np.where(sla>0,sla*atrv,base_sl*atrv); tp=np.where(tpa>0,tpa*atrv,atrv)
    st,tr=run_backtest(df,s,None,None,d,spread=SPREAD,max_hold=HZ,sl_series=sl,tp_series=tp)
    if len(tr)==0: return 0.0
    w=wt[tr['signal_bar'].values]; w[w==0]=1.0
    return (tr['pnl'].values*w).sum()

# چند گریدِ مختلفِ SL (offset حولِ پایه)
GRIDS=[
 ('A ±0.25 baseline', [1.0,1.25,1.5,1.75,2.0],   [1.2,1.45,1.7,1.95,2.2]),
 ('B tighter',        [0.8,1.1,1.4,1.7,2.0],      [1.0,1.3,1.6,1.9,2.2]),
 ('C wider',          [1.2,1.5,1.8,2.1,2.5],      [1.4,1.7,2.0,2.3,2.7]),
 ('D coarse 3pt',     [1.0,1.5,2.0],              [1.2,1.7,2.2]),
 ('E fine 7pt',       [1.0,1.2,1.4,1.6,1.8,2.0,2.2], [1.2,1.4,1.6,1.8,2.0,2.2,2.4]),
]
print(f"S65 baseline = {BASE_S65:.0f}$\n")
beat=0
for name,slL,slS in GRIDS:
    eL,wL,tpL,slaL=build('long',labL,slL,TP_L,SL_BASE_L)
    eS,wS,tpS,slaS=build('short',labS,slS,TP_S,SL_BASE_S)
    tot=ev('long',eL,wL,tpL,slaL,SL_BASE_L)+ev('short',eS,wS,tpS,slaS,SL_BASE_S)
    d=tot-BASE_S65; ok='✅' if tot>BASE_S65 else '❌'
    if tot>BASE_S65: beat+=1
    print(f"{name:20s} سودِخالص={tot:8.1f}$  Δ={d:+7.1f}$ ({d/BASE_S65*100:+.1f}%) {ok}")
print(f"\n{beat}/{len(GRIDS)} گرید S65 را زدند.")
