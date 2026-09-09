# -*- coding: utf-8 -*-
"""
S649 — UlcerCollapse — فازِ اکتشاف (مسیرِ C، فقط نیمهٔ اولِ داده)
==================================================================
فرضیه (Martin 1987، Ulcer Index): UI_p = RMS(درصدِ فاصله از سقفِ p کندلی). رویدادِ
«فروپاشیِ زخم»: در t−1 استرس بالا بود (UI14[t−1] در چندکِ ≥q از ۱۰۰ کندلِ قبلی) و در t
قیمت به سقفِ ۱۴ کندلی برگشت (close[t] ≥ max(close[t−13..t])). یعنی V-recovery کامل:
درد سپری شد، خریدارانِ گیرافتاده آزاد شدند، مقاومتِ نزدیک تمام شد. **فقط لانگ** (قانونِ S648).
تفاوت با S1511/S1520 (سقفِ تازهٔ ۹۰ کندلی): آن‌جا شرطِ «تازگیِ سقفِ بلند»؛ این‌جا شرطِ
«استرسِ قبلی» — سقفِ ۱۴ کندلی پس از drawdown، نه رکوردِ ۹۰ کندلی. خانوادهٔ Ulcer بکر است (grep=0).
گونه‌ها: q∈{50,75} × {plain, aligned(drift60>0)}؛ حالت‌ها cont/fade. هندسه RR=1.5 (S1511).
سه نول (قانونِ S647): blind، gated-random، و lift رویداد نسبت به هر دو. نیمهٔ دوم هرگز لمس نمی‌شود.
"""
import json, os, sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import indicator_bank as ib
from engine import scalp_engine as se
from tools import s434_fast_data as fd

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'results', '_s649_explore')
os.makedirs(OUT, exist_ok=True)

PIP = 0.1
MAX_HOLD = 64
TFS = ['M15','M30','H1','H2','H3','H4','H6','H8','H12','D1']
DRIFT_SEC = 60*86400
RR = 1.5
UI_P = 14
QS = [50, 75]

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
    ui = np.asarray(ib.compute('ulcer', df), dtype=float)          # UI14 روی close
    pui = np.roll(ui,1); pui[0] = np.nan
    rank = pd.Series(pui).rolling(100).rank(pct=True).values * 100   # چندکِ UI[t-1] در ۱۰۰ کندلِ قبل (شاملِ خودش)
    hh14 = pd.Series(c).rolling(UI_P).max().values
    at_high = c >= hh14 - 1e-9
    stressed = {q: np.nan_to_num(rank >= q, nan=False) for q in QS}
    events = {f'q{q}': at_high & stressed[q] for q in QS}
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
    for pname, ev in events.items():
        variants = [('plain',ev,wrbL,wrbS), ('aligned',ev&dpos,wrgL,wrgS), ('counter',ev&dneg,wrcL,wrcS)]
        for variant, sig, gL, gS in variants:
            for mode in ('cont','fade'):
                side = 'long' if mode=='cont' else 'short'
                wrb, wrg = (wrbL, gL) if side=='long' else (wrbS, gS)
                tr = SIM(sig,zeros) if side=='long' else SIM(zeros,sig)
                n,wr,ep = stats(tr); lift = wr-wrb; liftg = wr-wrg
                cells.append({'pat':pname,'variant':variant,'mode':mode,'side':side,'n':n,
                              'wr':round(wr,2),'blind':round(wrb,2),'gated':round(wrg,2),'lift':round(lift,2),
                              'lift_gated':round(liftg,2),'exp_pip':round(ep,2),
                              'lsn':round(lift*np.sqrt(max(n,0)),1),'lsn_gated':round(liftg*np.sqrt(max(n,0)),1)})
    res = {'tf':tf,'src':d.get('src'),'bars_first_half':int(half),'sl_pip':sl,
           'cost_to_sl_pct':round(100*3.3/sl,1),'n_events':{k:int(v.sum()) for k,v in events.items()},'n_at_high':int(at_high.sum()),'n_cells':len(cells),
           'gated_wr':{'L':round(wrgL,2),'S':round(wrgS,2)},'counter_wr':{'L':round(wrcL,2),'S':round(wrcS,2)},'cells':cells,'sec':round(time.time()-t0,1)}
    json.dump(res, open(os.path.join(OUT,f'{tf}.json'),'w'), ensure_ascii=False, indent=1)
    return res

if __name__=='__main__':
    for tf in TFS:
        try:
            r = run_tf(tf)
        except Exception as e:
            print(f'[S649] {tf}: ERROR {e}', flush=True); continue
        big = [c for c in r['cells'] if c['n']>=200] or r['cells']
        best = max(big, key=lambda c:c['lsn_gated'])
        print(f"[S649] {tf}: sl={r['sl_pip']} cells={r['n_cells']} gatedWR={r['gated_wr']} "
              f"best={best['pat']}/{best['variant']}/{best['mode']}/{best['side']} liftG={best['lift_gated']:+} "
              f"n={best['n']} lsnG={best['lsn_gated']} ({r['sec']}s)", flush=True)
    print('[S649] ALL DONE', flush=True)
