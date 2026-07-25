# -*- coding: utf-8 -*-
"""
s313b_squeeze_quality_grid.py — فاز E: بهبودِ لایهٔ Squeeze با فیلترهای کیفیتِ شکست
================================================================================
> ادامهٔ s313_squeeze_revival.py. یافتهٔ فاز B/C: PF با TF بالاتر بهتر می‌شود
> (M5 0.67 → M15 0.91 → M30 0.96 → H1 1.04 net مثبت). یعنی هستهٔ لبه در H1 واقعی
> است ولی ضعیف. این اسکریپت فیلترهای «کیفیتِ کندلِ شکست» را (قانونِ دومِ پروژه:
> چند بهبودِ همزمان) اضافه می‌کند تا false-breakoutها حذف و PF≥1.3 + WR≥60٪ شود:
>   body_min       : بدنهٔ کندلِ شکست ≥ x از دامنه (انفجارِ واقعی نه دوجی)
>   closepos_min   : close نزدیکِ سقفِ کندل (خریداران کنترل دارند)
>   breakout_atr_min : عمقِ عبور از سقفِ اخیر بر حسبِ ATR (شکستِ قاطع نه لمسِ مرزی)
>   RR نامتقارن    : اجازهٔ tp_atr > sl_atr (بگذار انفجار بدود)
>
> اجرا:  python3 strategies/s313b_squeeze_quality_grid.py XAUUSD_H1
"""
import os
import sys
import json
import itertools
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import trade_simulator as TS
from engine import rqs as RQS
from engine import scalp_engine as SE
from strategies.sim_strategies import S313_SqueezeBreakout_Long


def run(df, asset, tf, **kw):
    strat = S313_SqueezeBreakout_Long(**kw)
    warmup = max(260, kw.get('ema_slow', 200) + kw.get('sqz_lookback', 100) + 20)
    tr, _ = TS.simulate(df, strat, asset, tf=tf, warmup=warmup, max_bars_hold=None)
    return tr


def stats(tr, asset):
    if tr is None or len(tr) == 0:
        return dict(n=0, wr=0, pf=0, net=0, dd=0)
    n = len(tr); wins = (tr['outcome'] == 'win').sum()
    cap, _ = SE.run_capital(tr, asset, initial_capital=10000.0)
    return dict(n=n, wr=round(wins / n * 100, 1), pf=round(cap['profit_factor'], 2),
                net=round(cap['net_profit'], 0), dd=round(abs(cap['max_dd_pct']), 1))


def tf_base(tf):
    """پارامترهای پایهٔ مخصوصِ TF (بهترین از فاز B/C) + شبکهٔ کیفیت."""
    if tf.endswith('_H1'):
        base = dict(sqz_pct=0.30, max_hold=16)
        atr_pairs = [(2.15, 2.15), (2.15, 3.2), (1.7, 2.6), (2.15, 4.3)]
    elif tf.endswith('_M30'):
        base = dict(sqz_pct=0.25, max_hold=20)
        atr_pairs = [(2.15, 2.15), (2.15, 3.2), (1.7, 2.6), (2.15, 4.3)]
    elif tf.endswith('_M15'):
        base = dict(sqz_pct=0.20, max_hold=24)
        atr_pairs = [(2.15, 2.15), (2.15, 3.2), (2.15, 4.3)]
    else:  # M5
        base = dict(sqz_pct=0.15, max_hold=20)
        atr_pairs = [(2.15, 2.15), (2.15, 3.2), (2.15, 4.3)]
    return base, atr_pairs


def main():
    tf = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD_H1'
    asset = tf.split('_')[0]
    df = TS.load_data(tf)
    print(f"\n{'#'*74}\n# S313b Squeeze Quality-Grid — {tf} (rows={len(df)})\n{'#'*74}")

    base, atr_pairs = tf_base(tf)
    # شبکهٔ فیلترهای کیفیت (اعدادِ غیررند عمداً)
    body_grid = [0.0, 0.45, 0.60]
    cpos_grid = [0.0, 0.55, 0.70]
    depth_grid = [0.0, 0.15, 0.35]
    adx_grid = [0.0, 22.0]

    best = None
    passed = []
    tested = 0
    for (sl_a, tp_a) in atr_pairs:
        for body, cpos, depth, adxm in itertools.product(body_grid, cpos_grid, depth_grid, adx_grid):
            kw = dict(**base, sl_atr=sl_a, tp_atr=tp_a,
                      body_min=body, closepos_min=cpos,
                      breakout_atr_min=depth, adx_min=adxm)
            tr = run(df, asset, tf, **kw)
            s = stats(tr, asset)
            tested += 1
            if s['n'] >= 30 and s['wr'] >= 58 and s['pf'] >= 1.25:
                sl_med = float(np.median(tr['sl_pip'].values))
                tp_med = float(np.median(tr['tp_pip'].values))
                r = RQS.compute_rqs(tr, asset, sl_pip=sl_med, tp_pip=tp_med)
                rec = dict(kw=kw, s=s, rqs=r['rqs_score'], verdict=r['verdict'],
                           gates=r['gates'], metrics=r['metrics'])
                if r['verdict'] == 'ACCEPT':
                    passed.append(rec)
                key = (r['rqs_score'], s['net'])
                if best is None or key > best[0]:
                    best = (key, rec)

    print(f"\n  ترکیب‌های آزموده: {tested}")
    print(f"  کاندیدهای ACCEPT (RQS+ ≥ 80، همه ۶ گیت): {len(passed)}")
    for rec in sorted(passed, key=lambda x: -x['rqs'])[:6]:
        k = rec['kw']
        print(f"    ✅ RQS={rec['rqs']:.1f} {rec['s']} | "
              f"slatr={k['sl_atr']} tpatr={k['tp_atr']} body={k['body_min']} "
              f"cpos={k['closepos_min']} depth={k['breakout_atr_min']} adx≥{k['adx_min']}")

    if best is not None:
        print("\n  بهترین کاندید (حتی اگر ردشده):")
        rec = best[1]; k = rec['kw']
        tr = run(df, asset, tf, **k)
        sl_med = float(np.median(tr['sl_pip'].values)); tp_med = float(np.median(tr['tp_pip'].values))
        r = RQS.compute_rqs(tr, asset, sl_pip=sl_med, tp_pip=tp_med)
        print("   ", RQS.format_report(f"S313b-{tf}-best", r))
        print("    kw:", k)

    out = dict(tf=tf, tested=tested,
               passed=[dict(kw=p['kw'], rqs=p['rqs'], s=p['s'],
                            gates=p['gates'], metrics=p['metrics']) for p in passed],
               best=(dict(kw=best[1]['kw'], rqs=best[1]['rqs'], s=best[1]['s'],
                          gates=best[1]['gates'], metrics=best[1]['metrics'])
                     if best else None))
    outp = os.path.join(ROOT, 'results', f'_s313b_quality_{tf}.json')
    with open(outp, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\n  ⇒ saved {outp}")


if __name__ == '__main__':
    main()
