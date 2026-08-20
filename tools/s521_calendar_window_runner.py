# -*- coding: utf-8 -*-
"""S521 — آزمون فرضیهٔ پنجرهٔ تقویمی: WPR(round(56h/TF)) > −13 ⇒ LONG.

پیش‌ثبت: `results/S521_PREREG_CalendarWindowWPR_Xauusd_H1H2H3H6H8H12.md`
(commit شده قبل از این اجرا — مسیر B، خانوادهٔ ۶ کارت).

اصل صفر-بازنویسی (درس ۱۲ باگ مأموریت ۴):
  • willr/atr/simulate_trades/آستانه: عیناً ماژول S382
  • مدل صفر: عیناً `tools/s382_null_model.py` (K=2000، بذر 20260805)
  • داوری per-card: عیناً `run_card` از `tools/s382_mtf_runner.py`

دو وصلهٔ مجاز (تنها دلایل وجود این فایل):
  ۱) منبع داده = `data/full/` (۱۵.۵۹ سال)
  ۲) دورهٔ WPR per-card از فرمول قطعی 56h/TF — از طریق جایگزینی
     `L.signals` با نسخه‌ای که همان `L.willr(df, p)` را با p صریح
     صدا می‌زند (آرگومان پیش‌فرض ۱۴ در زمان تعریف بسته شده؛ patch
     متغیر سراسری WILLR_P اثری روی آن ندارد — این را آزموده‌ام).

n_trials = 23766 (بار ارثی صادقانه: 23755 جستجوی S382 + 5 کارت S520
+ 6 کارت این خانواده).
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

OUT = 'results/_s521'

# فرمول قطعی: p = round(56h / TF) — پنجرهٔ تقویمی ثابت ~۵۶ ساعت
PERIODS = {
    'XAUUSD_H1': 56,
    'XAUUSD_H2': 28,
    'XAUUSD_H3': 19,   # round(56/3)=18.67→19
    'XAUUSD_H6': 9,    # round(56/6)=9.33→9
    'XAUUSD_H8': 7,
    'XAUUSD_H12': 5,   # round(56/12)=4.67→5
}
N_TRIALS = 23766


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
    MTF.N_TRIALS = N_TRIALS          # بار چندگانگی به‌روزشده

    def load_full(card):
        df = pd.read_csv(f'data/full/{card}.csv')
        df['dt'] = pd.to_datetime(df['time'], unit='s')
        return df

    L.load = load_full

    cards = sys.argv[1:] or list(PERIODS)
    print(f'S521 calendar-window | willr(p=56h/TF)>{L.WILLR_THR} '
          f'sl_k={L.SL_K} rr={L.RR} side=long | data=data/full/ '
          f'k={MTF.K} n_trials={N_TRIALS}', flush=True)
    for card in cards:
        p = PERIODS[card]

        # وصلهٔ ۲: سیگنال با دورهٔ تقویمی — همان willr و همان معناشناسیِ
        # رویدادگذرِ ماژول S382، فقط p صریح.
        def signals_cal(df, _p=p):
            w = L.willr(df, _p)
            return (w.shift(1) <= L.WILLR_THR) & (w > L.WILLR_THR)

        L.signals = signals_cal

        try:
            r = MTF.run_card(card, L, NM)
        except Exception as e:
            print(f'{card}: ERROR {e}', flush=True)
            continue
        r['willr_period'] = p
        with open(f'{OUT}/{card}.json', 'w') as f:
            json.dump(r, f, ensure_ascii=False, default=str)
        print(f'{card} (p={p}): span={r.get("span_years")}y '
              f'n={r.get("n_trades")} sl={r.get("sl_pip")}pip '
              f'wr={r.get("wr")} be={r.get("be")} lift={r.get("lift")} '
              f'unc={r.get("uncond_wr")} pmax={r.get("perm_max")} '
              f'z={r.get("z")} rqs2={r.get("rqs2")} '
              f'verdict={r.get("verdict")}', flush=True)
        print(f'  saved -> {OUT}/{card}.json', flush=True)


if __name__ == '__main__':
    main()
