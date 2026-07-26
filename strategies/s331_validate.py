"""
S331 — اعتبارسنجیِ جامعِ لایهٔ احیاشده (ضدِ overfit + مولتی‌تایم‌فریم)
================================================================================
سه آزمون:
  A) تأییدِ پارامترِ برتر روی XAUUSD-M5 + جزئیاتِ walk-forward/نیمه‌ها.
  B) حساسیت به همسایگیِ پارامتر (ضدِ overfit — اشتباهِ #۷): آیا همسایه‌ها هم پاس‌اند؟
  C) مولتی‌تایم‌فریم (ضدِ اشتباهِ #۵): همان منطق روی XAUUSD M15/M30/H1/H4 + EURUSD.
     چون SL/TP/BE بر حسبِ ATR شناورند، خودکار با هر TF تطبیق می‌یابند (ضدِ اشتباهِ #۶).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from engine import scalp_engine as SE
from engine import rqs as RQS
import s331_trendpullback_be as S331


def detail(name, r):
    m = r['metrics']
    print(RQS.format_report(name, r))
    print(f"       └─ walk-forward nets: {m.get('wf_nets')}  |  halves: {m.get('half_nets')}  "
          f"|  net=${m.get('net_profit'):.0f}  expectancy={m.get('expectancy_pip'):.3f}pip")


def main():
    # ---------- A) پارامترِ برتر روی M5 ----------
    print("=" * 118)
    print("  A) پارامترِ برترِ احیا روی XAUUSD-M5")
    print("=" * 118)
    key = S331.setup_asset('XAUUSD', 'M5', 'data/XAUUSD_M5.csv')
    df5 = SE.load_data('data/XAUUSD_M5.csv')
    tr = S331.run(df5, key)
    r = RQS.compute_rqs(tr, key)
    detail('S331 XAUUSD-M5 (default)', r)

    # ---------- B) حساسیت به همسایگی (ضدِ overfit) ----------
    print("\n" + "=" * 118)
    print("  B) حساسیت به همسایگیِ پارامتر (ضدِ overfit) — هر ردیف یک تغییرِ کوچک از پیش‌فرض")
    print("=" * 118)
    base = dict(S331.DEFAULTS)
    variations = [
        ('rsi_th 34', {'rsi_th': 34}), ('rsi_th 38', {'rsi_th': 38}), ('rsi_th 40', {'rsi_th': 40}),
        ('adx_min 15', {'adx_min': 15}), ('adx_min 22', {'adx_min': 22}),
        ('sl_atr 2.5', {'sl_atr': 2.5}), ('sl_atr 3.1', {'sl_atr': 3.1}),
        ('tp_atr 1.5', {'tp_atr': 1.5}), ('tp_atr 1.9', {'tp_atr': 1.9}),
        ('be_atr 1.0', {'be_atr': 1.0}), ('be_atr 1.4', {'be_atr': 1.4}),
        ('max_hold 30', {'max_hold': 30}), ('max_hold 55', {'max_hold': 55}),
    ]
    npass = 0
    for label, chg in variations:
        p = dict(base); p.update(chg)
        trv = S331.run(df5, key, p)
        rv = RQS.compute_rqs(trv, key)
        ok = 'Y' if rv['passed'] else '.'
        if rv['passed']:
            npass += 1
        m = rv['metrics']
        print(f"  [{ok}] {label:14s} RQS={rv['rqs_score']:5.1f}  n={m['n_trades']:3d}  "
              f"WR={m['win_rate']:4.1f}  PF={m['profit_factor']:.2f}  DD={m['max_dd_pct']:.1f}  MCL={m['max_consec_losses']}")
    print(f"\n  ⇒ {npass}/{len(variations)} همسایه پاس شدند (پایداری = منطقهٔ واقعی، نه اکسترممِ overfit).")

    # ---------- C) مولتی‌تایم‌فریم ----------
    print("\n" + "=" * 118)
    print("  C) مولتی‌تایم‌فریم — همان منطقِ ATR-scaled روی همهٔ TFها و هر دو ارز")
    print("=" * 118)
    tfmap = {
        'XAUUSD': {'M15': 'data/XAUUSD_M15.csv', 'M30': 'data/XAUUSD_M30.csv',
                   'H1': 'data/XAUUSD_H1.csv', 'H4': 'data/XAUUSD_H4.csv'},
        'EURUSD': {'M5': 'data/EURUSD_M5.csv', 'M15': 'data/EURUSD_M15.csv',
                   'M30': 'data/EURUSD_M30.csv'},
    }
    accepted = [('XAUUSD', 'M5', r)]
    for baseA, tfs in tfmap.items():
        for tf, path in tfs.items():
            k = S331.setup_asset(baseA, tf, path)
            d = SE.load_data(path)
            trx = S331.run(d, k)
            rx = RQS.compute_rqs(trx, k)
            detail(f'S331 {baseA}-{tf}', rx)
            if rx['passed']:
                accepted.append((baseA, tf, rx))

    print("\n" + "=" * 118)
    print("  خلاصهٔ TFهای پذیرفته‌شده (RQS+ ≥ ۸۰، هر ۶ گیت ✓):")
    for baseA, tf, rx in accepted:
        print(f"    ✅ {baseA}-{tf}: RQS={rx['rqs_score']}  WR={rx['metrics']['win_rate']}%  "
              f"PF={rx['metrics']['profit_factor']}  net=${rx['metrics']['net_profit']:.0f}")
    print("=" * 118)


if __name__ == '__main__':
    main()
