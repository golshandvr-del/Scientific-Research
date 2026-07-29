# -*- coding: utf-8 -*-
"""
S342 — اسکنِ پارامتریِ لبهٔ «MA-return پس از ≥N کندل دوری» (Brooks فصل ۱۸).
هدف: یافتنِ ترکیبِ per-TF که RQS+ ≥ ۸۰ بدهد. اعداد غیررند (اشتباه #۷)، از XAU M5 شروع.
اجرا:  python3 -m strategies.s342_scan XAUUSD M5
"""
import sys
import itertools
import numpy as np

from engine import scalp_engine as se
from engine import rqs
from strategies.s342_brooks_ma_return import ma_return_signals, load_tf


def scan(asset, tf, top=15):
    df = load_tf(asset, tf)
    print(f"# {asset} {tf} rows={len(df)}")

    # شبکهٔ غیررند (فیبوناچی/لوکاس برای دوره‌ها؛ اشتباه #۷)
    ma_kinds   = ['ema', 'sma']
    ma_periods = [21, 34, 55]
    n_aways    = [8, 13, 21]
    slope_lbs  = [3, 5, 8]
    r2_mins    = [None, 0.20, 0.35]
    hurst_mins = [None, 0.52, 0.55]
    # SL/TP غیررند و با-روند (TP بزرگ‌تر — ممنوعیتِ trick اشتباه #۸)
    sltps      = [(120, 240), (150, 300), (180, 360), (200, 340)]

    results = []
    combos = list(itertools.product(ma_kinds, ma_periods, n_aways, slope_lbs,
                                    r2_mins, hurst_mins, sltps))
    for (mk, mp, na, sl_lb, r2m, hum, (slp, tpp)) in combos:
        for side in ('long', 'short'):
            s = ma_return_signals(df, side, ma_period=mp, ma_kind=mk,
                                  n_away=na, slope_lb=sl_lb,
                                  r2_min=r2m, hurst_min=hum)
            nsig = int(s.sum())
            if nsig < 30:
                continue
            long_sig = s if side == 'long' else np.zeros(len(df), bool)
            short_sig = s if side == 'short' else np.zeros(len(df), bool)
            tr = se.simulate_trades(df, long_sig, short_sig, sl_pip=slp, tp_pip=tpp,
                                    asset=asset, max_hold=48, allow_overlap=False)
            if len(tr) < 30:
                continue
            r = rqs.compute_rqs(tr, asset, sl_pip=slp, tp_pip=tpp)
            m = r['metrics']
            results.append((r['rqs_score'], r['verdict'], side, mk, mp, na, sl_lb,
                            r2m, hum, slp, tpp, m.get('n_trades', 0),
                            m.get('win_rate', 0), m.get('profit_factor', 0),
                            m.get('max_dd_pct', 0), m.get('max_consec_losses', 0),
                            m.get('p_value', 1)))

    results.sort(key=lambda t: -t[0])
    print(f"# tested {len(results)} valid combos; TOP {top}:")
    for row in results[:top]:
        (rqsv, verd, side, mk, mp, na, sl_lb, r2m, hum, slp, tpp,
         nt, wr, pf, dd, mcl, pv) = row
        print(f"RQS={rqsv:5.1f} {verd:6s} {side:5s} {mk}{mp} N={na} slope={sl_lb} "
              f"r2={r2m} hu={hum} SL/TP={slp}/{tpp} | n={nt} WR={wr:.1f} "
              f"PF={pf:.2f} DD={dd:.1f} MCL={mcl} p={pv:.3f}")
    return results


if __name__ == '__main__':
    asset = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD'
    tf = sys.argv[2] if len(sys.argv) > 2 else 'M5'
    scan(asset, tf)
