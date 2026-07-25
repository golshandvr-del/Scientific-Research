# -*- coding: utf-8 -*-
"""
S323c — آزمونِ مولتی‌تایم‌فریمِ اجباری (قانونِ اول پروژه) برای احیای S11
================================================================================
ناحیهٔ گیت-پاسِ کشف‌شده روی XAUUSD M15 (S323b): RQS=83.1
  near0.55 room1.3 rsi55 slp0.0 adx24 golden(h19-23) sl1.8 tp1.5 mh96

این اسکریپت **هر TF را جداگانه** با گریدِ متمرکز (شاملِ فیلترِ ADX که کلیدِ پایداری بود)
می‌آزماید. هر TF می‌تواند بهبودِ متناسبِ خود (به‌ویژه TP/SL و max_hold — اشتباه #۶) را
داشته باشد. دارایی‌ها: XAUUSD {M5,M15,M30,H1,H4} + EURUSD {M5,M15,M30}.
"""
import sys, os, time, itertools
sys.path.insert(0, '.')
import numpy as np
from engine import scalp_engine as se
from engine import rqs
import warnings; warnings.filterwarnings('ignore')
from strategies.s323_s11_sr_pullback_revival import build_features, make_signals, lite_stats

# گریدِ متمرکز حولِ ناحیهٔ برنده + دامنهٔ ADX بازتر برای TFهای دیگر
GRID = dict(
    near_max=[0.55, 0.85],
    room_min=[1.0, 1.3],
    rsi_max=[55, 60],
    slope_min=[0.0, 0.1],
    adx_min=[18, 22, 26, 30],
    golden=[True, False],
    h_lo=[19], h_hi=[23],
    sl_mult=[1.6, 1.8, 2.1],
    tp_mult=[1.3, 1.5, 1.7],
)
# max_hold متناسب با TF (اجتناب از اشتباه #۶: TP/SL/mh یکسان برای همه TF)
MH = {'M5': [216, 288], 'M15': [96, 120], 'M30': [48, 72],
      'H1': [24, 36], 'H4': [12, 18]}


def scan(asset, tf, budget=115):
    df = se.load_data(f'data/{asset}_{tf}.csv')
    f = build_features(df, asset)
    keys = list(GRID.keys())
    mhs = MH.get(tf, [96, 120])
    t0 = time.time(); res = []
    for combo in itertools.product(*[GRID[k] for k in keys]):
        if time.time() - t0 > budget:
            break
        cfg = dict(zip(keys, combo))
        if cfg['tp_mult'] >= cfg['sl_mult']:
            continue
        for max_hold in mhs:
            ls, ss, sl, tp = make_signals(f, cfg)
            tr = se.simulate_trades(df, ls, ss, sl, tp, asset,
                                    max_hold=max_hold, allow_overlap=False)
            n, wr, pf, net = lite_stats(tr)
            if n >= 30 and wr >= 60 and pf >= 1.30:
                sig = ls | ss
                med_tp = float(np.median(tp[sig])) if sig.any() else float(np.median(tp))
                r = rqs.compute_rqs(tr, asset,
                                    sl_pip=float(np.median(tr['sl_pip'])), tp_pip=med_tp)
                c2 = dict(cfg); c2['max_hold'] = max_hold
                res.append((r['rqs_score'], r['passed'], c2, r['metrics'], r['gates']))
    res.sort(key=lambda x: (x[1], x[0]), reverse=True)
    return res, time.time() - t0


def main():
    targets = [('XAUUSD', tf) for tf in ['M5', 'M15', 'M30', 'H1', 'H4']] + \
              [('EURUSD', tf) for tf in ['M5', 'M15', 'M30']]
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for asset, tf in targets:
        if only and f'{asset}_{tf}' != only:
            continue
        res, dt = scan(asset, tf)
        best = res[0] if res else None
        npass = sum(1 for r in res if r[1])
        print(f'\n### {asset} {tf}  | cands={len(res)} pass={npass}  ({dt:.0f}s)')
        for score, passed, cfg, m, g in res[:3]:
            gl = ''.join('1' if g[k] else '0' for k in ['G0','G1','G2','G3','G4','G5'])
            print(f'  RQS={score:5.1f} {"PASS" if passed else "FAIL"} G[{gl}] '
                  f'n={m["n_trades"]:3d} WR={m["win_rate"]:4.1f} PF={m["profit_factor"]:.2f} '
                  f'DD={m["max_dd_pct"]:.1f} MCL={m["max_consec_losses"]} p={m["p_value"]:.3f} '
                  f'net={m["net_profit"]:.0f} wf={[round(x) for x in m["wf_nets"]]} | '
                  f'near{cfg["near_max"]} room{cfg["room_min"]} rsi{cfg["rsi_max"]} '
                  f'slp{cfg["slope_min"]} adx{cfg["adx_min"]} gold{cfg["golden"]} '
                  f'sl{cfg["sl_mult"]}tp{cfg["tp_mult"]} mh{cfg["max_hold"]}')
        if not res:
            print('  NONE passed lite screen')


if __name__ == '__main__':
    main()
