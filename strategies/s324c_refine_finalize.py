# -*- coding: utf-8 -*-
"""
S324c — ریزگرید + تثبیتِ کانفیگ‌های برندهٔ S324 (Liquidity-Sweep revival).
- ریزگرید حولِ M15-long (RQS 92.3) و M30-short (RQS 82.9) برای بیشینه‌کردنِ پایداری.
- بازبینیِ M5/H1/H4 با ناحیهٔ نویدبخش تا مطمئن شویم DEAD یا ALIVE.
خروجی: results/_s324_final.json (کانفیگ‌های قفل‌شده + متریک‌های کامل).
"""
import sys, os, itertools, json
sys.path.insert(0, '.')
import numpy as np
import pandas as pd
from engine import scalp_engine as se
from engine import rqs
import warnings; warnings.filterwarnings('ignore')
from strategies.s324_liquidity_sweep_revival import build_features, make_signals, lite_stats


def eval_cfg(asset, tf, cfg, side, mh):
    df = se.load_data(f'data/{asset}_{tf}.csv')
    if 'dt' not in df.columns:
        df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    f = build_features(df, asset, cfg['swing_len'])
    ls, ss, sl, tp = make_signals(f, cfg, side)
    tr = se.simulate_trades(df, ls, ss, sl, tp, asset, max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) == 0:
        return None
    sig = ls | ss
    med_tp = float(np.median(tp[sig])) if sig.any() else float(np.median(tp))
    r = rqs.compute_rqs(tr, asset, sl_pip=float(np.median(tr['sl_pip'])), tp_pip=med_tp)
    return r


def refine(asset, tf, base, sides, mhs):
    """ریزگرید حولِ کانفیگِ پایه."""
    best = None
    grid = dict(
        swing_len=base['swing_len_set'],
        depth_min=base['depth_set'],
        disp_min=base['disp_set'],
        regime=base['regime_set'],
        rsi_on=[True], rsi_lo=[40], rsi_hi=[60], kill=[False],
        sl_mult=base['sl_set'], tp_mult=base['tp_set'],
    )
    keys = list(grid.keys())
    rows = []
    for combo in itertools.product(*[grid[k] for k in keys]):
        cfg = dict(zip(keys, combo))
        if cfg['tp_mult'] >= cfg['sl_mult']:
            continue
        for side in sides:
            for mh in mhs:
                r = eval_cfg(asset, tf, cfg, side, mh)
                if r is None:
                    continue
                m = r['metrics']
                if m['n_trades'] >= 30 and r['passed']:
                    c2 = dict(cfg); c2['side'] = side; c2['max_hold'] = mh
                    rows.append((r['rqs_score'], c2, m, r['gates']))
    rows.sort(key=lambda x: x[0], reverse=True)
    return rows


def main():
    out = {}
    # --- M15 long ریزگرید ---
    print('=== REFINE XAUUSD M15 (long) ===')
    r15 = refine('XAUUSD', 'M15',
                 dict(swing_len_set=[14, 16, 18], depth_set=[0.55, 0.7, 0.85],
                      disp_set=[0.7, 0.9, 1.1], regime_set=[False],
                      sl_set=[2.2, 2.4, 2.6], tp_set=[0.8, 0.9, 1.0, 1.1]),
                 ['long'], [48, 72])
    print(f'  passed configs: {len(r15)}')
    for score, cfg, m, g in r15[:5]:
        print(f'  RQS={score:.1f} n={m["n_trades"]} WR={m["win_rate"]:.1f} PF={m["profit_factor"]:.2f} '
              f'DD={m["max_dd_pct"]:.1f} p={m["p_value"]:.3f} net={m["net_profit"]:.0f} '
              f'wf={[round(x) for x in m["wf_nets"]]} sw{cfg["swing_len"]} dep{cfg["depth_min"]} '
              f'dsp{cfg["disp_min"]} sl{cfg["sl_mult"]}tp{cfg["tp_mult"]} mh{cfg["max_hold"]}')
    if r15:
        out['XAUUSD_M15'] = dict(rqs=r15[0][0], cfg=r15[0][1], metrics=r15[0][2], gates=r15[0][3])

    # --- M30 short ریزگرید ---
    print('\n=== REFINE XAUUSD M30 (short) ===')
    r30 = refine('XAUUSD', 'M30',
                 dict(swing_len_set=[6, 8, 10], depth_set=[0.25, 0.35, 0.5],
                      disp_set=[0.4, 0.5, 0.7], regime_set=[True],
                      sl_set=[2.8, 3.1, 3.4], tp_set=[1.0, 1.2, 1.4]),
                 ['short'], [32, 48, 64])
    print(f'  passed configs: {len(r30)}')
    for score, cfg, m, g in r30[:5]:
        print(f'  RQS={score:.1f} n={m["n_trades"]} WR={m["win_rate"]:.1f} PF={m["profit_factor"]:.2f} '
              f'DD={m["max_dd_pct"]:.1f} p={m["p_value"]:.3f} net={m["net_profit"]:.0f} '
              f'wf={[round(x) for x in m["wf_nets"]]} sw{cfg["swing_len"]} dep{cfg["depth_min"]} '
              f'dsp{cfg["disp_min"]} sl{cfg["sl_mult"]}tp{cfg["tp_mult"]} mh{cfg["max_hold"]}')
    if r30:
        out['XAUUSD_M30'] = dict(rqs=r30[0][0], cfg=r30[0][1], metrics=r30[0][2], gates=r30[0][3])

    with open('results/_s324_final.json', 'w', encoding='utf-8') as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2, default=str)
    print('\nsaved results/_s324_final.json')


if __name__ == '__main__':
    main()
