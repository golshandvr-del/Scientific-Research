# -*- coding: utf-8 -*-
"""
S637 — انتقال فرضیهٔ جهش-ادامه به TFهای پایین‌تر — «فقط نیمهٔ نخست»
=====================================================================
پیشینه: S950 (ACCEPT, H8) و S602 (ACCEPT, D1+H8) هر دو ادامهٔ شوک در طلا را
با مقیاس شرطی جهش-مقاوم اثبات کرده‌اند. هیچ‌کدام H1/H2/H4 را نیازموده‌اند.
فرضیهٔ S637: جذبِ تدریجیِ اطلاعاتِ پرش (Merton 1976) در H4/H2/H1 هم باید
ردی بگذارد — مگر آنکه نویز microstructure در این مقیاس‌ها غالب شود.

طرح: BV (Bipower Variation, جهش-مقاوم) پنجرهٔ 89 causal تا t-1؛
جهش = |r_t| > k·σ_BV؛ هم‌راستایی درفت = sign(close[t-1]-close[t-90]).
k ∈ {2.0, 2.6, 3.2} یکنواخت روی همهٔ TFها — بدون گیلاس‌چینی per-TF.
قاعدهٔ S633: تا z منصفانه ≥3 نشود hold-out سوزانده نمی‌شود.
قاعدهٔ S636: خانوادهٔ بکر است (هیچ hold-out سوخته در دههٔ ما ندارد).
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'research', 's637_explore')
os.makedirs(OUT, exist_ok=True)

W = 89          # پنجرهٔ BV و درفت (فیبوناچی — همان S950 برای قابلیت مقایسه)
KS = (2.0, 2.6, 3.2)
MH = {'H1': 34, 'H2': 34, 'H4': 34}   # همان max_hold سبک S950

def prep(TF):
    d = fd.load_fast('XAUUSD', TF); df = fd.as_dataframe(d)
    df = df.iloc[:len(df)//2].reset_index(drop=True)
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    tr_ = np.maximum(h-l, np.maximum(abs(h-np.roll(c,1)), abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
    atr = pd.Series(tr_).rolling(W).mean()
    sl = float(np.nanmedian(atr.values[W:])) * 1.618 / 0.1   # pip
    return df, sl

def wrn(t, side):
    t = t[t['direction']==side]
    if len(t)==0: return None, 0, None
    return 100*float((t['outcome']=='win').mean()), len(t), float(t['pnl_pip'].mean())

def base_side(df, sl, side):
    vals=[]; empty=pd.Series(False, index=df.index)
    for stride in (3,7,13):
        b=pd.Series(False,index=df.index); b.iloc[::stride]=True
        lo_,hi_=(b,empty) if side=='long' else (empty,b)
        t=se.simulate_trades(df,lo_,hi_,sl_pip=sl,tp_pip=sl,asset='XAUUSD',max_hold=34,allow_overlap=False)
        w,_,_=wrn(t,side)
        if w is not None: vals.append(w)
    return max(vals) if vals else None

res={}
for TF in ('H1','H2','H4'):
    df, sl = prep(TF)
    c = df['close'].values
    r = np.zeros(len(c)); r[1:] = np.diff(np.log(c))
    absr = np.abs(r)
    bp = pd.Series(absr).mul(pd.Series(absr).shift(1))
    sigBV = np.sqrt((np.pi/2.0) * bp.rolling(W).mean()).shift(1)   # causal تا t-1
    drift = pd.Series(c) - pd.Series(c).shift(W+1)                  # close[t-1]-close[t-90] با shift پایین
    drift = drift.shift(1)
    bl = base_side(df, sl, 'long'); bs = base_side(df, sl, 'short')
    res[TF] = {'sl_pip': round(sl,1), 'base_long': bl, 'base_short': bs, 'cells': {}}
    print(f"== {TF} sl={sl:.1f}pip base_long={bl:.2f} base_short={bs:.2f}")
    for k in KS:
        jump_up = (pd.Series(r) >  k*sigBV) & (drift > 0)
        jump_dn = (pd.Series(r) < -k*sigBV) & (drift < 0)
        jump_up = jump_up.fillna(False); jump_dn = jump_dn.fillna(False)
        t = se.simulate_trades(df, jump_up, jump_dn, sl_pip=sl, tp_pip=sl,
                               asset='XAUUSD', max_hold=MH[TF], allow_overlap=False)
        for side, bw in (('long', bl), ('short', bs)):
            w, n, pnl = wrn(t, side)
            if w is None or bw is None:
                print(f"  k={k} {side}: n={n} — تهی"); continue
            lift = w - bw
            z = lift / (100*np.sqrt(0.25/n)) if n>0 else 0.0
            res[TF]['cells'][f'k{k}_{side}'] = {'n':n,'wr':round(w,2),'lift':round(lift,2),
                                                'pnl':round(pnl,2),'z':round(z,2)}
            print(f"  k={k} {side:5s}: n={n:4d} wr={w:5.2f} lift={lift:+6.2f} pnl={pnl:+6.2f} z={z:+5.2f}")

with open(os.path.join(OUT,'jump_lower_tf.json'),'w') as f:
    json.dump(res, f, indent=1)
print("saved -> jump_lower_tf.json")
