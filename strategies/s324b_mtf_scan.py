# -*- coding: utf-8 -*-
"""
S324b — اسکنِ مولتی‌تایم‌فریمِ اجباری برای احیای S165 (Liquidity Sweep).
از یافتهٔ M5 استفاده می‌کند: short-bias قوی، killzone مضر، اما G4 (walk-forward) گلوگاه.
راهبرد: فیلترهای کیفیتِ قوی‌تر (depth/disp بالاتر) برای پایدارسازیِ لبه در همهٔ پنجره‌ها.
خروجی: results/_s324_mtf.json + خلاصهٔ بهترینِ هر TF.
"""
import sys, os, time, itertools, json
sys.path.insert(0, '.')
import numpy as np
import pandas as pd
from engine import scalp_engine as se
from engine import indicators as ind
from engine import rqs
import warnings; warnings.filterwarnings('ignore')

from strategies.s324_liquidity_sweep_revival import build_features, make_signals, lite_stats

# گرید متمرکز: هر دو جهت، فیلترهای کیفیتِ قوی‌تر برای پایداری، اعداد غیر-رند
GRID = dict(
    swing_len=[8, 12, 16],
    depth_min=[0.1, 0.35, 0.7, 1.1],      # عمقِ sweep — بالاتر = بازگشتِ قوی‌تر/پایدارتر
    disp_min=[0.5, 0.9, 1.4],             # قدرتِ کندلِ بازگشت
    regime=[True, False],
    rsi_on=[True],
    rsi_lo=[40], rsi_hi=[60],
    kill=[False],                          # M5 نشان داد killzone مضر است
    sl_mult=[1.8, 2.4, 3.1],
    tp_mult=[0.6, 0.9, 1.2],
)


def scan(asset, tf, sides, mhs, budget=260):
    df = se.load_data(f'data/{asset}_{tf}.csv')
    if 'dt' not in df.columns:
        df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    keys = list(GRID.keys())
    t0 = time.time(); res = []; fcache = {}
    for combo in itertools.product(*[GRID[k] for k in keys]):
        if time.time() - t0 > budget:
            print(f'  [budget hit {asset} {tf}]'); break
        cfg = dict(zip(keys, combo))
        if cfg['tp_mult'] >= cfg['sl_mult']:
            continue
        sw = cfg['swing_len']
        if sw not in fcache:
            fcache[sw] = build_features(df, asset, sw)
        f = fcache[sw]
        for side in sides:
            for mh in mhs:
                ls, ss, sl, tp = make_signals(f, cfg, side)
                if not (ls.any() or ss.any()):
                    continue
                tr = se.simulate_trades(df, ls, ss, sl, tp, asset, max_hold=mh, allow_overlap=False)
                n, wr, pf, net = lite_stats(tr)
                if n >= 30 and wr >= 60 and pf >= 1.3:
                    sig = ls | ss
                    med_tp = float(np.median(tp[sig])) if sig.any() else float(np.median(tp))
                    r = rqs.compute_rqs(tr, asset, sl_pip=float(np.median(tr['sl_pip'])), tp_pip=med_tp)
                    c2 = dict(cfg); c2['max_hold'] = mh; c2['side'] = side
                    res.append((r['rqs_score'], bool(r['passed']), c2, r['metrics'], r['gates']))
    res.sort(key=lambda x: (x[1], x[0]), reverse=True)
    return res


def main():
    JOBS = [
        ('XAUUSD', 'M5', [96, 144], ['short', 'long']),
        ('XAUUSD', 'M15', [48, 72], ['short', 'long']),
        ('XAUUSD', 'M30', [32, 48], ['short', 'long']),
        ('XAUUSD', 'H1', [16, 24], ['short', 'long']),
        ('XAUUSD', 'H4', [8, 12], ['short', 'long']),
        ('EURUSD', 'M5', [96, 144], ['short', 'long']),
        ('EURUSD', 'M15', [48, 72], ['short', 'long']),
        ('EURUSD', 'M30', [32, 48], ['short', 'long']),
    ]
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    out = {}
    for asset, tf, mhs, sides in JOBS:
        key = f'{asset}_{tf}'
        if only and key not in only and asset not in only and tf not in only:
            continue
        print(f'\n=== {key} ===')
        res = scan(asset, tf, sides, mhs)
        passed = [r for r in res if r[1]]
        print(f'  candidates={len(res)}  PASSED(RQS+>=80)={len(passed)}')
        top = res[:6]
        for score, ok, cfg, m, g in top:
            gl = ''.join('1' if g[k] else '0' for k in ['G0','G1','G2','G3','G4','G5'])
            print(f'  RQS={score:5.1f} {"PASS" if ok else "FAIL"} G[{gl}] {cfg["side"]:5s} '
                  f'n={m["n_trades"]:3d} WR={m["win_rate"]:4.1f} PF={m["profit_factor"]:.2f} '
                  f'DD={m["max_dd_pct"]:.1f} MCL={m["max_consec_losses"]} p={m["p_value"]:.3f} '
                  f'net={m["net_profit"]:.0f} wf={[round(x) for x in m["wf_nets"]]} '
                  f'| sw{cfg["swing_len"]} dep{cfg["depth_min"]} dsp{cfg["disp_min"]} '
                  f'reg{int(cfg["regime"])} sl{cfg["sl_mult"]}tp{cfg["tp_mult"]} mh{cfg["max_hold"]}')
        out[key] = [dict(rqs=score, passed=ok, cfg=cfg, metrics=m, gates=g)
                    for score, ok, cfg, m, g in top]
    with open('results/_s324_mtf.json', 'w', encoding='utf-8') as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2, default=str)
    print('\nsaved results/_s324_mtf.json')


if __name__ == '__main__':
    main()
