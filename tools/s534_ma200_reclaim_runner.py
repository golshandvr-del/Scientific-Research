# -*- coding: utf-8 -*-
"""S534 — تسخیرِ تازهٔ SMA200 (fresh reclaim) ⇒ LONG | XAUUSD H4/H6/H8/H12/D1 (+ گزارشی).

پیش‌ثبت: `results/S534_PREREG_Ma200FreshReclaim_Xauusd_H4H6H8H12D1.md`
(commit d0838c36 — قبل از این اجرا؛ مسیر B، صفر پارامتر آزاد).

رویداد: above = close > SMA200(close)؛ سیگنال = above & ~above.shift(1)  (فقط لبه)
هندسه: S382/S526 منجمد (SL=1.5·median ATR100، RR=1.5). نول بی‌قید هم‌هندسه
(uncond stride{1,3,7} + K=2000 جای‌گشت زمان‌بندی) — عیناً tools/s382_null_model.py.
داده: data/mt5_full (۱۵.۶ سال)؛ H4 در mt5_full نیست ⇒ data/XAUUSD_H4.csv (منبع ثبت می‌شود).
n_trials=5. seed=20260818. هر کارت بلافاصله در results/_s534/{card}.json ذخیره می‌شود.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
os.chdir(ROOT)

OUT = 'results/_s534'
JUDGED = ['XAUUSD_D1', 'XAUUSD_H12', 'XAUUSD_H8', 'XAUUSD_H6', 'XAUUSD_H4']
REPORT_ONLY = ['XAUUSD_H3', 'XAUUSD_H2', 'XAUUSD_H1', 'XAUUSD_M30',
               'XAUUSD_M15', 'XAUUSD_M5', 'XAUUSD_W1']
N_TRIALS = 5
MA_P = 200          # BLL 1992 / Faber 2007 — جست‌وجو نمی‌شود
SEED = 20260818
MIN_YEARS = 14.0    # گارد DATASETDRIFT


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    os.makedirs(OUT, exist_ok=True)
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')
    NM = _mod('tools/s382_null_model.py', '_nm')
    MTF = _mod('tools/s382_mtf_runner.py', '_mtf')
    MTF.N_TRIALS = N_TRIALS
    MTF.SEED = SEED
    NM.SEED = SEED
    src_used = {}

    def load_full(card):
        path = f'data/mt5_full/{card}.csv'
        if not os.path.exists(path):
            path = f'data/{card}.csv'
        df = pd.read_csv(path)
        df['dt'] = pd.to_datetime(df['time'], unit='s')
        span = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days / 365.25
        if span < MIN_YEARS:
            raise RuntimeError(f'DATASETDRIFT: {path} span={span:.1f}y < {MIN_YEARS}')
        src_used[card] = dict(path=path, rows=int(len(df)), span_years=round(span, 2),
                              first=str(df['dt'].iloc[0]), last=str(df['dt'].iloc[-1]))
        return df

    L.load = load_full

    def signals_reclaim(df):
        c = df['close']
        sma = c.rolling(MA_P).mean()
        above = (c > sma).fillna(False)
        return (above & ~above.shift(1).fillna(False)).astype(bool)

    L.signals = signals_reclaim

    cards = sys.argv[1:] or (JUDGED + REPORT_ONLY)
    print(f'S534 MA200 fresh reclaim | close crosses above SMA({MA_P}), edge only, '
          f'LONG | sl_k={L.SL_K} rr={L.RR} | unconditional null k={NM.K} '
          f'seed={SEED} n_trials={N_TRIALS}', flush=True)
    for card in cards:
        tag = ' [REPORT-ONLY]' if card in REPORT_ONLY else ''
        print(f'--- {card}{tag} ---', flush=True)
        try:
            r = MTF.run_card(card, L, NM)
        except Exception as e:
            print(f'{card}: ERROR {e}', flush=True)
            continue
        r['ma_period'] = MA_P
        r['report_only'] = card in REPORT_ONLY
        r['data_src'] = src_used.get(card)
        r['seed'] = SEED
        with open(f'{OUT}/{card}.json', 'w') as f:
            json.dump(r, f, ensure_ascii=False, default=str)
        print(f'{card}: span={r.get("span_years")}y nsig={r.get("n_signals")} '
              f'n={r.get("n_trades")} sl={r.get("sl_pip")}pip wr={r.get("wr")} '
              f'be={r.get("be")} lift={r.get("lift")} unc={r.get("uncond_wr")} '
              f'pmax={r.get("perm_max")} z={r.get("z")} rqs2={r.get("rqs2")} '
              f'verdict={r.get("verdict")}', flush=True)
        print(f'  saved -> {OUT}/{card}.json', flush=True)


if __name__ == '__main__':
    main()
