# -*- coding: utf-8 -*-
"""S541 — رانرِ HA Run-Flip روی خانوادهٔ ۱۱-کارتیِ XAUUSD (دادهٔ کامل).

پیش‌ثبت: `results/S541_PREREG_HEIKIN_ASHI_RUNFLIP_XAUUSD_MTF.md`
(commit شده **قبل** از این اجرا — مسیر B، n_trials=33).

═══════════════════════════════════════════════════════════════════════════
اصل معماری: صفر بازنویسی (میراث S520/S540)
═══════════════════════════════════════════════════════════════════════════

این رانر **هیچ** منطق داوری/شبیه‌سازی از خودش ندارد:

  • شبیه‌ساز/ATR/pip: عیناً `strategies/s382_williamsr_momentum.py`
  • مدل صفر: عیناً `tools/s382_null_model.py` (K=2000)
  • داوری per-card: عیناً `run_card` از `tools/s382_mtf_runner.py`

تنها وصله‌های مجاز (هر سه در پیش‌ثبت قفل شده‌اند):

  ۱) `L.signals` → رویداد HA Run-Flip با R=3 (منجمد، بدون جارو)
  ۲) `L.load`   → دادهٔ کامل `data/full/{card}.csv`؛ استثنای H4 = `data/XAUUSD_H4.csv`
                 (خودش ۱۵.۵ ساله است و در data/full وجود ندارد — الگوی S540)
  ۳) `MTF.SEED=20260819`، `MTF.N_TRIALS=33` (طبق پیش‌ثبت)

ذخیرهٔ مرحله‌به‌مرحله: JSON هر کارت بلافاصله در `results/_s541/` نوشته می‌شود.
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
os.chdir(ROOT)

OUT = 'results/_s541'
R_RUN = 3          # طولِ حداقلِ دنبالهٔ نزولی HA — منجمد در پیش‌ثبت
SEED = 20260819    # بذرِ پیش‌ثبت‌شده
N_TRIALS = 33      # ۱۱ کارت × ۳ مقدارِ R که در طراحی از ذهن گذشت

# خانوادهٔ سرنوشت‌ساز (headline) — دقیقاً از پیش‌ثبت §4
HEADLINE = ['XAUUSD_M15', 'XAUUSD_M20', 'XAUUSD_M30', 'XAUUSD_H1',
            'XAUUSD_H2', 'XAUUSD_H3', 'XAUUSD_H4', 'XAUUSD_H6',
            'XAUUSD_H8', 'XAUUSD_H12', 'XAUUSD_D1']
# کارت‌های صرفاً گزارشی — هرگز ACCEPT نمی‌گیرند (پیش‌ثبت §4/§6)
REPORT_ONLY = ['XAUUSD_W1']


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def heikin_ashi(df):
    """HA استاندارد — تعریفِ عینیِ پیش‌ثبت §2."""
    o = df['open'].to_numpy(float)
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    ha_c = (o + h + l + c) / 4.0
    ha_o = np.empty_like(ha_c)
    ha_o[0] = (o[0] + c[0]) / 2.0
    for i in range(1, len(ha_c)):
        ha_o[i] = (ha_o[i - 1] + ha_c[i - 1]) / 2.0
    return ha_o, ha_c


def make_signals(df):
    """رویدادِ ورود LONG: کندل فعلی HA صعودی و هر R_RUN کندلِ قبلی HA نزولی."""
    ha_o, ha_c = heikin_ashi(df)
    up = ha_c > ha_o
    down = ha_c < ha_o
    sig = up.copy()
    for k in range(1, R_RUN + 1):
        prev_down = np.empty_like(down)
        prev_down[:k] = False
        prev_down[k:] = down[:-k]
        sig &= prev_down
    return pd.Series(sig, index=df.index)


def main():
    os.makedirs(OUT, exist_ok=True)
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')
    NM = _mod('tools/s382_null_model.py', '_nm')
    MTF = _mod('tools/s382_mtf_runner.py', '_mtf')

    # وصلهٔ ۱: سیگنال = HA Run-Flip (منجمد)
    L.signals = make_signals

    # وصلهٔ ۲: منبع داده = دادهٔ کامل؛ استثنای H4 (BUG-DATASETDRIFT چاپ می‌شود)
    def load_full(card):
        path = f'data/{card}.csv' if card == 'XAUUSD_H4' else f'data/full/{card}.csv'
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

    # وصلهٔ ۳: بذر و فضای جست‌وجوی پیش‌ثبت‌شده
    MTF.SEED = SEED
    MTF.N_TRIALS = N_TRIALS

    cards = sys.argv[1:] or (HEADLINE + REPORT_ONLY)
    print(f'S541 HA Run-Flip | R={R_RUN} frozen | side=long | '
          f'geometry: sl=1.5xATR(100) rr={L.RR} | data=full 15.6y | '
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
        r['R_run'] = R_RUN
        with open(f'{OUT}/{card}.json', 'w') as f:
            json.dump(r, f, ensure_ascii=False, default=str)
        z = r.get('z')
        print(f'{card}: span={r.get("span_years")}y n={r.get("n_trades")} '
              f'sl={r.get("sl_pip")}pip wr={r.get("wr")} be={r.get("be")} '
              f'lift={r.get("lift")} unc={r.get("uncond_wr")} '
              f'pmax={r.get("perm_max")} z={z} rqs2={r.get("rqs2")} '
              f'verdict={r.get("verdict")}{tag}', flush=True)
        print(f'  saved -> {OUT}/{card}.json', flush=True)


if __name__ == '__main__':
    main()
