# -*- coding: utf-8 -*-
"""
S992b — پالایش لبهٔ ER (فقط نیمهٔ نخست): باند یکنواخت + تقویم + هندسه
- H8 short و H1 long: شبکهٔ همسایه با یک باند یکنواخت (lo0.3/hi0.75/k3) روی W{8,13,21}
- پایداری تقویمی: لیفت سالانه (سال‌های مثبت / کل)
- هندسهٔ RR: SL=1.5ATR، TP∈{1.0,1.5}×SL
"""
import sys, os, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'research', 's992_explore')

def wr(t): return 100*float((t['outcome']=='win').mean()) if len(t) else None
def run_side(df, sig, side, sl, tp, mh):
    empty = pd.Series(False, index=df.index)
    lo, hi = (sig, empty) if side=='long' else (empty, sig)
    t = se.simulate_trades(df, lo, hi, sl_pip=sl, tp_pip=tp, asset='XAUUSD', max_hold=mh, allow_overlap=False)
    if len(t)==0 or 'direction' not in t.columns: return t.iloc[0:0]
    return t[t['direction']==side]
def base_gated(df, gate, side, sl, tp, mh):
    best=None
    for st in (3,7,13):
        b = pd.Series(False, index=df.index); b.iloc[::st]=True
        v = wr(run_side(df, (b&gate).fillna(False).astype(bool), side, sl, tp, mh))
        if v is not None and (best is None or v>best): best=v
    return best

res={}
for TF, MH, sides in (('H8',21,('short','long')), ('H1',48,('long','short')), ('H4',34,('short','long'))):
    d = fd.load_fast('XAUUSD', TF); dff = fd.as_dataframe(d)
    df = dff.iloc[:len(dff)//2].reset_index(drop=True)
    h,l,c = df['high'].values, df['low'].values, df['close'].values; cs=pd.Series(c)
    yrs = pd.to_datetime(df['time'].values, unit='s').year
    tr_ = np.maximum(h-l, np.maximum(abs(h-np.roll(c,1)), abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
    sl = float(np.nanmedian(pd.Series(tr_).rolling(100).mean().values[100:]))*1.5/0.1
    res[TF]={}
    print(f"== {TF} sl={sl:.1f}", flush=True)
    for W in (8,13,21):
        net=cs-cs.shift(W); path=cs.diff().abs().rolling(W).sum(); er=net.abs()/path.replace(0,np.nan); sgn=np.sign(net)
        for lo_th,hi_th,k in ((0.3,0.75,3),(0.3,0.7,3),(0.35,0.8,3)):
            edge=((er>hi_th)&(er.shift(1).rolling(k).min()<lo_th)).fillna(False).astype(bool)
            edge=edge&~edge.shift(1,fill_value=False)
            for side in sides:
                gate=((sgn>0) if side=='long' else (sgn<0)).fillna(False).astype(bool)
                sig=edge&gate
                for rr in (1.0,1.5):
                    tp=sl*rr
                    t=run_side(df,sig,side,sl,tp,MH); n=len(t)
                    if n<15: continue
                    w=wr(t); b=base_gated(df,gate,side,sl,tp,MH)
                    lift=w-b; z=lift/(100*np.sqrt(0.25/n)); pnl=float(t['pnl_pip'].mean())
                    ty=yrs[t['entry_bar'].values.astype(int)]
                    ypos=sum(1 for y in np.unique(ty) if t['pnl_pip'].values[ty==y].mean()>0); ytot=len(np.unique(ty))
                    key=f"W{W}_lo{lo_th}_hi{hi_th}_k{k}_{side}_rr{rr}"
                    res[TF][key]=dict(n=n,wr=round(w,2),base=round(b,2),lift=round(lift,2),pnl=round(pnl,2),z=round(z,2),yrs_pos=f"{ypos}/{ytot}",power=round(lift*np.sqrt(n),1))
                    print(f"  {key:34s} n={n:4d} wr={w:6.2f} base={b:6.2f} lift={lift:+6.2f} pnl={pnl:+7.2f} z={z:+5.2f} yrs+={ypos}/{ytot} pow={lift*np.sqrt(n):+6.1f}", flush=True)
with open(os.path.join(OUT,'s992b_refine.json'),'w') as f: json.dump(res,f,indent=1)
print("saved -> s992b_refine.json")
