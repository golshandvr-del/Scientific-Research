# -*- coding: utf-8 -*-
"""S611 — جدول MTF گزارشی (پیش‌ثبت §6.3): قانونِ منجمدِ S153 روی همهٔ TFهای طلا.
گزارشی، نه داوری مجزا (بودجهٔ چندگانگی مصرف نمی‌شود). هندسهٔ پیپیِ منجمد.
هر TF بلافاصله JSON خودش را می‌نویسد (قانونِ افزایشی)."""
import os, sys, json, time
import numpy as np
import pandas as pd

ROOT = '/home/user/webapp'
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'strategies'))
from engine import scalp_engine as SE
from s153_gold_vwap_confluence_momentum import daily_vwap_z, gen_signal

CFG = dict(z_entry=1.5, ema_trend=200, atr_mult=0.5, cooldown=48,
           sl=80.0, tp=700.0, be=6.0, trail=6.0, mh=48)
OUT = os.path.join(ROOT, 'results', '_s611_vwap', 'mtf')
os.makedirs(OUT, exist_ok=True)

TFS = ['M1','M3','M4','M5','M6','M10','M12','M15','M20','M30',
       'H1','H2','H3','H4','H6','H8','H12','D1','W1']
# اجرای تک-TF: python3 s611_mtf_table.py M15  (ضد OOM روی M1 — درس S580)
if len(sys.argv) > 1:
    TFS = [sys.argv[1]]

from tools import s434_fast_data as fd

for tf in TFS:
    fp = os.path.join(OUT, f'{tf}.json')
    if os.path.exists(fp):
        print(tf, 'exists, skip'); continue
    t0 = time.time()
    try:
        d = fd.load_fast('XAUUSD', tf)
        df = pd.DataFrame({k: d[k] for k in ['time','open','high','low','close','volume']})
        df['dt'] = pd.to_datetime(df['time'], unit='s')
        asset = f'XAUUSD_S611_{tf}'
        SE.ASSETS[asset] = dict(file='', pip=0.10, contract=100.0, pip_value=10.0,
                                spread_pip=3.3, comm=0.0, slip_pip=0.0)
        vwap, z = daily_vwap_z(df)
        ls, ss = gen_signal(df, z, CFG['z_entry'], CFG['ema_trend'],
                            CFG['atr_mult'], CFG['cooldown'])
        nsig = int(ls.sum())
        row = dict(tf=tf, src=d['src'], n_bars=int(d['n_bars']),
                   span_years=d['span_years'], n_signals=nsig)
        if nsig >= 5:
            trd = SE.simulate_trades(df, ls, ss, CFG['sl'], CFG['tp'], asset,
                                     max_hold=CFG['mh'], be_trigger_pip=CFG['be'],
                                     trail_pip=CFG['trail'])
            if len(trd):
                sb = trd['signal_bar'].values
                mid = len(df)//2
                w = (trd['outcome']=='win').values
                row.update(n_trades=int(len(trd)),
                           wr=round(float(w.mean()*100),2),
                           net_pip=round(float(trd['pnl_pip'].sum()),1),
                           wr_h1=round(float(w[sb<mid].mean()*100),2) if (sb<mid).any() else None,
                           wr_h2=round(float(w[sb>=mid].mean()*100),2) if (sb>=mid).any() else None,
                           net_h1=round(float(trd['pnl_pip'].values[sb<mid].sum()),1),
                           net_h2=round(float(trd['pnl_pip'].values[sb>=mid].sum()),1))
        json.dump(row, open(fp,'w'), indent=1)
        print(tf, row.get('n_trades', 0), 'trades', f'{time.time()-t0:.0f}s', flush=True)
    except Exception as e:
        json.dump(dict(tf=tf, error=str(e)), open(fp,'w'))
        print(tf, 'ERROR', e, flush=True)
print('DONE')
