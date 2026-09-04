# -*- coding: utf-8 -*-
"""
S645 — PsarFlip — فازِ اکتشاف (مسیرِ C، فقط نیمهٔ اولِ داده)
===========================================================
فرضیه: Parabolic SAR (Wilder 1978؛ step=0.02, max=0.2 — متعارف، منجمد) — رویدادِ
گسستهٔ «برگشتِ SAR» (flip). دو گونه:
  • plain : هر flip (SAR از بالای قیمت به زیر → لانگ؛ آینه → شورت)
  • aged  : flip پس از روندِ بالغ (طولِ فازِ قبلی ≥ 13 کندل) — فیلترِ ساختاریِ Wilder
دو حالت: cont (پی‌گیریِ flip) / fade (محوِ flip). PSAR پرتکرار است → n≥200 در هر
سلول (قانونِ S644). خانواده در S500–S980 بکر است (S873 فقط در grep نام برده).
درس‌ها: TF درشت (S383)؛ نولِ هم‌جهت (S385)؛ RR=1؛ تشخیصِ S643 با n≥200.
نیمهٔ دوم هرگز لمس نمی‌شود.
"""
import json, os, sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import indicator_bank as ib
from engine import scalp_engine as se
from tools import s434_fast_data as fd

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'results', '_s645_explore')
os.makedirs(OUT, exist_ok=True)

PIP = 0.1
MAX_HOLD = 64
TFS = ['M15','M30','H1','H2','H3','H4','H6','H8','H12','D1']
AGE_MIN = 13

def stats(tr):
    if tr is None or not len(tr): return 0, 0.0, 0.0
    p = tr['pnl_pip'].values
    return len(p), 100.0*(p>0).mean(), float(p.mean())

def run_tf(tf):
    t0=time.time()
    d = fd.load_fast('XAUUSD', tf); df_all = fd.as_dataframe(d)
    half = len(df_all)//2
    df = df_all.iloc[:half].reset_index(drop=True)
    sar = ib.compute('psar', df).values
    o,h,l,c = df['open'].values, df['high'].values, df['low'].values, df['close'].values
    below = sar < c                       # فازِ صعودی
    pbelow = np.roll(below,1); pbelow[0]=below[0]
    bull = below & ~pbelow                # flip به صعودی
    bear = ~below & pbelow                # flip به نزولی
    # طولِ فازِ قبلی
    flips = bull | bear
    age = np.zeros(len(c), int); run = 0
    for i in range(len(c)):
        if flips[i]: age[i] = run; run = 1
        else: run += 1
    strong = age >= AGE_MIN
    pc = np.roll(c,1); pc[0]=c[0]
    tr_ = np.maximum(h-l, np.maximum(abs(h-pc), abs(l-pc)))
    slb = float(np.nanmedian(pd.Series(tr_).rolling(100).mean().values))/PIP
    sl = max(1.0, round(1.5*slb,1)); tp = sl
    zeros = np.zeros(len(df),bool); ones = np.ones(len(df),bool)
    _,wrbL,_ = stats(se.simulate_trades(df,ones,zeros,sl_pip=sl,tp_pip=tp,asset='XAUUSD',max_hold=MAX_HOLD))
    _,wrbS,_ = stats(se.simulate_trades(df,zeros,ones,sl_pip=sl,tp_pip=tp,asset='XAUUSD',max_hold=MAX_HOLD))
    cells=[]
    for variant, bu, be in [('plain', bull, bear), ('aged', bull&strong, bear&strong)]:
        for mode in ('cont','fade'):
            ls, ss = (bu, be) if mode=='cont' else (be, bu)
            for side, sig, zero, wrb in (('long', ls, zeros, wrbL), ('short', ss, zeros, wrbS)):
                if side=='long':
                    tr = se.simulate_trades(df,sig,zero,sl_pip=sl,tp_pip=tp,asset='XAUUSD',max_hold=MAX_HOLD)
                else:
                    tr = se.simulate_trades(df,zero,sig,sl_pip=sl,tp_pip=tp,asset='XAUUSD',max_hold=MAX_HOLD)
                n,wr,ep = stats(tr); lift = wr-wrb
                cells.append({'variant':variant,'mode':mode,'side':side,'n':n,
                              'wr':round(wr,2),'blind':round(wrb,2),'lift':round(lift,2),
                              'exp_pip':round(ep,2),'lsn':round(lift*np.sqrt(max(n,0)),1)})
    res = {'tf':tf,'src':d.get('src'),'bars_first_half':int(half),'sl_pip':sl,
           'cost_to_sl_pct':round(100*3.3/sl,1),'blind_long_wr':round(wrbL,2),
           'blind_short_wr':round(wrbS,2),'n_bull_events':int(bull.sum()),
           'n_bear_events':int(bear.sum()),'cells':cells,'sec':round(time.time()-t0,1)}
    json.dump(res, open(os.path.join(OUT,f'{tf}.json'),'w'), ensure_ascii=False, indent=1)
    return res

if __name__=='__main__':
    for tf in TFS:
        try:
            r = run_tf(tf)
        except Exception as e:
            print(f'[S645] {tf}: ERROR {e}', flush=True); continue
        best = max(r['cells'], key=lambda c:c['lsn'])
        print(f"[S645] {tf}: sl={r['sl_pip']} cost%={r['cost_to_sl_pct']} "
              f"best={best['variant']}/{best['mode']}/{best['side']} lift={best['lift']:+} "
              f"n={best['n']} lsn={best['lsn']} ({r['sec']}s)", flush=True)
    print('[S645] ALL DONE', flush=True)
