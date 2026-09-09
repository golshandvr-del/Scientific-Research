# -*- coding: utf-8 -*-
"""S997 داور رسمی — رکورد تازه روی کندل‌های حجمی K=12 (نیمهٔ دوم M5). قاعده در research/S997_PREREG.md منجمد است."""
import sys, os, json
import numpy as np, pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from engine import rqs2 as R
from strategies.s997_explore_volume_clock import volume_bars  # همان سازندهٔ کندل حجمی (بدون تغییر)
K, W, MH, RR, NT, SEED, PERM_K = 12, 90, 40, 1.5, 50, 997997, 500
m5 = fd.as_dataframe(fd.load_fast('XAUUSD','M5')); m5 = m5.iloc[len(m5)//2:].reset_index(drop=True)
df = volume_bars(m5, K)
print(f"M5 holdout {len(m5)} bars → {len(df)} volume bars; {pd.to_datetime(df['time'].iloc[0],unit='s')} → {pd.to_datetime(df['time'].iloc[-1],unit='s')}", flush=True)
h,l,c = df['high'].values, df['low'].values, df['close'].values; cs=pd.Series(c)
tr_ = np.maximum(h-l, np.maximum(abs(h-np.roll(c,1)), abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
sl = float(np.nanmedian(pd.Series(tr_).rolling(100).mean().values[100:]))*1.5/0.1; tp = sl*RR
nh = (cs > cs.shift(1).rolling(W).max()).fillna(False); nl = (cs < cs.shift(1).rolling(W).min()).fillna(False)
lo_sig = (nh & ~nh.shift(1,fill_value=False)).astype(bool); hi_sig = (nl & ~nl.shift(1,fill_value=False)).astype(bool)
empty = pd.Series(False, index=df.index)
def sim(lo, hi): return se.simulate_trades(df, lo, hi, sl_pip=sl, tp_pip=tp, asset='XAUUSD', max_hold=MH, allow_overlap=False)
def wr(t): return 100*float((t['outcome']=='win').mean()) if len(t) else None
tr = sim(lo_sig, hi_sig).reset_index(drop=True); n=len(tr)
print(f"sig long={int(lo_sig.sum())} short={int(hi_sig.sum())} trades n={n} WR={wr(tr):.2f} pnl={tr['pnl_pip'].mean():.3f} SL={sl:.1f} TP={tp:.1f}", flush=True)
null={}; rs=np.random.RandomState(SEED)
for side, s_ in (('long',lo_sig),('short',hi_sig)):
    uv=[]
    for st in (3,7,13):
        b=pd.Series(False,index=df.index); b.iloc[::st]=True
        t = sim(b, empty) if side=='long' else sim(empty, b); v=wr(t)
        if v is not None: uv.append(v)
    ns=int(s_.sum()); wrs=[]
    for _ in range(PERM_K):
        pick=rs.choice(len(df), size=ns, replace=False); s2=pd.Series(False,index=df.index); s2.iloc[pick]=True
        t = sim(s2, empty) if side=='long' else sim(empty, s2)
        if len(t): wrs.append(wr(t))
    a=np.array(wrs); null[side]=dict(uncond_wr=max(uv), perm_mean=float(a.mean()), perm_sd=float(a.std(ddof=1)), perm_max=float(a.max()), perm_k=len(a))
    print(f"[{side}] uncond hardest={max(uv):.2f} perm={a.mean():.2f}±{a.std(ddof=1):.2f}", flush=True)
OUTD=os.path.join(ROOT,'results','_s997'); os.makedirs(OUTD, exist_ok=True)
json.dump(null, open(os.path.join(OUTD,'null_model.json'),'w'), indent=1)
res=R.compute_rqs2(tr,'XAUUSD',sl_pip=sl,tp_pip=tp,bar_time=df['time'],close=df['close'],null=null,n_trials=NT,split_bar=int(0.70*len(df)))
json.dump(res, open(os.path.join(OUTD,'VOLK12_rqs2.json'),'w'), indent=1, default=str); tr.to_csv(os.path.join(OUTD,'VOLK12_trades.csv'), index=False); df.to_csv(os.path.join(OUTD,'VOLK12_bars.csv'), index=False)
g=res.get('gates',{}); gs=' '.join(f"H{i}:{'✓' if g.get(f'H{i}') else '✗'}" for i in range(11)); m=res.get('metrics',{}); v=res.get('verdict'); sc=res.get('rqs2_score')
line=f"S997_VolumeClockFreshRecord_VOLK12 | {v} RQS2={sc} | n={n} WR={wr(tr):.2f}% PF={m.get('profit_factor')} lift={m.get('skill_lift_pp')} z={m.get('skill_z')} p_perm={m.get('skill_p_perm')} | {gs}"
print("\n"+line, flush=True)
md_name=f"S997_VolumeClockFreshRecord_Xauusd_VOLK12_rqs2_{sc}_{v}.md"
md=f"""# S997 — VolumeClockFreshRecord — XAUUSD volume bars K=12 (from M5) — {v} (RQS2 v2.6 = {sc})

**دانشمند:** لاگرانژ (S990–S999) · **پیش‌ثبت:** `research/S997_PREREG.md` (کامیت قبل از هر عدد نیمهٔ دوم) · **runner:** `strategies/s997_volume_clock_runner.py`
**رکوردها:** `results/_s997/` · **داده:** `data/mt5_full/XAUUSD_M5.csv` ۱۵.۶ سال؛ نیمهٔ دوم ({len(m5)} کندل M5 → {len(df)} کندل حجمی)

## حکم موتور — عیناً
```
{line}
```
- قاعده: کندل حجمی (آستانه = median(حجم روزانهٔ ۲۰ روز قبل)/12)؛ W=90 رکورد تازهٔ close (لانگ) / کف تازه (شورت)؛ SL={sl:.1f} TP={tp:.1f} پیپ؛ max_hold={MH}؛ allow_overlap=False
- نول: {json.dumps(null)} · seed={SEED} · n_trials={NT}
- P1 (ساعت حجم > ساعت زمانی) در اکتشاف نیمهٔ اول در K=6 رد شد، در K=12 حاشیه‌ای.

## گیت‌ها
{gs}

## متریک‌ها (از موتور)
```
{json.dumps({k:vv for k,vv in m.items() if isinstance(vv,(int,float,str,bool,type(None)))}, indent=1, default=str)[:1800]}
```
— لاگرانژ، دههٔ S990–S999
"""
open(os.path.join(ROOT,'results',md_name),'w').write(md); print(f"MD -> results/{md_name}", flush=True)
