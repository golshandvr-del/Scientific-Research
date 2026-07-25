# -*- coding: utf-8 -*-
"""
S325b — اسکنِ کارآمدِ احیای S219 (Channels) با کشِ سیگنالِ ساختاری.
================================================================================
بهینه‌سازیِ سرعت: channel_signals (حلقهٔ Python) برای هر ترکیبِ *ساختاری*
(side, ema, k, pos_max, max_gap) فقط یک‌بار محاسبه و کش می‌شود؛ سپس فیلترِ RSI و
SL/TP/max_hold/breakeven روی آن به‌سرعت جارو می‌شوند.

افزوده نسبت به S325 (برای عبور از G1/G4 — net منفی با WR بالا یعنی باخت‌های بزرگ):
  • breakeven-stop شناور (be_mult×ATR): پس از حرکتِ مساعد، SL را به نقطهٔ سربه‌سر ببر
    ⇒ باخت‌های بزرگ را به سربه‌سر تبدیل می‌کند ⇒ PF↑ و G1/G4↑.
اجرا: python3 strategies/s325b_cached_scan.py XAUUSD_M30 XAUUSD_H1 XAUUSD_H4
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

# گریدِ ساختاری (سیگنال کش می‌شود) — TP<SL کلیدِ احیا
STRUCT = dict(ema=[(10, 30), (20, 50)], k=[3, 5],
             pos_max=[0.25, 0.35, 0.5], max_gap=[40, 80])
# گریدِ سریع (روی سیگنالِ کش‌شده)
RSI = [(True, 40), (True, 45), (False, 0)]
SLTP = [(1.9, 0.9), (2.5, 1.0), (2.5, 1.3), (3.2, 1.0), (3.2, 1.5)]
BE = [None, 0.8, 1.2]   # breakeven trigger (×ATR)


def eval_fast(df, asset, raw_sig, side, rsi_arr, rsi_on, rsi_lo, rsi_hi,
              atr_pip, sl_mult, tp_mult, mh, be_mult):
    n = len(df)
    sig = raw_sig.copy()
    if rsi_on:
        if side == 'long':
            ok = rsi_arr <= rsi_lo
        else:
            ok = rsi_arr >= rsi_hi
        ok = pd.Series(ok).shift(1).fillna(False).to_numpy()
        sig = sig & ok
    if sig.sum() < 30:
        return None
    ls = sig if side == 'long' else np.zeros(n, bool)
    ss = sig if side == 'short' else np.zeros(n, bool)
    sl_pip = np.clip(sl_mult * atr_pip, 5.0, None)
    tp_pip = np.clip(tp_mult * atr_pip, 5.0, None)
    # be_trigger_pip باید اسکالر باشد (مقایسهٔ peak_favor >= be_trigger_pip*pip در موتور)
    # ⇒ از میانهٔ ATR *روی همان سیگنال‌ها* به‌عنوان یک آستانهٔ نمایندهٔ اسکالر استفاده می‌کنیم.
    if be_mult is None:
        be_trig = None
    else:
        med_atr = float(np.median(atr_pip[sig])) if sig.sum() else float(np.median(atr_pip))
        be_trig = max(be_mult * med_atr, 3.0)
    tr = se.simulate_trades(df, ls, ss, sl_pip, tp_pip, asset, max_hold=mh,
                            allow_overlap=False, be_trigger_pip=be_trig)
    if tr is None or len(tr) < 30:
        return None
    med_tp = float(np.median(tp_pip[sig]))
    r = rqs.compute_rqs(tr, asset, sl_pip=float(np.median(tr['sl_pip'])), tp_pip=med_tp)
    return r


def scan_asset(asset, tf, budget=300):
    df = se.load_data(f'data/{asset}_{tf}.csv')
    if 'dt' not in df.columns:
        df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    pip = se.ASSETS[asset]['pip']
    atr_pip = ind.atr(df, 14).to_numpy() / pip
    rsi_arr = ind.rsi(df['close'], 14).to_numpy()
    mh_map = {'M5': [48, 96], 'M15': [32, 64], 'M30': [24, 48], 'H1': [16, 32], 'H4': [8, 16]}
    mhs = mh_map.get(tf, [32, 64])

    t0 = time.time()
    rows = []; passed = []
    struct_keys = list(STRUCT.keys())
    for side in ['long', 'short']:
        for combo in itertools.product(*[STRUCT[k] for k in struct_keys]):
            if time.time() - t0 > budget:
                print(f"  [budget hit {asset} {tf}]"); break
            d = dict(zip(struct_keys, combo))
            raw = S219.channel_signals(df, side, d['ema'][0], d['ema'][1],
                                       d['k'], d['pos_max'], d['max_gap'],
                                       require_pullback=True, anti_range=True)
            if raw.sum() < 30:
                continue
            for (rsi_on, rlo) in RSI:
                rhi = 100 - rlo if rlo else 0
                for (slm, tpm) in SLTP:
                    for be in BE:
                        for mh in mhs:
                            r = eval_fast(df, asset, raw, side, rsi_arr, rsi_on, rlo, rhi,
                                          atr_pip, slm, tpm, mh, be)
                            if r is None:
                                continue
                            m = r['metrics']
                            cfg = dict(ema_fast=d['ema'][0], ema_slow=d['ema'][1], k=d['k'],
                                       pos_max=d['pos_max'], max_gap=d['max_gap'],
                                       rsi_on=rsi_on, rsi_lo=rlo, rsi_hi=rhi,
                                       sl_mult=slm, tp_mult=tpm, be_mult=be,
                                       side=side, max_hold=mh)
                            rows.append((r['rqs_score'], cfg, m, r['gates'], r['passed']))
                            if r['passed']:
                                passed.append((r['rqs_score'], cfg, m, r['gates']))
    rows.sort(key=lambda x: x[0], reverse=True)
    passed.sort(key=lambda x: x[0], reverse=True)
    return rows, passed


def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else ['XAUUSD_M30']
    allout = {}
    for tgt in targets:
        asset, tf = tgt.split('_')
        print(f"\n=== {tgt} ===")
        rows, passed = scan_asset(asset, tf)
        print(f"  evaluated={len(rows)}  PASSED(RQS+>=80)={len(passed)}")
        for score, cfg, m, g in passed[:3]:
            gs = ''.join('1' if g[k] else '0' for k in sorted(g.keys()))
            print(f"  RQS={score:.1f} PASS G[{gs}] {cfg['side']} n={m['n_trades']} WR={m['win_rate']:.1f} "
                  f"PF={m['profit_factor']:.2f} DD={m['max_dd_pct']:.1f} p={m['p_value']:.3f} "
                  f"net={m['net_profit']:.0f} wf={[round(x) for x in m['wf_nets']]} "
                  f"| ema{cfg['ema_fast']}/{cfg['ema_slow']} k{cfg['k']} pos{cfg['pos_max']} "
                  f"rsi{cfg['rsi_on']} sl{cfg['sl_mult']}tp{cfg['tp_mult']} be{cfg['be_mult']} mh{cfg['max_hold']}")
        if not passed:
            print("  --- best 4 FAILs (diagnostic) ---")
            for score, cfg, m, g, ps in rows[:4]:
                gs = ''.join('1' if g[k] else '0' for k in sorted(g.keys()))
                print(f"  RQS={score:.1f} G[{gs}] {cfg['side']} n={m['n_trades']} WR={m['win_rate']:.1f} "
                      f"PF={m['profit_factor']:.2f} DD={m['max_dd_pct']:.1f} p={m['p_value']:.3f} "
                      f"net={m['net_profit']:.0f} wf={[round(x) for x in m['wf_nets']]} "
                      f"| sl{cfg['sl_mult']}tp{cfg['tp_mult']} be{cfg['be_mult']} mh{cfg['max_hold']}")
        if passed:
            best = passed[0]
            allout[tgt] = dict(rqs=best[0], cfg=best[1],
                               metrics={k: (float(v) if isinstance(v, (int, float, np.floating)) else v)
                                        for k, v in best[2].items() if k != 'equity_curve'})
    if allout:
        with open('results/_s325_channels.json', 'w', encoding='utf-8') as fp:
            json.dump(allout, fp, ensure_ascii=False, indent=2, default=str)
        print("\nsaved results/_s325_channels.json")


if __name__ == '__main__':
    main()
