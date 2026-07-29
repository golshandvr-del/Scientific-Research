# -*- coding: utf-8 -*-
"""
S343 MTF scan — تستِ measured-move fade روی همهٔ TFها و هر دو ارز (قانونِ MTF).
تمرکز روی بهترین منطقِ کشف‌شده در M5 (long-fade, رِنجِ کوچک, climaxِ قوی) + فیلترِ
Hurst (mean-reversion). گریدِ TP/SL **per-TF و غیررند** (اشتباهِ #۶/#۷).

اجرا:  PYTHONPATH=. python3 strategies/s343_mtf_scan.py
"""
import itertools
import numpy as np
from engine import scalp_engine as se
from engine import rqs
from strategies.s343_brooks_ttr_mmfade import build_signals

# گریدِ TP/SL متناسب با هر TF (طلا: pip موتور=0.10$؛ TF بالاتر ⇒ SL/TP بزرگ‌تر)
# per-TF grid: (tp_list, sl_list, mh_list)
XAU_GRID = {
    'M5':  ([200, 280, 380],           [90, 130, 180],   [48, 96]),
    'M15': ([300, 450, 650],           [150, 220, 320],  [32, 64]),
    'M30': ([450, 650, 900],           [220, 320, 460],  [24, 48]),
    'H1':  ([650, 950, 1400],          [320, 460, 680],  [18, 36]),
    'H4':  ([1400, 2100, 3000],        [700, 1050, 1500],[12, 24]),
}
EUR_GRID = {
    'M5':  ([12, 18, 26],  [7, 10, 14],   [48, 96]),
    'M15': ([18, 28, 40],  [10, 15, 22],  [32, 64]),
    'M30': ([28, 42, 60],  [15, 22, 32],  [24, 48]),
}

# پارامترهای سیگنالِ برگزیده از کشفِ M5 (long-fade در دُمِ توزیع) + چند واریانت
SIG_GRID = [
    dict(N=21, smallMult=0.5, k=1.0, climaxMult=1.6),
    dict(N=21, smallMult=0.5, k=1.5, climaxMult=1.6),
    dict(N=21, smallMult=0.7, k=1.0, climaxMult=1.2),
    dict(N=13, smallMult=0.5, k=0.6, climaxMult=1.2),
]
HURST_GRID = [None, 0.5, 0.55]
SIDE_GRID = ['long', 'short', 'both']


def scan_file(path, asset, tf, grid):
    df = se.load_data(path)
    tp_list, sl_list, mh_list = grid
    best = []
    for sig in SIG_GRID:
        for hmax in HURST_GRID:
            for side in SIDE_GRID:
                ls, ss = build_signals(df, atrLen=21, gap=sig['N'], side=side,
                                       hurstmax=hmax, **sig)
                if int(ls.sum() + ss.sum()) < 25:
                    continue
                for tp, sl, mh in itertools.product(tp_list, sl_list, mh_list):
                    tr = se.simulate_trades(df, ls, ss, sl_pip=sl, tp_pip=tp,
                                            asset=asset, max_hold=mh, allow_overlap=False)
                    if len(tr) < 25:
                        continue
                    tr['tp_pip'] = tp
                    r = rqs.compute_rqs(tr, asset, sl_pip=sl, tp_pip=tp)
                    m = r['metrics']
                    best.append((r['rqs_score'], m.get('net_profit', 0),
                                 f"{asset} {tf} | N{sig['N']} sm{sig['smallMult']} k{sig['k']} "
                                 f"cx{sig['climaxMult']} h{hmax} {side} tp{tp} sl{sl} mh{mh} "
                                 f"| n={m.get('n_trades',0)} WR={m.get('win_rate',0):.0f} "
                                 f"PF={m.get('profit_factor',0):.2f} DD={m.get('max_dd_pct',0):.0f} "
                                 f"p={m.get('p_value',1):.3f} RQS={r['rqs_score']:.1f}"))
    best.sort(reverse=True)
    return best[:3]


if __name__ == '__main__':
    jobs = [(f'data/XAUUSD_{tf}.csv', 'XAUUSD', tf, g) for tf, g in XAU_GRID.items()]
    jobs += [(f'data/EURUSD_{tf}.csv', 'EURUSD', tf, g) for tf, g in EUR_GRID.items()]
    for path, asset, tf, grid in jobs:
        try:
            top = scan_file(path, asset, tf, grid)
            print(f"===== {asset} {tf} — top3 =====")
            for rqs_s, net, line in top:
                print("  " + line)
        except FileNotFoundError:
            print(f"[skip] {path} not found")
        except Exception as e:
            print(f"[err] {asset} {tf}: {e}")
