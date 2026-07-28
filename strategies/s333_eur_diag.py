# -*- coding: utf-8 -*-
"""چرا EURUSD رد شد؟ تشخیصِ صادقانه: long-biasِ طلا در یورو نیست."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from strategies import s333_s79_pullback_revival as S
from engine import scalp_engine as SE
from engine import indicator_bank as ib

df = SE.load_data(SE.ASSETS['EURUSD_M15']['file'])
hu = ib.compute('hurst', df).values
for conf in ['none', 'rsi_turn', 'price_turn']:
    base = S.core_signal_confirmed(df, 20, 100, 21, 35, confirm=conf)
    sig = base & (np.nan_to_num(hu, nan=-1) > 0.55)
    tr, r = S.evaluate(df, sig, 'EURUSD_M15', 180, 180, 96)
    if tr is None:
        print(conf, 'no trades'); continue
    m = r['metrics']
    print('%-11s n=%3d WR=%.1f%% PF=%.2f exp=%+.1f p=%.2f RQS=%.1f' % (
        conf, m['n_trades'], m['win_rate'], m['profit_factor'],
        m['expectancy_pip'], m['p_value'], r['rqs_score']))
