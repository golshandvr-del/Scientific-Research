# -*- coding: utf-8 -*-
"""
S996 — داورِ رسمیِ استخرِ «پارگیِ کانالِ کمترین‌مربعات» — XAUUSD {H4,H6,H8} — نیمهٔ دوم (holdout)
قاعده و اعضا در research/S996_PREREG.md منجمد شده‌اند. ماشینِ استخر = engine/rqs2_pool (دست‌نخورده)
و منطقِ داوری/نولِ آمیخته عیناً از S604/S606 کپی شده.
اجرا: python3 strategies/s996_ols_channel_pool.py
"""
import sys, os, json
import numpy as np, pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from engine import rqs2 as R
import engine.rqs2_pool as rp

W, TH, SEED, PERM_K = 55, 2.0, 996996, 500
N_TRIALS, N_TRIALS_STRESS, SPLIT_FRAC = 215, 1000, 0.70
CARDS = {'H4':30, 'H6':24, 'H8':21}
MEMBERS = [('H4','long'),('H4','short'),('H6','long'),('H6','short'),('H8','short')]   # frozen from first half
FIRST_HALF_LIFT = {('H4','long'):13.90,('H4','short'):7.41,('H6','long'):5.30,('H6','short'):16.98,('H8','short'):17.21}
OUT = os.path.join(ROOT,'results','_s996'); os.makedirs(OUT, exist_ok=True)

def ols_channel(cs, W):
    x = np.arange(W, dtype=float); xm = x.mean(); Sxx = float(((x-xm)**2).sum()); wts=(x-xm)
    ym = cs.rolling(W).mean()
    Sxy = cs.rolling(W).apply(lambda y: float(np.dot(wts, y)), raw=True); slope = Sxy/Sxx
    Syy = cs.rolling(W).apply(lambda y: float(((y-y.mean())**2).sum()), raw=True)
    sig_e = np.sqrt((Syy - slope**2*Sxx).clip(lower=0)/(W-2))
    zres = (cs - (ym + slope*(x[-1]-xm)))/sig_e.replace(0,np.nan)
    return zres, slope

def wr(t): return 100*float((t['outcome']=='win').mean()) if len(t) else None

