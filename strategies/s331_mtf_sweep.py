"""
S331 — جاروی مستقلِ مولتی‌تایم‌فریم (قانونِ شناوری: هر TF پارامترِ خودش)
================================================================================
اعتبارسنجیِ اولیه نشان داد منطقِ M5 با همان پارامترها روی M15/M30/H1/H4 و EURUSD رد
می‌شود. اما طبقِ «قانونِ شاید» و «قانونِ بی‌نهایتِ بهبود»، پیش از اعلامِ مرگِ یک TF باید
با پارامترهای *مستقلِ* آن TF جارو شود (ضدِ اشتباهِ #۵ و #۶). این ماژول برای هر TF یک
جاروی مستقلِ کوچک انجام می‌دهد و بهترین RQS+ آن TF را گزارش می‌کند.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from engine import scalp_engine as SE
from engine import rqs as RQS
from itertools import product
import s331_trendpullback_be as S331


def sweep_tf(base, tf, path):
    key = S331.setup_asset(base, tf, path)
    df = SE.load_data(path)
    best = None
    # فضای مستقلِ هر TF — عمداً وسیع‌تر برای دادنِ شانسِ کامل به احیا
    rsi_ths  = [34, 36, 40, 44]
    adx_mins = [15, 20, 26]
    sltp     = [(2.4, 1.5), (2.8, 1.7), (2.0, 1.4), (3.2, 1.9), (1.8, 1.2)]
    be_atrs  = [None, 1.0, 1.3, 1.6]
    holds    = [24, 40, 60]
    n_tested = 0
    for rsi_th, adx_min in product(rsi_ths, adx_mins):
        for (sl_atr, tp_atr), be_atr, mh in product(sltp, be_atrs, holds):
            p = dict(S331.DEFAULTS)
            p.update(dict(rsi_th=rsi_th, adx_min=adx_min, sl_atr=sl_atr,
                          tp_atr=tp_atr, be_atr=be_atr, max_hold=mh))
            tr = S331.run(df, key, p)
            if tr is None or len(tr) < 30:
                continue
            r = RQS.compute_rqs(tr, key)
            n_tested += 1
            if best is None or r['rqs_score'] > best[0]['rqs_score']:
                best = (r, p)
    return best, n_tested


def main():
    print("=" * 118)
    print("  S331 — جاروی مستقلِ مولتی‌تایم‌فریم (هر TF بهترین پارامترِ خودش)")
    print("=" * 118)
    targets = [
        ('XAUUSD', 'M15', 'data/XAUUSD_M15.csv'),
        ('XAUUSD', 'M30', 'data/XAUUSD_M30.csv'),
        ('XAUUSD', 'H1',  'data/XAUUSD_H1.csv'),
        ('XAUUSD', 'H4',  'data/XAUUSD_H4.csv'),
        ('EURUSD', 'M15', 'data/EURUSD_M15.csv'),
        ('EURUSD', 'M30', 'data/EURUSD_M30.csv'),
    ]
    for base, tf, path in targets:
        best, n = sweep_tf(base, tf, path)
        if best is None:
            print(f"  {base}-{tf}: هیچ ترکیبی n≥30 نداد.")
            continue
        r, p = best
        m = r['metrics']
        g = r['gates']; gl = ''.join('✓' if g[k] else '✗' for k in ['G0','G1','G2','G3','G4','G5'])
        tag = '✅ ACCEPTED' if r['passed'] else '⛔ best-fail'
        print(f"  {base}-{tf}: {tag}  RQS={r['rqs_score']:.1f}  [{gl}]  "
              f"n={m['n_trades']} WR={m['win_rate']:.1f} PF={m['profit_factor']:.2f} "
              f"DD={m['max_dd_pct']:.1f} MCL={m['max_consec_losses']}  ({n} combos)")
        print(f"        best params: rsi_th={p['rsi_th']} adx_min={p['adx_min']} "
              f"sl_atr={p['sl_atr']} tp_atr={p['tp_atr']} be_atr={p['be_atr']} mh={p['max_hold']}")
    print("=" * 118)


if __name__ == '__main__':
    main()
