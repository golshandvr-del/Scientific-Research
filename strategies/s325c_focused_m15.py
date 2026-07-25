# -*- coding: utf-8 -*-
"""
S325c — اسکنِ هدفمندِ احیای S219 روی M15 (تعادلِ تریدِ زیاد + سرعت).
================================================================================
یافته‌های H4/M30 (نشستِ فعلی): WR بالا (۶۷–۷۵٪) ✅ اما PF≈۱ و walk-forward ناپایدار
(regime-dependent) ⇒ G2/G4 رد. دو محورِ حل هنوز کامل تست نشده:
  1) breakeven/trailing → تبدیلِ باخت‌های بزرگ به سربه‌سر ⇒ PF↑
  2) فیلترِ regime-strength (فاصلهٔ ema نسبت به ATR) → حذفِ رژیمِ ضعیف ⇒ WF پایدار

این اسکن: گریدِ ساختاریِ کوچکِ منتخب + جاروی کاملِ be/trail + فیلترِ regime-strength.
هر سیگنالِ ساختاری فقط یک‌بار محاسبه و کش می‌شود.
اجرا: python3 strategies/s325c_focused_m15.py XAUUSD M15
"""
import sys, os, time, itertools, json
sys.path.insert(0, '.')
sys.path.insert(0, 'strategies')
import numpy as np
import pandas as pd
from engine import scalp_engine as se
from engine import indicators as ind
from engine import rqs
import warnings; warnings.filterwarnings('ignore')
import s219_brooks_channels as S219

# گریدِ ساختاریِ کوچک (بهترین‌های نشستِ قبل) — سیگنال کش می‌شود
STRUCT = [
    dict(ema=(10, 30), k=3, pos_max=0.35, max_gap=80),
    dict(ema=(10, 30), k=5, pos_max=0.25, max_gap=80),
    dict(ema=(20, 50), k=3, pos_max=0.35, max_gap=80),
    dict(ema=(20, 50), k=5, pos_max=0.25, max_gap=40),
]
# فیلترِ regime-strength: |ema_fast - ema_slow| / ATR ≥ آستانه (0 = خاموش)
REGIME = [0.0, 0.5, 1.0, 1.8]
# breakeven/trailing (×ATR)
BE   = [None, 0.6, 1.0, 1.5]
TRAIL = [None, 1.2, 2.0]
SLTP = [(2.0, 1.0), (2.5, 1.1), (2.5, 1.4), (3.0, 1.2)]


def eval_cfg(df, asset, raw, side, atr_arr, atr_pip, ema_gap_ratio,
             reg_min, sl_mult, tp_mult, mh, be_mult, trail_mult):
    n = len(df)
    sig = raw.copy()
    if reg_min > 0:
        ok = (ema_gap_ratio >= reg_min)
        ok = pd.Series(ok).shift(1).fillna(False).to_numpy()
        sig = sig & ok
    ns = int(sig.sum())
    if ns < 40:
        return None
    ls = sig if side == 'long' else np.zeros(n, bool)
    ss = sig if side == 'short' else np.zeros(n, bool)
    sl_pip = np.clip(sl_mult * atr_pip, 5.0, None)
    tp_pip = np.clip(tp_mult * atr_pip, 5.0, None)
    med_atr = float(np.median(atr_pip[sig]))
    be_trig = None if be_mult is None else max(be_mult * med_atr, 3.0)
    trail = None if trail_mult is None else max(trail_mult * med_atr, 3.0)
    tr = se.simulate_trades(df, ls, ss, sl_pip, tp_pip, asset, max_hold=mh,
                            allow_overlap=False, be_trigger_pip=be_trig, trail_pip=trail)
    if tr is None or len(tr) < 40:
        return None
    r = rqs.compute_rqs(tr, asset, sl_pip=float(np.median(tr['sl_pip'])),
                        tp_pip=float(np.median(tp_pip[sig])))
    return r


