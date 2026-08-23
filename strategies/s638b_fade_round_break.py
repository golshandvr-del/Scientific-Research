# -*- coding: utf-8 -*-
"""
S638b — فیدِ شکست سطح رُند (آینهٔ مستقیم s638) — «فقط نیمهٔ نخست»
===================================================================
یافتهٔ s638: ادامهٔ شکست سطح رُند در طلا یکنواخت ضدمهارت است
(قوی‌ترین: M30 G10 down-break continuation short z=-3.92).
آزمون آینه با شبیه‌سازی مستقیم (اسپرد تقارن WR را می‌شکند، استنتاج ممنوع):
  فید down-break  → LONG در بستهٔ زیرِ سطح رُند (خریدِ دیپ از میان عدد رُند)
  فید up-break    → SHORT در بستهٔ بالای سطح رُند
باند یکنواخت: G∈{10,25} × TF∈{M30,H1} (H4 در s638 سیگنال ضعیف بود).
توجه چندگانگی: این موج دوم همان خانواده است — در صورت رسیدن به PREREG
n_trials باید کل سلول‌های s638+s638b را بشمارد.
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'research', 's638_explore')
os.makedirs(OUT, exist_ok=True)

def prep(TF):
    d = fd.load_fast('XAUUSD', TF); df = fd.as_dataframe(d)
    df = df.iloc[:len(df)//2].reset_index(drop=True)
    h,l,c = df['high'].values, df['low'].values, df['close'].values
    tr_ = np.maximum(h-l, np.maximum(abs(h-np.roll(c,1)), abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
    sl = float(np.nanmedian(pd.Series(tr_).rolling(100).mean().values[100:]))*1.5/0.1
    return df, sl

def wrn(t, side):
    t = t[t['direction']==side]
    if len(t)==0: return None,0,None
    return 100*float((t['outcome']=='win').mean()), len(t), float(t['pnl_pip'].mean())

def base_side(df, sl, side):
    vals=[]; empty=pd.Series(False,index=df.index)
    for stride in (3,7,13):
        b=pd.Series(False,index=df.index); b.iloc[::stride]=True
        lo_,hi_=(b,empty) if side=='long' else (empty,b)
        t=se.simulate_trades(df,lo_,hi_,sl_pip=sl,tp_pip=sl,asset='XAUUSD',max_hold=48,allow_overlap=False)
        w,_,_=wrn(t,side)
        if w is not None: vals.append(w)
    return max(vals) if vals else None

res={}
for TF in ('M30','H1'):
    df, sl = prep(TF)
    c = df['close'].values; cs = pd.Series(c); c1 = cs.shift(1)
    bl = base_side(df, sl, 'long'); bs = base_side(df, sl, 'short')
    res[TF]={'sl_pip':round(sl,1),'base_long':bl,'base_short':bs,'cells':{}}
    print(f"== {TF} sl={sl:.1f} base_long={bl:.2f} base_short={bs:.2f}")
    for G in (10.0, 25.0):
        lev_below = np.floor(cs/G)*G
        lev_above = lev_below + G
        down_break = (c1 > lev_above) & (cs < lev_above)   # از بالا سطح را شکسته پایین
        up_break   = (c1 < lev_below) & (cs > lev_below)   # از پایین سطح را شکسته بالا
        fade_long  = down_break.fillna(False)   # فید ریزش → LONG
        fade_short = up_break.fillna(False)     # فید صعود → SHORT
        t = se.simulate_trades(df, fade_long, fade_short, sl_pip=sl, tp_pip=sl,
                               asset='XAUUSD', max_hold=48, allow_overlap=False)
        for side, bw in (('long',bl),('short',bs)):
            w,n,pnl = wrn(t, side)
            if w is None or bw is None:
                print(f"  G{int(G)} fade {side}: n={n} تهی"); continue
            lift=w-bw; z=lift/(100*np.sqrt(0.25/n)) if n>0 else 0.0
            res[TF]['cells'][f'G{int(G)}_fade_{side}']={'n':n,'wr':round(w,2),'lift':round(lift,2),'pnl':round(pnl,2),'z':round(z,2)}
            print(f"  G{int(G)} fade {side:5s}: n={n:4d} wr={w:5.2f} lift={lift:+6.2f} pnl={pnl:+6.2f} z={z:+5.2f}")

with open(os.path.join(OUT,'s638b_fade.json'),'w') as f:
    json.dump(res,f,indent=1)
print("saved -> s638b_fade.json")
