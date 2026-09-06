# -*- coding: utf-8 -*-
"""
S648 — ReversalPatternDrift — فازِ اکتشاف (مسیرِ C، فقط نیمهٔ اولِ داده)
========================================================================
فرضیه: الگوهای بازگشتیِ ۲–۳ کندلیِ کم‌تکرار (Nison 1991) که در S500–S980 بکرند:
  harami، morning/evening star، piercing/dark-cloud، three-inside، tweezer.
مکانیسم: «خستگیِ حرکتِ مقابل + کندلِ تأیید» — رویدادِ خودِ کندل است (بدونِ تأخیرِ فیلتر؛ قانونِ S645).
با قانونِ S647 (تجزیهٔ گیت و رویداد) سه نول گزارش می‌شود:
  blind (هر کندل)، gated-random (هر کندل با درفتِ هم‌جهت)، و lift رویداد نسبت به هر دو.
گونه‌ها: plain / aligned (جهتِ الگو = درفتِ ۶۰ روزِ تقویمی؛ pullback-resumption)
         / counter (جهتِ الگو ≠ درفت؛ بازگشتِ واقعی).  حالت‌ها: cont / fade.
هندسه: RR=1.618 (منجمد؛ به ارث از S919). قانونِ S644: فقط سلول‌های n≥200 شاهدند.
تعدادِ سلول‌ها به‌صراحت گزارش می‌شود (multiplicity). نیمهٔ دوم هرگز لمس نمی‌شود.
"""
import json, os, sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import indicator_bank as ib
from engine import scalp_engine as se
from tools import s434_fast_data as fd

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'results', '_s648_explore')
os.makedirs(OUT, exist_ok=True)

PIP = 0.1
MAX_HOLD = 64
TFS = ['M15','M30','H1','H2','H3','H4','H6','H8','H12','D1']
DRIFT_SEC = 60*86400
RR = 1.618
PATS = [('harami','cdl_harami_bull','cdl_harami_bear'),('star','cdl_morningstar','cdl_eveningstar'),
        ('pierce','cdl_piercing','cdl_darkcloud'),('3inside','cdl_3inside_up','cdl_3inside_dn'),
        ('tweezer','cdl_tweezerbottom','cdl_tweezertop')]

def stats(tr):
    if tr is None or not len(tr): return 0, 0.0, 0.0
    p = tr['pnl_pip'].values
    return len(p), 100.0*(p>0).mean(), float(p.mean())

def run_tf(tf):
    t0=time.time()
    d = fd.load_fast('XAUUSD', tf); df_all = fd.as_dataframe(d)
    half = len(df_all)//2
    df = df_all.iloc[:half].reset_index(drop=True)
    o,h,l,c = df['open'].values, df['high'].values, df['low'].values, df['close'].values
    t = df['time'].values.astype(np.int64)
    # درفتِ ۶۰ روزِ تقویمی، علّی: close[t-1] - close[idx(time[t-1]-60d)]
    pc1 = np.roll(c,1); pc1[0]=c[0]
    pt1 = np.roll(t,1); pt1[0]=t[0]
    j = np.searchsorted(t, pt1 - DRIFT_SEC, side='left')
    drift = pc1 - c[np.clip(j,0,len(c)-1)]
    drift[j <= 0] = 0.0
    dpos = drift > 0; dneg = drift < 0
    pats = {name:(np.asarray(ib.compute(fb,df))!=0, np.asarray(ib.compute(fr,df))!=0) for name,fb,fr in PATS}
    pc = np.roll(c,1); pc[0]=c[0]
    tr_ = np.maximum(h-l, np.maximum(abs(h-pc), abs(l-pc)))
    slb = float(np.nanmedian(pd.Series(tr_).rolling(100).mean().values))/PIP
    sl = max(1.0, round(1.5*slb,1))
    zeros = np.zeros(len(df),bool); ones = np.ones(len(df),bool)
    tp = round(RR*sl,1)
    SIM = lambda ls, ss: se.simulate_trades(df,ls,ss,sl_pip=sl,tp_pip=tp,asset='XAUUSD',max_hold=MAX_HOLD)
    _,wrbL,_ = stats(SIM(ones,zeros)); _,wrbS,_ = stats(SIM(zeros,ones))
    _,wrgL,_ = stats(SIM(dpos,zeros)); _,wrgS,_ = stats(SIM(zeros,dneg))     # gated-random (S647)
    _,wrcL,_ = stats(SIM(dneg,zeros)); _,wrcS,_ = stats(SIM(zeros,dpos))     # counter-random
    cells=[]
    for pname,(bu0,be0) in pats.items():
        variants = [('plain',bu0,be0,wrbL,wrbS), ('aligned',bu0&dpos,be0&dneg,wrgL,wrgS), ('counter',bu0&dneg,be0&dpos,wrcL,wrcS)]
        for variant, bu, be, gL, gS in variants:
            for mode in ('cont','fade'):
                ls, ss = (bu, be) if mode=='cont' else (be, bu)
                for side, sig, wrb, wrg in (('long', ls, wrbL, gL), ('short', ss, wrbS, gS)):
                    tr = SIM(sig,zeros) if side=='long' else SIM(zeros,sig)
                    n,wr,ep = stats(tr); lift = wr-wrb; liftg = wr-wrg
                    cells.append({'pat':pname,'variant':variant,'mode':mode,'side':side,'n':n,
                                  'wr':round(wr,2),'blind':round(wrb,2),'gated':round(wrg,2),'lift':round(lift,2),
                                  'lift_gated':round(liftg,2),'exp_pip':round(ep,2),
                                  'lsn':round(lift*np.sqrt(max(n,0)),1),'lsn_gated':round(liftg*np.sqrt(max(n,0)),1)})
    res = {'tf':tf,'src':d.get('src'),'bars_first_half':int(half),'sl_pip':sl,
           'cost_to_sl_pct':round(100*3.3/sl,1),'n_events':{k:[int(v[0].sum()),int(v[1].sum())] for k,v in pats.items()},'n_cells':len(cells),
           'gated_wr':{'L':round(wrgL,2),'S':round(wrgS,2)},'counter_wr':{'L':round(wrcL,2),'S':round(wrcS,2)},'cells':cells,'sec':round(time.time()-t0,1)}
    json.dump(res, open(os.path.join(OUT,f'{tf}.json'),'w'), ensure_ascii=False, indent=1)
    return res

if __name__=='__main__':
    for tf in TFS:
        try:
            r = run_tf(tf)
        except Exception as e:
            print(f'[S648] {tf}: ERROR {e}', flush=True); continue
        big = [c for c in r['cells'] if c['n']>=200] or r['cells']
        best = max(big, key=lambda c:c['lsn_gated'])
        print(f"[S648] {tf}: sl={r['sl_pip']} cells={r['n_cells']} gatedWR={r['gated_wr']} "
              f"best={best['pat']}/{best['variant']}/{best['mode']}/{best['side']} liftG={best['lift_gated']:+} "
              f"n={best['n']} lsnG={best['lsn_gated']} ({r['sec']}s)", flush=True)
    print('[S648] ALL DONE', flush=True)
