# -*- coding: utf-8 -*-
"""
S63x — اجراکنندهٔ رسمی احکام دههٔ S630–S639 (پیش‌ثبت: research/S630_S639_OFFICIAL_PREREG.md)
==============================================================================================
usage: python3 s63x_official_runner.py <layer>   e.g.  s630
هر لایه: نیمهٔ دوم | یک اجرا | نول ① سخت‌ترین stride گیت‌خورده | نول ② جایگشت K=500 |
compute_rqs2 با n_trials صادقانهٔ پیش‌ثبت‌شده | حکم موتور = کلمهٔ نهایی | MD خودکار.
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from engine import rqs2 as R

PERM_K = 500
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')

CFG = {
 's630': dict(name='IbsShortRegime',   tf='H1', side='short', mh=64, nt=4,  seed=630630),
 's633': dict(name='HeikinRun6Long',   tf='H6', side='long',  mh=64, nt=12, seed=633633),
 's634': dict(name='Hour08Short',      tf='H1', side='short', mh=64, nt=24, seed=634634),
 's635': dict(name='Hour20Long',       tf='H1', side='long',  mh=64, nt=24, seed=635635),
 's636': dict(name='IbsLongNoMorning', tf='H1', side='long',  mh=64, nt=15, seed=636636),
 's637': dict(name='JumpShort',        tf='H4', side='short', mh=34, nt=18, seed=637637),
 's638': dict(name='RoundRejectShort', tf='H4', side='short', mh=48, nt=32, seed=638638),
 's639': dict(name='WeeklyAnchorLong', tf='H1', side='long',  mh=48, nt=24, seed=639639),
}

layer = sys.argv[1]
cfg = CFG[layer]
TF, SIDE, MH, NT, SEED = cfg['tf'], cfg['side'], cfg['mh'], cfg['nt'], cfg['seed']

d = fd.load_fast('XAUUSD', TF)
df_full = fd.as_dataframe(d)
half = len(df_full)//2
df = df_full.iloc[half:].reset_index(drop=True)
h, l, c, o = df['high'].values, df['low'].values, df['close'].values, df['open'].values
cs = pd.Series(c)
tr_ = np.maximum(h-l, np.maximum(abs(h-np.roll(c,1)), abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
hours = pd.to_datetime(df['time'].values, unit='s').hour

def med_atr(w): return float(np.nanmedian(pd.Series(tr_).rolling(w).mean().values[w:]))

# ---------- قاعدهٔ منجمد هر لایه ----------
gate = pd.Series(True, index=df.index)
if layer == 's630':
    sl_pip = med_atr(100)*1.5/0.1
    rng = h-l; ibs = np.where(rng>0,(c-l)/np.where(rng>0,rng,1.0),0.5)
    ik = pd.Series(ibs).rolling(5).mean()
    dn = (cs < cs.rolling(144).mean()).fillna(False)
    sig = ((ik.shift(1)<=0.765)&(ik>0.765)&dn).fillna(False)
    gate = dn
elif layer == 's633':
    sl_pip = med_atr(100)*1.5/0.1
    ha_c = (o+h+l+c)/4.0
    ha_o = np.zeros(len(c)); ha_o[0]=o[0]
    for i in range(1,len(c)): ha_o[i]=(ha_o[i-1]+ha_c[i-1])/2.0
    bull = ha_c > ha_o
    run = np.zeros(len(c),dtype=int); run[0]=1 if bull[0] else -1
    for i in range(1,len(c)):
        run[i]=(run[i-1]+1 if run[i-1]>0 else 1) if bull[i] else (run[i-1]-1 if run[i-1]<0 else -1)
    sig = pd.Series(run==6, index=df.index)
elif layer == 's634':
    sl_pip = med_atr(100)*1.5/0.1
    sig = pd.Series(hours==8, index=df.index)
elif layer == 's635':
    sl_pip = med_atr(100)*1.5/0.1
    sig = pd.Series(hours==20, index=df.index)
elif layer == 's636':
    sl_pip = med_atr(100)*1.5/0.1
    rng = h-l; ibs = np.where(rng>0,(c-l)/np.where(rng>0,rng,1.0),0.5)
    ik = pd.Series(ibs).rolling(5).mean()
    up = (cs > cs.rolling(144).mean()).fillna(False)
    win = pd.Series(~np.isin(hours,[3,4,5,6,7,8,9]), index=df.index)
    sig = ((ik<0.28)&up&win).fillna(False)
    gate = (up&win).fillna(False)
elif layer == 's637':
    sl_pip = med_atr(89)*1.618/0.1
    r = np.zeros(len(c)); r[1:] = np.diff(np.log(c))
    ar = np.abs(r)
    bp = pd.Series(ar).mul(pd.Series(ar).shift(1))
    sig_bv = np.sqrt((np.pi/2.0)*bp.rolling(89).mean()).shift(1)
    drift = (cs - cs.shift(90)).shift(1)
    sig = ((pd.Series(r) < -3.2*sig_bv)&(drift<0)).fillna(False)
    gate = (drift<0).fillna(False)
elif layer == 's638':
    sl_pip = med_atr(100)*1.5/0.1
    G = 10.0
    lev_above = np.floor(cs/G)*G + G
    c1 = cs.shift(1)
    sig = ((pd.Series(h)>=lev_above)&(cs<=lev_above-0.2*G)&(c1<lev_above)).fillna(False)
elif layer == 's639':
    sl_pip = med_atr(100)*1.5/0.1
    tt = pd.to_datetime(df['time'].values, unit='s')
    iso = tt.isocalendar()
    wk = pd.Series(np.asarray(iso.year)*100+np.asarray(iso.week), index=df.index)
    w_open = pd.Series(np.where(wk!=wk.shift(1), o, np.nan), index=df.index).ffill()
    atr100 = pd.Series(tr_).rolling(100).mean()
    dist = (cs - w_open)/atr100.replace(0,np.nan)
    sig = (dist>1.0).fillna(False)

tp_pip = sl_pip
empty = pd.Series(False, index=df.index)
lo_sig, hi_sig = (sig, empty) if SIDE=='long' else (empty, sig)
print(f"[{layer}] {cfg['name']} TF={TF} side={SIDE} holdout_bars={len(df)} sig_bars={int(sig.sum())} SL=TP={sl_pip:.1f}", flush=True)

tr = se.simulate_trades(df, lo_sig, hi_sig, sl_pip=sl_pip, tp_pip=tp_pip,
                        asset='XAUUSD', max_hold=MH, allow_overlap=False)
tr = tr[tr['direction']==SIDE].reset_index(drop=True)
n = len(tr); wr = 100*float((tr['outcome']=='win').mean()) if n else 0.0
print(f"trades n={n} WR={wr:.2f}% pnl={float(tr['pnl_pip'].mean()) if n else 0:.3f}", flush=True)

# نول ① سخت‌ترین stride گیت‌خورده — شبیه‌سازی مستقل همین سمت
def uncond(stride):
    b = pd.Series(False, index=df.index); b.iloc[::stride]=True
    s2 = (b & gate).fillna(False)
    lo_, hi_ = (s2, empty) if SIDE=='long' else (empty, s2)
    t = se.simulate_trades(df, lo_, hi_, sl_pip=sl_pip, tp_pip=tp_pip,
                           asset='XAUUSD', max_hold=MH, allow_overlap=False)
    t = t[t['direction']==SIDE]
    return 100*float((t['outcome']=='win').mean()) if len(t) else None

uv = [v for v in (uncond(s) for s in (3,7,13)) if v is not None]
uncond_wr = max(uv)
print(f"uncond hardest={uncond_wr:.2f}", flush=True)

# نول ② جایگشت درون گیت K=500
rs = np.random.RandomState(SEED)
pool = np.where(gate.values)[0]
n_sig = int(sig.sum())
wrs = []
for _ in range(PERM_K):
    pick = rs.choice(pool, size=min(n_sig, len(pool)), replace=False)
    s2 = pd.Series(False, index=df.index); s2.iloc[pick]=True
    lo_, hi_ = (s2, empty) if SIDE=='long' else (empty, s2)
    t = se.simulate_trades(df, lo_, hi_, sl_pip=sl_pip, tp_pip=tp_pip,
                           asset='XAUUSD', max_hold=MH, allow_overlap=False)
    t = t[t['direction']==SIDE]
    if len(t): wrs.append(100*float((t['outcome']=='win').mean()))
a = np.array(wrs)
null = {SIDE: dict(uncond_wr=uncond_wr, perm_mean=float(a.mean()), perm_sd=float(a.std(ddof=1)),
                   perm_max=float(a.max()), perm_k=len(a))}
print(f"perm mean={a.mean():.2f} sd={a.std(ddof=1):.2f} k={len(a)}", flush=True)

OUTD = os.path.join(ROOT, 'results', f'_{layer}')
os.makedirs(OUTD, exist_ok=True)
with open(os.path.join(OUTD,'null_model.json'),'w') as f: json.dump(null,f,indent=1)

res = R.compute_rqs2(tr, 'XAUUSD', sl_pip=sl_pip, tp_pip=tp_pip,
                     bar_time=df['time'], close=df['close'],
                     null=null, n_trials=NT, split_bar=int(0.70*len(df)))
with open(os.path.join(OUTD,f'{TF}_rqs2.json'),'w') as f: json.dump(res,f,indent=1,default=str)
tr.to_csv(os.path.join(OUTD,f'{TF}_trades.csv'), index=False)

g = res.get('gates', {})
gs = ' '.join(f"H{i}:{'✓' if g.get(f'H{i}') else '✗'}" for i in range(11))
m = res.get('metrics', {})
verdict = res.get('verdict'); score = res.get('rqs2_score')
line = (f"{layer.upper()}_{cfg['name']}_{TF} | {verdict} RQS2={score} | n={n} WR={wr:.2f}% "
        f"PF={m.get('profit_factor')} lift={m.get('skill_lift_pp')}pp z={m.get('skill_z')} "
        f"p_perm={m.get('skill_p_perm')} | {gs}")
print("\n"+line, flush=True)

# MD خودکار
num = layer[1:].upper()
md_name = f"S{num}_{cfg['name']}_Xauusd_{TF}_rqs2_{score}_{verdict}.md"
md = f"""# S{num} — {cfg['name']} · XAUUSD-{TF} · حکم رسمی: {verdict} (RQS2={score})

> **پیش‌ثبت:** `research/S630_S639_OFFICIAL_PREREG.md` (کامیت شده قبل از اجرا) · n_trials={NT} · seed={SEED}
> **حکم موتور RQS2 v2.6 — کلمهٔ نهایی، دست‌نخورده:**

```
{line}
```

## قاعدهٔ منجمد
سمت: {SIDE} · SL=TP={sl_pip:.1f} pip · max_hold={MH} · allow_overlap=False · نیمهٔ دوم داده

## اعداد
- n={n} · WR={wr:.2f}% · uncond hardest={uncond_wr:.2f} · perm_mean={a.mean():.2f} sd={a.std(ddof=1):.2f} K={len(a)}
- آرتیفکت‌ها: `results/_{layer}/{{{TF}_rqs2.json, {TF}_trades.csv, null_model.json}}`

— لاگرانژ، دههٔ S630–S639
"""
with open(os.path.join(ROOT,'results',md_name),'w') as f: f.write(md)
print(f"MD -> results/{md_name}", flush=True)
