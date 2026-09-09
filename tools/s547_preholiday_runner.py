# -*- coding: utf-8 -*-
"""S547 — رانرِ Pre-Holiday Drift (Ariel 1990) روی خانوادهٔ ۱۱-کارتیِ XAUUSD (دادهٔ کامل).

پیش‌ثبت: `results/S547_PREREG_PREHOLIDAY_DRIFT_XAUUSD_MTF.md`
(commit شده **قبل** از این اجرا — n_trials=24).

صفر بازنویسی (میراث S520/S541..S546):
  • شبیه‌ساز/ATR/pip: عیناً `strategies/s382_williamsr_momentum.py`
  • مدل صفر: عیناً `tools/s382_null_model.py` (K=2000، غیرشرطی)
  • داوری per-card: عیناً `run_card` از `tools/s382_mtf_runner.py`

وصله‌های مجاز (قفل در پیش‌ثبت):
  ۱) L.signals → آخرین کندلِ روزِ معاملاتیِ قبل از روزِ پیش‌تعطیلات P (LONG)
  ۲) L.load   → data/full/{card}.csv (gunzip از data/mt5_full؛ H4 تجمیع‌شده از H1 همان منبع)
  ۳) MTF.SEED=20260825، MTF.N_TRIALS=24
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar
from dateutil.easter import easter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
os.chdir(ROOT)

OUT = 'results/_s547'
SEED = 20260825
N_TRIALS = 24      # ۱۲ کارت × ۲ واریانت ذهنی پنجره

HEADLINE = ['XAUUSD_M15', 'XAUUSD_M20', 'XAUUSD_M30', 'XAUUSD_H1',
            'XAUUSD_H2', 'XAUUSD_H3', 'XAUUSD_H4', 'XAUUSD_H6',
            'XAUUSD_H8', 'XAUUSD_H12', 'XAUUSD_D1']
REPORT_ONLY = ['XAUUSD_W1']


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def preholiday_days(y0=2010, y1=2027):
    """روزهای پیش‌تعطیلات P — تقویم قطعی NYSE-style (منجمد در پیش‌ثبت)."""
    h = USFederalHolidayCalendar().holidays(f'{y0}-01-01', f'{y1}-12-31', return_name=True)
    keep = h[~h.str.contains('Columbus|Veterans')]
    gf = pd.DatetimeIndex([pd.Timestamp(easter(y)) - pd.Timedelta(days=2) for y in range(y0, y1 + 1)])
    hol = keep.index.union(gf).sort_values()
    pre = []
    for d in hol:
        p = d - pd.offsets.BDay(1)
        while p in hol:
            p = p - pd.offsets.BDay(1)
        pre.append(p)
    return pd.DatetimeIndex(pre).unique().sort_values()


_PRE = preholiday_days()


def make_signals(df):
    """سیگنال روی آخرین کندلِ آخرین روزِ معاملاتیِ پیش از P (ورود در close آن = open روز P)."""
    dt = pd.to_datetime(df['time'], unit='s')
    dates = dt.dt.normalize().to_numpy()
    n = len(df)
    sig = np.zeros(n, dtype=bool)
    for p in _PRE.to_numpy():
        k = int(np.searchsorted(dates, p, side='left'))   # اولین کندل با تاریخ ≥ P
        if k == 0 or k >= n:
            continue
        # k-1 = آخرین کندل با تاریخ < P؛ فقط اگر آن روز حداکثر ۴ روز قبل از P باشد (داده‌ای موجود)
        gap_days = (p - dates[k - 1]) / np.timedelta64(1, 'D')
        if gap_days <= 4:
            sig[k - 1] = True
    return pd.Series(sig, index=df.index)


def main():
    os.makedirs(OUT, exist_ok=True)
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')
    NM = _mod('tools/s382_null_model.py', '_nm')
    MTF = _mod('tools/s382_mtf_runner.py', '_mtf')

    L.signals = make_signals

    def load_full(card):
        # همهٔ کارت‌ها از data/full (gunzip از data/mt5_full)؛ H4 از H1 همان منبع تجمیع شده (روش resample_cards، اعتبار H1→D1 = تطابق کامل)
        path = f'data/full/{card}.csv'
        df = pd.read_csv(path)
        df['dt'] = pd.to_datetime(df['time'], unit='s')
        span = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days / 365.25
        print(f'  [DATA] {path} rows={len(df)} '
              f'{df["dt"].iloc[0].date()} → {df["dt"].iloc[-1].date()} '
              f'({span:.2f}y)', flush=True)
        if span < 14.0:
            raise RuntimeError(f'BUG-DATASETDRIFT: span {span:.2f}y < 14y for {card}')
        return df

    L.load = load_full
    MTF.SEED = SEED
    MTF.N_TRIALS = N_TRIALS

    cards = sys.argv[1:] or (HEADLINE + REPORT_ONLY)
    print(f'S547 Pre-Holiday Drift | {len(_PRE)} pre-holiday days 2010-2027 | side=long | '
          f'geometry: sl=1.5xATR(100) rr={L.RR} | data=full 15.6y (mt5_full) | '
          f'k={MTF.K} seed={SEED} n_trials={N_TRIALS}', flush=True)
    for card in cards:
        tag = ' [REPORT-ONLY]' if card in REPORT_ONLY else ''
        print(f'--- {card}{tag} ---', flush=True)
        try:
            r = MTF.run_card(card, L, NM)
        except Exception as e:
            print(f'{card}: ERROR {e}', flush=True)
            continue
        r['report_only'] = card in REPORT_ONLY
        with open(f'{OUT}/{card}.json', 'w') as f:
            json.dump(r, f, ensure_ascii=False, default=str)
        print(f'{card}: span={r.get("span_years")}y n={r.get("n_trades")} '
              f'sl={r.get("sl_pip")}pip wr={r.get("wr")} be={r.get("be")} '
              f'lift={r.get("lift")} unc={r.get("uncond_wr")} '
              f'pmax={r.get("perm_max")} z={r.get("z")} rqs2={r.get("rqs2")} '
              f'verdict={r.get("verdict")}{tag}', flush=True)
        print(f'  saved -> {OUT}/{card}.json', flush=True)


if __name__ == '__main__':
    main()
