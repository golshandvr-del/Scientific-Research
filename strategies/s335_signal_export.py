# -*- coding: utf-8 -*-
"""
s335_signal_export.py — استخراجِ سیگنالِ ورودِ مرجعِ پایتون (با پارامترهای واقعیِ
هر TF) برای برابریِ سیگنالِ TS↔Python. برای هر TF یک JSON با کندل‌ها + آرایهٔ
بولینِ سیگنال (True روی کندلِ i = تصمیمِ ورودِ کندلِ i) می‌نویسد.
harnessِ TS برای هر i از i=need..N، computeS335(candles[0..i]) را صدا می‌زند و
active را با سیگنالِ پایتون[i] مقایسه می‌کند.
"""
import sys, os, json
sys.path.insert(0, '/home/user/webapp')
os.chdir('/home/user/webapp')
import numpy as np
from engine import scalp_engine as se
import strategies.s335_mtf as M

# پارامترهای نهاییِ هر TF — دقیقاً منطبق با S335_CFG در TS و ردیف‌های ACCEPT
FINAL = {
    'M5':  dict(trigger='zero_up',  rf_dip=1.0, tf_min=0.2, hu_min=0.53, r2_min=None, chop_max=38.2),
    'M15': dict(trigger='dip_turn', rf_dip=1.0, tf_min=0.5, hu_min=0.50, r2_min=0.55, chop_max=None),
    'H1':  dict(trigger='dip_turn', rf_dip=1.0, tf_min=0.5, hu_min=0.50, r2_min=None, chop_max=38.2),
}
BARS = 8000  # زیرمجموعهٔ کافی

def main():
    for tf, cfg in FINAL.items():
        df = se.load_data(f'data/XAUUSD_{tf}.csv')
        if len(df) > BARS:
            df = df.iloc[:BARS].reset_index(drop=True)
        S = M.precompute(df)
        sig = M.build_signal(S, cfg['trigger'], cfg['rf_dip'], cfg['tf_min'],
                             cfg['hu_min'], cfg['r2_min'], cfg['chop_max'])
        out = {
            'tf': tf, 'cfg': cfg, 'ind': M.IND,
            'candles': [
                {'time': int(df['time'].iloc[i]),
                 'open': round(float(df['open'].iloc[i]), 5),
                 'high': round(float(df['high'].iloc[i]), 5),
                 'low':  round(float(df['low'].iloc[i]), 5),
                 'close':round(float(df['close'].iloc[i]), 5)}
                for i in range(len(df))
            ],
            'signal': [bool(x) for x in sig],
        }
        path = f'strategies/s335_signal_{tf}.json'
        with open(path, 'w') as f:
            json.dump(out, f)
        print(f"wrote {path}  bars={len(df)}  entries={int(sig.sum())}")

if __name__ == '__main__':
    main()
