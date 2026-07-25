# -*- coding: utf-8 -*-
"""
S323d — تثبیتِ کانفیگ‌های نهاییِ احیای S11 + گزارشِ کاملِ RQS+ + ذخیرهٔ JSON
================================================================================
کانفیگ‌های نهایی (از اسکنِ مولتی‌TF، S323c):
  XAUUSD M15: near0.85 room1.3 rsi55 slp0.0 adx22 golden sl1.8 tp1.5 mh96
  XAUUSD M30: near0.85 room1.3 rsi55 slp0.0 adx22 golden sl2.1 tp1.3 mh48
  XAUUSD H1 : near0.55 room1.3 rsi55 slp0.0 adx30 golden sl1.8 tp1.7 mh36
همه با پنجرهٔ طلاییِ ۱۹–۲۳ UTC، فقط LONG. (M5/H4/EURUSD رد شدند.)
"""
import sys, os, json
sys.path.insert(0, '.')
import numpy as np
from engine import scalp_engine as se
from engine import rqs
import warnings; warnings.filterwarnings('ignore')
from strategies.s323_s11_sr_pullback_revival import build_features, make_signals

FINAL = {
    ('XAUUSD', 'M15'): dict(near_max=0.85, room_min=1.3, rsi_max=55, slope_min=0.0,
                            adx_min=22, golden=True, h_lo=19, h_hi=23,
                            sl_mult=1.8, tp_mult=1.5, max_hold=96),
    ('XAUUSD', 'M30'): dict(near_max=0.85, room_min=1.3, rsi_max=55, slope_min=0.0,
                            adx_min=22, golden=True, h_lo=19, h_hi=23,
                            sl_mult=2.1, tp_mult=1.3, max_hold=48),
    ('XAUUSD', 'H1'):  dict(near_max=0.55, room_min=1.3, rsi_max=55, slope_min=0.0,
                            adx_min=30, golden=True, h_lo=19, h_hi=23,
                            sl_mult=1.8, tp_mult=1.7, max_hold=36),
}


def main():
    out = {}
    for (asset, tf), cfg in FINAL.items():
        df = se.load_data(f'data/{asset}_{tf}.csv')
        f = build_features(df, asset)
        ls, ss, sl, tp = make_signals(f, cfg)
        tr = se.simulate_trades(df, ls, ss, sl, tp, asset,
                                max_hold=cfg['max_hold'], allow_overlap=False)
        sig = ls | ss
        med_tp = float(np.median(tp[sig])) if sig.any() else float(np.median(tp))
        r = rqs.compute_rqs(tr, asset, sl_pip=float(np.median(tr['sl_pip'])), tp_pip=med_tp)
        m, g = r['metrics'], r['gates']
        gl = ''.join('1' if g[k] else '0' for k in ['G0','G1','G2','G3','G4','G5'])
        print(f'{asset} {tf:3s} | RQS={r["rqs_score"]:5.1f} {r["verdict"]:6s} G[{gl}] '
              f'n={m["n_trades"]:3d} WR={m["win_rate"]:.1f} PF={m["profit_factor"]:.2f} '
              f'DD={m["max_dd_pct"]:.1f} MCL={m["max_consec_losses"]} p={m["p_value"]:.4f} '
              f'net={m["net_profit"]:.0f} exp={m["expectancy_pip"]:.2f} '
              f'wf={m["wf_nets"]} half={m["half_nets"]}')
        out[f'{asset}_{tf}'] = {'cfg': cfg, 'rqs': float(r['rqs_score']),
                                'passed': bool(r['passed']), 'metrics': m,
                                'gates': {k: bool(v) for k, v in g.items()}}
    with open('results/_s323_sr_pullback_revival.json', 'w') as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
    total_net = sum(v['metrics']['net_profit'] for v in out.values())
    print(f'\nجمعِ net سه TF گیت-پاس (XAUUSD M15+M30+H1) = {total_net:+.0f}$')
    print('saved -> results/_s323_sr_pullback_revival.json')


if __name__ == '__main__':
    main()
