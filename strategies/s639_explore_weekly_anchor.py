# -*- coding: utf-8 -*-
"""
S639 — لنگرِ بازشدنِ هفتگی (Weekly-Open Anchor) — «فقط نیمهٔ نخست»
====================================================================
خانوادهٔ بکر (grep آرشیو: صفر مطالعه). مبنای علمی: قیمت بازشدن هفته
لنگرِ مرجع نهنگ‌ها/ETFهاست (anchoring bias, Tversky & Kahneman 1974؛
TWAP هفتگی صندوق‌ها حول open می‌چرخد). دو مکانیزم متضاد:
  M1) ادامه (momentum): فاصلهٔ نرمالیزهٔ close از weekly_open در جهت
      مثبت → LONG (جریان هفتگی ادامه دارد) + آینه.
  M2) بازگشت (reversion): فاصلهٔ کشیده → معامله در خلاف جهت.
فاصله با ATR نرمالیزه: dist = (close - w_open)/ATR100.
باند یکنواخت آستانه q ∈ {0.5, 1.0, 2.0} × TF ∈ {H1, H4} — بدون گیلاس‌چینی.
روزهای دوشنبه حذف نمی‌شوند (لنگر تازه، فاصله کوچک — خودش فیلتر طبیعی است).
قاعدهٔ S633: hold-out فقط با z منصفانه ≥3.
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'research', 's639_explore')
os.makedirs(OUT, exist_ok=True)

def prep(TF):
    d = fd.load_fast('XAUUSD', TF); df = fd.as_dataframe(d)
    df = df.iloc[:len(df)//2].reset_index(drop=True)
    h,l,c = df['high'].values, df['low'].values, df['close'].values
    tr_ = np.maximum(h-l, np.maximum(abs(h-np.roll(c,1)), abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
    atr = pd.Series(tr_).rolling(100).mean()
    sl = float(np.nanmedian(atr.values[100:]))*1.5/0.1
    return df, sl, atr

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
for TF in ('H1','H4'):
    df, sl, atr = prep(TF)
    tt = pd.to_datetime(df['time'].values, unit='s')
    # شناسهٔ هفته: iso year*100+week
    iso = tt.isocalendar()
    wk = (np.asarray(iso.year)*100 + np.asarray(iso.week))
    wk = pd.Series(wk, index=df.index)
    is_new_week = wk != wk.shift(1)
    w_open = pd.Series(np.where(is_new_week, df['open'].values, np.nan), index=df.index).ffill()
    dist = (pd.Series(df['close'].values) - w_open) / atr.replace(0, np.nan)
    dist_c = dist.shift(0)   # سیگنال روی کندل بسته؛ ورود در open بعدی توسط انجین
    bl = base_side(df, sl, 'long'); bs = base_side(df, sl, 'short')
    res[TF]={'sl_pip':round(sl,1),'base_long':bl,'base_short':bs,'cells':{}}
    print(f"== {TF} sl={sl:.1f} base_long={bl:.2f} base_short={bs:.2f}")
    for q in (0.5, 1.0, 2.0):
        mom_long  = (dist_c >  q).fillna(False)
        mom_short = (dist_c < -q).fillna(False)
        # M1 ادامه
        t1 = se.simulate_trades(df, mom_long, mom_short, sl_pip=sl, tp_pip=sl,
                                asset='XAUUSD', max_hold=48, allow_overlap=False)
        # M2 بازگشت (سیگنال‌ها جابه‌جا)
        t2 = se.simulate_trades(df, mom_short, mom_long, sl_pip=sl, tp_pip=sl,
                                asset='XAUUSD', max_hold=48, allow_overlap=False)
        for name, t in (('mom', t1), ('rev', t2)):
            for side, bw in (('long',bl),('short',bs)):
                w,n,pnl = wrn(t, side)
                if w is None or bw is None:
                    print(f"  q{q} {name} {side}: n={n} تهی"); continue
                lift=w-bw; z=lift/(100*np.sqrt(0.25/n)) if n>0 else 0.0
                res[TF]['cells'][f'q{q}_{name}_{side}']={'n':n,'wr':round(w,2),'lift':round(lift,2),'pnl':round(pnl,2),'z':round(z,2)}
                print(f"  q{q} {name} {side:5s}: n={n:4d} wr={w:5.2f} lift={lift:+6.2f} pnl={pnl:+6.2f} z={z:+5.2f}")

with open(os.path.join(OUT,'weekly_anchor.json'),'w') as f:
    json.dump(res,f,indent=1)
print("saved -> weekly_anchor.json")
