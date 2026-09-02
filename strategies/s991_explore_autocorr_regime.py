# -*- coding: utf-8 -*-
"""
S991 — رژیم خودهمبستگی مرتبهٔ ۱ بازده (Lo–MacKinlay 1988) — «فقط نیمهٔ نخست»
==============================================================================
فرضیه: علامت ρ₁ غلتان بازده‌های لگاریتمی (پنجرهٔ W، علّی: shift(1)) رژیم را تعیین می‌کند:
  ρ₁ > +θ ⇒ رژیم مومنتوم: هم‌جهت با بازده کندل قبل معامله کن.
  ρ₁ < −θ ⇒ رژیم بازگشت: خلاف‌جهت بازده کندل قبل معامله کن.
سیگنال فقط روی کندل‌های با |r_{t}| > q-چندک (حرکت معنادار؛ حذف نویز).
پایه = سخت‌ترین stride درون همان رژیم (گیت)، جهت‌به‌جهت مستقل. z_fair = lift/(100·√(0.25/n)).
خانواده در بانک نتایج بکر است (grep autocorr/lag1 = 0).
"""
import sys, os, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'research', 's991_explore')
os.makedirs(OUT, exist_ok=True)

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
        v = wr(run_side(df, (b&gate).fillna(False).astype(bool), side, sl, mh))
        if v is not None and (best is None or v>best): best=v
    return best

res = {}
for TF, MH in (('H1',48), ('H4',34), ('H8',21), ('D1',13)):
    d = fd.load_fast('XAUUSD', TF); dff = fd.as_dataframe(d)
    df = dff.iloc[:len(dff)//2].reset_index(drop=True)
    h,l,c = df['high'].values, df['low'].values, df['close'].values
    tr_ = np.maximum(h-l, np.maximum(abs(h-np.roll(c,1)), abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
    sl = float(np.nanmedian(pd.Series(tr_).rolling(100).mean().values[100:]))*1.5/0.1
    r = pd.Series(np.r_[0.0, np.diff(np.log(c))])
    res[TF] = {'sl_pip': sl, 'cells': {}}
    print(f"== {TF} sl={sl:.1f} bars={len(df)}", flush=True)
    for W in (34, 89, 233):
        rho = r.rolling(W).corr(r.shift(1)).shift(1)   # علّی: ρ₁ تا کندل قبل
        for th in (0.10, 0.20):
            for q in (0.0, 0.5):
                big = (r.abs() > r.abs().rolling(W).quantile(q).shift(1)) if q>0 else pd.Series(True,index=r.index)
                for regime in ('mom','rev'):
                    g = (rho > th) if regime=='mom' else (rho < -th)
                    gate = g.fillna(False).astype(bool)
                    for side in ('long','short'):
                        # mom: long اگر r>0؛ rev: long اگر r<0
                        if regime=='mom': dir_ok = (r>0) if side=='long' else (r<0)
                        else:             dir_ok = (r<0) if side=='long' else (r>0)
                        sig = (gate & big & dir_ok).fillna(False).astype(bool)
                        if int(sig.sum()) < 20: continue
                        t = run_side(df, sig, side, sl, MH); n=len(t)
                        if n < 20: continue
                        w = wr(t); b = base_gated(df, gate, side, sl, MH)
                        if b is None: continue
                        lift = w-b; z = lift/(100*np.sqrt(0.25/n)); pnl=float(t['pnl_pip'].mean())
                        key=f"W{W}_th{th}_q{q}_{regime}_{side}"
                        res[TF]['cells'][key]=dict(n=n,wr=round(w,2),base=round(b,2),lift=round(lift,2),pnl=round(pnl,3),z=round(z,2))
                        flag = ' <==' if (z>=2.0 and lift>=4) else ''
                        print(f"  {key:30s} n={n:5d} wr={w:6.2f} base={b:6.2f} lift={lift:+6.2f} pnl={pnl:+7.2f} z={z:+5.2f}{flag}", flush=True)

with open(os.path.join(OUT,'autocorr_regime.json'),'w') as f: json.dump(res,f,indent=1)
print("saved -> autocorr_regime.json")
