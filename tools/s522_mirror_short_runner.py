# -*- coding: utf-8 -*-
"""S522 — آینهٔ SHORT قاعدهٔ S382: WPR(14) گذر به زیر −87 ⇒ SHORT.

پیش‌ثبت: `results/S522_PREREG_MirrorShortWPR_Xauusd_H4H6H8H12.md`
(commit شده قبل از این اجرا — مسیر B، خانوادهٔ ۴ کارت، صفر پارامتر آزاد).

اصل صفر-بازنویسی — سه وصلهٔ مجاز:
  ۱) منبع داده = `data/full/` (۱۵.۵۹ سال)
  ۲) `L.signals` → گذرِ آینه: (w.shift(1) >= −87) & (w < −87)
  ۳) `L.simulate_trades` → wrapper که is_long را به False برمی‌گرداند.
     چون run_card و null هر دو True را hardcode کرده‌اند، این wrapper
     به‌طور یکنواخت جهت را در سیگنال، خط‌پایهٔ بی‌قید (stride 1/3/7)
     و جایگشت K=2000 معکوس می‌کند — یعنی مدل صفر هم به‌درستی
     «SHORT بی‌قید» می‌شود (مقایسهٔ عادلانه، همان پروتکل اندازه‌گیری).

n_trials = 23770 (23766 قبلی + 4 عضو این خانواده).
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

OUT = 'results/_s522'
MIRROR_THR = -87.0   # آینهٔ دقیق −13 حول مرکز −50
CARDS = ['XAUUSD_H4', 'XAUUSD_H6', 'XAUUSD_H8', 'XAUUSD_H12']
N_TRIALS = 23770


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

    # وصلهٔ ۱: دادهٔ کامل. نکته: مجموعهٔ mt5_full عمداً H4 ندارد چون
    # data/XAUUSD_H4.csv قدیمی خودش کامل است (۱۵.۵۳y، همان کارت لایو).
    def load_full(card):
        path = f'data/full/{card}.csv'
        if not os.path.exists(path):
            path = f'data/{card}.csv'
        df = pd.read_csv(path)
        df['dt'] = pd.to_datetime(df['time'], unit='s')
        return df

    L.load = load_full

    # وصلهٔ ۲: سیگنال آینه (رویدادِ گذر به زیر −87)
    def signals_mirror(df):
        w = L.willr(df)
        return (w.shift(1) >= MIRROR_THR) & (w < MIRROR_THR)

    L.signals = signals_mirror

    # وصلهٔ ۳: جهت SHORT به‌طور یکنواخت (سیگنال + هر دو خط‌پایهٔ صفر)
    _sim = L.simulate_trades

    def simulate_short(df, sig, sl_px, tp_px_mult, is_long, ps):
        return _sim(df, sig, sl_px, tp_px_mult, False, ps)

    L.simulate_trades = simulate_short

    cards = sys.argv[1:] or CARDS
    print(f'S522 mirror-short | willr(14)<{MIRROR_THR} (cross event) '
          f'sl_k={L.SL_K} rr={L.RR} side=SHORT | data=data/full/ '
          f'k={MTF.K} n_trials={N_TRIALS}', flush=True)
    for card in cards:
        try:
            r = MTF.run_card(card, L, NM)
        except Exception as e:
            print(f'{card}: ERROR {e}', flush=True)
            continue
        r['side'] = 'short'
        r['mirror_thr'] = MIRROR_THR
        with open(f'{OUT}/{card}.json', 'w') as f:
            json.dump(r, f, ensure_ascii=False, default=str)
        print(f'{card}: span={r.get("span_years")}y n={r.get("n_trades")} '
              f'sl={r.get("sl_pip")}pip wr={r.get("wr")} be={r.get("be")} '
              f'lift={r.get("lift")} unc={r.get("uncond_wr")} '
              f'pmax={r.get("perm_max")} z={r.get("z")} '
              f'rqs2={r.get("rqs2")} verdict={r.get("verdict")}', flush=True)
        print(f'  saved -> {OUT}/{card}.json', flush=True)


if __name__ == '__main__':
    main()
