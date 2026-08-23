# -*- coding: utf-8 -*-
"""
S638 — سطوح رُند روانی طلا (Round-Number Levels) — «فقط نیمهٔ نخست»
=====================================================================
خانوادهٔ بکر: در ۶۰۶ سند آرشیو هیچ مطالعهٔ اختصاصی سطح رُند وجود ندارد.
مبنای علمی: خوشه‌بندی سفارش‌ها روی اعداد رُند (Osler 2003, "Currency Orders
and Exchange Rate Dynamics") — استاپ‌ها پشت سطح، لیمیت‌ها روی سطح ⇒
دو مکانیزم متضاد قابل‌آزمون:
  M1) عبور-ادامه (breakout): بستهٔ قبلی زیر سطح، بستهٔ فعلی بالای سطح → LONG
      (آبشار استاپ‌های شورت بالای عدد رُند سوخت حرکت است) + آینهٔ شورت.
  M2) پس‌زنی (rejection): high سطح را لمس کرده اما close با حاشیه پایین مانده
      → SHORT فید (دیوار لیمیت‌فروش روی سطح) + آینهٔ لانگ.
شبکهٔ سطح G ∈ {10, 25} دلار — یکنواخت روی TFها، بدون گیلاس‌چینی.
قاعدهٔ S633: hold-out فقط با z منصفانه ≥3 سوزانده می‌شود.
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
for TF in ('M30','H1','H4'):
    df, sl = prep(TF)
    o,h,l,c = df['open'].values, df['high'].values, df['low'].values, df['close'].values
    cs = pd.Series(c); hs=pd.Series(h); ls=pd.Series(l)
    bl = base_side(df, sl, 'long'); bs = base_side(df, sl, 'short')
    res[TF] = {'sl_pip': round(sl,1), 'base_long': bl, 'base_short': bs, 'cells': {}}
    print(f"== {TF} sl={sl:.1f} base_long={bl:.2f} base_short={bs:.2f}")
    for G in (10.0, 25.0):
        lev_below = np.floor(c/G)*G          # نزدیک‌ترین سطح زیر close فعلی
        lev_above = lev_below + G
        c1 = cs.shift(1)
        lev_of_now_below = np.floor(cs/G)*G  # سطحی که الان بالایش بسته‌ایم
        # M1 عبور-ادامه: بستهٔ قبلی زیر همان سطح، فعلی بالا
        m1_long  = (c1 < lev_of_now_below) & (cs > lev_of_now_below)
        lev_of_now_above = np.floor(cs/G)*G + G
        m1_short = (c1 > lev_of_now_above) & (cs < lev_of_now_above)
        # M2 پس‌زنی: high سطح بالایی را لمس، close حداقل 20% G پایین‌تر
        m2_short = (hs >= pd.Series(lev_above)) & (cs <= pd.Series(lev_above) - 0.2*G) & (c1 < pd.Series(lev_above))
        m2_long  = (ls <= pd.Series(lev_below)) & (cs >= pd.Series(lev_below) + 0.2*G) & (c1 > pd.Series(lev_below))
        for name, lo_sig, hi_sig in (('M1break', m1_long, m1_short), ('M2reject', m2_long, m2_short)):
            lo_sig = lo_sig.fillna(False); hi_sig = hi_sig.fillna(False)
            t = se.simulate_trades(df, lo_sig, hi_sig, sl_pip=sl, tp_pip=sl,
                                   asset='XAUUSD', max_hold=48, allow_overlap=False)
            for side, bw in (('long',bl),('short',bs)):
                w,n,pnl = wrn(t, side)
                if w is None or bw is None:
                    print(f"  G{int(G)} {name} {side}: n={n} تهی"); continue
                lift = w-bw; z = lift/(100*np.sqrt(0.25/n)) if n>0 else 0.0
                res[TF]['cells'][f'G{int(G)}_{name}_{side}']={'n':n,'wr':round(w,2),'lift':round(lift,2),'pnl':round(pnl,2),'z':round(z,2)}
                print(f"  G{int(G)} {name:8s} {side:5s}: n={n:4d} wr={w:5.2f} lift={lift:+6.2f} pnl={pnl:+6.2f} z={z:+5.2f}")

with open(os.path.join(OUT,'round_levels.json'),'w') as f:
    json.dump(res, f, indent=1)
print("saved -> round_levels.json")