def scan(asset, tf, budget=300):
    df = se.load_data(f'data/{asset}_{tf}.csv')
    pip = se.ASSETS[asset]['pip']
    atr_arr = ind.atr(df, 14).to_numpy()
    atr_pip = atr_arr / pip
    mh_map = {'M5': [64, 96], 'M15': [48, 80], 'M30': [32, 48], 'H1': [16, 32], 'H4': [8, 16]}
    mhs = mh_map.get(tf, [48, 80])

    t0 = time.time(); rows = []; passed = []; n_eval = 0; hit = False
    for side in ['long', 'short']:
        if hit:
            break
        for d in STRUCT:
            if time.time() - t0 > budget:
                print(f"  [budget hit after {n_eval} evals]"); hit = True; break
            ef = ind.ema(df['close'], d['ema'][0]).to_numpy()
            es = ind.ema(df['close'], d['ema'][1]).to_numpy()
            ema_gap_ratio = np.abs(ef - es) / np.where(atr_arr > 0, atr_arr, np.nan)
            raw = S219.channel_signals(df, side, d['ema'][0], d['ema'][1],
                                       d['k'], d['pos_max'], d['max_gap'])
            if raw.sum() < 40:
                continue
            for reg in REGIME:
                for (slm, tpm) in SLTP:
                    for be in BE:
                        for tr_m in TRAIL:
                            for mh in mhs:
                                if time.time() - t0 > budget:
                                    hit = True; break
                                n_eval += 1
                                r = eval_cfg(df, asset, raw, side, atr_arr, atr_pip,
                                             ema_gap_ratio, reg, slm, tpm, mh, be, tr_m)
                                if r is None:
                                    continue
                                m = r['metrics']
                                cfg = dict(ema_fast=d['ema'][0], ema_slow=d['ema'][1], k=d['k'],
                                           pos_max=d['pos_max'], max_gap=d['max_gap'],
                                           regime_min=reg, sl_mult=slm, tp_mult=tpm,
                                           be_mult=be, trail_mult=tr_m, side=side, max_hold=mh)
                                rows.append((r['rqs_score'], cfg, m, r['gates'], r['passed']))
                                if r['passed']:
                                    passed.append((r['rqs_score'], cfg, m, r['gates']))
                            if hit: break
                        if hit: break
                    if hit: break
                if hit: break
    rows.sort(key=lambda x: x[0], reverse=True)
    passed.sort(key=lambda x: x[0], reverse=True)
    print(f"  [done {asset} {tf}: {n_eval} evals in {time.time()-t0:.0f}s]")
    return rows, passed


def fmt(score, cfg, m, g):
    gs = ''.join('1' if g[k] else '0' for k in sorted(g.keys()))
    return (f"  RQS={score:.1f} G[{gs}] {cfg['side']} n={m['n_trades']} WR={m['win_rate']:.1f} "
            f"PF={m['profit_factor']:.2f} DD={m['max_dd_pct']:.1f} p={m['p_value']:.3f} "
            f"net={m['net_profit']:.0f} wf={[round(x) for x in m['wf_nets']]} "
            f"| reg{cfg['regime_min']} sl{cfg['sl_mult']}tp{cfg['tp_mult']} "
            f"be{cfg['be_mult']} tr{cfg['trail_mult']} mh{cfg['max_hold']}")


def main():
    asset = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD'
    tf = sys.argv[2] if len(sys.argv) > 2 else 'M15'
    print(f"\n=== S325c Focused | {asset} {tf} ===")
    rows, passed = scan(asset, tf)
    print(f"  evaluated={len(rows)}  PASSED(RQS+>=80)={len(passed)}")
    if passed:
        for s, c, m, g in passed[:5]:
            print(fmt(s, c, m, g))
    else:
        print("  --- best 6 FAILs (diagnostic) ---")
        for s, c, m, g, ps in rows[:6]:
            print(fmt(s, c, m, g))
    if passed:
        best = passed[0]
        out = {f'{asset}_{tf}': dict(rqs=best[0], cfg=best[1],
               metrics={k: (float(v) if isinstance(v, (int, float, np.floating)) else v)
                        for k, v in best[2].items() if k != 'equity_curve'})}
        with open(f'results/_s325c_{asset}_{tf}.json', 'w', encoding='utf-8') as fp:
            json.dump(out, fp, ensure_ascii=False, indent=2, default=str)
        print(f"\nsaved results/_s325c_{asset}_{tf}.json")


if __name__ == '__main__':
    main()
