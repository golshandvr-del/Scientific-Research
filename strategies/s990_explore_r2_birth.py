# -*- coding: utf-8 -*-
"""
S990 — تولد روند: شتاب r² رگرسیون خطی — «فقط نیمهٔ نخست»
==========================================================
فرضیه (docs/indicators/statistical.md §4، «استفادهٔ خلاقانه»): افزایش سریع r²
= گذار رنج→روند. سیگنال = لبه (r2 از زیر lo به بالای hi می‌پرد در ≤ k کندل)،
جهت = علامت شیب رگرسیون (جهت‌مندی S522). لبه نه حالت (S963)، مشتق نه انتگرال (S616).
خط پایه = سخت‌ترین stride درون همان گیت جهت (شیب مثبت/منفی).
z_fair = lift / (100*sqrt(0.25/n)).
"""
import sys, os, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'research', 's990_explore')
os.makedirs(OUT, exist_ok=True)

def r2_slope(c, w):
    """r² و شیب رگرسیون خطی close بر زمان در پنجرهٔ w (علّی)."""
    s = pd.Series(c)
    t = np.arange(w, dtype=float)
    tm = t.mean(); tv = ((t-tm)**2).sum()
    def f(x):
        xm = x.mean(); cov = ((t-tm)*(x-xm)).sum()
        xv = ((x-xm)**2).sum()
        if xv <= 0: return np.nan
        return cov/np.sqrt(tv*xv)
    corr = s.rolling(w).apply(f, raw=True)
    return (corr**2).values, np.sign(corr.values)

def wr(t): return 100*float((t['outcome']=='win').mean()) if len(t) else None

def run_side(df, sig, side, sl, mh):
    empty = pd.Series(False, index=df.index)
    lo, hi = (sig, empty) if side=='long' else (empty, sig)
    t = se.simulate_trades(df, lo, hi, sl_pip=sl, tp_pip=sl, asset='XAUUSD', max_hold=mh, allow_overlap=False)
    return t[t['direction']==side]

def base_gated(df, gate, side, sl, mh):
    best=None
    for st in (3,7,13):
        b = pd.Series(False, index=df.index); b.iloc[::st]=True
        v = wr(run_side(df, (b&gate).fillna(False), side, sl, mh))
        if v is not None and (best is None or v>best): best=v
    return best

res = {}
for TF, MH in (('H1',48), ('H4',34), ('H8',21)):
    d = fd.load_fast('XAUUSD', TF); dff = fd.as_dataframe(d)
    df = dff.iloc[:len(dff)//2].reset_index(drop=True)
    h,l,c = df['high'].values, df['low'].values, df['close'].values
    tr_ = np.maximum(h-l, np.maximum(abs(h-np.roll(c,1)), abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
    sl = float(np.nanmedian(pd.Series(tr_).rolling(100).mean().values[100:]))*1.5/0.1
    res[TF] = {'sl_pip': sl, 'cells': {}}
    print(f"== {TF} sl={sl:.1f} bars={len(df)}", flush=True)
    for W in (21, 34, 55):
        r2, sgn = r2_slope(c, W)
        r2s = pd.Series(r2); sg = pd.Series(sgn)
        for lo_th, hi_th, k in ((0.3,0.7,3),(0.4,0.8,3),(0.3,0.7,5),(0.5,0.85,3)):
            # لبه: اکنون r2>hi و در k کندل قبل r2<lo
            was_low = (r2s.shift(1).rolling(k).min() < lo_th)
            edge = ((r2s > hi_th) & was_low).fillna(False)
            # فقط اولین کندل لبه (لبه نه حالت)
            edge = (edge & ~edge.shift(1).fillna(False))
            for side in ('long','short'):
                dir_ok = (sg>0) if side=='long' else (sg<0)
                sig = (edge & dir_ok).fillna(False)
                gate = dir_ok.fillna(False)
                n_sig = int(sig.sum())
                if n_sig < 15: 
                    continue
                t = run_side(df, sig, side, sl, MH)
                n = len(t)
                if n < 15: continue
                w = wr(t); b = base_gated(df, gate, side, sl, MH)
                lift = w-b if b is not None else None
                z = lift/(100*np.sqrt(0.25/n)) if lift is not None else None
                pnl = float(t['pnl_pip'].mean())
                key = f"W{W}_lo{lo_th}_hi{hi_th}_k{k}_{side}"
                res[TF]['cells'][key] = dict(n=n, wr=round(w,2), base=round(b,2) if b else None,
                                            lift=round(lift,2) if lift is not None else None,
                                            pnl=round(pnl,3), z=round(z,2) if z is not None else None)
                print(f"  {key:32s} n={n:5d} wr={w:6.2f} base={b:6.2f} lift={lift:+6.2f} pnl={pnl:+7.2f} z={z:+5.2f}", flush=True)

with open(os.path.join(OUT,'r2_birth.json'),'w') as f: json.dump(res, f, indent=1)
print("saved -> r2_birth.json")
