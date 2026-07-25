# -*- coding: utf-8 -*-
"""S320 — اسکنِ سریعِ همهٔ TFها برای دیدنِ بهترین PF/WR (تشخیص، نه انتخابِ نهایی)."""
import sys, os, itertools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from engine import scalp_engine as se
from engine import rqs
from strategies.s320_bb_rsi_regime_revival import GRID, build_features, make_signals, lite_stats

TF_FILE = {'M5':'data/{a}_M5.csv','M15':'data/{a}_M15.csv','M30':'data/{a}_M30.csv',
           'H1':'data/{a}_H1.csv','H4':'data/{a}_H4.csv'}


def scan(asset, tf):
    df = se.load_data(TF_FILE[tf].format(a=asset))
    feats = build_features(df)
    keys = list(GRID.keys())
    best_pf = (0, 0, 0, 0, None)     # (pf,wr,n,net,cfg)
    best_bal = (-1, None, None)      # (min(gate margin), cfg, stats) — نزدیک‌ترین به پاسِ G0&G2
    rows = []
    for combo in itertools.product(*[GRID[k] for k in keys]):
        cfg = dict(zip(keys, combo))
        ls, ss, sl, tp = make_signals(feats, cfg, asset)
        tr = se.simulate_trades(df, ls, ss, sl, tp, asset, max_hold=cfg['max_hold'])
        n, wr, pf, net = lite_stats(tr)
        if n < 30:
            continue
        rows.append((pf, wr, n, net, cfg, tr, ls, ss, tp))
        if pf > best_pf[0]:
            best_pf = (pf, wr, n, net, cfg)
        # امتیازِ تعادل: هر دو گیت باید پاس شوند
        bal = min(wr - 60, (pf - 1.3) * 40)
        if bal > best_bal[0]:
            best_bal = (bal, cfg, (pf, wr, n, net))
    # بهترین کاندیدا با WR>=60 & PF>=1.3 → RQS کامل
    passers = [(pf, wr, n, net, cfg, tr, ls, ss, tp) for (pf, wr, n, net, cfg, tr, ls, ss, tp) in rows
               if wr >= 60 and pf >= 1.3]
    passers.sort(key=lambda x: x[0], reverse=True)
    print(f"\n### {asset} {tf}  (rows={len(df)})")
    print(f"  bestPF: PF={best_pf[0]:.2f} WR={best_pf[1]:.1f} n={best_pf[2]} net_pip={best_pf[3]:.0f} {best_pf[4] and {k:best_pf[4][k] for k in ['adx_gate','rsi_lo','rsi_hi','sl_mult','tp_mult']}}")
    print(f"  bestBAL(G0&G2): margin={best_bal[0]:.2f} stats={best_bal[2]} cfg={best_bal[1] and {k:best_bal[1][k] for k in ['adx_gate','rsi_lo','rsi_hi','sl_mult','tp_mult']}}")
    print(f"  #configs passing G0&G2 lite = {len(passers)}")
    for pf, wr, n, net, cfg, tr, ls, ss, tp in passers[:3]:
        sig = ls | ss
        med_tp = float(np.median(tp[sig])) if sig.any() else float(np.median(tp))
        r = rqs.compute_rqs(tr, asset, sl_pip=float(np.median(tr['sl_pip'])), tp_pip=med_tp)
        gl = ''.join('1' if r['gates'][g] else '0' for g in ['G0','G1','G2','G3','G4','G5'])
        m = r['metrics']
        print(f"    RQS={r['rqs_score']:.1f} {'PASS' if r['passed'] else 'FAIL'} G[{gl}] "
              f"WR={m['win_rate']:.1f} PF={m['profit_factor']:.2f} DD={m['max_dd_pct']:.1f} "
              f"wf={m['wf_nets']} half={m['half_nets']} | adx<{cfg['adx_gate']} rsi[{cfg['rsi_lo']}/{cfg['rsi_hi']}] sl{cfg['sl_mult']}tp{cfg['tp_mult']}")


if __name__ == '__main__':
    asset = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD'
    tfs = sys.argv[2].split(',') if len(sys.argv) > 2 else ['M15','M30','H1']
    for tf in tfs:
        scan(asset, tf)
