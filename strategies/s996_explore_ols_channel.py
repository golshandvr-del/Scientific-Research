# -*- coding: utf-8 -*-
"""
S996 — کانالِ کمترین‌مربعات (Lagrange–Gauss OLS residual channel) — «فقط نیمهٔ نخست»
======================================================================================
هیچ لایه‌ای در repo از «باقیماندهٔ رگرسیون خطی» به‌عنوان مختصات لبه استفاده نکرده (۰ ارجاع).
تعریف: در پنجرهٔ W، خط OLS روی close؛ e_t = close_t − fit_t؛ σ_e = sqrt(SSE/(W−2))؛ zres_t = e_t/σ_e.
رویداد (تازه، فقط کندل اول): |zres| از زیر θ به بالای θ می‌رود (خروج از کانال).
بازوها:
  break: zres>+θ و slope>0 → LONG؛ zres<−θ و slope<0 → SHORT  (ادامهٔ روند، پارگی کانال هم‌جهت)
  fade : zres>+θ → SHORT؛ zres<−θ → LONG                        (بازگشت به خط)
  cbrk : خروج خلافِ شیب (zres>+θ و slope<0 → LONG …)              (شکستِ ضدروند)
W∈{34,55,89}؛ θ∈{2.0,2.5}؛ TF∈{H4,H6,H8}؛ rr∈{1.0,1.5}؛ null = سخت‌ترین stride غیرشرطی.
"""
import sys, os, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'research', 's996_explore'); os.makedirs(OUT, exist_ok=True)

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

def ols_channel(cs, W):
    x = np.arange(W, dtype=float); xm = x.mean(); Sxx = float(((x-xm)**2).sum())
    ym = cs.rolling(W).mean()
    # Sxy = Σ (x-xm)(y-ym) = Σ (x-xm) y   (weights fixed per window)
    wts = (x-xm)
    Sxy = cs.rolling(W).apply(lambda y: float(np.dot(wts, y)), raw=True)
    slope = Sxy/Sxx
    Syy = cs.rolling(W).apply(lambda y: float(((y-y.mean())**2).sum()), raw=True)
    sse = (Syy - slope**2*Sxx).clip(lower=0)
    sig_e = np.sqrt(sse/(W-2))
    fit_last = ym + slope*(x[-1]-xm)
    zres = (cs - fit_last)/sig_e.replace(0,np.nan)
    return zres, slope

res={}
for TF, MH in (('H4',30),('H6',24),('H8',21)):
    d = fd.load_fast('XAUUSD', TF); dff = fd.as_dataframe(d)
    df = dff.iloc[:len(dff)//2].reset_index(drop=True)
    h,l,c = df['high'].values, df['low'].values, df['close'].values; cs=pd.Series(c)
    yrs = pd.to_datetime(df['time'].values, unit='s').year
    tr_ = np.maximum(h-l, np.maximum(abs(h-np.roll(c,1)), abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
    sl = float(np.nanmedian(pd.Series(tr_).rolling(100).mean().values[100:]))*1.5/0.1
    res[TF]={'sl_pip':sl,'cells':{}}
    bases={}
    print(f"== {TF} sl={sl:.1f} bars={len(df)}", flush=True)
    for W in (34,55,89):
        zres, slope = ols_channel(cs, W)
        for th in (2.0,2.5):
            up_x = ((zres> th)&(zres.shift(1)<= th)).fillna(False)
            dn_x = ((zres<-th)&(zres.shift(1)>=-th)).fillna(False)
            sp = (slope>0).fillna(False); sn = (slope<0).fillna(False)
            arms = {
              'break_long': up_x&sp, 'break_short': dn_x&sn,
              'fade_long': dn_x, 'fade_short': up_x,
              'cbrk_long': up_x&sn, 'cbrk_short': dn_x&sp,
            }
            for arm, sig in arms.items():
                side = 'long' if arm.endswith('long') else 'short'
                sig = sig.astype(bool)
                for rr in (1.0,1.5):
                    tp=sl*rr
                    if (side,rr) not in bases: bases[(side,rr)] = base_uncond(df, side, sl, tp, MH)
                    b = bases[(side,rr)]
                    t=run_side(df,sig,side,sl,tp,MH); n=len(t)
                    if n<20 or b is None: continue
                    w=wr(t); lift=w-b; z=lift/(100*np.sqrt(0.25/n)); pnl=float(t['pnl_pip'].mean())
                    ty=yrs[t['entry_bar'].values.astype(int)]
                    ypos=sum(1 for y in np.unique(ty) if t['pnl_pip'].values[ty==y].mean()>0); ytot=len(np.unique(ty))
                    key=f"W{W}_th{th}_{arm}_rr{rr}"
                    res[TF]['cells'][key]=dict(n=n,wr=round(w,2),base=round(b,2),lift=round(lift,2),pnl=round(pnl,2),z=round(z,2),yrs_pos=f"{ypos}/{ytot}",power=round(lift*np.sqrt(n),1))
                    flag=' <==' if (z>=2.5 and lift>=4 and pnl>0) else ''
                    print(f"  {key:30s} n={n:4d} wr={w:6.2f} base={b:6.2f} lift={lift:+6.2f} pnl={pnl:+7.2f} z={z:+5.2f} yrs+={ypos}/{ytot} pow={lift*np.sqrt(n):+6.1f}{flag}", flush=True)
with open(os.path.join(OUT,'ols_channel.json'),'w') as f: json.dump(res,f,indent=1)
print("saved -> ols_channel.json")
