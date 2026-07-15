"""
اکتشاف مرحله ۲: هدف کاربر به >60% کاهش یافته.
سوال: با RR ملایم نامتقارن (BE در بازه 55-62%) در بهترین context موجود
(session+trend+pullback)، آیا WR بالای 60% با فرکانس کافی و expectancy مثبت
به‌دست می‌آید؟ (ورود در OPEN کندل بعد — بدون look-ahead)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np
import pandas as pd
import indicators as ind

df = pd.read_csv('data/XAUUSD_M15.csv')
df['dt'] = pd.to_datetime(df['time'], unit='s')
df['hour'] = df['dt'].dt.hour
close = df['close']; high = df['high']; low = df['low']; openp = df['open']
atr = ind.atr(df, 14)
ema50 = ind.ema(close, 50); ema200 = ind.ema(close, 200)
rsi14 = ind.rsi(close, 14)
o=openp.values; h=high.values; l=low.values; c=close.values; atrv=atr.values
n=len(df)

def p_win(mask, tp_mult, sl_mult, direction='long', max_hold=48, spread=0.20):
    idx=np.where(mask.values)[0]; wins=0; tot=0
    for si in idx:
        eb=si+1
        if eb>=n: continue
        a=atrv[si]
        if not np.isfinite(a) or a<=0: continue
        if direction=='long':
            fill=o[eb]+spread; slp=fill-sl_mult*a; tpp=fill+tp_mult*a
        else:
            fill=o[eb]-spread; slp=fill+sl_mult*a; tpp=fill-tp_mult*a
        res=None
        for j in range(eb,min(eb+max_hold,n)):
            if direction=='long':
                hs=l[j]<=slp; ht=h[j]>=tpp
            else:
                hs=h[j]>=slp; ht=l[j]<=tpp
            if hs and ht: res='loss';break
            elif ht: res='win';break
            elif hs: res='loss';break
        if res is None: continue
        tot+=1
        if res=='win': wins+=1
    return (wins/tot*100 if tot else 0), tot

uptrend=(close>ema50)&(ema50>ema200)
base=pd.Series(True,index=df.index); base.iloc[:300]=False

# context‌های کاندید
contexts = {
    'uptrend_all': uptrend & base,
    'uptrend_golden(19-23)': uptrend & (df['hour']>=19)&(df['hour']<23) & base,
    'uptrend_pullback(rsi<50)': uptrend & (rsi14<50) & base,
    'uptrend_golden_pullback': uptrend & (df['hour']>=19)&(df['hour']<23) & (rsi14<50) & base,
    'uptrend_overlap(13-17)_pullback': uptrend & (df['hour']>=13)&(df['hour']<17) & (rsi14<50) & base,
}

# RR‌های کاندید با BE مختلف
rrs = [
    ('TP1.0/SL1.0 (BE50)', 1.0, 1.0),
    ('TP1.0/SL1.3 (BE56.5)', 1.0, 1.3),
    ('TP1.0/SL1.5 (BE60.0)', 1.0, 1.5),
    ('TP1.0/SL1.6 (BE61.5)', 1.0, 1.6),
    ('TP0.8/SL1.3 (BE61.9)', 0.8, 1.3),
]

for cname, cmask in contexts.items():
    print(f"\n### context: {cname}  (n_signals={int(cmask.sum())})")
    for rname, tp, sl in rrs:
        be = sl/(tp+sl)*100
        wr, tot = p_win(cmask, tp, sl)
        # expectancy تقریبی (بدون هزینه دقیق، فقط علامت)
        edge = wr - be
        flag = '  <-- WR>BE' if wr>be else ''
        print(f"   {rname}: WR={wr:.2f}% n={tot}  edge(WR-BE)={edge:+.1f}{flag}")
