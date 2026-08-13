# -*- coding: utf-8 -*-
"""S520 — اجرای قاعدهٔ منجمدِ S382 روی تایم‌فریم‌های **بکرِ** دادهٔ کامل.

پیش‌ثبت: `results/S520_PREREG_WilliamsRVirginTFs_Xauusd_H2H3H6H8H12.md`
(commit شده **قبل** از این اجرا — مسیرِ B چندگانگی، خانوادهٔ ۵-کارتی).

═══════════════════════════════════════════════════════════════════════════
اصل معماری: صفر بازنویسی
═══════════════════════════════════════════════════════════════════════════

درسِ ۱۲ باگِ مأموریت ۴ («بازسازیِ رابط از حافظه به‌جای خواندنِ منبع»)
اینجا به قانونِ سخت تبدیل می‌شود: این رانر **هیچ** منطقی از خودش ندارد.

  • قاعده و شبیه‌ساز: عیناً `strategies/s382_williamsr_momentum.py`
  • مدلِ صفر: عیناً `tools/s382_null_model.py` (K=2000، بذر 20260805)
  • داوری per-card: عیناً `run_card` از `tools/s382_mtf_runner.py`

تنها تفاوتِ مجاز — و تنها دلیلِ وجودِ این فایل — منبعِ داده است:
`L.load` به `data/full/{card}.csv` هدایت می‌شود (دادهٔ کاملِ ۱۵.۵۹ ساله)،
چون تایم‌فریم‌های H2/H3/H6/H8/H12 در `data/` قدیمی وجود ندارند.

پارامترها قفل: willr(14)>−13، SL=1.5×ATR(100)، RR=1.5، long-only.
n_trials=23755 (همان فضای جست‌وجوی واقعیِ S382 — کم‌گزارشی ممنوع).

ذخیرهٔ مرحله‌به‌مرحله: نتیجهٔ هر کارت بلافاصله در `results/_s520/` نوشته
می‌شود (قانونِ «اندک‌اندک» — سندباکس ناپایدار است).
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

OUT = 'results/_s520'

# خانوادهٔ پیش‌ثبت‌شده — دقیقاً همین ۵ کارت، نه یکی بیشتر (EURUSD حذفِ کاربر)
CARDS = ['XAUUSD_H2', 'XAUUSD_H3', 'XAUUSD_H6', 'XAUUSD_H8', 'XAUUSD_H12']


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

    # تنها وصله: منبعِ داده = دادهٔ کاملِ ۱۵.۵۹ ساله در data/full/
    def load_full(card):
        df = pd.read_csv(f'data/full/{card}.csv')
        df['dt'] = pd.to_datetime(df['time'], unit='s')
        return df

    L.load = load_full

    cards = sys.argv[1:] or CARDS
    print(f'S520 virgin-TF | frozen S382 rule: willr({L.WILLR_P})>{L.WILLR_THR} '
          f'sl_k={L.SL_K} rr={L.RR} side=long | data=data/full/ '
          f'k={MTF.K} n_trials={MTF.N_TRIALS}', flush=True)
    for card in cards:
        try:
            r = MTF.run_card(card, L, NM)
        except Exception as e:
            print(f'{card}: ERROR {e}', flush=True)
            continue
        with open(f'{OUT}/{card}.json', 'w') as f:
            json.dump(r, f, ensure_ascii=False, default=str)
        z = r.get('z')
        print(f'{card}: span={r.get("span_years")}y n={r.get("n_trades")} '
              f'sl={r.get("sl_pip")}pip wr={r.get("wr")} be={r.get("be")} '
              f'lift={r.get("lift")} unc={r.get("uncond_wr")} '
              f'pmax={r.get("perm_max")} z={z} rqs2={r.get("rqs2")} '
              f'verdict={r.get("verdict")}', flush=True)
        print(f'  saved -> {OUT}/{card}.json', flush=True)


if __name__ == '__main__':
    main()
