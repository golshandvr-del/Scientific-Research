# -*- coding: utf-8 -*-
"""
s336_test_trail.py — آیا breakeven-stop + trailing، لایهٔ شورت را به RQS+≥80 می‌رساند؟
=====================================================================================
بهترین ترکیبِ یافته‌شده: crsi_dn82 + (entropy<2.4 & efi<0)، TP بزرگ. PF>1 شد ولی
RQS+ به‌خاطرِ G0(WR<60) رد شد. اینجا مدیریتِ خروجِ پویا (be/trail) را می‌آزماییم.
"""
import numpy as np
from engine import scalp_engine as se, rqs
from engine import indicator_bank as ib


def main():
    df = se.load_data('data/XAUUSD_M5.csv')
    n = len(df)
    crsi = ib.compute('crsi', df).values
    base = np.r_[False, (crsi[:-1] >= 82) & (crsi[1:] < 82)]
    entropy = ib.compute('entropy', df).shift(1).values
    efi = ib.compute('efi', df).shift(1).values
    filt = np.nan_to_num(entropy < 2.4, nan=False).astype(bool) & \
           np.nan_to_num(efi < 0, nan=False).astype(bool)
    sig = base & filt
    print('n_sig =', int(sig.sum()))
    for tp, sl in [(110, 60), (89, 55), (144, 80)]:
        for bet, trl in [(None, None), (30, None), (40, 20), (55, 30), (30, 15), (20, 10)]:
            tr = se.simulate_trades(df, np.zeros(n, bool), sig, sl, tp, 'XAUUSD', 24,
                                    False, be_trigger_pip=bet, trail_pip=trl)
            if len(tr) < 30:
                continue
            tr = tr.copy(); tr['tp_pip'] = float(tp)
            r = rqs.compute_rqs(tr, 'XAUUSD', sl_pip=sl, tp_pip=tp)
            m = r['metrics']
            gl = ''.join('1' if v else '0' for v in r['gates'].values())
            print(f'TP{tp}/SL{sl} be={bet} trail={trl} | n={m["n_trades"]} '
                  f'WR={m["win_rate"]:.1f} PF={m["profit_factor"]:.2f} '
                  f'DD={m["max_dd_pct"]:.1f} RQS={r["rqs_score"]:.1f} G={gl}')


if __name__ == '__main__':
    main()
