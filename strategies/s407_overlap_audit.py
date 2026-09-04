#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S407 — ممیزی هم‌پوشانی (تعهد مأموریت ۱، فقط‌خواندنی)
======================================================
مقایسهٔ روزهای ورود S407 (M15 فیل، V ثابت) با:
  • S404 (M30 فیل، ACCEPT 96.8 — بلوک خودم)
  • S562-M15 (لایبنیتس، ACCEPT 95.3 — از آرتیفکت منجمدِ results/_s562_arms/signal_bars_M15.json،
    فیلد signal_times_rolling؛ هیچ فایل بلوک S560 نوشته نمی‌شود)
خروجی: results/_s407_overlap.json
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from engine import scalp_engine as se
from strategies.s400_gap_open import build_days, daily_atr
from strategies.s404_gap_fill_window import vol_flags
from strategies import s404_gap_fill_window as s404
from strategies import s407_gap_fill_m15_vfixed as s407

ROOT = os.path.join(os.path.dirname(__file__), '..')


def entry_days(tf, runner, **kw):
    df = se.load_data(f'data/XAUUSD_{tf}.csv')
    days = build_days(df); atr = daily_atr(days); vf = vol_flags(days, atr)
    tr = runner(df, days, atr, vflags=vf, **kw)
    t = pd.to_datetime(df['dt'].values[tr['entry_bar'].values])
    return sorted(set(pd.DatetimeIndex(t).normalize().strftime('%Y-%m-%d'))), t


def main():
    d407, t407 = entry_days('M15', s407.run_layer, q=70, k_sl=2.0, use_v=True)
    d404, t404 = entry_days('M30', s404.run_layer, k_sl=2.0, use_v=True, cooldown_d=0)

    sb = json.load(open(os.path.join(ROOT, 'results/_s562_arms/signal_bars_M15.json')))
    t562 = pd.to_datetime(np.array(sb['signal_times_rolling'], dtype='int64'), unit='s')
    d562 = sorted(set(pd.DatetimeIndex(t562).normalize().strftime('%Y-%m-%d')))

    def cmp(a, b):
        sa, sb_ = set(a), set(b)
        inter = sa & sb_
        return dict(n_a=len(sa), n_b=len(sb_), shared=len(inter),
                    share_of_a=round(100 * len(inter) / max(1, len(sa)), 1),
                    share_of_b=round(100 * len(inter) / max(1, len(sb_)), 1),
                    jaccard=round(100 * len(inter) / max(1, len(sa | sb_)), 1))

    # پنجرهٔ مشترک: داده‌ی M15 (data/XAUUSD_M15.csv) از 2020-02 شروع می‌شود؛ S404/S562 از 2011.
    lo, hi = d407[0], d407[-1]
    d404w = [d for d in d404 if lo <= d <= hi]
    d562w = [d for d in d562 if lo <= d <= hi]

    out = {
        'S407_n_days': len(d407),
        'window_note': 'S404/S562 restricted to S407 data window [first,last] for fair comparison',
        'vs_S404_M30_window': cmp(d407, d404w),
        'vs_S562_M15_rolling_window': cmp(d407, d562w),
        'S407_first': d407[0], 'S407_last': d407[-1],
        'vs_S404_M30': cmp(d407, d404),
        'vs_S562_M15_rolling': cmp(d407, d562),
        'note': 'day-level overlap; S562 times from frozen read-only artifact (Leibniz block untouched)',
    }
    print(json.dumps(out, indent=1, ensure_ascii=False))
    with open(os.path.join(ROOT, 'results/_s407_overlap.json'), 'w') as f:
        json.dump(out, f, indent=1, ensure_ascii=False)


if __name__ == '__main__':
    main()
