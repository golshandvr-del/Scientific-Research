# -*- coding: utf-8 -*-
"""
S1990 — جذبِ شوکِ نزولی (Bear-Shock Absorption) — «فقط نیمهٔ نخست»
======================================================================
یافتهٔ جانبی دههٔ S990: در M30 (S994/S995) follow-SHORT روی کندل‌های نزولیِ پردامنه/پرحجم به‌طور سیستماتیک منفی بود
(z تا −۳.۸، ۰/۸ سال). فرضیهٔ مستقل: طلا فروش‌های شدیدِ تک‌کندلی را «جذب» می‌کند ⇒ FADE = LONG بعد از کندل نزولیِ شوک.
رویداد (ناپیوسته): range_t ≥ k×ATR21[t−1] (k∈{2.0,2.618}) و close<open و retention ρ=|c−o|/(h−l) ≥ 0.618 (کندل نزولیِ تمیز) — همان
دستور زبان S965 ولی با جهتِ معکوس. کنترل: آینهٔ صعودی (fade SHORT بعد از شوک صعودی) — اگر فرضیهٔ «جذب» خاصِ فروش باشد باید ≈۰ یا منفی شود.
گیت‌ها: A raw؛ B drift>0 (close[t−1]>close[t−1−K]، K=۶۰ روز تقویمی به کندل)؛ C CALM (ATR13 ≤ median233)؛ D drift∧calm؛ E anti-drift.
TF∈{H1,H4,H6,H8}؛ rr∈{1.0,1.5}؛ max_hold ≈ ۲ روز. نول = سخت‌ترین stride درونِ همان گیت.
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

BARS_PER_DAY = {'H1':24,'H4':6,'H6':4,'H8':3}
res={}
for TF in ('H1','H4','H6','H8'):
    bpd = BARS_PER_DAY[TF]; MH = 2*bpd
    dff = fd.as_dataframe(fd.load_fast('XAUUSD', TF)); df = dff.iloc[:len(dff)//2].reset_index(drop=True)
    h,l,c,o = df['high'].values, df['low'].values, df['close'].values, df['open'].values; cs=pd.Series(c)
    yrs = pd.to_datetime(df['time'].values, unit='s').year
    tr_ = np.maximum(h-l, np.maximum(abs(h-np.roll(c,1)), abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]; trs=pd.Series(tr_)
    sl = float(np.nanmedian(trs.rolling(100).mean().values[100:]))*1.5/0.1
    atr21 = trs.rolling(21).mean().shift(1); atr13 = trs.rolling(13).mean()
    rng = pd.Series(h-l); rho = (pd.Series(np.abs(c-o))/rng.replace(0,np.nan)).fillna(0)
    K = int(60*bpd*5/7)  # ~60 calendar days in bars (5/7 trading)
    drift = (cs.shift(1) > cs.shift(1+K)).fillna(False)
    calm = (atr13 <= atr13.shift(1).rolling(233).median()).fillna(False)
    res[TF]={'sl_pip':sl,'bars':len(df),'cells':{}}
    print(f"== {TF} sl={sl:.1f} bars={len(df)} K={K} drift%={100*drift.mean():.0f} calm%={100*calm.mean():.0f}", flush=True)
    for k in (2.0, 2.618):
        shock = (rng >= k*atr21) & (rho >= 0.618)
        bear = shock & pd.Series(c<o); bull = shock & pd.Series(c>o)
        gates = {'A_raw': pd.Series(True,index=df.index), 'B_drift': drift, 'C_calm': calm, 'D_both': drift&calm, 'E_antidrift': ~drift}
        for gname, g in gates.items():
            for arm, ev, side in (('fadeBear_long', bear, 'long'), ('fadeBull_short', bull, 'short')):
                sig = (ev & g).fillna(False).astype(bool)
                for rr in (1.0,1.5):
                    tp=sl*rr; t=run_side(df,sig,side,sl,tp,MH); n=len(t)
                    if n<20: continue
                    b=base_gated(df,g.astype(bool),side,sl,tp,MH)
                    if b is None: continue
                    w=wr(t); lift=w-b; z=lift/(100*np.sqrt(0.25/n)); pnl=float(t['pnl_pip'].mean())
                    ty=yrs[t['entry_bar'].values.astype(int)]
                    ypos=sum(1 for y in np.unique(ty) if t['pnl_pip'].values[ty==y].mean()>0); ytot=len(np.unique(ty))
                    key=f"k{k}_{gname}_{arm}_rr{rr}"
                    res[TF]['cells'][key]=dict(n=n,wr=round(w,2),base=round(b,2),lift=round(lift,2),pnl=round(pnl,2),z=round(z,2),yrs_pos=f"{ypos}/{ytot}",power=round(lift*np.sqrt(n),1))
                    flag=' <==' if (z>=2.5 and lift>=4 and pnl>0) else ''
                    print(f"  {key:36s} n={n:4d} wr={w:6.2f} base={b:6.2f} lift={lift:+6.2f} pnl={pnl:+7.2f} z={z:+5.2f} yrs+={ypos}/{ytot}{flag}", flush=True)
with open(os.path.join(OUT,'bear_shock_absorption.json'),'w') as f: json.dump(res,f,indent=1)
print("saved -> bear_shock_absorption.json")
