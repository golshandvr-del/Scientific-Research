# -*- coding: utf-8 -*-
"""S321d — نقشه‌برداریِ سبک و کنترل‌شدهٔ فضای پارامتریِ MA-Ribbon روی XAUUSD M30.
هدف: فهمیدن اینکه آیا ناحیهٔ WR بالا پایدار است یا نویزِ overfit. گرید کوچک، ضدِ انجماد."""
import sys; sys.path.insert(0,'.')
import numpy as np, itertools
from engine import scalp_engine as se
from engine import rqs
import strategies.s321b_ma_ribbon_enhanced as S

def main():
    pip=se.ASSETS['XAUUSD']['pip']
    df=se.load_data('data/XAUUSD_M30.csv')
    feats=S.build_features(df,pip)
    atr_med=float(np.nanmedian(feats['atr_pip']))
    # small, deliberate grid (~144 combos)
    G=dict(ord_thr=[0.40,0.55],wz_gate=[0.15,0.30],
           pull_min=[0.05],pull_max=[0.70,0.82],
           rsi_min=[45,52],rsi_max=[85],
           sl_mult=[2.0,2.3],tp_mult=[2.6,3.2],
           be_mult=[0.0,0.6],max_hold=[48])
    rows=[]
    for combo in itertools.product(*[G[k] for k in G]):
        cfg=dict(zip(G.keys(),combo))
        if cfg['tp_mult']<=cfg['sl_mult']: continue
        ls,ss,sl,tp=S.make_signals(feats,cfg,'long')
        be=None if cfg['be_mult']<=0 else cfg['be_mult']*atr_med
        tr=se.simulate_trades(df,ls,ss,sl,tp,'XAUUSD',max_hold=cfg['max_hold'],
                              allow_overlap=False,be_trigger_pip=be)
        n,wr,pf,net=S.lite_stats(tr)
        if n>=30:
            rows.append((wr,pf,n,net,cfg))
    rows.sort(key=lambda x:(x[0],x[1]),reverse=True)
    print(f'configs n>=30: {len(rows)}')
    print('--- TOP 10 by WR ---')
    for wr,pf,n,net,cfg in rows[:10]:
        print(f'WR={wr:4.1f} PF={pf:.2f} n={n:3d} net={net:7.0f} | ord{cfg["ord_thr"]} wz{cfg["wz_gate"]} pmax{cfg["pull_max"]} rsi{cfg["rsi_min"]}-{cfg["rsi_max"]} sl{cfg["sl_mult"]}tp{cfg["tp_mult"]} be{cfg["be_mult"]}')
    print('--- TOP 8 by PF ---')
    rows.sort(key=lambda x:(x[1],x[0]),reverse=True)
    for wr,pf,n,net,cfg in rows[:8]:
        print(f'PF={pf:.2f} WR={wr:4.1f} n={n:3d} net={net:7.0f} | ord{cfg["ord_thr"]} wz{cfg["wz_gate"]} pmax{cfg["pull_max"]} rsi{cfg["rsi_min"]}-{cfg["rsi_max"]} sl{cfg["sl_mult"]}tp{cfg["tp_mult"]} be{cfg["be_mult"]}')

if __name__=='__main__':
    main()
