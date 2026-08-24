#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S404 — ممیزیِ هم‌پوشانی (قانونِ Overlap ماموریت ۱)
==================================================
مقایسهٔ روزها/لحظه‌های ورودِ S404 (ACCEPT 96.8) با لایه‌های زندهٔ هم‌خانواده:
  - S560-M5 (ACCEPT 96.0، بلوکِ لایب‌نیتس) — سیگنالِ گپِ منفی، TF متفاوت
  - S560-M1 (ACCEPT 95.6)
فقط خواندنِ read-only از کدِ دیگران (tools/s560_*)؛ هیچ فایلی از بلوکِ دیگران
نوشته/تغییر داده نمی‌شود. خروجی: results/_s404_overlap.json
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from engine import scalp_engine as se
from strategies.s400_gap_open import build_days, daily_atr
from strategies.s404_gap_fill_window import run_layer, vol_flags

# read-only از بلوکِ S560 (لایب‌نیتس)
from tools import s434_fast_data as fd
from tools.s560_gapopen_explore import day_breaks, causal_neg_gap_quantile

S560_CFG = {'M5': dict(q=80, sw=True), 'M1': dict(q=80, sw=True)}


def s404_entry_times():
    df = se.load_data('data/XAUUSD_M30.csv')
    days = build_days(df)
    atr = daily_atr(days)
    vf = vol_flags(days, atr)
    strat = run_layer(df, days, atr, 2.0, True, 0, vflags=vf)
    t = pd.to_datetime(df['dt'].values[strat['entry_bar'].values])
    return t


def s560_entry_times(tf):
    d = fd.load_fast('XAUUSD', tf)
    t, o, c = d['time'], d['open'], d['close']
    n = len(t)
    brk = day_breaks(t, tf)
    brk = brk[brk + 1 < n]
    gaps = o[brk + 1] - c[brk]
    weekend = (t[brk + 1] - t[brk]) > 86400
    cfg = S560_CFG[tf]
    thr = causal_neg_gap_quantile(gaps, cfg['q'], weekend, cfg['sw'])
    cond = (gaps < 0) & ~np.isnan(thr) & (np.abs(gaps) > thr)
    ent = brk[cond] + 1                     # موتور در openِ کندلِ بعد وارد می‌شود
    return pd.to_datetime(t[ent], unit='s')


def main():
    a = s404_entry_times()
    out = {'s404': {'n': int(len(a))}}
    a_days = set(pd.DatetimeIndex(a).normalize())
    for tf in ('M5', 'M1'):
        b = s560_entry_times(tf)
        b_days = set(pd.DatetimeIndex(b).normalize())
        inter = a_days & b_days
        union = a_days | b_days
        # هم‌پوشانی لحظه‌ای: ورودِ S560 درونِ ±30 دقیقهٔ ورودِ S404
        av = np.sort(a.values.astype('int64'))
        bv = np.sort(b.values.astype('int64'))
        tol = 30 * 60 * 10**9
        idx = np.searchsorted(av, bv)
        mom = 0
        for i, x in zip(idx, bv):
            near = []
            if i < len(av): near.append(abs(av[i] - x))
            if i > 0: near.append(abs(av[i-1] - x))
            if near and min(near) <= tol:
                mom += 1
        out[f's560_{tf}'] = {
            'n': int(len(b)),
            'shared_days': int(len(inter)),
            's404_share_of_own_days_pct': round(100*len(inter)/len(a_days), 2),
            'jaccard_days_pct': round(100*len(inter)/len(union), 2),
            'momentary_pm30min': int(mom),
        }
    outp = os.path.join(os.path.dirname(__file__), '..', 'results', '_s404_overlap.json')
    with open(outp, 'w') as f:
        json.dump(out, f, indent=1)
    print(json.dumps(out, indent=1))
    print(f"saved → {outp}")


if __name__ == '__main__':
    main()
