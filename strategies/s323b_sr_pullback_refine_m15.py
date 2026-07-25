# -*- coding: utf-8 -*-
"""
S323b — ریزگرید حولِ ناحیهٔ گیت-پاسِ XAUUSD M15 (هدف: RQS+ ≥ 80)
================================================================================
ناحیهٔ پایه (از S323): near0.55 room1.3 rsi55 slp0.0 adx18 golden sl1.6 tp1.5 mh96
⇒ RQS=75.9، هر ۶ گیت پاس. برای رساندن به ≥۸۰ باید PF و پایداریِ walk-forward بهبود یابد.

اهرم‌های ریزتنظیمِ شناور (غیر-رند):
  • sl/tp حولِ 1.6/1.5 با گام‌های ظریف (بیشینه‌سازیِ PF بدونِ افتِ WR<60).
  • near/room ظریف (کیفیتِ pullback).
  • آستانهٔ ADX/شیب (پایدارسازیِ walk-forwardِ پنجرهٔ دوم که نازک بود).
  • RSI و پنجرهٔ طلایی ظریف.
"""
import sys, os, time, itertools
sys.path.insert(0, '.')
import numpy as np
from engine import scalp_engine as se
from engine import rqs
import warnings; warnings.filterwarnings('ignore')
from strategies.s323_s11_sr_pullback_revival import build_features, make_signals, lite_stats

ASSET = 'XAUUSD'; TF = 'M15'

GRID = dict(
    near_max=[0.45, 0.55, 0.65],
    room_min=[1.0, 1.3, 1.6],
    rsi_max=[50, 55, 60],
    slope_min=[0.0, 0.1],
    adx_min=[15, 20, 24],
    golden=[True],
    h_lo=[18, 19], h_hi=[23],
    sl_mult=[1.4, 1.6, 1.8],
    tp_mult=[1.3, 1.5, 1.7],
)
MHS = [72, 96, 120]


def main():
    df = se.load_data(f'data/{ASSET}_{TF}.csv')
    f = build_features(df, ASSET)
    keys = list(GRID.keys())
    t0 = time.time()
    res = []
    for combo in itertools.product(*[GRID[k] for k in keys]):
        if time.time() - t0 > 260:
            print('  [time budget hit]'); break
        cfg = dict(zip(keys, combo))
        if cfg['tp_mult'] >= cfg['sl_mult']:
            continue
        for max_hold in MHS:
            ls, ss, sl, tp = make_signals(f, cfg)
            tr = se.simulate_trades(df, ls, ss, sl, tp, ASSET,
                                    max_hold=max_hold, allow_overlap=False)
            n, wr, pf, net = lite_stats(tr)
            if n >= 40 and wr >= 60 and pf >= 1.30:
                sig = ls | ss
                med_tp = float(np.median(tp[sig])) if sig.any() else float(np.median(tp))
                r = rqs.compute_rqs(tr, ASSET,
                                    sl_pip=float(np.median(tr['sl_pip'])), tp_pip=med_tp)
                c2 = dict(cfg); c2['max_hold'] = max_hold
                res.append((r['rqs_score'], r['passed'], c2, r['metrics'], r['gates']))
    res.sort(key=lambda x: (x[1], x[0]), reverse=True)
    print(f'=== S323b refine {ASSET} {TF} === candidates(n>=40,WR>=60,PF>=1.3): {len(res)}  ({time.time()-t0:.0f}s)')
    print('=' * 120)
    for score, passed, cfg, m, g in res[:20]:
        gl = ''.join('1' if g[k] else '0' for k in ['G0', 'G1', 'G2', 'G3', 'G4', 'G5'])
        print(f'RQS={score:5.1f} {"PASS" if passed else "FAIL"} G[{gl}] '
              f'n={m["n_trades"]:3d} WR={m["win_rate"]:4.1f} PF={m["profit_factor"]:.2f} '
              f'DD={m["max_dd_pct"]:.1f} MCL={m["max_consec_losses"]} p={m["p_value"]:.3f} '
              f'net={m["net_profit"]:.0f} wf={[round(x) for x in m["wf_nets"]]} | '
              f'near{cfg["near_max"]} room{cfg["room_min"]} rsi{cfg["rsi_max"]} '
              f'slp{cfg["slope_min"]} adx{cfg["adx_min"]} h{cfg["h_lo"]} '
              f'sl{cfg["sl_mult"]}tp{cfg["tp_mult"]} mh{cfg["max_hold"]}')


if __name__ == '__main__':
    main()
