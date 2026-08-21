# -*- coding: utf-8 -*-
"""
s562_overlap_audit.py — ممیزی هم‌پوشانی S562 (M15/H1 ACCEPT) — قانون Overlap

مقایسه در سطح «روز UTC ورود» (لایه‌های گپ حداکثر یک ورود در روز دارند):
  1) S562-M15 vs S562-H1          (درون-خانواده، TFهای هم‌زمان)
  2) S562-M15/H1 vs S560-M5 ACCEPT (خویشاوند مستقیم — همان سیگنال بدون فیلتر)
  3) S562-M15/H1 vs S404-M30 ACCEPT (لایهٔ گپ‌فیل دانشمند موازی — فقط-خواندنی)
  4) S562-M15 vs S355-M5 زنده      (لحظه‌ای S560 قبلاً صفر بود؛ روزانه گزارش)

خروجی: results/_s562_arms/overlap.json
"""
from __future__ import annotations

import json
import os
import sys
import datetime as dt

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import scalp_engine as se                      # noqa: E402
from tools.s560_adjudicate import build                    # noqa: E402
from tools.s562_volfilter import vol_filter_mask, frozen_geometry  # noqa: E402


def day_set(times_epoch):
    return {dt.datetime.utcfromtimestamp(int(x)).strftime('%Y-%m-%d')
            for x in times_epoch}


def entry_days_s562(tf, qv):
    d, df, mask, split_bar, cfg = build(tf)
    fm = vol_filter_mask(d, tf, mask, qv)
    sl, tp, mh = frozen_geometry(tf)
    z = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, fm, z, sl, tp, 'XAUUSD',
                            max_hold=mh, allow_overlap=False)
    et = df['time'].values[tr['entry_bar'].values.astype(int)]
    return day_set(et), len(tr)


def entry_days_s560_m5():
    d, df, mask, split_bar, cfg = build('M5')
    z = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, mask, z, 48.1, 48.1, 'XAUUSD',
                            max_hold=1, allow_overlap=False)
    et = df['time'].values[tr['entry_bar'].values.astype(int)]
    return day_set(et), len(tr)


def entry_days_s404():
    """بازسازی فقط-خواندنی معاملات S404 با پیکربندی برنده (k_sl=2.0, V, cd=0)."""
    from strategies.s404_gap_fill_window import run_layer, vol_flags
    from strategies.s400_gap_open import build_days, daily_atr
    from tools import s434_fast_data as fd
    d = fd.load_fast('XAUUSD', 'M30')
    df = fd.as_dataframe(d)
    if 'dt' not in df.columns:                    # زنجیرهٔ S404 ستون dt می‌خواهد
        df = df.assign(dt=df['time'])
    days = build_days(df)
    atr = daily_atr(days)
    tr = run_layer(df, days, atr, 2.0, True, 0)
    t = df['time'].values
    et = t[tr['entry_bar'].values.astype(int)] if 'entry_bar' in tr.columns \
        else np.array([days[k]['fb'] for k in range(len(days))])[:0]
    if 'entry_bar' not in tr.columns:
        # fallback: ستون‌های موجود را بیاب
        col = [c for c in tr.columns if 'bar' in c.lower()][0]
        et = t[tr[col].values.astype(int)]
    return day_set(et), len(tr)


def jaccard(a, b):
    return len(a & b) / max(1, len(a | b))


def main():
    m15_days, n_m15 = entry_days_s562('M15', 85)
    h1_days, n_h1 = entry_days_s562('H1', 78)
    m5_days, n_m5 = entry_days_s560_m5()
    try:
        s404_days, n_404 = entry_days_s404()
        s404_err = None
    except Exception as e:  # noqa: BLE001
        s404_days, n_404, s404_err = set(), 0, str(e)

    def pair(a, na, b, nb):
        inter = len(a & b)
        return dict(n_a=na, n_b=nb, days_a=len(a), days_b=len(b),
                    shared_days=inter,
                    share_of_a_pct=round(100 * inter / max(1, len(a)), 2),
                    share_of_b_pct=round(100 * inter / max(1, len(b)), 2),
                    jaccard=round(jaccard(a, b), 4))

    out = {
        'm15_vs_h1': pair(m15_days, n_m15, h1_days, n_h1),
        'm15_vs_s560m5': pair(m15_days, n_m15, m5_days, n_m5),
        'h1_vs_s560m5': pair(h1_days, n_h1, m5_days, n_m5),
        'm15_vs_s404m30': pair(m15_days, n_m15, s404_days, n_404),
        'h1_vs_s404m30': pair(h1_days, n_h1, s404_days, n_404),
        's404_error': s404_err,
        'note_s355': ('momentary overlap S560-family vs S355 measured 0 in '
                      'S560 audit (chance 0.24); S562 masks are strict subsets '
                      'of S560 masks => momentary overlap remains 0.'),
    }
    os.makedirs(os.path.join(ROOT, 'results', '_s562_arms'), exist_ok=True)
    p = os.path.join(ROOT, 'results', '_s562_arms', 'overlap.json')
    json.dump(out, open(p, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"saved → {p}")


if __name__ == '__main__':
    main()
