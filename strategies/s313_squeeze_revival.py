# -*- coding: utf-8 -*-
"""
s313_squeeze_revival.py — احیای S132/S136/S138 (Bollinger-Squeeze → Breakout) با RQS+
================================================================================
> نشستِ احیا. لایهٔ سوختهٔ منشأ: S132/S136/S138 (Bollinger Squeeze → Expansion
> Breakout LONG روی XAUUSD M15). در ممیزیِ S300 با WR≈40٪ رد شد (G0 fail) چون از
> پارادایمِ قدیم (max_hold=96 کندل + خروجِ هدف-پنهانِ نامتقارن) استفاده می‌کرد.
>
> **چرا این لایه (شکستنِ الگوی «فقط زمان‌محورها احیا می‌شوند»):** همهٔ احیاهای
> موفقِ تاکنون (S302/S303/S306/S310/S312) زمان‌محور یا price-action بودند. طبقِ
> «اشتباهاتِ رایجِ #1 و #3»، این نشست عمداً یک لایهٔ *اندیکاتوریِ ساختاری* با
> مفهومِ ریاضیِ عمیق (Volatility-Clustering / فشردگیِ بولینگر) را برای احیا برمی‌گزیند.

روش (قانونِ دومِ پروژه: چند بهبودِ همزمان مجاز):
  فاز A — بازتولیدِ خام (baseline): پارادایمِ قدیمِ S132 (max_hold بلند، RR نامتقارن).
  فاز B — grid احیا: SL/TP بر حسبِ ATR (نه عددِ رند) × max_hold کوتاه × sqz_pct.
  فاز C — بهترین کاندید + فیلترهای کیفیت (ADX، breakout-lb) اگر لازم شد.
  فاز D — RQS+ کامل روی بهترین (۶ گیت) + پایداریِ سالانه.

مولتی‌تایم‌فریم: با آرگومانِ خط‌فرمان روی TFهای مختلف اجرا می‌شود (شروع از M5):
  python3 strategies/s313_squeeze_revival.py XAUUSD_M5
  python3 strategies/s313_squeeze_revival.py XAUUSD_M15   ... M30 ... H1
هر TF SL/TP و max_hold خودش را می‌گیرد (اشتباهِ رایج #6).
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
from strategies.sim_strategies import S313_SqueezeBreakout_Long


def run_one(df, asset, tf, **kw):
    strat = S313_SqueezeBreakout_Long(**kw)
    warmup = max(260, kw.get('ema_slow', 200) + kw.get('sqz_lookback', 100) + 20)
    trades, _ = TS.simulate(df, strat, asset, tf=tf, warmup=warmup,
                            max_bars_hold=None)  # max_hold داخلِ advise مدیریت می‌شود
    return trades


def quick_stats(trades, asset):
    if trades is None or len(trades) == 0:
        return dict(n=0, wr=0, pf=0, net=0, dd=0)
    n = len(trades)
    wins = (trades['outcome'] == 'win').sum()
    wr = wins / n * 100
    cap, _ = SE.run_capital(trades, asset, initial_capital=10000.0)
    return dict(n=n, wr=round(wr, 1), pf=round(cap['profit_factor'], 2),
                net=round(cap['net_profit'], 0), dd=round(abs(cap['max_dd_pct']), 1))


def tf_params(tf_name):
    """پارامترهای مخصوصِ هر TF (max_hold و شبکهٔ ATR-mult غیررند)."""
    if tf_name.endswith('_M5'):
        holds = [8, 12, 20]
        atr_mults = [1.35, 1.7, 2.15]      # ATR-scaled RR (غیررند)
        sqz_pcts = [0.10, 0.15, 0.20]
    elif tf_name.endswith('_M15'):
        holds = [8, 16, 24]
        atr_mults = [1.35, 1.7, 2.15]
        sqz_pcts = [0.10, 0.15, 0.20]
    elif tf_name.endswith('_M30'):
        holds = [6, 12, 20]
        atr_mults = [1.35, 1.7, 2.15]
        sqz_pcts = [0.12, 0.18, 0.25]
    else:  # H1
        holds = [5, 10, 16]
        atr_mults = [1.35, 1.7, 2.15]
        sqz_pcts = [0.15, 0.22, 0.30]
    return holds, atr_mults, sqz_pcts


def main():
    tf_name = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD_M5'
    asset = tf_name.split('_')[0]
    df = TS.load_data(tf_name)
    print(f"\n{'#'*74}\n# S313 Squeeze→Breakout Revival — {tf_name}  (rows={len(df)})\n{'#'*74}")

    # ---- فاز A: بازتولیدِ خام (پارادایمِ قدیمِ S132) ----
    print("\n[فاز A] baseline خام (پارادایمِ قدیم: max_hold=96، RR نامتقارن SL≈TP بزرگ):")
    tr = run_one(df, asset, tf_name, sl_atr=1.0, tp_atr=4.0, max_hold=96,
                 sqz_pct=0.15)
    print("   ", quick_stats(tr, asset))

    # ---- فاز B+C: grid احیا (ATR-scaled RR متقارن × max_hold کوتاه × sqz_pct × ADX) ----
    holds, atr_mults, sqz_pcts = tf_params(tf_name)
    print("\n[فاز B+C] grid احیا (RR متقارنِ ATR-scaled، max_hold کوتاه):")
    best = None
    rows = []
    for m in atr_mults:
        for mh in holds:
            for sp in sqz_pcts:
                for adx_min in (0.0, 20.0):
                    kw = dict(sl_atr=m, tp_atr=m, max_hold=mh, sqz_pct=sp,
                              adx_min=adx_min)
                    tr = run_one(df, asset, tf_name, **kw)
                    s = quick_stats(tr, asset)
                    rows.append((kw, s))
                    if s['n'] >= 30 and s['wr'] >= 55 and s['pf'] >= 1.3:
                        score = (s['wr'], s['pf'], s['net'])
                        if best is None or score > best[0]:
                            best = (score, kw, s)
    # نمایشِ ۱۲ ردیفِ برتر بر اساسِ WR
    rows_ok = [r for r in rows if r[1]['n'] >= 30]
    rows_ok.sort(key=lambda r: (r[1]['wr'], r[1]['pf']), reverse=True)
    for kw, s in rows_ok[:12]:
        print(f"    atr={kw['sl_atr']:.2f} mh={kw['max_hold']:3d} "
              f"sqz={kw['sqz_pct']:.2f} adx≥{kw['adx_min']:.0f}: {s}")

    # ---- فاز D: RQS+ کامل روی بهترین کاندید ----
    print("\n[فاز D] RQS+ کامل روی بهترین کاندید:")
    candidates = []
    if best is not None:
        candidates.append(('best', best[1]))
    else:
        # fallback: بهترین بر اساسِ WR حتی اگر گیتِ اولیه را رد کند (برای تشخیص)
        if rows_ok:
            candidates.append(('top-wr', rows_ok[0][0]))
        else:
            candidates.append(('mid', dict(sl_atr=1.7, tp_atr=1.7,
                                            max_hold=holds[1], sqz_pct=sqz_pcts[1])))

    results_out = {}
    for label, kw in candidates:
        tr = run_one(df, asset, tf_name, **kw)
        if tr is None or len(tr) == 0:
            print(f"  [{label}] no trades"); continue
        # sl_pip/tp_pip واقعیِ میانه برای breakeven-WR در RQS
        sl_med = float(np.median(tr['sl_pip'].values))
        tp_med = float(np.median(tr['tp_pip'].values))
        r = RQS.compute_rqs(tr, asset, sl_pip=sl_med, tp_pip=tp_med)
        print(f"  [{label}] {kw}")
        print("   ", RQS.format_report(f"S313-{tf_name}-{label}", r))
        results_out[label] = dict(kw=kw, rqs=r['rqs_score'], verdict=r['verdict'],
                                  gates=r['gates'], metrics=r['metrics'])

    outp = os.path.join(ROOT, 'results', f'_s313_squeeze_{tf_name}.json')
    with open(outp, 'w') as f:
        json.dump(results_out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\n  ⇒ saved {outp}")


if __name__ == '__main__':
    main()
