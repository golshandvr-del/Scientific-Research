# -*- coding: utf-8 -*-
"""
S324e — تأییدِ سریعِ کانفیگ‌های نهاییِ قفل‌شدهٔ S324 (احیای S165 Liquidity-Sweep).
فقط دو کانفیگِ برندهٔ نشستِ قبلی را روی XAUUSD M15/M30 اجرا و متریکِ کامل RQS+ را چاپ/ذخیره می‌کند.
(اسکنِ سنگینِ M5/H1/H4 قبلاً انجام شده؛ اینجا فقط بازتولیدِ سبکِ برندگان است.)
"""
import sys, os, json
sys.path.insert(0, '.')
import numpy as np
import pandas as pd
from engine import scalp_engine as se
from engine import rqs
import warnings; warnings.filterwarnings('ignore')
from strategies.s324_liquidity_sweep_revival import build_features, make_signals

# کانفیگ‌های نهاییِ قفل‌شده (خروجیِ ریزگریدِ S324c)
FINAL = {
    'XAUUSD_M15': dict(
        side='long', max_hold=48,
        cfg=dict(swing_len=16, depth_min=0.7, disp_min=0.9, regime=False,
                 rsi_on=True, rsi_lo=40, rsi_hi=60, kill=False,
                 sl_mult=2.4, tp_mult=0.8)),
    'XAUUSD_M30': dict(
        side='short', max_hold=48,
        cfg=dict(swing_len=8, depth_min=0.25, disp_min=0.5, regime=True,
                 rsi_on=True, rsi_lo=40, rsi_hi=60, kill=False,
                 sl_mult=3.1, tp_mult=1.2)),
}


def run(key, spec):
    asset, tf = key.split('_')
    df = se.load_data(f'data/{asset}_{tf}.csv')
    if 'dt' not in df.columns:
        df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    f = build_features(df, asset, spec['cfg']['swing_len'])
    ls, ss, sl, tp = make_signals(f, spec['cfg'], spec['side'])
    tr = se.simulate_trades(df, ls, ss, sl, tp, asset,
                            max_hold=spec['max_hold'], allow_overlap=False)
    sig = ls | ss
    med_tp = float(np.median(tp[sig])) if sig.any() else float(np.median(tp))
    r = rqs.compute_rqs(tr, asset, sl_pip=float(np.median(tr['sl_pip'])), tp_pip=med_tp)
    m = r['metrics']
    print(f"\n=== {key} ({spec['side']}) ===")
    print(f"  RQS+={r['rqs_score']:.1f}  passed={r['passed']}  gates={r['gates']}")
    print(f"  n={m['n_trades']} WR={m['win_rate']:.1f}% PF={m['profit_factor']:.2f} "
          f"DD={m['max_dd_pct']:.1f}% MCL={m['max_consec_losses']} p={m['p_value']:.3f}")
    print(f"  net=${m['net_profit']:.0f}  wf={[round(x) for x in m['wf_nets']]}")
    return dict(rqs=r['rqs_score'], passed=bool(r['passed']), gates=r['gates'],
                side=spec['side'], max_hold=spec['max_hold'], cfg=spec['cfg'],
                metrics={k: (float(v) if isinstance(v, (int, float, np.floating)) else v)
                         for k, v in m.items() if k != 'equity_curve'})


def main():
    out = {}
    for key, spec in FINAL.items():
        out[key] = run(key, spec)
    with open('results/_s324_final.json', 'w', encoding='utf-8') as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2, default=str)
    print('\nsaved results/_s324_final.json')


if __name__ == '__main__':
    main()
