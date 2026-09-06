# -*- coding: utf-8 -*-
"""
S99x — اجراکنندهٔ رسمی احکام دههٔ S990–S999 (لاگرانژ)
=====================================================
usage: python3 s99x_official_runner.py <layer>   e.g. s990
هر لایه: نیمهٔ دوم | یک اجرا | نول ① سخت‌ترین stride گیت‌خورده | نول ② جایگشت K=500 |
compute_rqs2 با n_trials صادقانهٔ پیش‌ثبت‌شده (research/S99x_PREREG.md) | MD خودکار.
قاعدهٔ هر لایه در تابع rule_<layer>(df) تعریف می‌شود و باید پیش از اجرا کامیت شده باشد.
"""
import sys, os, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from engine import rqs2 as R

PERM_K = 500
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')

def med_atr(h,l,c,w):
    tr_ = np.maximum(h-l, np.maximum(abs(h-np.roll(c,1)), abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
    return float(np.nanmedian(pd.Series(tr_).rolling(w).mean().values[w:]))

def r2_slope(c, w):
    s = pd.Series(c); t = np.arange(w, dtype=float); tm=t.mean(); tv=((t-tm)**2).sum()
    def f(x):
        xm=x.mean(); xv=((x-xm)**2).sum()
        return np.nan if xv<=0 else ((t-tm)*(x-xm)).sum()/np.sqrt(tv*xv)
    corr = s.rolling(w).apply(f, raw=True)
    return (corr**2), np.sign(corr)

# ---------------- قواعد منجمد ----------------
CFG = {
 's990': dict(name='R2TrendBirthLong', tf='H1', side='long', mh=48, nt=27, seed=990990),
 's991': dict(name='AutocorrMomLong',  tf='H8', side='long', mh=21, nt=159, seed=991991),
 's992': dict(name='ErShockLong',      tf='H1', side='long', mh=48, nt=146, seed=992992),
 's993': dict(name='ErShockCalmShort', tf='H1', side='short', mh=48, nt=200, seed=993993),
 's994': dict(name='SeasonalVolumeShockLong', tf='M30', side='long', mh=64, nt=64, seed=994994),
 's995': dict(name='SeasonalRangeShockLong', tf='H2', side='long', mh=40, nt=160, seed=995995),
}

def rule_s990(df):
    h,l,c = df['high'].values, df['low'].values, df['close'].values
    sl = med_atr(h,l,c,100)*1.5/0.1
    r2, sg = r2_slope(c, 21)
    was_low = (r2.shift(1).rolling(3).min() < 0.40)
    edge = ((r2 > 0.80) & was_low).fillna(False).astype(bool)
    edge = edge & ~edge.shift(1, fill_value=False)
    gate = (sg > 0).fillna(False).astype(bool)
    sig = (edge & gate)
    return sig, gate, sl, sl

def rule_s991(df):
    h,l,c = df['high'].values, df['low'].values, df['close'].values
    sl = med_atr(h,l,c,100)*1.5/0.1
    r = pd.Series(np.r_[0.0, np.diff(np.log(c))])
    rho = r.rolling(34).corr(r.shift(1)).shift(1)
    gate = (rho > 0.20).fillna(False).astype(bool)
    big = (r.abs() > r.abs().rolling(34).quantile(0.5).shift(1)).fillna(False)
    sig = (gate & big & (r > 0)).astype(bool)
    return sig, gate, sl, sl

def rule_s992(df):
    h,l,c = df['high'].values, df['low'].values, df['close'].values
    sl = med_atr(h,l,c,100)*1.5/0.1
    cs = pd.Series(c); net = cs - cs.shift(13); path = cs.diff().abs().rolling(13).sum()
    er = net.abs()/path.replace(0,np.nan)
    edge = ((er > 0.70) & (er.shift(1).rolling(3).min() < 0.30)).fillna(False).astype(bool)
    edge = edge & ~edge.shift(1, fill_value=False)
    gate = (net > 0).fillna(False).astype(bool)
    return (edge & gate), gate, sl, sl*1.5

def rule_s993(df):
    h,l,c = df['high'].values, df['low'].values, df['close'].values
    sl = med_atr(h,l,c,100)*1.5/0.1
    cs = pd.Series(c); net = cs - cs.shift(13); path = cs.diff().abs().rolling(13).sum()
    er = net.abs()/path.replace(0,np.nan)
    edge = ((er > 0.70) & (er.shift(1).rolling(3).min() < 0.30)).fillna(False).astype(bool)
    edge = edge & ~edge.shift(1, fill_value=False)
    tr_ = np.maximum(h-l, np.maximum(abs(h-np.roll(c,1)), abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
    atr13 = pd.Series(tr_).rolling(13).mean()
    calm = (atr13 <= atr13.shift(1).rolling(233).median()).fillna(False).astype(bool)
    gate = ((net < 0).fillna(False).astype(bool)) & calm
    return (edge & gate), gate, sl, sl*1.5

def rule_s994(df):
    h,l,c,o = df['high'].values, df['low'].values, df['close'].values, df['open'].values
    sl = med_atr(h,l,c,100)*1.5/0.1
    t = df['time'].values.astype(np.int64); slot = t % 86400
    v = pd.Series(df['volume'].values.astype(float)); rv = pd.Series(np.nan, index=df.index)
    for s_ in np.unique(slot):
        idx = np.where(slot==s_)[0]; vs = v.iloc[idx]
        med = vs.shift(1).rolling(20, min_periods=10).median()
        rv.iloc[idx] = (vs/med.replace(0,np.nan)).values
    sig = ((rv >= 3.0) & pd.Series(c > o)).fillna(False).astype(bool)
    gate = pd.Series(True, index=df.index)
    return sig, gate, sl, sl*1.5

def rule_s995(df):
    h,l,c,o = df['high'].values, df['low'].values, df['close'].values, df['open'].values
    sl = med_atr(h,l,c,100)*1.5/0.1
    t = df['time'].values.astype(np.int64); slot = t % 86400
    v = pd.Series((h-l).astype(float)); rr = pd.Series(np.nan, index=df.index)
    for s_ in np.unique(slot):
        idx = np.where(slot==s_)[0]; vs = v.iloc[idx]
        med = vs.shift(1).rolling(20, min_periods=10).median()
        rr.iloc[idx] = (vs/med.replace(0,np.nan)).values
    rng = np.where((h-l)>0, h-l, np.nan); rho = pd.Series(np.abs(c-o)/rng).fillna(0)
    sig = ((rr >= 3.5) & (rho >= 0.618) & pd.Series(c > o)).fillna(False).astype(bool)
    gate = pd.Series(True, index=df.index)
    return sig, gate, sl, sl*1.5

# ---------------- اجرا ----------------
layer = sys.argv[1]; cfg = CFG[layer]
TF, SIDE, MH, NT, SEED = cfg['tf'], cfg['side'], cfg['mh'], cfg['nt'], cfg['seed']
d = fd.load_fast('XAUUSD', TF); df_full = fd.as_dataframe(d)
half = len(df_full)//2
df = df_full.iloc[half:].reset_index(drop=True)
sig, gate, sl_pip, tp_pip = globals()[f'rule_{layer}'](df)
sig = pd.Series(np.asarray(sig,bool), index=df.index); gate = pd.Series(np.asarray(gate,bool), index=df.index)
empty = pd.Series(False, index=df.index)
lo_sig, hi_sig = (sig, empty) if SIDE=='long' else (empty, sig)
print(f"[{layer}] {cfg['name']} TF={TF} side={SIDE} holdout_bars={len(df)} sig_bars={int(sig.sum())} SL={sl_pip:.1f} TP={tp_pip:.1f}", flush=True)

tr = se.simulate_trades(df, lo_sig, hi_sig, sl_pip=sl_pip, tp_pip=tp_pip, asset='XAUUSD', max_hold=MH, allow_overlap=False)
tr = tr[tr['direction']==SIDE].reset_index(drop=True)
n = len(tr); wr = 100*float((tr['outcome']=='win').mean()) if n else 0.0
print(f"trades n={n} WR={wr:.2f}% pnl={float(tr['pnl_pip'].mean()) if n else 0:.3f}", flush=True)

def sim_side(s2):
    lo_, hi_ = (s2, empty) if SIDE=='long' else (empty, s2)
    t = se.simulate_trades(df, lo_, hi_, sl_pip=sl_pip, tp_pip=tp_pip, asset='XAUUSD', max_hold=MH, allow_overlap=False)
    return t[t['direction']==SIDE]
def uncond(stride):
    b = pd.Series(False, index=df.index); b.iloc[::stride]=True
    t = sim_side((b & gate))
    return 100*float((t['outcome']=='win').mean()) if len(t) else None
uv = [v for v in (uncond(s) for s in (3,7,13)) if v is not None]
uncond_wr = max(uv); print(f"uncond hardest={uncond_wr:.2f}", flush=True)

rs = np.random.RandomState(SEED); pool = np.where(gate.values)[0]; n_sig = int(sig.sum()); wrs=[]
for _ in range(PERM_K):
    pick = rs.choice(pool, size=min(n_sig,len(pool)), replace=False)
    s2 = pd.Series(False, index=df.index); s2.iloc[pick]=True
    t = sim_side(s2)
    if len(t): wrs.append(100*float((t['outcome']=='win').mean()))
a = np.array(wrs)
null = {SIDE: dict(uncond_wr=uncond_wr, perm_mean=float(a.mean()), perm_sd=float(a.std(ddof=1)), perm_max=float(a.max()), perm_k=len(a))}
print(f"perm mean={a.mean():.2f} sd={a.std(ddof=1):.2f} k={len(a)}", flush=True)

OUTD = os.path.join(ROOT,'results',f'_{layer}'); os.makedirs(OUTD, exist_ok=True)
with open(os.path.join(OUTD,'null_model.json'),'w') as f: json.dump(null,f,indent=1)
res = R.compute_rqs2(tr, 'XAUUSD', sl_pip=sl_pip, tp_pip=tp_pip, bar_time=df['time'], close=df['close'],
                     null=null, n_trials=NT, split_bar=int(0.70*len(df)))
with open(os.path.join(OUTD,f'{TF}_rqs2.json'),'w') as f: json.dump(res,f,indent=1,default=str)
tr.to_csv(os.path.join(OUTD,f'{TF}_trades.csv'), index=False)

g = res.get('gates',{}); gs = ' '.join(f"H{i}:{'✓' if g.get(f'H{i}') else '✗'}" for i in range(11))
m = res.get('metrics',{}); v = res.get('verdict'); sc = res.get('rqs2_score')
lift = m.get('skill_lift_pp'); z = m.get('z', m.get('skill_z')); pp = m.get('p_perm', m.get('skill_p_perm')); pf = m.get('pf', m.get('profit_factor'))
line = f"S{layer[1:]}_{cfg['name']}_{TF} | {v} RQS2={sc} | n={n} WR={wr:.2f}% PF={pf} lift={lift} z={z} p_perm={pp} | {gs}"
print("\n"+line, flush=True)
md_name = f"S{layer[1:]}_{cfg['name']}_Xauusd_{TF}_rqs2_{sc}_{v}.md"
md = f"""# S{layer[1:]} — {cfg['name']} — XAUUSD-{TF} — {v} (RQS2 v2.6 = {sc})

**دانشمند:** لاگرانژ (S990–S999) · **پیش‌ثبت:** `research/S{layer[1:]}_PREREG.md` (کامیت قبل از هر عدد نیمهٔ دوم)
**runner:** `strategies/s99x_official_runner.py {layer}` · **رکوردها:** `results/_{layer}/` · **داده:** `data/mt5_full/` ۱۵.۶y، نیمهٔ دوم ({len(df)} کندل)

## حکم موتور — عیناً
```
{line}
```
- side={SIDE} · SL={sl_pip:.1f} TP={tp_pip:.1f} پیپ · max_hold={MH} · allow_overlap=False · اسپرد 3.3 پیپ
- نول: سخت‌ترین stride گیت‌خورده = {uncond_wr:.2f} · جایشگت K={len(a)} mean={a.mean():.2f} sd={a.std(ddof=1):.2f} max={a.max():.2f} · seed={SEED}
- n_trials={NT} (صادقانه: تعداد سلول‌های اکتشاف نیمهٔ اول)

## گیت‌ها
{gs}

## متریک‌ها (از موتور)
```
{json.dumps(m, indent=1, default=str)[:1800]}
```

— لاگرانژ، دههٔ S990–S999
"""
with open(os.path.join(ROOT,'results',md_name),'w') as f: f.write(md)
print(f"MD -> results/{md_name}", flush=True)
