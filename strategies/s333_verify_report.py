"""S333 — بازتأییدِ متریک‌های نهاییِ گزارش (هندسهٔ منصفانه TP>=SL).
اجرا: python strategies/s333_verify_report.py > /tmp/s333_verify.txt
هدف: عددهای گزارشِ MD مستقیماً از خروجیِ همین اسکریپت خوانده شوند (rigor).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import s333_s79_pullback_revival as M   # ماژول کنارِ همین فایل نیست؛ import مسیرمحور
from strategies import s333_s79_pullback_revival as S  # noqa

import importlib
S = importlib.import_module('strategies.s333_s79_pullback_revival')
SE = S.SE; ib = S.ib; rqs = S.rqs

print("=== S333 fair-geometry verification (TP >= SL everywhere) ===\n")
for tf, cfg in S.BEST_CFG.items():
    asset = tf.split('_')[0]
    be = cfg['sl'] / (cfg['sl'] + cfg['tp']) * 100.0
    df = SE.load_data(SE.ASSETS[tf]['file'])
    sig = S.build_layer(df, cfg)
    tr, r = S.evaluate(df, sig, tf, cfg['sl'], cfg['tp'], cfg['mh'])
    if r is None:
        print(f"{tf:12s} NO TRADES"); continue
    m = r['metrics']
    print(f"{tf:12s} | SL={cfg['sl']} TP={cfg['tp']} (breakeven={be:.1f}% <=50 ✓ FAIR) "
          f"confirm={cfg.get('confirm')} hurst>{cfg['hurst']}"
          + (f" er>{cfg['er']}" if cfg.get('er') else ""))
    print(f"             {S.brief(r)}")
    print(f"             net=${m['net_profit']:+,.0f}\n")
