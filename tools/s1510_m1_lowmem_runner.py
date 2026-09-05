# اجرای M1 با حافظهٔ کم — منطق و پارامترها عیناً s1510؛ فقط dtype float32 و gc
import sys, os, gc, runpy
sys.path.insert(0, '/home/user/webapp')
import pandas as pd, numpy as np
_orig_read_csv = pd.read_csv
def read_csv_lowmem(path, *a, **k):
    df = _orig_read_csv(path, *a, **k)
    for c in ['open','high','low','close']:
        if c in df: df[c] = df[c].astype('float32')
    if 'volume' in df: df = df.drop(columns=['volume'])
    if 'tick_volume' in df: df = df.drop(columns=['tick_volume'])
    if 'spread' in df: df = df.drop(columns=['spread'])
    gc.collect()
    return df
pd.read_csv = read_csv_lowmem
sys.argv = ['s1510_momentum_record.py', 'XAUUSD_M1']
runpy.run_path('/home/user/webapp/strategies/s1510_momentum_record.py', run_name='__main__')
