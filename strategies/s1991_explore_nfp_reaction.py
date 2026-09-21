# -*- coding: utf-8 -*-
"""
S1991 — واکنشِ NFP (Post-NFP Informed Reaction) — «فقط نیمهٔ نخست»
=====================================================================
S311 (DEAD): «درفتِ پیش از NFP» وجود ندارد — NFP دوطرفه است. هیچ لایه‌ای *واکنشِ پس از* اعلام را نیازموده (۰ ارجاع).
تشخیص ساعتِ اعلام از داده (بدون نگاه به بازده): در جمعه‌های هفتهٔ اول ماه، کندل H1 ساعت ۱۵ سرور دامنهٔ 3.66× میانه دارد
(ساعت ۱۶: 2.54×، ۱۷: 2.1×) — یعنی 15:00 سرور = 08:30 ET.
فرضیه (S965 grammar): کندلِ اعلام (h=15) با retention ρ=|c−o|/(h−l) ≥ ρ_min و دامنهٔ ≥ k×ATR21[t−1] «مطلع» است ⇒ follow در open کندل 16.
کنترل‌ها: (i) fade همان کندل؛ (ii) همان قاعده روی کندل ۱۵ در جمعه‌های دیگر (غیر NFP) — باید ضعیف‌تر باشد (P1)؛ (iii) کندل ۱۵ روزهای عادی.
شبکه: ρ∈{0.5,0.618}؛ k∈{1.5,2.0}؛ TF=H1؛ max_hold∈{8,24}؛ rr∈{1.0,1.5}. نول = سخت‌ترین stride درونِ همان گیت (کندل‌های h=15 جمعهٔ NFP).
تعریفِ NFP-day (علّی، تقویمی): اولین جمعهٔ ماه (روز ≤7). استثناهای BLS (تعطیلی/شات‌داون) نادیده گرفته می‌شوند — نویزِ برچسب، به‌ضررِ فرضیه.
"""
import sys, os, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'research', 's1991_explore'); os.makedirs(OUT, exist_ok=True)

def wr(t): return 100*float((t['outcome']=='win').mean()) if len(t) else None
def run_side(df, sig, side, sl, tp, mh):
    empty = pd.Series(False, index=df.index)
    lo, hi = (sig, empty) if side=='long' else (empty, sig)
    t = se.simulate_trades(df, lo, hi, sl_pip=sl, tp_pip=tp, asset='XAUUSD', max_hold=mh, allow_overlap=False)
    if len(t)==0 or 'direction' not in t.columns: return t.iloc[0:0]
    return t[t['direction']==side]
def base_gated(df, gate, side, sl, tp, mh):
    best=None
    for st in (1,2,3):   # gate is sparse (~1 bar/month) — strides 1..3 within gate
        b = pd.Series(False, index=df.index); b.iloc[::st]=True
        v = wr(run_side(df, (b&gate).astype(bool), side, sl, tp, mh))
        if v is not None and (best is None or v>best): best=v
    return best

dff = fd.as_dataframe(fd.load_fast('XAUUSD','H1')); df = dff.iloc[:len(dff)//2].reset_index(drop=True)
h,l,c,o = df['high'].values, df['low'].values, df['close'].values, df['open'].values
t = pd.to_datetime(df['time'].values, unit='s'); yrs = t.year
tr_ = np.maximum(h-l, np.maximum(abs(h-np.roll(c,1)), abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]; trs=pd.Series(tr_)
sl = float(np.nanmedian(trs.rolling(100).mean().values[100:]))*1.5/0.1
atr21 = trs.rolling(21).mean().shift(1)
rng = pd.Series(h-l); rho = (pd.Series(np.abs(c-o))/rng.replace(0,np.nan)).fillna(0)
hr = pd.Series(t.hour); dow = pd.Series(t.dayofweek); dom = pd.Series(t.day)
is_nfp = (dow==4)&(dom<=7)&(hr==15)
is_ofri = (dow==4)&(dom>7)&(hr==15)
is_wk = (dow<4)&(hr==15)
print(f"== H1 first half sl={sl:.1f} bars={len(df)} nfp_bars={int(is_nfp.sum())} otherFri15={int(is_ofri.sum())} weekday15={int(is_wk.sum())}", flush=True)
res={'sl_pip':sl,'cells':{}}
for gname, g in (('NFP', is_nfp), ('otherFri', is_ofri), ('weekday', is_wk)):
    for rmin in (0.5, 0.618):
        for k in (1.5, 2.0):
            inf = g & (rho>=rmin) & (rng>=k*atr21)
            up = inf & pd.Series(c>o); dn = inf & pd.Series(c<o)
            for mode in ('follow','fade'):
                for side in ('long','short'):
                    body = up if ((side=='long')==(mode=='follow')) else dn
                    sig = body.fillna(False).astype(bool)
                    for MH in (8, 24):
                        for rr in (1.0,1.5):
                            tp=sl*rr; tt=run_side(df,sig,side,sl,tp,MH); n=len(tt)
                            if n<15: continue
                            b=base_gated(df,g.astype(bool),side,sl,tp,MH)
                            if b is None: continue
                            w=wr(tt); lift=w-b; z=lift/(100*np.sqrt(0.25/n)); pnl=float(tt['pnl_pip'].mean())
                            ty=yrs[tt['entry_bar'].values.astype(int)]
                            ypos=sum(1 for y in np.unique(ty) if tt['pnl_pip'].values[ty==y].mean()>0); ytot=len(np.unique(ty))
                            key=f"{gname}_rho{rmin}_k{k}_{mode}_{side}_mh{MH}_rr{rr}"
                            res['cells'][key]=dict(n=n,wr=round(w,2),base=round(b,2),lift=round(lift,2),pnl=round(pnl,2),z=round(z,2),yrs_pos=f"{ypos}/{ytot}",power=round(lift*np.sqrt(n),1))
                            flag=' <==' if (z>=2.5 and lift>=4 and pnl>0) else ''
                            print(f"  {key:44s} n={n:4d} wr={w:6.2f} base={b:6.2f} lift={lift:+6.2f} pnl={pnl:+7.2f} z={z:+5.2f} yrs+={ypos}/{ytot}{flag}", flush=True)
with open(os.path.join(OUT,'nfp_reaction.json'),'w') as f: json.dump(res,f,indent=1)
print("saved -> nfp_reaction.json")
