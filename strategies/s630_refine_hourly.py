# -*- coding: utf-8 -*-
"""
S630 — پالایشِ خانوادهٔ IBS روی TFهای ساعتی — «فقط نیمهٔ نخست» (Route C)
هدف: تعریفِ دقیقِ خانوادهٔ پیش‌ثبت (PREREG). هنوز اکتشاف است؛ نیمهٔ دوم مُهروموم.
هندسه ثابت و متقارن: SL = TP = 1.5×ATR(100) — بدون جست‌وجو روی هندسه (حفظ کم‌پارامتری).
"""
import sys, os, json, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'research', 's630_explore')
os.makedirs(OUT, exist_ok=True)

def run_tf(TF):
    d = fd.load_fast('XAUUSD', TF)
    df = fd.as_dataframe(d)
    half = len(df) // 2
    df = df.iloc[:half].reset_index(drop=True)
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    rng = h - l
    ibs = np.where(rng > 0, (c - l) / np.where(rng > 0, rng, 1.0), 0.5)
    ibs_s = pd.Series(ibs)
    tr = np.maximum(h - l, np.maximum(abs(h - np.roll(c, 1)), abs(l - np.roll(c, 1))))
    tr[0] = h[0] - l[0]
    atr = pd.Series(tr).rolling(100).mean().values
    med_atr = float(np.nanmedian(atr))
    pip = 0.1
    sl_pip = med_atr * 1.5 / pip
    tp_pip = sl_pip
    res = []
    for k in [2, 3, 5, 8]:
        ibs_k = ibs_s.rolling(k).mean()
        for thr in [0.11, 0.145, 0.19, 0.235, 0.28]:
            lo = (ibs_k.shift(1) >= thr) & (ibs_k < thr)
            hi = (ibs_k.shift(1) <= 1 - thr) & (ibs_k > 1 - thr)
            if int(lo.sum() + hi.sum()) < 40:
                continue
            t = se.simulate_trades(df, lo.fillna(False), hi.fillna(False),
                                   sl_pip=sl_pip, tp_pip=tp_pip, asset='XAUUSD',
                                   max_hold=64, allow_overlap=False)
            if len(t) < 40:
                continue
            wins = t['outcome'].eq('win') if 'outcome' in t else (t['pnl_pip'] > 0)
            wr = float(wins.mean()); n = len(t)
            by = t.groupby('direction').agg(n=('pnl_pip','count'), wr=('outcome', lambda s: (s=='win').mean()))
            rec = dict(tf=TF, k=k, thr=thr, n=n, wr=round(wr*100,2),
                       pnl=round(float(t['pnl_pip'].mean()),3),
                       long_n=int(by.loc['long','n']) if 'long' in by.index else 0,
                       long_wr=round(float(by.loc['long','wr'])*100,2) if 'long' in by.index else None,
                       short_n=int(by.loc['short','n']) if 'short' in by.index else 0,
                       short_wr=round(float(by.loc['short','wr'])*100,2) if 'short' in by.index else None)
            res.append(rec)
            print(rec, flush=True)
    return dict(tf=TF, sl_pip=sl_pip, tp_pip=tp_pip, half_bars=len(df), results=res)

all_out = {}
for TF in ['M30', 'H1', 'H2', 'H3', 'H6']:
    print(f'===== {TF} =====')
    all_out[TF] = run_tf(TF)

with open(f'{OUT}/hourly_refine.json', 'w') as f:
    json.dump(all_out, f, ensure_ascii=False, indent=1)
print('saved -> hourly_refine.json')
