# -*- coding: utf-8 -*-
"""
S993 — لبهٔ ER کافمن × اهرم‌های اثبات‌شدهٔ بانک (CALM S606 / درفت S966) — «فقط نیمهٔ نخست»
==========================================================================================
S992 (REJECT 17.8، lift انتقالی +6.07pp، n=111 توان‌ناکافی) نشان داد لبهٔ ER واقعی است.
پرسش S993: کدام گیت اطلاعات‌افزاست (P1: لیفت بازو > لیفت والد بدون گیت)؟
  A) والد: لبهٔ ER W13 (lo0.3/hi0.7/k3) لانگ — همان S992
  B) + CALM: σ_t(ATR13) ≤ median(σ_{t−233..t−1})     (S606)
  C) + DRIFT: close[i−1] > close[i−1−180]           (S966)
  D) + هر دو
و برای تراکم بیشتر: TF∈{M30,H1,H2} (زیستگاه چگال‌تر). پایه = سخت‌ترین stride درون همان گیت مرکب.
"""
import sys, os, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'research', 's993_explore'); os.makedirs(OUT, exist_ok=True)

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
for TF, MH in (('M30',64),('H1',48),('H2',40)):
    d = fd.load_fast('XAUUSD', TF); dff = fd.as_dataframe(d)
    df = dff.iloc[:len(dff)//2].reset_index(drop=True)
    h,l,c = df['high'].values, df['low'].values, df['close'].values; cs=pd.Series(c)
    yrs = pd.to_datetime(df['time'].values, unit='s').year
    tr_ = np.maximum(h-l, np.maximum(abs(h-np.roll(c,1)), abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
    trs = pd.Series(tr_)
    sl = float(np.nanmedian(trs.rolling(100).mean().values[100:]))*1.5/0.1
    atr13 = trs.rolling(13).mean()
    calm = (atr13 <= atr13.shift(1).rolling(233).median()).fillna(False).astype(bool)
    drift = (cs.shift(1) > cs.shift(181)).fillna(False).astype(bool)
    res[TF]={'sl_pip':sl,'cells':{}}
    print(f"== {TF} sl={sl:.1f} bars={len(df)} calm%={100*calm.mean():.0f} drift%={100*drift.mean():.0f}", flush=True)
    for W in (13, 21):
        net=cs-cs.shift(W); path=cs.diff().abs().rolling(W).sum(); er=net.abs()/path.replace(0,np.nan)
        edge=((er>0.70)&(er.shift(1).rolling(3).min()<0.30)).fillna(False).astype(bool)
        edge=edge&~edge.shift(1,fill_value=False)
        for side in ('long','short'):
            dir_ok=((net>0) if side=='long' else (net<0)).fillna(False).astype(bool)
            for arm, g in (('A_raw',dir_ok),('B_calm',dir_ok&calm),('C_drift',dir_ok&drift),('D_both',dir_ok&calm&drift),('E_anticalm',dir_ok&~calm)):
                sig=edge&g
                for rr in (1.0,1.5):
                    tp=sl*rr
                    t=run_side(df,sig,side,sl,tp,MH); n=len(t)
                    if n<20: continue
                    w=wr(t); b=base_gated(df,g,side,sl,tp,MH)
                    if b is None: continue
                    lift=w-b; z=lift/(100*np.sqrt(0.25/n)); pnl=float(t['pnl_pip'].mean())
                    ty=yrs[t['entry_bar'].values.astype(int)]
                    ypos=sum(1 for y in np.unique(ty) if t['pnl_pip'].values[ty==y].mean()>0); ytot=len(np.unique(ty))
                    key=f"W{W}_{side}_{arm}_rr{rr}"
                    res[TF]['cells'][key]=dict(n=n,wr=round(w,2),base=round(b,2),lift=round(lift,2),pnl=round(pnl,2),z=round(z,2),yrs_pos=f"{ypos}/{ytot}",power=round(lift*np.sqrt(n),1))
                    flag=' <==' if (z>=2.5 and lift>=4 and pnl>0) else ''
                    print(f"  {key:28s} n={n:4d} wr={w:6.2f} base={b:6.2f} lift={lift:+6.2f} pnl={pnl:+7.2f} z={z:+5.2f} yrs+={ypos}/{ytot} pow={lift*np.sqrt(n):+6.1f}{flag}", flush=True)
with open(os.path.join(OUT,'er_gated.json'),'w') as f: json.dump(res,f,indent=1)
print("saved -> er_gated.json")
