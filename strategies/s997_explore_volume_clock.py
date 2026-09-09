# -*- coding: utf-8 -*-
"""
S997 — ساعتِ حجم (Clark 1973 / Ané–Geman 2000: subordinated process) — «فقط نیمهٔ نخست»
=======================================================================================
فرض: بازار در «زمانِ حجم» می‌تپد، نه در زمانِ ساعتی. رکوردهای تازهٔ قیمت (S526: close > max(close[−90..−1]))
روی کندل‌های حجمی (هر کندل = سهمِ ثابتی از حجمِ روزانه، آستانهٔ تطبیقیِ علّی) باید اطلاعاتی‌تر از همان قاعده
روی کندل‌های زمانی هم‌رزولوشن باشند (فالسیفایر P1: lift ساعتِ حجم > lift ساعتِ زمانی).
ساخت: از M5 (data/mt5_full)؛ آستانهٔ کندل = median(حجم روزانهٔ ۲۰ روز قبل)/K؛ K∈{6,12,24} ≈ H4/H2/H1.
قواعد: FH (fresh high → long)، FL (fresh low → short)؛ W∈{55,90}؛ rr∈{1.0,1.5}. کنترل: همان قواعد روی H4/H2/H1 زمانی.
هیچ لایه‌ای در repo کندل حجمی نساخته (S856 فقط پیش‌ثبت «variance clock» بدون حکم).
"""
import sys, os, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'research', 's997_explore'); os.makedirs(OUT, exist_ok=True)

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

def volume_bars(m5, K, ndays=20):
    """کندل حجمی با آستانهٔ تطبیقیِ علّی: thr(day) = median(daily vol of previous ndays)/K."""
    t = m5['time'].values.astype(np.int64); day = t//86400
    v = m5['volume'].values.astype(float); o,h,l,c = (m5[k].values.astype(float) for k in ('open','high','low','close'))
    dv = pd.Series(v).groupby(day).sum()
    thr_day = (dv.shift(1).rolling(ndays, min_periods=10).median()/K)
    thr = thr_day.reindex(day).values
    rows=[]; acc=0.0; bo=None; bh=-np.inf; bl=np.inf
    for i in range(len(t)):
        th = thr[i]
        if np.isnan(th): continue
        if bo is None: bo=o[i]; bh=h[i]; bl=l[i]; acc=0.0
        bh=max(bh,h[i]); bl=min(bl,l[i]); acc+=v[i]
        if acc>=th:
            rows.append((t[i], bo, bh, bl, c[i], acc)); bo=None
    return pd.DataFrame(rows, columns=['time','open','high','low','close','volume'])

def cells_for(df, tag, MH, yrs, res):
    h,l,c = df['high'].values, df['low'].values, df['close'].values; cs=pd.Series(c)
    tr_ = np.maximum(h-l, np.maximum(abs(h-np.roll(c,1)), abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
    sl = float(np.nanmedian(pd.Series(tr_).rolling(100).mean().values[100:]))*1.5/0.1
    res[tag]={'sl_pip':sl,'bars':len(df),'cells':{}}
    print(f"== {tag} sl={sl:.1f} bars={len(df)} mh={MH}", flush=True)
    bases={}
    for W in (55,90):
        nh = (cs > cs.shift(1).rolling(W).max()).fillna(False); nl = (cs < cs.shift(1).rolling(W).min()).fillna(False)
        sigs = {'FH_long': (nh & ~nh.shift(1,fill_value=False)).astype(bool), 'FL_short': (nl & ~nl.shift(1,fill_value=False)).astype(bool)}
        for arm, sig in sigs.items():
            side = 'long' if arm.endswith('long') else 'short'
            for rr in (1.0,1.5):
                tp=sl*rr
                if (side,rr) not in bases: bases[(side,rr)] = base_uncond(df, side, sl, tp, MH)
                b=bases[(side,rr)]; t=run_side(df,sig,side,sl,tp,MH); n=len(t)
                if n<20 or b is None: continue
                w=wr(t); lift=w-b; z=lift/(100*np.sqrt(0.25/n)); pnl=float(t['pnl_pip'].mean())
                ty=yrs[t['entry_bar'].values.astype(int)]
                ypos=sum(1 for y in np.unique(ty) if t['pnl_pip'].values[ty==y].mean()>0); ytot=len(np.unique(ty))
                key=f"W{W}_{arm}_rr{rr}"
                res[tag]['cells'][key]=dict(n=n,wr=round(w,2),base=round(b,2),lift=round(lift,2),pnl=round(pnl,2),z=round(z,2),yrs_pos=f"{ypos}/{ytot}",power=round(lift*np.sqrt(n),1))
                flag=' <==' if (z>=2.5 and lift>=4 and pnl>0) else ''
                print(f"  {key:22s} n={n:5d} wr={w:6.2f} base={b:6.2f} lift={lift:+6.2f} pnl={pnl:+7.2f} z={z:+5.2f} yrs+={ypos}/{ytot} pow={lift*np.sqrt(n):+6.1f}{flag}", flush=True)

res={}
m5 = fd.as_dataframe(fd.load_fast('XAUUSD','M5')); m5 = m5.iloc[:len(m5)//2].reset_index(drop=True)
print(f"M5 first half: {len(m5)} bars, {pd.to_datetime(m5['time'].iloc[0],unit='s')} → {pd.to_datetime(m5['time'].iloc[-1],unit='s')}", flush=True)
for K, MH, TFc in ((6,30,'H4'),(12,40,'H2'),(24,48,'H1')):
    vb = volume_bars(m5, K)
    yrs = pd.to_datetime(vb['time'].values, unit='s').year
    cells_for(vb, f"VOL_K{K}", MH, yrs, res)
    dff = fd.as_dataframe(fd.load_fast('XAUUSD', TFc)); dft = dff.iloc[:len(dff)//2].reset_index(drop=True)
    cells_for(dft, f"TIME_{TFc}", MH, pd.to_datetime(dft['time'].values, unit='s').year, res)
with open(os.path.join(OUT,'volume_clock.json'),'w') as f: json.dump(res,f,indent=1)
print("saved -> volume_clock.json")
