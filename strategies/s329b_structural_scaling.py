# -*- coding: utf-8 -*-
"""
S329b — شناورسازیِ ساختاریِ کاملِ Market-Inertia SHORT روی TFهای غیرِ M15
================================================================================
یافتهٔ S329 (grid فقط روی SL/TP): روی M5/M30/H1/H4 لایه رد شد (WR ~۴۰-۵۲٪، PF<1).
اما این نتیجه‌گیریِ زودهنگام (اشتباهِ رایجِ ۵) نیست؛ چون فقط SL/TP شناور شده بود،
نه پارامترهای *ساختاریِ* سیگنال.

فرضیهٔ علمی (قانونِ «همه چیز شناور است»):
  پارامترهای منطقِ سیگنال — `lb` (طولِ lookbackِ سقفِ اخیر) و `adx_hi` (آستانهٔ روند)
  و جفتِ EMA — در S303 مخصوصِ **M15** کالیبره شده‌اند. lb=20 کندلِ M15 ≈ ۵ ساعت.
  همان lb=20 روی M5 فقط ۱۰۰ دقیقه (نویزی) و روی H4 حدودِ ۳.۳ روز (خیلی دیر) است.
  ⇒ باید bar-count را طوری تنظیم کنیم که **پنجرهٔ زمانیِ معادل** حفظ شود، و ADX/EMA
  را هم grid بزنیم.

این اسکریپت برای هر TF:
  • lb را به‌صورتِ «معادلِ زمانیِ ۵ ساعتِ M15» + چند مقدارِ اطراف تنظیم می‌کند.
  • adx_hi ∈ {22, 25, 28, 32} و (ef,es) ∈ {(20,50),(13,34),(10,30)} را می‌گردد.
  • SL/TP را بر مبنایِ بهترین مضربِ ATR از S329 نگه می‌دارد و ۲ مضرب اطراف را چک می‌کند.
یک grid کامل‌تر تا مطمئن شویم آیا لایه در آن TF واقعاً مرده است یا فقط بد-کالیبره بود.
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
from engine import indicators as ind
from strategies.s329_market_inertia_mtf import MarketInertiaShortMTF, median_atr_pip


# طولِ معادلِ زمانی: در M15 → lb=20 کندل = ۳۰۰ دقیقه. برای هر TF چند lb اطرافِ آن.
TF_MIN = {'M5': 5, 'M15': 15, 'M30': 30, 'H1': 60, 'H4': 240}


def lb_candidates(tf):
    base_minutes = 300.0  # 20×15
    eq = base_minutes / TF_MIN[tf]
    eq = max(3, int(round(eq)))
    cands = sorted(set([max(3, int(eq * f)) for f in (0.5, 1.0, 1.5, 2.0)]))
    return cands


class MISHORT_Struct(MarketInertiaShortMTF):
    """اجازهٔ تنظیمِ ef/es/adx_hi/lb علاوه بر SL/TP (همه از grid)."""
    pass  # سازندهٔ والد همهٔ این‌ها را می‌پذیرد


def grid_full(asset, tf, warmup=2000, top=8):
    df = TS.load_data(f'{asset}_{tf}')
    matr = median_atr_pip(df, asset, warmup)
    max_hold = max(12, int(round(12 * 60 / TF_MIN[tf])))
    results = []
    for lb in lb_candidates(tf):
        for adx_hi in (22, 25, 28, 32):
            for (ef, es) in ((20, 50), (13, 34), (10, 30)):
                for sl_mult in (8.0, 9.5, 11.0):
                    sl_pip = round(sl_mult * matr, 1)
                    for rr in (0.9, 1.0, 1.1):
                        tp_pip = round(sl_pip * rr, 1)
                        strat = MISHORT_Struct(ef=ef, es=es, adx_hi=adx_hi, lb=lb,
                                               sl_pip=sl_pip, tp_pip=tp_pip,
                                               max_hold=max_hold)
                        tr, eq = TS.simulate(df, strat, asset, warmup=warmup)
                        r = RQS.compute_rqs(tr, asset)
                        m = r['metrics']
                        results.append(dict(
                            asset=asset, tf=tf, lb=lb, adx_hi=adx_hi, ef=ef, es=es,
                            sl_mult=sl_mult, sl_pip=sl_pip, tp_pip=tp_pip, rr=rr,
                            max_hold=max_hold, rqs=r['rqs_score'], verdict=r['verdict'],
                            passed=r['passed'], n=m.get('n_trades', 0),
                            wr=m.get('win_rate', 0), pf=m.get('profit_factor', 0),
                            dd=m.get('max_dd_pct', 0), mcl=m.get('max_consec_losses', 0),
                            p=m.get('p_value', 1), gates=r['gates'],
                        ))
    results.sort(key=lambda x: (x['passed'], x['rqs']), reverse=True)
    return results, matr, max_hold


if __name__ == '__main__':
    asset = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD'
    tfs = sys.argv[2].split(',') if len(sys.argv) > 2 else ['M5', 'M30', 'H1', 'H4']
    all_res = []
    for tf in tfs:
        print(f'\n===== {asset} {tf}  (lb cands={lb_candidates(tf)}) =====')
        res, matr, mh = grid_full(asset, tf)
        n_pass = sum(1 for r in res if r['passed'])
        print(f'medianATR={matr:.1f}pip  max_hold={mh}  combos={len(res)}  PASSED={n_pass}')
        for r in res[:8]:
            g = ''.join('✓' if v else '✗' for v in r['gates'].values())
            print(f"  lb={r['lb']:3d} adx>{r['adx_hi']} ema{r['ef']}/{r['es']} "
                  f"SL={r['sl_pip']:6.1f} rr={r['rr']} | {r['verdict']:6s} "
                  f"RQS={r['rqs']:5.1f} n={r['n']:4d} WR={r['wr']:4.1f}% PF={r['pf']:.2f} "
                  f"DD={r['dd']:.1f}% MCL={r['mcl']} p={r['p']:.3f} {g}")
        all_res.extend(res)
    out = os.path.join(ROOT, 'results', f'_s329b_struct_{asset}.json')
    with open(out, 'w') as f:
        json.dump(all_res, f, indent=2, default=str)
    print(f'\nsaved: {out}')
