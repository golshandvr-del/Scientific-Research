# -*- coding: utf-8 -*-
"""
s312_midmonth_revival.py — احیای S142 (Gold Mid-Month Drift) با معیارِ RQS+
================================================================================
> نشستِ احیا. لایهٔ سوختهٔ منشأ: S142 (dom{10,13,20}، ساعت 1-12 UTC، Long).
> در ممیزیِ S300 با WR≈41.8٪ رد شد (G0 fail) چون از پارادایمِ قدیم (TP بزرگِ
> نامتقارن ~SL100/TP500) استفاده می‌کرد. این اسکریپت با روشِ اثبات‌شدهٔ S306
> (RR متقارن + فیلترِ کیفیت) تلاش می‌کند لبهٔ واقعیِ mid-month را با WR≥60٪ آزاد کند.

روش (قانونِ دومِ پروژه: چند بهبودِ همزمان مجاز):
  فاز A — بازتولیدِ خام (baseline): S142 با RR نامتقارنِ قدیم ⇒ نمایشِ WR پایین.
  فاز B — grid RR متقارنِ غیررند: SL/TP ∈ اعدادِ واقعیِ غیررند (اشتباهِ رایج #7).
  فاز C — بهترین کاندید + فیلترِ کیفیت (EMA200 + ATR-band) اگر لازم شد.
  فاز D — RQS+ کامل روی بهترین (۶ گیت) + پایداریِ سالانه.

مولتی‌تایم‌فریم: این اسکریپت با آرگومانِ خط‌فرمان روی TFهای مختلف اجرا می‌شود.
  python3 strategies/s312_midmonth_revival.py XAUUSD_M5
  python3 strategies/s312_midmonth_revival.py XAUUSD_M15
  ...
هر TF SL/TP خودش را می‌گیرد (اشتباهِ رایج #6: TP/SL یکسان ممنوع).
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
from engine import scalp_engine as SE
from strategies.sim_strategies import S312_MidMonth_Long


def run_one(df, asset, tf, **kw):
    strat = S312_MidMonth_Long(**kw)
    warmup = max(220, kw.get('ema_period', 200) + 20)
    trades, _ = TS.simulate(df, strat, asset, tf=tf, warmup=warmup,
                            max_bars_hold=kw.get('max_hold', 24))
    return trades


def quick_stats(trades, asset):
    if trades is None or len(trades) == 0:
        return dict(n=0, wr=0, pf=0, net=0)
    n = len(trades)
    wins = (trades['outcome'] == 'win').sum()
    wr = wins / n * 100
    cap, _ = SE.run_capital(trades, asset, initial_capital=10000.0)
    return dict(n=n, wr=round(wr, 1), pf=round(cap['profit_factor'], 2),
                net=round(cap['net_profit'], 0), dd=round(abs(cap['max_dd_pct']), 1))


def main():
    tf_name = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD_M5'
    asset = tf_name.split('_')[0]
    df = TS.load_data(tf_name)
    print(f"\n{'#'*72}\n# S312 Mid-Month Revival — {tf_name}  (rows={len(df)})\n{'#'*72}")

    # ---- فاز A: بازتولیدِ خام (پارادایمِ قدیمِ S142: RR نامتقارن) ----
    print("\n[فاز A] baseline خام (RR نامتقارنِ قدیم SL100/TP500):")
    tr = run_one(df, asset, tf_name, sl_pip=100, tp_pip=500, max_hold=96)
    print("   ", quick_stats(tr, asset))

    # ---- فاز B: grid RR متقارنِ غیررند ----
    # اعدادِ غیررند عمداً (اشتباهِ رایج #7). مقیاسِ SL بر حسبِ TF متفاوت است:
    #   M5 نوسانِ کندلی کوچک‌تر ⇒ SL کوچک‌تر؛ M30/H1 بزرگ‌تر.
    if tf_name.endswith('M5'):
        sl_grid = [85, 115, 135, 165, 195]
        holds = [36, 60, 96]
    elif tf_name.endswith('M15'):
        sl_grid = [135, 175, 215, 255, 295]
        holds = [16, 24, 48]
    elif tf_name.endswith('M30'):
        sl_grid = [175, 235, 295, 355]
        holds = [12, 24, 36]
    else:  # H1
        sl_grid = [235, 315, 395, 475]
        holds = [8, 16, 24]

    print("\n[فاز B] grid RR متقارن (SL=TP، اعدادِ غیررند):")
    best = None
    for sl in sl_grid:
        for mh in holds:
            tr = run_one(df, asset, tf_name, sl_pip=sl, tp_pip=sl, max_hold=mh)
            s = quick_stats(tr, asset)
            tag = f"SL=TP={sl:4d} mh={mh:3d}"
            print(f"    {tag}: {s}")
            if s['n'] >= 30 and s['wr'] >= 55:
                score = (s['wr'], s['pf'])
                if best is None or score > best[0]:
                    best = (score, dict(sl_pip=sl, tp_pip=sl, max_hold=mh), s)

    # ---- فاز C+D: RQS+ کامل روی بهترین کاندید (با و بدونِ فیلترِ کیفیت) ----
    print("\n[فاز C+D] RQS+ کامل روی بهترین کاندید:")
    candidates = []
    if best is not None:
        candidates.append(('no-filter', best[1]))
    else:
        # fallback: میانهٔ grid
        mid_sl = sl_grid[len(sl_grid) // 2]
        candidates.append(('no-filter', dict(sl_pip=mid_sl, tp_pip=mid_sl, max_hold=holds[1])))

    # همان کاندید + فیلترِ کیفیت (EMA200 close-above)
    base_kw = candidates[0][1]
    candidates.append(('quality(EMA200)', dict(**base_kw, quality_filter=True)))

    results_out = {}
    for label, kw in candidates:
        tr = run_one(df, asset, tf_name, **kw)
        if tr is None or len(tr) == 0:
            print(f"  [{label}] no trades"); continue
        r = RQS.compute_rqs(tr, asset, sl_pip=kw['sl_pip'], tp_pip=kw['tp_pip'])
        print(f"  [{label}] {kw}")
        print("   ", RQS.format_report(f"S312-{tf_name}-{label}", r))
        results_out[label] = dict(kw=kw, rqs=r['rqs_score'], verdict=r['verdict'],
                                  gates=r['gates'], metrics=r['metrics'])

    # ذخیرهٔ JSON برای بازتولید
    outp = os.path.join(ROOT, 'results', f'_s312_midmonth_{tf_name}.json')
    with open(outp, 'w') as f:
        json.dump(results_out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\n  ⇒ saved {outp}")


if __name__ == '__main__':
    main()
