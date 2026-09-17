# -*- coding: utf-8 -*-
"""
S1990 — اکتشاف B: رکورد تازه × جلسهٔ معاملاتی (Record × Session) — «فقط نیمهٔ نخست»
======================================================================================
اکتشاف A (جذب شوک نزولی) نول بود. خانوادهٔ دوم: لبهٔ اثبات‌شدهٔ رکورد تازه (S526: close>max(close[−90..−1])، لبهٔ تازه)
در TF پایین می‌میرد (S1510/S999). فرضیهٔ خرد-ساختاری: رکوردی که در جلسهٔ کم‌نقدینگی (آسیا) زده می‌شود نویزِ سفارش‌های
نازک است؛ رکوردِ جلسهٔ لندن/نیویورک (COMEX فعال، دادهٔ آمریکا) «مطلع» است. گیت = بازهٔ ساعت سرور کندلِ رکورد:
S1 [00,08)، S2 [08,16)، S3 [16,24). کنترل: raw. هیچ لایه‌ای «رکورد × جلسه» را نیازموده (۰ ارجاع).
TF∈{H1,H2,H4}؛ W∈{90}؛ side long/short؛ rr∈{1.0,1.5}. نول = سخت‌ترین stride درونِ همان گیت جلسه (فصل‌زدایی خودکار).
"""
import sys, os, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'research', 's1990_explore'); os.makedirs(OUT, exist_ok=True)

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
        v = wr(run_side(df, (b&gate).astype(bool), side, sl, tp, mh))
        if v is not None and (best is None or v>best): best=v
    return best

res={}
for TF, MH in (('H1',48),('H2',40),('H4',30)):
    dff = fd.as_dataframe(fd.load_fast('XAUUSD', TF)); df = dff.iloc[:len(dff)//2].reset_index(drop=True)
    h,l,c = df['high'].values, df['low'].values, df['close'].values; cs=pd.Series(c)
    yrs = pd.to_datetime(df['time'].values, unit='s').year
    hr = ((df['time'].values.astype(np.int64) % 86400)//3600)
    tr_ = np.maximum(h-l, np.maximum(abs(h-np.roll(c,1)), abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
    sl = float(np.nanmedian(pd.Series(tr_).rolling(100).mean().values[100:]))*1.5/0.1
    nh = (cs > cs.shift(1).rolling(90).max()).fillna(False); nl = (cs < cs.shift(1).rolling(90).min()).fillna(False)
    e_hi = (nh & ~nh.shift(1,fill_value=False)).astype(bool); e_lo = (nl & ~nl.shift(1,fill_value=False)).astype(bool)
    gates = {'raw': pd.Series(True,index=df.index), 'S1_00-08': pd.Series(hr<8,index=df.index), 'S2_08-16': pd.Series((hr>=8)&(hr<16),index=df.index), 'S3_16-24': pd.Series(hr>=16,index=df.index)}
    res[TF]={'sl_pip':sl,'bars':len(df),'cells':{}}
    print(f"== {TF} sl={sl:.1f} bars={len(df)} rec_hi={int(e_hi.sum())} rec_lo={int(e_lo.sum())}", flush=True)
    for gname, g in gates.items():
        for side, edge in (('long',e_hi),('short',e_lo)):
            sig=(edge&g).astype(bool)
            for rr in (1.0,1.5):
                tp=sl*rr; t=run_side(df,sig,side,sl,tp,MH); n=len(t)
                if n<20: continue
                b=base_gated(df,g.astype(bool),side,sl,tp,MH)
                if b is None: continue
                w=wr(t); lift=w-b; z=lift/(100*np.sqrt(0.25/n)); pnl=float(t['pnl_pip'].mean())
                ty=yrs[t['entry_bar'].values.astype(int)]
                ypos=sum(1 for y in np.unique(ty) if t['pnl_pip'].values[ty==y].mean()>0); ytot=len(np.unique(ty))
                key=f"{gname}_{side}_rr{rr}"
                res[TF]['cells'][key]=dict(n=n,wr=round(w,2),base=round(b,2),lift=round(lift,2),pnl=round(pnl,2),z=round(z,2),yrs_pos=f"{ypos}/{ytot}",power=round(lift*np.sqrt(n),1))
                flag=' <==' if (z>=2.5 and lift>=4 and pnl>0) else ''
                print(f"  {key:26s} n={n:4d} wr={w:6.2f} base={b:6.2f} lift={lift:+6.2f} pnl={pnl:+7.2f} z={z:+5.2f} yrs+={ypos}/{ytot}{flag}", flush=True)
with open(os.path.join(OUT,'record_session.json'),'w') as f: json.dump(res,f,indent=1)
print("saved -> record_session.json")
