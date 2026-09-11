# -*- coding: utf-8 -*-
"""
S999 — رکوردِ تودرتو (Nested Record: رکورد تازهٔ H1 درونِ رژیمِ رکوردِ H4/H8) — «فقط نیمهٔ نخست»
==================================================================================================
درسِ دهه: لبهٔ رکورد تازه (S526/S1511/S1520/S1521) روی H6/H8 واقعی است اما در TF پایین (H1..H3) می‌میرد.
فرض لاگرانژ: اطلاعاتِ رکورد در TF پایین با «رژیمِ رکورد» در TF بالا هم‌ساز می‌شود — رکورد H1 که در حالی رخ می‌دهد که
H4 (یا H8) خود اخیراً (≤ L کندلِ بالادستی) رکورد ۹۰ زده است. کنترل‌ها (P1 قانون S965): رکورد H1 خام (بدون گیت) و رکورد H1
با گیتِ معکوس (بالادستی دور از رکورد). هر لایه‌ای که «tf بالا × رکورد tf پایین» را آزموده باشد در repo نیست (۰ ارجاع nested).
شبکه: W1∈{55,90}؛ parent∈{H4,H8}؛ L∈{1,3}؛ side long/short (آینه)؛ rr∈{1.0,1.5}. بازو: nested / raw / anti.
"""
import sys, os, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'research', 's999_explore'); os.makedirs(OUT, exist_ok=True)

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

def parent_regime(df1, dfp, W=90, L=1):
    """برای هر کندل H1: آیا آخرین کندلِ *بسته‌شدهٔ* والد (قبل از زمان بازشدن H1) در L کندل اخیر خود رکورد ۹۰ زده؟ (علّی)"""
    cp = pd.Series(dfp['close'].values); nh = (cp > cp.shift(1).rolling(W).max()).fillna(False); nl = (cp < cp.shift(1).rolling(W).min()).fillna(False)
    rec_hi = nh.rolling(L, min_periods=1).max().astype(bool).values; rec_lo = nl.rolling(L, min_periods=1).max().astype(bool).values
    tp_open = dfp['time'].values.astype(np.int64); step = int(np.median(np.diff(tp_open))); tp_close = tp_open + step
    t1 = df1['time'].values.astype(np.int64)
    idx = np.searchsorted(tp_close, t1, 'right') - 1          # آخرین والدی که قبل از t1 بسته شده
    ok = idx >= 0; idx = np.clip(idx, 0, len(tp_close)-1)
    return pd.Series(rec_hi[idx] & ok, index=df1.index), pd.Series(rec_lo[idx] & ok, index=df1.index)

res={}
TF1, MH = 'H1', 48
d1 = fd.as_dataframe(fd.load_fast('XAUUSD', TF1)); df = d1.iloc[:len(d1)//2].reset_index(drop=True)
h,l,c = df['high'].values, df['low'].values, df['close'].values; cs=pd.Series(c)
yrs = pd.to_datetime(df['time'].values, unit='s').year
tr_ = np.maximum(h-l, np.maximum(abs(h-np.roll(c,1)), abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
sl = float(np.nanmedian(pd.Series(tr_).rolling(100).mean().values[100:]))*1.5/0.1
print(f"== H1 first half sl={sl:.1f} bars={len(df)}", flush=True)
parents = {p: fd.as_dataframe(fd.load_fast('XAUUSD', p)) for p in ('H4','H8')}
res={'sl_pip':sl,'cells':{}}
for W1 in (55,90):
    nh1 = (cs > cs.shift(1).rolling(W1).max()).fillna(False); nl1 = (cs < cs.shift(1).rolling(W1).min()).fillna(False)
    e_hi = (nh1 & ~nh1.shift(1,fill_value=False)).astype(bool); e_lo = (nl1 & ~nl1.shift(1,fill_value=False)).astype(bool)
    for P in ('H4','H8'):
        for L in (1,3):
            g_hi, g_lo = parent_regime(df, parents[P], 90, L)
            for side, edge, g in (('long', e_hi, g_hi), ('short', e_lo, g_lo)):
                arms = {'nested': (edge & g, g), 'raw': (edge, pd.Series(True,index=df.index)), 'anti': (edge & ~g, ~g)}
                for arm,(sig,gate) in arms.items():
                    if arm!='nested' and (P!='H4' or L!=1): continue   # کنترل‌ها یک بار برای هر (W1,side)؛ anti فقط با H4/L1
                    for rr in (1.0,1.5):
                        tp=sl*rr; t=run_side(df,sig.astype(bool),side,sl,tp,MH); n=len(t)
                        if n<20: continue
                        b=base_gated(df,gate.astype(bool),side,sl,tp,MH)
                        if b is None: continue
                        w=wr(t); lift=w-b; z=lift/(100*np.sqrt(0.25/n)); pnl=float(t['pnl_pip'].mean())
                        ty=yrs[t['entry_bar'].values.astype(int)]
                        ypos=sum(1 for y in np.unique(ty) if t['pnl_pip'].values[ty==y].mean()>0); ytot=len(np.unique(ty))
                        key=f"W{W1}_{P}_L{L}_{side}_{arm}_rr{rr}" if arm=='nested' else f"W{W1}_{side}_{arm}_rr{rr}"
                        res['cells'][key]=dict(n=n,wr=round(w,2),base=round(b,2),lift=round(lift,2),pnl=round(pnl,2),z=round(z,2),yrs_pos=f"{ypos}/{ytot}",power=round(lift*np.sqrt(n),1),gate_pct=round(100*float(gate.mean()),1))
                        flag=' <==' if (z>=2.5 and lift>=4 and pnl>0) else ''
                        print(f"  {key:34s} n={n:5d} wr={w:6.2f} base={b:6.2f} lift={lift:+6.2f} pnl={pnl:+7.2f} z={z:+5.2f} yrs+={ypos}/{ytot} gate%={100*gate.mean():4.1f}{flag}", flush=True)
with open(os.path.join(OUT,'nested_record.json'),'w') as f: json.dump(res,f,indent=1)
print("saved -> nested_record.json")
