# -*- coding: utf-8 -*-
"""
S998 — بازافروزیِ انحنا (Lagrange second-order term) — «فقط نیمهٔ نخست»
========================================================================
هیچ لایه‌ای در repo از «مشتق دوم / انحنا» به‌عنوان مختصات لبه استفاده نکرده (۰ ارجاع: quadratic/curvature/second-order/convex).
مدل محلی قیمت: p(t) ≈ p0 + v·t + ½a·t². با هموارسازی EMA(W) روی close:
   v_t = m_t − m_{t−1}   (شیب)      a_t = v_t − v_{t−1}   (انحنا)
رویداد (لبه، فقط کندل اول): a از ≤0 به >0 برمی‌گردد در حالی که v>0 و v ≥ q·σ_v  (روند صعودی که پس از کُندشدن دوباره شتاب می‌گیرد) ⇒ LONG
         آینه: a از ≥0 به <0 با v<0 ⇒ SHORT.
کنترل‌ها: (i) flip بدون شرط شیب (state)؛ (ii) «inflection down» ضدروند (a>0→<0 با v>0 ⇒ short) — باید بی‌اثر/منفی باشد.
شبکه: W∈{8,13,21}؛ q∈{0, 0.5}؛ TF∈{H1,H2,H4}؛ rr∈{1.0,1.5}. نول = سخت‌ترین stride غیرشرطی.
"""
import sys, os, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'research', 's998_explore'); os.makedirs(OUT, exist_ok=True)

def wr(t): return 100*float((t['outcome']=='win').mean()) if len(t) else None
def run_side(df, sig, side, sl, tp, mh):
    empty = pd.Series(False, index=df.index)
    lo, hi = (sig, empty) if side=='long' else (empty, sig)
    t = se.simulate_trades(df, lo, hi, sl_pip=sl, tp_pip=tp, asset='XAUUSD', max_hold=mh, allow_overlap=False)
    if len(t)==0 or 'direction' not in t.columns: return t.iloc[0:0]
    return t[t['direction']==side]
def base_uncond(df, side, sl, tp, mh):
    best=None
    for st in (3,7,13):
        b = pd.Series(False, index=df.index); b.iloc[::st]=True
        v = wr(run_side(df, b, side, sl, tp, mh))
        if v is not None and (best is None or v>best): best=v
    return best

res={}
for TF, MH in (('H1',48),('H2',40),('H4',30)):
    dff = fd.as_dataframe(fd.load_fast('XAUUSD', TF)); df = dff.iloc[:len(dff)//2].reset_index(drop=True)
    h,l,c = df['high'].values, df['low'].values, df['close'].values; cs=pd.Series(c)
    yrs = pd.to_datetime(df['time'].values, unit='s').year
    tr_ = np.maximum(h-l, np.maximum(abs(h-np.roll(c,1)), abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
    sl = float(np.nanmedian(pd.Series(tr_).rolling(100).mean().values[100:]))*1.5/0.1
    res[TF]={'sl_pip':sl,'cells':{}}; bases={}
    print(f"== {TF} sl={sl:.1f} bars={len(df)}", flush=True)
    for W in (8,13,21):
        m = cs.ewm(span=W, adjust=False).mean(); v = m.diff(); a = v.diff()
        sv = v.rolling(233).std().shift(1)
        for q in (0.0, 0.5):
            vpos = (v>0) & (v >= q*sv); vneg = (v<0) & (v <= -q*sv)
            up_flip = (a>0) & (a.shift(1)<=0); dn_flip = (a<0) & (a.shift(1)>=0)
            arms = {
              'reignite_long':  (up_flip & vpos), 'reignite_short': (dn_flip & vneg),   # لبهٔ اصلی
              'flipstate_long': up_flip, 'flipstate_short': dn_flip,                    # کنترل: بدون شیب
              'inflect_short':  (dn_flip & vpos), 'inflect_long': (up_flip & vneg),     # کنترل ضدروند
            }
            for arm, sig in arms.items():
                side = 'long' if arm.endswith('long') else 'short'
                sig = sig.fillna(False).astype(bool)
                for rr in (1.0,1.5):
                    tp=sl*rr
                    if (side,rr) not in bases: bases[(side,rr)] = base_uncond(df, side, sl, tp, MH)
                    b=bases[(side,rr)]; t=run_side(df,sig,side,sl,tp,MH); n=len(t)
                    if n<20 or b is None: continue
                    w=wr(t); lift=w-b; z=lift/(100*np.sqrt(0.25/n)); pnl=float(t['pnl_pip'].mean())
                    ty=yrs[t['entry_bar'].values.astype(int)]
                    ypos=sum(1 for y in np.unique(ty) if t['pnl_pip'].values[ty==y].mean()>0); ytot=len(np.unique(ty))
                    key=f"W{W}_q{q}_{arm}_rr{rr}"
                    res[TF]['cells'][key]=dict(n=n,wr=round(w,2),base=round(b,2),lift=round(lift,2),pnl=round(pnl,2),z=round(z,2),yrs_pos=f"{ypos}/{ytot}",power=round(lift*np.sqrt(n),1))
                    flag=' <==' if (z>=2.5 and lift>=4 and pnl>0) else ''
                    print(f"  {key:34s} n={n:5d} wr={w:6.2f} base={b:6.2f} lift={lift:+6.2f} pnl={pnl:+7.2f} z={z:+5.2f} yrs+={ypos}/{ytot} pow={lift*np.sqrt(n):+6.1f}{flag}", flush=True)
with open(os.path.join(OUT,'curvature.json'),'w') as f: json.dump(res,f,indent=1)
print("saved -> curvature.json")
