# -*- coding: utf-8 -*-
"""
S630b — موجِ بهبودِ IBS پس از REJECT — «فقط نیمهٔ نخست» (قانون بهبود)
======================================================================
یافتهٔ hold-out: سمتِ long زنده (+1.4pp)، سمتِ short ضدمهارت در روند سکولار.
فرضیه‌های بهبود (چندگانهٔ هم‌زمان، طبق قانون):
  A) long-only (حذف کامل شورت)
  B) long-only + گیتِ روند (close > SMA144 → همسو با روند بخر در اشباع فروش)
  C) long-only + گیتِ ضدروند (close < SMA144 → فقط در افت بخر) — رقیب B
  D) دوطرفه ولی شورت فقط زیر SMA144 (شورت پشت گیتِ رژیم نزولی)
سنجش در برابر خطِ مبنای بی‌قیدِ «همان گیت» — تا بتای گیت با آلفای سیگنال قاطی نشود.
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'research', 's630_explore')
K_IBS, THR = 5, 0.235
FALSE = None

def wrn(t, side=None):
    if side is not None and 'direction' in t:
        t = t[t['direction'] == side]
    if len(t) == 0: return None, 0
    return round(100*float((t['outcome']=='win').mean()),2), len(t)

def uncond_wr_gated(df, gate_long, gate_short, sl_pip, tp_pip, stride=7):
    """خط مبنای بی‌قیدِ گیت‌خورده: ورود هر stride کندل ولی فقط جایی که گیت باز است."""
    base = pd.Series(False, index=df.index); base.iloc[::stride] = True
    lo = (base & gate_long).fillna(False) if gate_long is not None else pd.Series(False, index=df.index)
    hi = (base & gate_short).fillna(False) if gate_short is not None else pd.Series(False, index=df.index)
    t = se.simulate_trades(df, lo, hi, sl_pip=sl_pip, tp_pip=tp_pip,
                           asset='XAUUSD', max_hold=64, allow_overlap=False)
    return wrn(t,'long'), wrn(t,'short')

all_res = {}
for TF in ['M30', 'H1', 'H2']:
    d = fd.load_fast('XAUUSD', TF)
    df = fd.as_dataframe(d)
    df = df.iloc[:len(df)//2].reset_index(drop=True)   # فقط نیمهٔ اول
    h,l,c = df['high'].values, df['low'].values, df['close'].values
    rng = h-l
    ibs = np.where(rng>0,(c-l)/np.where(rng>0,rng,1.0),0.5)
    ibs_k = pd.Series(ibs).rolling(K_IBS).mean()
    lo_sig = ((ibs_k.shift(1)>=THR)&(ibs_k<THR)).fillna(False)
    hi_sig = ((ibs_k.shift(1)<=1-THR)&(ibs_k>1-THR)).fillna(False)
    tr_ = np.maximum(h-l, np.maximum(abs(h-np.roll(c,1)), abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
    atr = pd.Series(tr_).rolling(100).mean().values
    sl_pip = float(np.nanmedian(atr))*1.5/0.1; tp_pip = sl_pip
    sma144 = pd.Series(c).rolling(144).mean()
    up = (pd.Series(c) > sma144).fillna(False)
    dn = (pd.Series(c) < sma144).fillna(False)
    none_gate = pd.Series(True, index=df.index)

    arms = {
      'A_long_only':        (lo_sig, None, none_gate, None),
      'B_long_uptrend':     (lo_sig & up, None, up, None),
      'C_long_downtrend':   (lo_sig & dn, None, dn, None),
      'D_short_gated_down': (lo_sig, hi_sig & dn, none_gate, dn),
    }
    res = {}
    for name,(lo,hi,gl,gs) in arms.items():
        lo = lo.fillna(False)
        hi = hi.fillna(False) if hi is not None else pd.Series(False, index=df.index)
        t = se.simulate_trades(df, lo, hi, sl_pip=sl_pip, tp_pip=tp_pip,
                               asset='XAUUSD', max_hold=64, allow_overlap=False)
        (bl, bln),(bs, bsn) = uncond_wr_gated(df, gl, gs, sl_pip, tp_pip)
        lw, ln = wrn(t,'long'); sw, sn = wrn(t,'short')
        lift_l = None if (lw is None or bl is None) else round(lw-bl,2)
        lift_s = None if (sw is None or bs is None) else round(sw-bs,2)
        rec = dict(n=len(t), long=dict(n=ln,wr=lw,base=bl,lift=lift_l),
                   short=dict(n=sn,wr=sw,base=bs,lift=lift_s),
                   pnl=round(float(t['pnl_pip'].mean()),3) if len(t) else None)
        res[name]=rec
        print(TF, name, rec, flush=True)
    all_res[TF] = dict(sl_pip=sl_pip, arms=res)

with open(f'{OUT}/s630b_improve.json','w') as f:
    json.dump(all_res,f,ensure_ascii=False,indent=1)
print('saved -> s630b_improve.json')
