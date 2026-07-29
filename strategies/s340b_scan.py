# -*- coding: utf-8 -*-
"""
S340b — جاروی گریدِ micro-channel + فیلترهای رژیمِ بانک (r2/hurst/chop) — همه TF / دو ارز.
================================================================================
هدف: یافتنِ پیکربندی‌ای که RQS+ ≥ ۸۰ می‌دهد؛ اجتناب از اشتباهاتِ رایج:
  #5 (چند-TF، نه یک TF)، #6 (TP/SL per-TF نه یکسان)، #7 (اعداد غیررند)، #3 (فیلترهای بانک).

مراحلِ فیلتر (stage):
  raw   : فقط منطقِ micro-channel خام (بدون فیلترِ رژیمِ اضافه)
  r2    : + فیلترِ خطی‌بودنِ روند r2_fib_* بالای آستانه (روندِ تمیز)
  hurst : + فیلترِ hurst > آستانه (حافظهٔ روندی/persistence — هم‌راستا با ادامهٔ روند)
  combo : + هر دو (r2 & hurst) هم‌زمان (قانونِ همکاریِ بهبودها)

استفاده:
  python -m strategies.s340b_scan XAUUSD M5 long raw
  python -m strategies.s340b_scan XAUUSD M5 long combo
"""
import sys
import itertools
import numpy as np
import pandas as pd

from engine import scalp_engine as se
from engine import indicator_bank as ib
from engine import rqs
from strategies.s340_brooks_micro_channel import micro_channel_signals

# --- گریدِ پارامترها (اعداد غیررند/فیبوناچی‌محور — اشتباه #۷) ---
KWIN = [(3, 7), (4, 9), (5, 12)]              # (k_min, k_max)
EMAS = [(13, 34), (21, 55), (8, 21)]          # (fast, slow) فیبوناچی
BODY = [0.40, 0.55]                            # نسبتِ بدنه‌های قوی
CPOS = [0.45, 0.6]                             # close_pos_min (قدرتِ failed-breakout)
OVL  = [0.55, 0.7]                             # overlap_max

# TP/SL غیررندِ per-TF (pip) — نسبتِ ادامهٔ روند TP≥SL (طلا مومنتومی)
TPSL = {
    'M1':  [(90, 130), (75, 150)],
    'M5':  [(135, 205), (115, 240), (150, 150)],
    'M15': [(190, 290), (165, 330)],
    'M30': [(250, 380), (210, 430)],
    'H1':  [(330, 500), (280, 560)],
    'H4':  [(520, 780), (440, 880)],
    'D1':  [(900, 1350), (760, 1500)],
}
MAXHOLD = {'M1': 60, 'M5': 48, 'M15': 40, 'M30': 32, 'H1': 28, 'H4': 20, 'D1': 14}

# آستانه‌های فیلترِ رژیم (غیررند)
R2_THR = 0.18
HURST_THR = 0.52


def _regime_mask(df, stage):
    """ماسکِ بولینِ رژیم؛ True = اجازهٔ ورود. علّی (بدونِ look-ahead)."""
    n = len(df)
    if stage == 'raw':
        return np.ones(n, dtype=bool)
    r2 = ib.compute('r2_fib_34', df).to_numpy()
    hu = ib.compute('hurst', df).to_numpy()
    m = np.ones(n, dtype=bool)
    if stage in ('r2', 'combo'):
        m &= np.nan_to_num(r2, nan=0.0) >= R2_THR
    if stage in ('hurst', 'combo'):
        m &= np.nan_to_num(hu, nan=0.0) >= HURST_THR
    return m


def scan(asset, tf, side, stage, top=6, verbose=True):
    path = f'data/{asset}_{tf}.csv'
    df = se.load_data(path)
    reg = _regime_mask(df, stage)
    mh = MAXHOLD.get(tf, 32)
    tpsl_list = TPSL.get(tf, [(150, 230)])

    results = []
    for (kmin, kmax), (ef, es), bmin, cpos, ovl in itertools.product(
            KWIN, EMAS, BODY, CPOS, OVL):
        sig = micro_channel_signals(df, side, kmin, kmax, ef, es, bmin, cpos, ovl)
        sig = sig & reg
        if sig.sum() < 25:
            continue
        for sl, tp in tpsl_list:
            long_sig = sig if side == 'long' else np.zeros(len(df), bool)
            short_sig = sig if side == 'short' else np.zeros(len(df), bool)
            trades = se.simulate_trades(df, long_sig, short_sig, sl_pip=sl, tp_pip=tp,
                                        asset=asset, max_hold=mh, allow_overlap=False)
            r = rqs.compute_rqs(trades, asset, sl_pip=sl, tp_pip=tp)
            m = r['metrics']
            results.append(dict(
                rqs=r['rqs_score'], passed=r['verdict'] == 'ACCEPT', gates=r.get('gates', {}),
                n=m.get('n_trades', 0), wr=m.get('win_rate', 0), pf=m.get('profit_factor', 0),
                p=m.get('p_value', 1), dd=m.get('max_dd_pct', 0), mcl=m.get('max_consec_losses', 0),
                kmin=kmin, kmax=kmax, ef=ef, es=es, bmin=bmin, cpos=cpos, ovl=ovl,
                sl=sl, tp=tp, reg=stage))

    results.sort(key=lambda d: d['rqs'], reverse=True)
    if verbose:
        print(f"\n===== {asset} {tf} {side} [{stage}] — top {top} of {len(results)} configs =====")
        for d in results[:top]:
            gline = ''.join('1' if v else '0' for v in d['gates'].values()) if d['gates'] else '?'
            print(f"{asset} {tf} {side} [{stage}]: RQS={d['rqs']:.1f} pass={d['passed']} "
                  f"G[{gline}] n={d['n']} WR={d['wr']:.1f} PF={d['pf']:.2f} p={d['p']:.3f} "
                  f"dd={d['dd']:.1f} mcl={d['mcl']} | k{d['kmin']}-{d['kmax']} ema{d['ef']}/{d['es']} "
                  f"body{d['bmin']} cpos{d['cpos']} ovl{d['ovl']} SL{d['sl']} TP{d['tp']}")
    return results


if __name__ == '__main__':
    asset = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD'
    tf = sys.argv[2] if len(sys.argv) > 2 else 'M5'
    side = sys.argv[3] if len(sys.argv) > 3 else 'long'
    stage = sys.argv[4] if len(sys.argv) > 4 else 'raw'
    scan(asset, tf, side, stage)
