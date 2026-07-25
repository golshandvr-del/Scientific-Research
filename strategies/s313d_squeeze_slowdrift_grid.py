# -*- coding: utf-8 -*-
"""
s313d_squeeze_slowdrift_grid.py — فاز F: احیای Squeeze با فرضیهٔ «drift کندِ افق‌بلند»
================================================================================
> کشفِ قاطعِ S313c (probe): لبهٔ جهت‌دارِ Squeeze-Breakout در افقِ کوتاه (H=6,12)
> بی‌معناست ولی در افقِ بلند (H=24,48) معنادار می‌شود (H1: t=+3.41 در H=24).
> یعنی این یک «انفجارِ سریعِ اسکالپی» نیست، بلکه یک DRIFTِ کندِ امتدادی است.
>
> پس فرضیهٔ اصلاح‌شده:
>   ۱) max_hold باید بلند باشد (≈۲۴–۶۰ کندل) تا drift کند بریده نشود — علتِ اصلیِ
>      شکستِ تلاشِ اولم که max_hold=12–24 کوتاه گذاشته بودم.
>   ۲) برای عبور از گیتِ G0 (WR≥60٪) روی یک drift-play، دو مسیر آزموده می‌شود:
>        (الف) RR نامتقارن به نفعِ WR (tp < sl): قفلِ زودِ سودِ کوچک از drift.
>        (ب) RR متقارن/به‌نفعِ TP + فیلترِ کیفیت: WR کمتر ولی PF بالاتر.
>   ۳) اعدادِ ATR غیررند (اشتباهِ رایج #7).
>   ۴) روی H1 (قوی‌ترین لبه) و M30 (لبهٔ دوم) تمرکز؛ M15/M5 لبهٔ ضعیف‌تر.
>
> اجرا:  python3 strategies/s313d_squeeze_slowdrift_grid.py XAUUSD_H1
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


def tf_grid(tf):
    """شبکهٔ مخصوصِ TF: max_hold بلند + جفت‌های ATR (نامتقارن هر دو جهت)."""
    if tf.endswith('_H1'):
        sqz = [0.25, 0.30]; holds = [24, 36, 48]
        # (sl, tp): هم نامتقارن به‌نفعِ WR (tp<sl) هم متقارن هم به‌نفعِ TP
        pairs = [(2.6, 1.7), (3.2, 2.15), (2.15, 2.15), (1.7, 1.7),
                 (2.15, 3.2), (2.6, 4.3)]
    elif tf.endswith('_M30'):
        sqz = [0.20, 0.25]; holds = [24, 36, 48]
        pairs = [(2.6, 1.7), (3.2, 2.15), (2.15, 2.15), (1.7, 1.7),
                 (2.15, 3.2), (2.6, 4.3)]
    elif tf.endswith('_M15'):
        sqz = [0.15, 0.20]; holds = [36, 48, 60]
        pairs = [(2.6, 1.7), (3.2, 2.15), (2.15, 2.15), (2.15, 3.2)]
    else:  # M5
        sqz = [0.12, 0.15]; holds = [36, 48, 60]
        pairs = [(2.6, 1.7), (3.2, 2.15), (2.15, 2.15), (2.15, 3.2)]
    return sqz, holds, pairs


def main():
    tf = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD_H1'
    asset = tf.split('_')[0]
    df = TS.load_data(tf)
    print(f"\n{'#'*74}\n# S313d Squeeze Slow-Drift Grid — {tf} (rows={len(df)})\n{'#'*74}")

    sqz_grid, hold_grid, pair_grid = tf_grid(tf)
    # فیلترهای کیفیتِ اختیاری (سبک — از probe دیدیم اثرشان محدود است)
    qual_grid = [(0.0, 0.0, 0.0), (0.0, 0.55, 0.0), (0.45, 0.60, 0.15)]

    best = None
    passed = []
    tested = 0
    top_by_pf = []
    for sqz in sqz_grid:
        for mh in hold_grid:
            for (sl_a, tp_a) in pair_grid:
                for (body, cpos, depth) in qual_grid:
                    kw = dict(sqz_pct=sqz, max_hold=mh, sl_atr=sl_a, tp_atr=tp_a,
                              body_min=body, closepos_min=cpos, breakout_atr_min=depth)
                    tr = run(df, asset, tf, **kw)
                    s = stats(tr, asset)
                    tested += 1
                    if s['n'] >= 30:
                        top_by_pf.append((s['pf'], s['wr'], s['net'], kw, s))
                    if s['n'] >= 30 and s['wr'] >= 55 and s['pf'] >= 1.15:
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
    print(f"  کاندیدهای ACCEPT (RQS+ ≥ 80): {len(passed)}")
    for rec in sorted(passed, key=lambda x: -x['rqs'])[:8]:
        k = rec['kw']
        print(f"    ✅ RQS={rec['rqs']:.1f} {rec['s']} | sqz={k['sqz_pct']} mh={k['max_hold']} "
              f"sl={k['sl_atr']} tp={k['tp_atr']} q=({k['body_min']},{k['closepos_min']},{k['breakout_atr_min']})")

    # نمایشِ ۶ ترکیبِ برترِ PF (برای دیدِ کلی حتی اگر ردشدند)
    print("\n  ۶ ترکیبِ برترِ PF (تشخیصی):")
    for pf, wr, net, kw, s in sorted(top_by_pf, key=lambda x: -x[0])[:6]:
        print(f"    PF={pf:.2f} WR={wr:.1f}% net={net:+.0f} n={s['n']} | "
              f"sqz={kw['sqz_pct']} mh={kw['max_hold']} sl={kw['sl_atr']} tp={kw['tp_atr']} "
              f"q=({kw['body_min']},{kw['closepos_min']},{kw['breakout_atr_min']})")

    if best is not None:
        print("\n  بهترین کاندیدِ RQS (حتی اگر ردشده):")
        rec = best[1]; k = rec['kw']
        tr = run(df, asset, tf, **k)
        sl_med = float(np.median(tr['sl_pip'].values)); tp_med = float(np.median(tr['tp_pip'].values))
        r = RQS.compute_rqs(tr, asset, sl_pip=sl_med, tp_pip=tp_med)
        print("   ", RQS.format_report(f"S313d-{tf}-best", r))
        print("    kw:", k)

    out = dict(tf=tf, tested=tested,
               passed=[dict(kw=p['kw'], rqs=p['rqs'], s=p['s'],
                            gates=p['gates'], metrics=p['metrics']) for p in passed],
               top_pf=[dict(pf=t[0], wr=t[1], net=t[2], kw=t[3]) for t in
                       sorted(top_by_pf, key=lambda x: -x[0])[:10]],
               best=(dict(kw=best[1]['kw'], rqs=best[1]['rqs'], s=best[1]['s'],
                          gates=best[1]['gates'], metrics=best[1]['metrics'])
                     if best else None))
    outp = os.path.join(ROOT, 'results', f'_s313d_slowdrift_{tf}.json')
    with open(outp, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\n  ⇒ saved {outp}")


if __name__ == '__main__':
    main()
