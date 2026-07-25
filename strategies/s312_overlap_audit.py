# -*- coding: utf-8 -*-
"""
s312_overlap_audit.py — ممیزیِ همپوشانیِ S312 با S221(همان S142) و S306 (قانونِ همپوشانیِ پروژه)
================================================================================
سه پرسشِ قانونِ همپوشانی:
  ۱) با کدام لایه/لایه‌ها همپوشانی دارد و «چند درصد»؟ (روزِ ورود + کندلِ ورود)
  ۲) اگر همپوشانیِ بالا بود، آیا آن ۱٪ متفاوت ارزشِ افزودن دارد؟
  ۳) آیا بخشِ همپوشان می‌تواند به‌عنوان فیلتر لایهٔ سوخته‌ای را احیا کند؟

نکتهٔ محوری: S312 و S221 هر دو از **همان بُعدِ ورود** (dom{10,13,20}, ساعت 1..12, طلا Long)
می‌آیند ⇒ همپوشانیِ *روزِ ورود* ذاتاً بالا. اما ساختارِ خروج (RR) کاملاً متفاوت است:
  - S221: نامتقارنِ معکوس (SL بزرگ / TP کوچک) ⇒ WRِ مصنوعیِ بالا، اما زیرِ شبیه‌سازِ
    رویداد-محور روی M30/H1 گیتِ G1 (معناداری) را رد می‌کند ⇒ لبهٔ آماریِ واقعی ندارد.
  - S312: متقارن (SL=TP) ⇒ WR واقع‌بینانه (~۶۱٪) اما G1 روی هر ۳ TF پاس (p<0.01).
این اسکریپت این تمایز را کمّی می‌کند.

اجرا: python3 strategies/s312_overlap_audit.py
"""
import os
import sys
import json
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import trade_simulator as TS
from engine import rqs as RQS
from strategies.sim_strategies import S312_MidMonth_Long, S306_TurnOfMonth_Long


def entry_days_and_bars(tr, df):
    """مجموعهٔ روزهای ورود و اندیس کندلِ ورود از یک جدولِ trade."""
    if tr is None or len(tr) == 0:
        return set(), set()
    eb = tr['entry_bar'].values
    days = set(pd.DatetimeIndex(df['dt'].values[eb]).normalize())
    bars = set(int(x) for x in eb)
    return days, bars


def jacc(a, b):
    if not a and not b:
        return 0.0
    return 100.0 * len(a & b) / max(len(a | b), 1)


def main():
    print(f"{'#'*72}\n# S312 OVERLAP AUDIT (vs S221 same-entry, vs S306 orthogonal)\n{'#'*72}")
    out = {}
    tf = 'XAUUSD_M15'
    df = TS.load_data(tf)
    asset = 'XAUUSD'

    # S312 (symmetric) — نسخهٔ فعالِ پیشنهادی
    s312 = S312_MidMonth_Long(sl_pip=295, tp_pip=295, max_hold=48, quality_filter=True)
    tr312, _ = TS.simulate(df, s312, asset, tf=tf, warmup=240, max_bars_hold=48)
    d312, b312 = entry_days_and_bars(tr312, df)

    # S221 (asymmetric SL200/TP60) — همان بُعدِ ورود، خروجِ متفاوت
    s221 = S312_MidMonth_Long(sl_pip=200, tp_pip=60, max_hold=96, quality_filter=True)
    tr221, _ = TS.simulate(df, s221, asset, tf=tf, warmup=240, max_bars_hold=96)
    d221, b221 = entry_days_and_bars(tr221, df)

    # S306 (Turn-of-Month) — لایهٔ متعامدِ فعال
    s306 = S306_TurnOfMonth_Long()
    tr306, _ = TS.simulate(df, s306, asset, tf=tf, warmup=240, max_bars_hold=48)
    d306, b306 = entry_days_and_bars(tr306, df)

    print(f"\nS312 (sym):  n_trades={len(tr312):4d}  entry_days={len(d312):4d}")
    print(f"S221 (asym): n_trades={len(tr221):4d}  entry_days={len(d221):4d}")
    print(f"S306 (TOM):  n_trades={len(tr306):4d}  entry_days={len(d306):4d}")

    print("\n-- همپوشانیِ روزِ ورود (Jaccard %) --")
    print(f"  S312 ∩ S221 = {jacc(d312,d221):5.1f}%   "
          f"(مشترک={len(d312&d221)}, یگانهٔ S312={len(d312-d221)}, یگانهٔ S221={len(d221-d312)})")
    print(f"  S312 ∩ S306 = {jacc(d312,d306):5.1f}%   (مشترک={len(d312&d306)})")

    print("\n-- همپوشانیِ کندلِ ورودِ دقیق (Jaccard %) --")
    print(f"  S312 ∩ S221 = {jacc(b312,b221):5.1f}%")
    print(f"  S312 ∩ S306 = {jacc(b312,b306):5.1f}%")

    out = dict(
        tf=tf,
        n312=len(tr312), n221=len(tr221), n306=len(tr306),
        day_overlap_s221=round(jacc(d312, d221), 1),
        day_overlap_s306=round(jacc(d312, d306), 1),
        bar_overlap_s221=round(jacc(b312, b221), 1),
        bar_overlap_s306=round(jacc(b312, b306), 1),
        shared_days_s221=len(d312 & d221),
        unique_days_s312=len(d312 - d221),
    )
    outp = os.path.join(ROOT, 'results', '_s312_overlap.json')
    with open(outp, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\n⇒ saved {outp}")


if __name__ == '__main__':
    main()
