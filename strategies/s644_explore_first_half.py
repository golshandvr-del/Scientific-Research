# -*- coding: utf-8 -*-
"""
S644 — KumoBreak — فازِ اکتشاف (مسیرِ C، فقط نیمهٔ اولِ داده)
=============================================================
فرضیه: Ichimoku (9/26/52 متعارف — پارامترِ آزاد صفر). ابر (Kumo) در کندلِ t از
دادهٔ t−26 ساخته می‌شود (senkou به جلو شیفت می‌خورد) → بدونِ نگاه به آینده.
رویدادِ گسسته: close از **بالای** ابر خارج می‌شود (قبل ≤ kumo_top، اکنون > kumo_top)
→ لانگ؛ آینه → شورت. سه گونهٔ تأیید (همه از ادبیاتِ Hosoda، نه از داده):
  • plain  : فقط شکستِ ابر
  • tk     : + Tenkan > Kijun (لانگ) / Tenkan < Kijun (شورت)
  • chikou : + close > close[t−26] (لانگ) / < (شورت)  — تأییدِ Chikou
S322 (M15، pullback، ۴ پارامتر) خویشاوندِ دور است و REJECT شد؛ این خانوادهٔ
شکستِ ابرِ درشت در S500–S980 بکر است (grep ichimoku|kumo = 0).

درس‌های دکاد: فقط TFهای درشت (S383)؛ نولِ هم‌جهتِ کور (S385)؛ RR=1؛
تشخیصِ S643: اگر یک سمت در هر دو جهت مثبت باشد → بازبرچسبِ رژیم.
نیمهٔ دوم هرگز لمس نمی‌شود.
"""
import json, os, sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se
from tools import s434_fast_data as fd

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'results', '_s644_explore')
os.makedirs(OUT, exist_ok=True)

PIP = 0.1
MAX_HOLD = 64
TFS = ['M15','M30','H1','H2','H3','H4','H6','H8','H12','D1']
T, K, S = 9, 26, 52   # متعارف — منجمد

def ichimoku(df):
    h, l, c = df['high'], df['low'], df['close']
    tenkan = (h.rolling(T).max() + l.rolling(T).min()) / 2
    kijun  = (h.rolling(K).max() + l.rolling(K).min()) / 2
    spanA  = ((tenkan + kijun) / 2).shift(K)                 # ابر در t از t−26
    spanB  = ((h.rolling(S).max() + l.rolling(S).min()) / 2).shift(K)
    top = np.maximum(spanA, spanB); bot = np.minimum(spanA, spanB)
    return tenkan.values, kijun.values, top.values, bot.values

def stats(tr):
    if tr is None or not len(tr): return 0, 0.0, 0.0
    p = tr['pnl_pip'].values
    return len(p), 100.0*(p>0).mean(), float(p.mean())

def run_tf(tf):
    t0=time.time()
    d = fd.load_fast('XAUUSD', tf); df_all = fd.as_dataframe(d)
    half = len(df_all)//2
    df = df_all.iloc[:half].reset_index(drop=True)
    tenkan, kijun, top, bot = ichimoku(df)
    c = df['close'].values; pc = np.roll(c,1); pc[0]=c[0]
    ptop = np.roll(top,1); ptop[0]=top[0]; pbot = np.roll(bot,1); pbot[0]=bot[0]
    with np.errstate(invalid='ignore'):
        brk_up = (pc <= ptop) & (c > top)
        brk_dn = (pc >= pbot) & (c < bot)
        tk_up = tenkan > kijun; tk_dn = tenkan < kijun
        c26 = np.roll(c, K); c26[:K] = np.nan
        ch_up = c > c26; ch_dn = c < c26
    brk_up = np.nan_to_num(brk_up, nan=False).astype(bool)
    brk_dn = np.nan_to_num(brk_dn, nan=False).astype(bool)
    h,l = df['high'].values, df['low'].values
    tr_ = np.maximum(h-l, np.maximum(abs(h-pc), abs(l-pc)))
    slb = float(np.nanmedian(pd.Series(tr_).rolling(100).mean().values))/PIP
    sl = max(1.0, round(1.5*slb,1)); tp = sl
    zeros = np.zeros(len(df),bool); ones = np.ones(len(df),bool)
    _,wrbL,_ = stats(se.simulate_trades(df,ones,zeros,sl_pip=sl,tp_pip=tp,asset='XAUUSD',max_hold=MAX_HOLD))
    _,wrbS,_ = stats(se.simulate_trades(df,zeros,ones,sl_pip=sl,tp_pip=tp,asset='XAUUSD',max_hold=MAX_HOLD))
    variants = {'plain':(brk_up, brk_dn),
                'tk':(brk_up & tk_up, brk_dn & tk_dn),
                'chikou':(brk_up & ch_up, brk_dn & ch_dn)}
    cells=[]
    for var,(lu,sd) in variants.items():
        for mode in ('cont','fade'):
            ls, ss = (lu, sd) if mode=='cont' else (sd, lu)
            n,wr,ep = stats(se.simulate_trades(df,ls,zeros,sl_pip=sl,tp_pip=tp,asset='XAUUSD',max_hold=MAX_HOLD))
            cells.append({'variant':var,'mode':mode,'side':'long','n':n,'wr':round(wr,2),'blind':round(wrbL,2),
                          'lift':round(wr-wrbL,2),'exp_pip':round(ep,2),'lsn':round((wr-wrbL)*np.sqrt(max(n,0)),1)})
            n,wr,ep = stats(se.simulate_trades(df,zeros,ss,sl_pip=sl,tp_pip=tp,asset='XAUUSD',max_hold=MAX_HOLD))
            cells.append({'variant':var,'mode':mode,'side':'short','n':n,'wr':round(wr,2),'blind':round(wrbS,2),
                          'lift':round(wr-wrbS,2),'exp_pip':round(ep,2),'lsn':round((wr-wrbS)*np.sqrt(max(n,0)),1)})
    res = {'tf':tf,'src':d.get('src'),'bars_first_half':int(half),'sl_pip':sl,
           'cost_to_sl_pct':round(100*3.3/sl,1),'blind_long_wr':round(wrbL,2),
           'blind_short_wr':round(wrbS,2),'n_break_up':int(brk_up.sum()),
           'n_break_dn':int(brk_dn.sum()),'cells':cells,'sec':round(time.time()-t0,1)}
    json.dump(res, open(os.path.join(OUT,f'{tf}.json'),'w'), ensure_ascii=False, indent=1)
    return res

if __name__=='__main__':
    for tf in TFS:
        try:
            r = run_tf(tf)
        except Exception as e:
            print(f'[S644] {tf}: ERROR {e}', flush=True); continue
        best = max(r['cells'], key=lambda c:c['lsn'])
        print(f"[S644] {tf}: sl={r['sl_pip']} cost%={r['cost_to_sl_pct']} up={r['n_break_up']} dn={r['n_break_dn']} "
              f"best={best['variant']}/{best['mode']}/{best['side']} lift={best['lift']:+} "
              f"n={best['n']} lsn={best['lsn']} ({r['sec']}s)", flush=True)
    print('[S644] ALL DONE', flush=True)
