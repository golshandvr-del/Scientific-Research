"""
S331 — تأییدِ نهاییِ ۳ تایم‌فریمِ پذیرفته‌شده (M5/M30/H4) + ضدِ overfit
================================================================================
جاروی مستقل (s331_mtf_sweep.py) سه TF را پاس کرد: XAUUSD M5/M30/H4.
چون M30/H4 از یک جاروی ۷۲۰-ترکیبی «برنده» شدند، ریسکِ overfit دارند؛ اینجا با
جزئیاتِ walk-forward + آزمونِ همسایگیِ پارامتر (ضدِ اشتباهِ #۷) تأیید می‌شوند.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from engine import scalp_engine as SE
from engine import rqs as RQS
import s331_trendpullback_be as S331

TF_DATA = {
    ('XAUUSD', 'M5'):  'data/XAUUSD_M5.csv',
    ('XAUUSD', 'M30'): 'data/XAUUSD_M30.csv',
    ('XAUUSD', 'H4'):  'data/XAUUSD_H4.csv',
}


def confirm_tf(base, tf):
    path = TF_DATA[(base, tf)]
    key = S331.setup_asset(base, tf, path)
    df = SE.load_data(path)
    p = S331.TF_PROFILES[(base, tf)]
    tr = S331.run(df, key, p)
    r = RQS.compute_rqs(tr, key)
    m = r['metrics']
    print(RQS.format_report(f'S331 {base}-{tf}', r))
    print(f"       └─ WF: {m.get('wf_nets')}  halves: {m.get('half_nets')}  "
          f"net=${m.get('net_profit'):.0f}  exp={m.get('expectancy_pip'):.2f}pip")

    # همسایگی: تغییرِ کوچکِ هر پارامترِ کلیدی
    print(f"       └─ آزمونِ همسایگی (ضدِ overfit):")
    neigh = [
        ('rsi_th-2', {'rsi_th': p['rsi_th'] - 2}), ('rsi_th+2', {'rsi_th': p['rsi_th'] + 2}),
        ('adx-4', {'adx_min': p['adx_min'] - 4}), ('adx+4', {'adx_min': p['adx_min'] + 4}),
        ('sl-0.3', {'sl_atr': round(p['sl_atr'] - 0.3, 2)}), ('sl+0.3', {'sl_atr': round(p['sl_atr'] + 0.3, 2)}),
        ('tp-0.2', {'tp_atr': round(p['tp_atr'] - 0.2, 2)}), ('tp+0.2', {'tp_atr': round(p['tp_atr'] + 0.2, 2)}),
        ('mh+16', {'max_hold': p['max_hold'] + 16}),
    ]
    npass = 0; ntot = 0
    line = "          "
    for label, chg in neigh:
        pp = dict(p); pp.update(chg)
        trn = S331.run(df, key, pp)
        if trn is None or len(trn) < 30:
            line += f"{label}:n<30  "
            continue
        rn = RQS.compute_rqs(trn, key)
        ntot += 1
        ok = 'Y' if rn['passed'] else '.'
        if rn['passed']:
            npass += 1
        line += f"{label}:{ok}({rn['rqs_score']:.0f})  "
    print(line)
    print(f"          ⇒ {npass}/{ntot} همسایه پاس")
    return r


def main():
    print("=" * 114)
    print("  S331 — تأییدِ نهاییِ ۳ تایم‌فریم + ضدِ overfit")
    print("=" * 114)
    for base, tf in [('XAUUSD', 'M5'), ('XAUUSD', 'M30'), ('XAUUSD', 'H4')]:
        confirm_tf(base, tf)
        print()
    print("=" * 114)


if __name__ == '__main__':
    main()
