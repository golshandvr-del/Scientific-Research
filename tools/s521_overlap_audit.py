# -*- coding: utf-8 -*-
"""S521 — ممیزیِ هم‌پوشانی با لایهٔ فعالِ S382-H4 (قانونِ هم‌پوشانیِ پروژه).

پیش‌ثبت‌شده در PREREG S521: هر کارتِ غیرمنفی بلافاصله ممیزیِ
هم‌پوشانیِ تقویمی با معاملاتِ لایوِ S382-H4 (n=869) می‌شود و بخشِ
هم‌پوشان به‌عنوانِ فیلتر (تشخیصی، بدونِ داوریِ RQS2 جدید) گزارش می‌شود.

تفاوت با ممیز S520: سیگنالِ هر کارت WPR با دورهٔ تقویمی
p=round(56h/TF) است، نه p=14. مرجعِ H4 همان بازتولیدِ منجمد است.
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
PERIODS = {
    'XAUUSD_H1': 56, 'XAUUSD_H2': 28, 'XAUUSD_H3': 19,
    'XAUUSD_H6': 9, 'XAUUSD_H8': 7, 'XAUUSD_H12': 5,
}
COST_PIP = 3.3


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def trades_with_time(L, df, sig):
    ps = L.pip_size('XAUUSD')
    sl_abs = float(np.nanmedian(L.atr(df).to_numpy())) * L.SL_K
    tr = L.simulate_trades(df, sig, sl_abs, L.RR, True, ps)
    dtv = df['dt'].values.astype('datetime64[ns]').astype(np.int64)
    tr = tr.copy()
    tr['t_entry'] = dtv[tr['entry_bar'].values]
    tr['t_exit'] = dtv[tr['exit_bar'].values]
    sl_pip = sl_abs / ps
    be = 100.0 * (sl_pip + COST_PIP) / (sl_pip * L.RR + sl_pip)
    return tr, be


def seg_stats(tr, be):
    n = len(tr)
    if n == 0:
        return dict(n=0, wr=None, lift=None)
    wr = 100.0 * float((tr['outcome'] == 'win').mean())
    return dict(n=n, wr=round(wr, 2), lift=round(wr - be, 2))


def main():
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')

    # مرجع: H4ِ پذیرفته‌شده (قاعدهٔ منجمد p=14، دادهٔ قدیمی)
    df_h4 = pd.read_csv('data/XAUUSD_H4.csv')
    df_h4['dt'] = pd.to_datetime(df_h4['time'], unit='s')
    tr_h4, _ = trades_with_time(L, df_h4, L.signals(df_h4))
    print(f'مرجع S382-H4: n={len(tr_h4)} (انتظار: 869)', flush=True)
    iv_e = tr_h4['t_entry'].values
    iv_x = tr_h4['t_exit'].values
    order = np.argsort(iv_e)
    iv_e, iv_x = iv_e[order], iv_x[order]

    def overlaps_h4(t):
        j = np.searchsorted(iv_e, t, 'right') - 1
        lo = max(0, j - 8)
        return bool(np.any((iv_e[lo:j + 1] <= t) & (t < iv_x[lo:j + 1])))

    results = {}
    for card, p in PERIODS.items():
        df = pd.read_csv(f'data/full/{card}.csv')
        df['dt'] = pd.to_datetime(df['time'], unit='s')
        w = L.willr(df, p)
        sig = (w.shift(1) <= L.WILLR_THR) & (w > L.WILLR_THR)
        tr, be = trades_with_time(L, df, sig)
        ov = np.array([overlaps_h4(t) for t in tr['t_entry'].values])
        s_all = seg_stats(tr, be)
        s_ov = seg_stats(tr[ov], be)
        s_no = seg_stats(tr[~ov], be)
        pct = 100.0 * float(ov.mean()) if len(tr) else 0.0
        results[card] = dict(willr_period=p, be=round(be, 2),
                             overlap_pct=round(pct, 1),
                             all=s_all, overlap=s_ov, non_overlap=s_no)
        print(f'{card} (p={p}): overlap={pct:.1f}% | '
              f'all n={s_all["n"]} lift={s_all["lift"]:+.2f} | '
              f'OV n={s_ov["n"]} lift={s_ov["lift"]} | '
              f'nonOV n={s_no["n"]} lift={s_no["lift"]}', flush=True)

    with open(f'{OUT}/overlap_audit.json', 'w') as f:
        json.dump(results, f, ensure_ascii=False)
    print(f'\nsaved -> {OUT}/overlap_audit.json', flush=True)


if __name__ == '__main__':
    main()
