# -*- coding: utf-8 -*-
"""S543 — رانرِ Break-Retest-Hold روی خانوادهٔ ۱۱-کارتیِ XAUUSD (دادهٔ کامل).

پیش‌ثبت: `results/S543_PREREG_BREAK_RETEST_HOLD_XAUUSD_MTF.md`
(commit شده **قبل** از این اجرا — مسیر B، n_trials=44).

اصل معماری: صفر بازنویسی (میراث S520/S541/S542). این رانر هیچ منطق
داوری/شبیه‌سازی از خودش ندارد:

  • شبیه‌ساز/ATR/pip: عیناً `strategies/s382_williamsr_momentum.py`
  • مدل صفر: عیناً `tools/s382_null_model.py` (K=2000)
  • داوری per-card: عیناً `run_card` از `tools/s382_mtf_runner.py`

وصله‌های مجاز (هر سه در پیش‌ثبت قفل):
  ۱) L.signals → ماشین حالت سه‌فازی Break-Retest-Hold
       LOOK=55 (سطح = rolling_max(high,55) با شیفت ۱)
       W=20 (سقف انتظار پولبک+تأیید از لحظهٔ شکست)
       TOL=0.25×ATR100 (تلورانس لمس/ابطال)
  ۲) L.load   → data/full/{card}.csv؛ استثنای H4 = data/XAUUSD_H4.csv
  ۳) MTF.SEED=20260821، MTF.N_TRIALS=44
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

OUT = 'results/_s543'
LOOK = 55       # سطح = سقف ۵۵ کندلی — منجمد در پیش‌ثبت §2
W = 20          # سقف کندل‌های انتظار پس از شکست — منجمد
TOL_K = 0.25    # تلورانس = 0.25×ATR100 — منجمد
SEED = 20260821
N_TRIALS = 44   # ۱۱ کارت × ۴ واریانت ذهنی طراحی (LOOK×TOL)

HEADLINE = ['XAUUSD_M15', 'XAUUSD_M20', 'XAUUSD_M30', 'XAUUSD_H1',
            'XAUUSD_H2', 'XAUUSD_H3', 'XAUUSD_H4', 'XAUUSD_H6',
            'XAUUSD_H8', 'XAUUSD_H12', 'XAUUSD_D1']
REPORT_ONLY = ['XAUUSD_W1']

_ATR_REF = None  # پر می‌شود در main با L.atr


def make_signals(df):
    """ماشین حالت سه‌فازی: شکست سقف ۵۵کندلی → پولبک به سطح → کلوز بازگشتی بالای سطح.

    چرا حالتمند: قانون S541 (هموارسازی مرده) + قانون S542 (آناتومی تک‌کندل
    مرده) ⇒ فقط رویدادهای ساختاری با حافظهٔ چندکندلی مجازند. این ماشین سه
    فاز مجزا دارد و سیگنالش تنها با توالیِ خاصی از رویدادها روشن می‌شود.
    """
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    n = len(df)

    lvl = pd.Series(h).rolling(LOOK).max().shift(1).to_numpy(float)  # L(t)
    atr = _ATR_REF(df).to_numpy(float)

    sig = np.zeros(n, dtype=bool)
    state = 0          # 0=جستجوی شکست، 1=انتظار پولبک، 2=انتظار نگهداشت
    B = np.nan         # سطح شکسته‌شدهٔ قفل‌شده
    t_break = -1

    for t in range(1, n):
        if not np.isfinite(lvl[t]) or not np.isfinite(atr[t]):
            continue
        tol = TOL_K * atr[t]
        if state == 0:
            if np.isfinite(lvl[t - 1]) and c[t] > lvl[t] and c[t - 1] <= lvl[t - 1]:
                B = lvl[t]
                t_break = t
                state = 1
        elif state == 1:
            if t - t_break > W or c[t] < B - tol:
                state = 0          # اپیزود باطل
            elif l[t] <= B + tol:
                state = 2          # پولبک لمس شد
                if c[t] > B:       # همین کندل هم نگه داشت ⇒ سیگنال
                    sig[t] = True
                    state = 0
        elif state == 2:
            if t - t_break > W or c[t] < B - tol:
                state = 0          # اپیزود باطل
            elif c[t] > B:
                sig[t] = True      # نگهداشت تأیید شد — LONG در کلوز
                state = 0

    return pd.Series(sig, index=df.index)


def main():
    global _ATR_REF
    os.makedirs(OUT, exist_ok=True)
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')
    NM = _mod('tools/s382_null_model.py', '_nm')
    MTF = _mod('tools/s382_mtf_runner.py', '_mtf')

    _ATR_REF = L.atr
    L.signals = make_signals

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
    MTF.SEED = SEED
    MTF.N_TRIALS = N_TRIALS

    cards = sys.argv[1:] or (HEADLINE + REPORT_ONLY)
    print(f'S543 Break-Retest-Hold | LOOK={LOOK} W={W} TOL={TOL_K}xATR frozen | '
          f'side=long | geometry: sl=1.5xATR(100) rr={L.RR} | data=full 15.6y | '
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
        r['look'] = LOOK
        r['wait'] = W
        r['tol_k'] = TOL_K
        with open(f'{OUT}/{card}.json', 'w') as f:
            json.dump(r, f, ensure_ascii=False, default=str)
        z = r.get('z')
        print(f'{card}: span={r.get("span_years")}y n={r.get("n_trades")} '
              f'sl={r.get("sl_pip")}pip wr={r.get("wr")} be={r.get("be")} '
              f'lift={r.get("lift")} unc={r.get("uncond_wr")} '
              f'pmax={r.get("perm_max")} z={z} rqs2={r.get("rqs2")} '
              f'verdict={r.get("verdict")}{tag}', flush=True)
        print(f'  saved -> {OUT}/{card}.json', flush=True)


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


if __name__ == '__main__':
    main()
