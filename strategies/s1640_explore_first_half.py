# -*- coding: utf-8 -*-
"""
S1640 — TestedCeilingRecord — فازِ اکتشاف (مسیرِ C، فقط نیمهٔ اولِ داده)
========================================================================
پایه (اثبات‌شده: S526/S1511/S1520/S1621): لبهٔ تازهٔ ۹۰ کندلی — close[t] > max(close[t−90..t−1])
و کندلِ قبل چنین نبود؛ گیتِ درفت close[t−1] − close[t−91] > 0؛ LONG-only؛ SL=1.5×medATR100، TP=1.5×SL.
اهرمِ نو (Osler 2003؛ خوشهٔ استاپ بالای سطوحِ آزموده‌شده): سقفِ قبلی M = max(close[t−90..t−1])
«آزموده» است اگر در ۹۰ کندلِ قبل ≥ K کندلِ *مجزا* (غیرِ کندلِ رکوردساز) high ≥ M − 0.5×ATR100[t−1]
داشته باشند. فرض: هر تماسِ ناکام استاپ‌های خرید را بالای M متراکم می‌کند؛ شکستِ نهایی آن‌ها را
آزاد می‌کند ⇒ lift(tested) > lift(untested).
اکتشاف: K ∈ {1,2,3} + بازوی untested + پایهٔ بی‌گیت. TF: H4,H6,H8,H12 (همه mt5_full).
سه نول (S647): blind، gated-random (drift>0)، پایهٔ رکورد. آزمونِ دو-رژیمی: نیمِ اول/دومِ نیمهٔ اول.
پیش‌شمارشِ رویداد (درسِ S1622). نیمهٔ دوم هرگز لمس نمی‌شود.
"""
import json, os, sys, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se
from tools import s434_fast_data as fd

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results', '_s1640_explore')
os.makedirs(OUT, exist_ok=True)
PIP = 0.1; MAX_HOLD = 64; W = 90; RR = 1.5; TOL = 0.5
TFS = ['H4', 'H6', 'H8', 'H12']

def stats(tr):
    if tr is None or not len(tr): return 0, 0.0, 0.0
    p = tr['pnl_pip'].values; return len(p), 100.0*(p>0).mean(), float(p.mean())

def atr100(df):
    h,l,c = df['high'].values, df['low'].values, df['close'].values
    pc = np.roll(c,1); pc[0]=c[0]
    tr_ = np.maximum(h-l, np.maximum(abs(h-pc), abs(l-pc)))
    return pd.Series(tr_).rolling(100).mean().values, pd.Series(tr_).ewm(alpha=1/100, adjust=False).mean().values

def run_tf(tf):
    t0=time.time()
    d = fd.load_fast('XAUUSD', tf); df_all = fd.as_dataframe(d)
    half = len(df_all)//2; df = df_all.iloc[:half].reset_index(drop=True)
    h,c = df['high'].values, df['close'].values; n=len(c)
    tsec = df['time'].values.astype(np.int64)
    atr_sma, atr_rma = atr100(df)
    patr = np.roll(atr_rma,1); patr[0]=np.nan             # ATR100 علّی (t−1)
    cs = pd.Series(c)
    prevmax = cs.shift(1).rolling(W).max().values           # max(close[t−90..t−1])
    fresh = np.nan_to_num(c > prevmax, nan=False)
    pfresh = np.roll(fresh,1); pfresh[0]=False
    edge = fresh & ~pfresh
    pc1 = np.roll(c,1); pc1[0]=np.nan
    pc90 = np.roll(c, W+1); pc90[:W+1] = np.nan
    drift = pc1 - pc90                                     # close[t−1] − close[t−91]
    dpos = np.nan_to_num(drift > 0, nan=False)
    base = edge & dpos & ~np.isnan(patr)
    touches = np.zeros(n, int)
    for i in np.where(base)[0]:
        thr = prevmax[i] - TOL*patr[i]
        touches[i] = int((h[i-W:i] >= thr).sum())
    tested = touches - 1        # کندلِ رکوردسازِ M خودش همیشه می‌شمارد → تماسِ مجزا = touches−1
    sl = max(1.0, round(1.5*float(np.nanmedian(atr_sma))/PIP,1)); tp = round(RR*sl,1)
    zeros = np.zeros(n,bool); ones = np.ones(n,bool)
    SIM = lambda ls: se.simulate_trades(df,ls,zeros,sl_pip=sl,tp_pip=tp,asset='XAUUSD',max_hold=MAX_HOLD)
    _,wrb,_ = stats(SIM(ones)); _,wrg,_ = stats(SIM(dpos))
    nb,wrbase,epbase = stats(SIM(base))
    mid = n//2; ar = np.arange(n)
    arms = {'base': base}
    for K in (1,2,3): arms[f'tested>={K}'] = base & (tested>=K)
    arms['untested0'] = base & (tested==0)
    arms['untested<2'] = base & (tested<2)
    cells=[]
    for name, sig in arms.items():
        nn,wr,ep = stats(SIM(sig))
        n1,w1,e1 = stats(SIM(sig & (ar<mid))); n2,w2,e2 = stats(SIM(sig & (ar>=mid)))
        cells.append({'arm':name,'n':nn,'wr':round(wr,2),'lift_blind':round(wr-wrb,2),'lift_gated':round(wr-wrg,2),
                      'lift_vs_base':round(wr-wrbase,2),'exp_pip':round(ep,2),
                      'reg1':{'n':n1,'wr':round(w1,2),'exp':round(e1,2)},'reg2':{'n':n2,'wr':round(w2,2),'exp':round(e2,2)},
                      'lsn_gated':round((wr-wrg)*np.sqrt(max(nn,0)),1)})
    res={'tf':tf,'src':d.get('src'),'bars_first_half':int(half),'sl_pip':sl,'tp_pip':tp,'blind_wr':round(wrb,2),'gated_wr':round(wrg,2),
         'n_edge':int(edge.sum()),'n_base':int(base.sum()),
         'touch_hist':{int(k):int(v) for k,v in zip(*np.unique(tested[base],return_counts=True))},
         'reg_split_time':str(pd.to_datetime(tsec[mid],unit='s')),'cells':cells,'sec':round(time.time()-t0,1)}
    json.dump(res, open(os.path.join(OUT,f'{tf}.json'),'w'), ensure_ascii=False, indent=1)
    return res

if __name__=='__main__':
    for tf in TFS:
        r = run_tf(tf)
        print(f"[S1640] {tf}: sl={r['sl_pip']} tp={r['tp_pip']} n_edge={r['n_edge']} n_base={r['n_base']} gatedWR={r['gated_wr']} touch_hist={r['touch_hist']} split={r['reg_split_time'][:10]}")
        for c in r['cells']:
            print(f"   {c['arm']:<11} n={c['n']:>4} wr={c['wr']:5.2f} liftG={c['lift_gated']:+6.2f} vsBase={c['lift_vs_base']:+6.2f} exp={c['exp_pip']:+7.2f} | r1 n={c['reg1']['n']} wr={c['reg1']['wr']} exp={c['reg1']['exp']} | r2 n={c['reg2']['n']} wr={c['reg2']['wr']} exp={c['reg2']['exp']}")
    print('[S1640] ALL DONE')
