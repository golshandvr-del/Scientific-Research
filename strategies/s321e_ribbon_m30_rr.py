# -*- coding: utf-8 -*-
"""S321e — شکستنِ سقفِ WR روی M30: sweep نامتقارنِ RR + break-even، با RQS+ کامل.
ناحیهٔ برنده تثبیت‌شده: ord0.40 wz0.15 pmax0.82 rsi45-85. فقط RR/be/max_hold شناور."""
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
    base=dict(ord_thr=0.40,wz_gate=0.15,pull_min=0.05,pull_max=0.82,rsi_min=45,rsi_max=85)
    res=[]
    for sl_mult in [2.0,2.3,2.6,3.0]:
        for tp_mult in [1.6,1.9,2.2,2.6]:
            if tp_mult>=sl_mult+0.4: continue   # keep RR<=~1 to lift WR
            for be_mult in [0.0,0.4,0.7,1.0]:
                for mh in [40,64]:
                    cfg=dict(base); cfg.update(sl_mult=sl_mult,tp_mult=tp_mult,be_mult=be_mult,max_hold=mh)
                    ls,ss,sl,tp=S.make_signals(feats,cfg,'long')
                    be=None if be_mult<=0 else be_mult*atr_med
                    tr=se.simulate_trades(df,ls,ss,sl,tp,'XAUUSD',max_hold=mh,
                                          allow_overlap=False,be_trigger_pip=be)
                    n,wr,pf,net=S.lite_stats(tr)
                    if n>=40 and wr>=59 and pf>=1.25:
                        med_tp=float(np.median(tp[ls|ss]))
                        r=rqs.compute_rqs(tr,'XAUUSD',sl_pip=float(np.median(tr['sl_pip'])),tp_pip=med_tp)
                        res.append((r['rqs_score'],r['passed'],sl_mult,tp_mult,be_mult,mh,r['metrics'],r['gates']))
    res.sort(key=lambda x:(x[1],x[0]),reverse=True)
    print(f'candidates WR>=59 & PF>=1.25: {len(res)}')
    for score,passed,sl,tp,be,mh,m,g in res[:15]:
        gl=''.join('1' if g[k] else '0' for k in ['G0','G1','G2','G3','G4','G5'])
        print(f'RQS={score:5.1f} {"PASS" if passed else "FAIL"} G[{gl}] n={m["n_trades"]:3d} WR={m["win_rate"]:4.1f} PF={m["profit_factor"]:.2f} DD={m["max_dd_pct"]:.1f} MCL={m["max_consec_losses"]} p={m["p_value"]:.3f} net={m["net_profit"]:.0f} | sl{sl}tp{tp}be{be}mh{mh}')
    if not res: print('NONE reached WR>=59')

if __name__=='__main__':
    main()
