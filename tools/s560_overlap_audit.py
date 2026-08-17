# -*- coding: utf-8 -*-
"""
s560_overlap_audit.py — قانون همپوشانی S560 (بند ۴.۳ سند Handoff — فوری)

سؤال ۱: ورودهای S560 (M1/M5 پذیرفته) با کدام لایهٔ زندهٔ سایت هم‌رویدادند و
        چند درصد؟ خط مبنای شانس: دوجمله‌ای با نرخ آتش‌باری بی‌قید لایهٔ موجود
        (روش s356_overlap_analysis — یک‌طرفه به سمت بیش‌همپوشانی).
سؤال ۲ (بند ۳ — فیلتر): آیا «روزِ S560» (روزی که گپ منفی بزرگ رخ داده) به‌عنوان
        فیلتر روی لایهٔ زندهٔ S355 (XAUUSD-M5) ارزش می‌افزاید؟ سنجش: WR ورودهای
        S355 در روزهای S560 در برابر سایر روزها + آزمون دقیق فیشر.

لایه‌های سنجیده: S355 (M5 — تنها لایهٔ زندهٔ هم-TF با S560-M5).
سایر لایه‌ها (S344-M15، S312-M30، S356-H1، S382-H4) روی TFهای ردشدهٔ S560 هستند؛
برایشان فقط هم‌روزیِ رویداد گزارش می‌شود (سیگنال S560 یک لحظهٔ روز است —
open روز — و لایه‌های درون‌روزی در ادامهٔ روز می‌آیند: همپوشانی «لحظه‌ای» صفرِ
ساختاری دارد، ولی «روزی» باید اندازه گرفته شود).
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'strategies'))

from engine import scalp_engine as se                      # noqa: E402
from tools import s434_fast_data as fd                     # noqa: E402
from tools.s560_adjudicate import build, LOCK_PATH         # noqa: E402
import s333_s79_pullback_revival as s333                   # noqa: E402
from strategies.s351_lpsb import lpsb_signals              # noqa: E402
from strategies.s351_verdict import CENTRAL                # noqa: E402

OUT = os.path.join(ROOT, 'results', '_s560_arms', 'overlap.json')
WARMUP = 400


def day_key(ts: np.ndarray) -> np.ndarray:
    return (ts // 86400).astype(np.int64)


def main():
    # --- S560-M5: روزهای سیگنال ---
    d5, df5, mask560, split_bar, cfg = build('M5')
    sig_idx = np.flatnonzero(mask560)
    entry_idx = sig_idx + 1                       # کندل ورود
    t5 = d5['time']
    s560_days = set(day_key(t5[entry_idx]).tolist())
    print(f"S560-M5: {len(entry_idx)} ورود · {len(s560_days)} روز یکتا")

    # --- S355 (لایهٔ زندهٔ M5) روی همان دادهٔ کامل ---
    cfg355 = s333.BEST_CFG['XAUUSD_M5']
    base = s333.build_layer(df5, cfg355)
    _, _, state = lpsb_signals(df5, CENTRAL['L'], CENTRAL['f'], warmup=WARMUP)
    m355 = np.asarray(base, bool) & (np.asarray(state) == -1)
    idx355 = np.flatnonzero(m355)
    print(f"S355-M5: {len(idx355)} سیگنال روی دادهٔ کامل")

    # ۱) همپوشانی لحظه‌ای (هم‌کندلی ±۱) + خط مبنای شانس
    n = len(t5)
    fire_rate = len(idx355) / n
    s560_set = set(sig_idx.tolist())
    coincide = sum(1 for i in idx355
                   if (i in s560_set or (i - 1) in s560_set or (i + 1) in s560_set))
    k_tests = len(idx355) * 3
    expected = k_tests * (len(sig_idx) / n)
    # p یک‌طرفه (پواسون تقریبی برای شمارش کم)
    from math import exp
    lam = expected
    p_over = 1.0 - sum(exp(-lam) * lam**k / np.math.factorial(k)
                       for k in range(coincide)) if coincide < 100 else 0.0

    # ۲) همپوشانی روزی
    days355 = day_key(t5[idx355])
    on_day = np.isin(days355, list(s560_days))
    share = float(on_day.mean() * 100)
    all_days = len(set(day_key(t5).tolist()))
    base_rate = len(s560_days) / all_days * 100

    # ۳) بند ۳ — فیلتر: WR معاملات S355 در روزهای S560 در برابر بقیه
    sl, tp, mh = float(cfg355['sl']), float(cfg355['tp']), int(cfg355['mh'])
    z = np.zeros(n, bool)
    tr = se.simulate_trades(df5, m355, z, sl, tp, 'XAUUSD',
                            max_hold=mh, allow_overlap=False)
    ed = day_key(t5[tr['entry_bar'].values.astype(int)])
    in560 = np.isin(ed, list(s560_days))
    win = (tr['pnl_pip'].values > 0)
    a, b = int((win & in560).sum()), int((~win & in560).sum())
    c, dd_ = int((win & ~in560).sum()), int((~win & ~in560).sum())
    from scipy import stats
    if min(a + b, c + dd_) >= 5:
        _, p_fisher = stats.fisher_exact([[a, b], [c, dd_]], alternative='two-sided')
    else:
        p_fisher = None
    wr_in = 100 * a / (a + b) if a + b else None
    wr_out = 100 * c / (c + dd_) if c + dd_ else None

    out = dict(
        s560_m5=dict(n_entries=int(len(entry_idx)), n_days=len(s560_days)),
        s355=dict(n_signals=int(len(idx355)), fire_rate=fire_rate),
        momentary=dict(coincidences_pm1=int(coincide),
                       expected_by_chance=round(float(expected), 2),
                       p_over=round(float(p_over), 4)),
        daily=dict(s355_share_on_s560_days_pct=round(share, 2),
                   chance_baseline_pct=round(base_rate, 2)),
        filter_test=dict(
            s355_trades_on_s560_days=a + b, wr_on=round(wr_in, 2) if wr_in else None,
            s355_trades_off=c + dd_, wr_off=round(wr_out, 2) if wr_out else None,
            fisher_p=round(float(p_fisher), 4) if p_fisher is not None else None),
    )
    json.dump(out, open(OUT, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"saved → {OUT}")


if __name__ == '__main__':
    main()