members=[]; card_meta={}
for TF, MH in CARDS.items():
    dff = fd.as_dataframe(fd.load_fast('XAUUSD', TF)); half=len(dff)//2
    df = dff.iloc[half:].reset_index(drop=True)
    h,l,c = df['high'].values, df['low'].values, df['close'].values; cs=pd.Series(c)
    tr_ = np.maximum(h-l, np.maximum(abs(h-np.roll(c,1)), abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
    sl = float(np.nanmedian(pd.Series(tr_).rolling(100).mean().values[100:]))*1.5/0.1; tp = sl
    zres, slope = ols_channel(cs, W)
    up_x = ((zres> TH)&(zres.shift(1)<= TH)).fillna(False); dn_x = ((zres<-TH)&(zres.shift(1)>=-TH)).fillna(False)
    sigs = {'long': (up_x & (slope>0).fillna(False)).astype(bool), 'short': (dn_x & (slope<0).fillna(False)).astype(bool)}
    empty = pd.Series(False, index=df.index)
    dt = pd.to_datetime(df['time'].values, unit='s').values.astype('datetime64[ns]')
    def sim(side, s2):
        lo_, hi_ = (s2, empty) if side=='long' else (empty, s2)
        t = se.simulate_trades(df, lo_, hi_, sl_pip=sl, tp_pip=tp, asset='XAUUSD', max_hold=MH, allow_overlap=False)
        if len(t)==0 or 'direction' not in t.columns: return t.iloc[0:0]
        return t[t['direction']==side].reset_index(drop=True)
    for side in ('long','short'):
        if (TF,side) not in MEMBERS: continue
        tr = sim(side, sigs[side]); n=len(tr)
        uv=[]
        for st in (3,7,13):
            b = pd.Series(False, index=df.index); b.iloc[::st]=True; v=wr(sim(side,b))
            if v is not None: uv.append(v)
        uncond = max(uv)
        rs = np.random.RandomState(SEED+hash(TF+side)%1000); wrs=[]
        for _ in range(PERM_K):
            pick = rs.choice(len(df), size=n, replace=False); s2=pd.Series(False,index=df.index); s2.iloc[pick]=True
            t=sim(side,s2)
            if len(t): wrs.append(wr(t))
        a=np.array(wrs)
        null = {side: dict(uncond_wr=uncond, perm_mean=float(a.mean()), perm_sd=float(a.std(ddof=1)), perm_max=float(a.max()), perm_k=len(a))}
        other = 'short' if side=='long' else 'long'; null[other] = dict(uncond_wr=None, perm_mean=None, perm_sd=None, perm_max=None, perm_k=None)
        card=f'{TF}-{side}'
        print(f"[{card}] holdout n={n} WR={wr(tr):.2f} uncond={uncond:.2f} perm={a.mean():.2f}±{a.std(ddof=1):.2f} SL={sl:.1f} (holdout lift {wr(tr)-uncond:+.2f}pp)", flush=True)
        g = dict(card=card, tr=tr, dt=dt, lift=FIRST_HALF_LIFT[(TF,side)], sl_pip=sl, tp_pip=tp, null=null, tf=TF, side=side, n=n, wr=wr(tr), uncond=uncond)
        members.append(g); card_meta[card]=dict(n=n, wr=wr(tr), uncond=uncond, sl=sl, first_half_lift=FIRST_HALF_LIFT[(TF,side)], holdout_lift=wr(tr)-uncond, perm_mean=float(a.mean()), perm_sd=float(a.std(ddof=1)))

res = rp.pool_cards([dict(card=g['card'], tr=g['tr'], dt=g['dt'], lift=g['lift']) for g in members])
pool = res['pool']; print(f"pool: n_before={res['n_before']} n_after={res['n_after']} used={res['used']} dropped={res['dropped']}", flush=True)
share = pool['src_card'].value_counts(normalize=True).to_dict()
by = {g['card']: g for g in members}

# blended null (S604 logic) — per side across member cards, weighted by pool share
null={}
for side in ('long','short'):
    nu=du=nm=ns=dp=0.0; kmin=None; pmax=None
    for g in members:
        w=float(share.get(g['card'],0.0)); d=g['null'][side]
        if w<=0 or d.get('uncond_wr') is None: continue
        nu+=d['uncond_wr']*w; du+=w; nm+=d['perm_mean']*w; ns+=(d['perm_sd']**2)*(w**2); dp+=w
        kmin = d['perm_k'] if kmin is None else min(kmin,d['perm_k']); pmax = d['perm_max'] if pmax is None else max(pmax,d['perm_max'])
    null[side]=dict(uncond_wr=nu/du if du else None, perm_mean=nm/dp if dp else None, perm_sd=float(np.sqrt(ns))/dp if dp else None, perm_max=pmax, perm_k=kmin)
sl_med=float(sum(by[c]['sl_pip']*w for c,w in share.items())); tp_med=float(sum(by[c]['tp_pip']*w for c,w in share.items()))

STEP=3600*1_000_000_000
t_lo=int(pool['t_entry'].values.astype(np.int64).min()); t_hi=int(pool['t_exit'].values.astype(np.int64).max())
axis_t=np.arange(t_lo-STEP, t_hi+2*STEP, STEP, dtype=np.int64); axis_dt=axis_t.astype('datetime64[ns]')
d1h=fd.load_fast('XAUUSD','H1')
ref_t=pd.to_datetime(d1h['time'], unit='s').values.astype('datetime64[ns]').astype(np.int64); ref_c=np.asarray(d1h['close'],float)
axis_close=ref_c[np.clip(np.searchsorted(ref_t, axis_t,'right')-1,0,len(ref_c)-1)]
pool=pool.copy()
pool['entry_bar']=np.clip(np.searchsorted(axis_t,pool['t_entry'].values.astype(np.int64),'left'),0,len(axis_t)-1)
pool['exit_bar']=np.maximum(np.clip(np.searchsorted(axis_t,pool['t_exit'].values.astype(np.int64),'left'),0,len(axis_t)-1),pool['entry_bar'])
pool=pool.sort_values('exit_bar',kind='mergesort').reset_index(drop=True)
te=pool['t_entry'].values.astype(np.int64); split_ns=int(np.quantile(te,SPLIT_FRAC)); holdout=te>=split_ns
common=dict(sl_pip=sl_med,tp_pip=tp_med,bar_time=axis_dt,null=null,close=axis_close,holdout_mask=holdout,allow_overlap=False)
r=R.compute_rqs2(pool,'XAUUSD',n_trials=N_TRIALS,**common)
r_st=R.compute_rqs2(pool,'XAUUSD',n_trials=N_TRIALS_STRESS,**common)

def line(tag, rr_):
    g=rr_.get('gates',{}); gs=' '.join(f"H{i}:{'✓' if g.get(f'H{i}') else '✗'}" for i in range(11)); m=rr_.get('metrics',{})
    return f"{tag} | {rr_.get('verdict')} RQS2={rr_.get('rqs2_score')} | n={m.get('n_trades')} WR={m.get('win_rate')} PF={m.get('profit_factor')} lift={m.get('skill_lift_pp')} z={m.get('skill_z')} p_perm={m.get('skill_p_perm')} | {gs}"
L1=line(f"S996_OlsChannelBreakPool (n_trials={N_TRIALS})", r); L2=line(f"S996 STRESS (n_trials={N_TRIALS_STRESS})", r_st)
print("\n"+L1+"\n"+L2, flush=True)
pool.to_csv(os.path.join(OUT,'pool_trades.csv'), index=False)
json.dump(dict(cards=card_meta, share=share, null=null, sl_med=sl_med, tp_med=tp_med, official=r, stress=r_st, pool_sel=res.get('selection'), dropped=res['dropped'], seed=SEED, n_trials=N_TRIALS),
          open(os.path.join(OUT,'verdict.json'),'w'), indent=1, default=str)
v=r.get('verdict'); sc=r.get('rqs2_score')
md_name=f"S996_OlsChannelBreakPool_Xauusd_H4H6H8_rqs2_{sc}_{v}.md"
cards_tbl='\n'.join(f"| {c} | {m['n']} | {m['wr']:.2f} | {m['uncond']:.2f} | {m['holdout_lift']:+.2f} | {m['first_half_lift']:+.2f} | {m['sl']:.1f} | {share.get(c,0):.2f} |" for c,m in card_meta.items())
md=f"""# S996 — OlsChannelBreakPool — XAUUSD {{H4,H6,H8}} — {v} (RQS2 v2.6 = {sc})

**دانشمند:** لاگرانژ (S990–S999) · **پیش‌ثبت:** `research/S996_PREREG.md` (کامیت قبل از هر عدد نیمهٔ دوم) · **runner:** `strategies/s996_ols_channel_pool.py`
**رکوردها:** `results/_s996/` · **داده:** `data/mt5_full/` ۱۵.۶ سال، نیمهٔ دوم هر کارت · ماشین استخر: `engine/rqs2_pool` (دست‌نخورده)

## حکم موتور — عیناً
```
{L1}
{L2}
```
## قاعده (منجمد)
OLS روی close در پنجرهٔ W=55؛ zres=(close−fit)/σ_e؛ رویداد = عبورِ تازهٔ zres از ±2.0 هم‌جهت با شیب؛ SL=1.5×ATR100 (میانهٔ کارت)، TP=SL؛ max_hold H4:30/H6:24/H8:21؛ FIFO تقویمی.

## کارت‌ها (نیمهٔ دوم)
| card | n | WR | uncond | holdout lift | first-half lift | SL pip | share |
|---|---|---|---|---|---|---|---|
{cards_tbl}
- استخر: n_before={res['n_before']} n_after={res['n_after']} · used={res['used']} · dropped={res['dropped']}
- نول آمیخته: {json.dumps(null, default=str)}
- SL/TP وزنی: {sl_med:.1f}/{tp_med:.1f} · seed={SEED} · n_trials={N_TRIALS} (۲۱۰ سلول + ۵ تصمیم انجماد)

## متریک‌ها (رسمی)
```
{json.dumps({k:v for k,v in r.get('metrics',{}).items() if isinstance(v,(int,float,str,bool,type(None)))}, indent=1, default=str)[:2000]}
```
notes: {r.get('notes')}

— لاگرانژ، دههٔ S990–S999
"""
open(os.path.join(ROOT,'results',md_name),'w').write(md); print(f"MD -> results/{md_name}", flush=True)
