# -*- coding: utf-8 -*-
"""
S992 — شوک نسبت کارایی کافمن (Efficiency-Ratio Shock) — «فقط نیمهٔ نخست»
========================================================================
ER_W = |close_t − close_{t−W}| / Σ|Δclose| در W کندل ∈ [0,1]  (کافمن 1995؛ بانک: 0 اشاره = بکر)
فرضیه (مشتق نه انتگرال — S616؛ لبه نه حالت — S963): پرش ER از زیر lo به بالای hi در ≤ k کندل
= «حرکت یک‌طرفهٔ ناگهانی» (اطلاعات وارد شد) ⇒ follow جهت حرکت (S522 جهت‌مندی).
ابطال‌گر P1 (درس S965): بازوی لبه باید از حالت ساده (ER>hi بدون شرط لبه) بهتر باشد.
پایه = سخت‌ترین stride درون گیت جهت (sign(close−close_W)). هندسه TP=SL (کاوش).
"""
import sys, os, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'research', 's992_explore')
os.makedirs(OUT, exist_ok=True)

def wr(t): return 100*float((t['outcome']=='win').mean()) if len(t) else None
def run_side(df, sig, side, sl, tp, mh):
    empty = pd.Series(False, index=df.index)
    lo, hi = (sig, empty) if side=='long' else (empty, sig)
    t = se.simulate_trades(df, lo, hi, sl_pip=sl, tp_pip=tp, asset='XAUUSD', max_hold=mh, allow_overlap=False)
    return t[t['direction']==side]
def base_gated(df, gate, side, sl, tp, mh):
    best=None
    for st in (3,7,13):
        b = pd.Series(False, index=df.index); b.iloc[::st]=True
        v = wr(run_side(df, (b&gate).fillna(False).astype(bool), side, sl, tp, mh))
        if v is not None and (best is None or v>best): best=v
    return best

res = {}
for TF, MH in (('H1',48), ('H4',34), ('H8',21), ('D1',13)):
    d = fd.load_fast('XAUUSD', TF); dff = fd.as_dataframe(d)
    df = dff.iloc[:len(dff)//2].reset_index(drop=True)
    h,l,c = df['high'].values, df['low'].values, df['close'].values
    cs = pd.Series(c)
    tr_ = np.maximum(h-l, np.maximum(abs(h-np.roll(c,1)), abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
    sl = float(np.nanmedian(pd.Series(tr_).rolling(100).mean().values[100:]))*1.5/0.1
    res[TF] = {'sl_pip': sl, 'cells': {}}
    print(f"== {TF} sl={sl:.1f} bars={len(df)}", flush=True)
    for W in (8, 13, 21):
        net = cs - cs.shift(W)
        path = cs.diff().abs().rolling(W).sum()
        er = (net.abs()/path.replace(0,np.nan))
        sgn = np.sign(net)
        for lo_th, hi_th, k in ((0.3,0.7,2),(0.3,0.8,2),(0.4,0.8,3),(0.2,0.7,3)):
            state = (er > hi_th)
            was_low = (er.shift(1).rolling(k).min() < lo_th)
            edge = (state & was_low).fillna(False).astype(bool)
            edge = edge & ~edge.shift(1, fill_value=False)
            state_edge = state.fillna(False).astype(bool)
            state_edge = state_edge & ~state_edge.shift(1, fill_value=False)
            for side in ('long','short'):
                dir_ok = ((sgn>0) if side=='long' else (sgn<0)).fillna(False).astype(bool)
                gate = dir_ok
                for arm, s in (('edge', edge), ('state', state_edge)):
                    sig = (s & dir_ok)
                    if int(sig.sum()) < 20: continue
                    t = run_side(df, sig, side, sl, sl, MH); n=len(t)
                    if n < 20: continue
                    w = wr(t); b = base_gated(df, gate, side, sl, sl, MH)
                    if b is None: continue
                    lift=w-b; z=lift/(100*np.sqrt(0.25/n)); pnl=float(t['pnl_pip'].mean())
                    key=f"W{W}_lo{lo_th}_hi{hi_th}_k{k}_{arm}_{side}"
                    res[TF]['cells'][key]=dict(n=n,wr=round(w,2),base=round(b,2),lift=round(lift,2),pnl=round(pnl,3),z=round(z,2))
                    flag=' <==' if (z>=2.0 and lift>=4) else ''
                    print(f"  {key:34s} n={n:5d} wr={w:6.2f} base={b:6.2f} lift={lift:+6.2f} pnl={pnl:+7.2f} z={z:+5.2f}{flag}", flush=True)

with open(os.path.join(OUT,'er_shock.json'),'w') as f: json.dump(res,f,indent=1)
print("saved -> er_shock.json")
