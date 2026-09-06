# -*- coding: utf-8 -*-
"""
S994 — شوکِ حجمِ فصل‌زدوده (Admati–Pfleiderer intraday seasonality) — «فقط نیمهٔ نخست»
======================================================================================
S916/S917 (کینز) شوک حجم خام را رد کردند. اما حجمِ خام دو آلودگی دارد:
  (۱) فصلی‌بودن ساعتی (لندن/نیویورک همیشه پرحجم‌اند)  (۲) رشد ۴× حجم در ۱۵ سال.
هر دو با نرمال‌سازی به «میانهٔ همان ساعت در N روز گذشته» حذف می‌شود:
   rv_t = volume_t / median(volume همان ساعت، ۲۰ روز اخیر)
فرضیه: rv ≥ θ در ساعتی که «قرار نبود» پرحجم باشد = معاملهٔ مطلع؛ جهت = بدنهٔ کندل (follow، قانون S965).
بازوها: follow / fade؛ retention ρ=|c−o|/(h−l) ≥ {0, 0.5}؛ θ∈{2.0, 3.0}؛ TF∈{M30,H1}؛ rr∈{1.0,1.5}.
جست‌وجوی repo: هیچ لایه‌ای حجم را به ساعتِ روز نرمال نکرده (بکر).
"""
import sys, os, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'research', 's994_explore'); os.makedirs(OUT, exist_ok=True)

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

def seasonal_rv(df, ndays=20):
    """volume / median of same hour-of-day (and same minute slot) over previous ndays sessions — causal."""
    t = df['time'].values.astype(np.int64)
    slot = (t % 86400)                       # seconds into the day (server tz)
    v = pd.Series(df['volume'].values.astype(float))
    rv = pd.Series(np.nan, index=df.index)
    for s in np.unique(slot):
        idx = np.where(slot==s)[0]
        vs = v.iloc[idx]
        med = vs.shift(1).rolling(ndays, min_periods=10).median()
        rv.iloc[idx] = (vs / med.replace(0,np.nan)).values
    return rv

res={}
for TF, MH in (('M30',64),('H1',48)):
    d = fd.load_fast('XAUUSD', TF); dff = fd.as_dataframe(d)
    df = dff.iloc[:len(dff)//2].reset_index(drop=True)
    h,l,c,o = df['high'].values, df['low'].values, df['close'].values, df['open'].values
    yrs = pd.to_datetime(df['time'].values, unit='s').year
    tr_ = np.maximum(h-l, np.maximum(abs(h-np.roll(c,1)), abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
    trs = pd.Series(tr_)
    sl = float(np.nanmedian(trs.rolling(100).mean().values[100:]))*1.5/0.1
    rv = seasonal_rv(df, 20)
    rng = np.where((h-l)>0, h-l, np.nan)
    rho = pd.Series(np.abs(c-o)/rng).fillna(0)
    up = pd.Series(c>o); dn = pd.Series(c<o)
    res[TF]={'sl_pip':sl,'rv_q':{q:round(float(rv.quantile(q)),3) for q in (0.5,0.9,0.95,0.99)},'cells':{}}
    print(f"== {TF} sl={sl:.1f} bars={len(df)} rv quantiles={res[TF]['rv_q']}", flush=True)
    for th in (2.0, 3.0):
        shock = (rv >= th).fillna(False).astype(bool)
        for rmin in (0.0, 0.5):
            ok = shock & (rho >= rmin)
            for mode in ('follow','fade'):
                for side in ('long','short'):
                    body = up if ((side=='long')==(mode=='follow')) else dn
                    sig = (ok & body).fillna(False).astype(bool)
                    gate = pd.Series(True, index=df.index)   # unconditional habitat: null = hardest stride, whole series
                    for rr in (1.0,1.5):
                        tp=sl*rr
                        t=run_side(df,sig,side,sl,tp,MH); n=len(t)
                        if n<20: continue
                        w=wr(t); b=base_gated(df,gate,side,sl,tp,MH)
                        if b is None: continue
                        lift=w-b; z=lift/(100*np.sqrt(0.25/n)); pnl=float(t['pnl_pip'].mean())
                        ty=yrs[t['entry_bar'].values.astype(int)]
                        ypos=sum(1 for y in np.unique(ty) if t['pnl_pip'].values[ty==y].mean()>0); ytot=len(np.unique(ty))
                        key=f"th{th}_rho{rmin}_{mode}_{side}_rr{rr}"
                        res[TF]['cells'][key]=dict(n=n,wr=round(w,2),base=round(b,2),lift=round(lift,2),pnl=round(pnl,2),z=round(z,2),yrs_pos=f"{ypos}/{ytot}",power=round(lift*np.sqrt(n),1))
                        flag=' <==' if (z>=2.5 and lift>=4 and pnl>0) else ''
                        print(f"  {key:32s} n={n:5d} wr={w:6.2f} base={b:6.2f} lift={lift:+6.2f} pnl={pnl:+7.2f} z={z:+5.2f} yrs+={ypos}/{ytot} pow={lift*np.sqrt(n):+6.1f}{flag}", flush=True)
with open(os.path.join(OUT,'seasonal_volume.json'),'w') as f: json.dump(res,f,indent=1)
print("saved -> seasonal_volume.json")
