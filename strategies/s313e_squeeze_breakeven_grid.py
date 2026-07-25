# -*- coding: utf-8 -*-
"""
s313e_squeeze_breakeven_grid.py — فاز G: شکستنِ trade-off G0/G2 با Breakeven-Trailing
================================================================================
> یافتهٔ فاز F (S313d): روی H1، لبهٔ drift-کند به WR≈۶۱–۶۴٪ (بالای G0) می‌رسد ولی
> PF روی ~۱.۱۳ گیر می‌کند (زیرِ G2=۱.۳) چون sl>tp باختی‌ها بزرگ‌اند. تنشِ ذاتیِ
> G0↔G2 با یک بهبودِ ساختاری شکسته می‌شود: BREAKEVEN-TRAILING — وقتی سود به آستانه
> رسید، SL به entry+ε منتقل می‌شود ⇒ دمِ باخت‌های بزرگ بریده و PF بالا می‌رود،
> بی‌آنکه WR افت کند (قانونِ «همه چیز شناور» + قانونِ همکاریِ بهبودها).
>
> پایهٔ H1 (بهترین از فاز F): sqz=0.25, mh=48, sl_atr=3.2, tp_atr=2.15, cpos=0.55.
> این اسکریپت روی همان پایه، be_trigger_atr × be_offset_atr را جارو می‌کند + چند
> واریانتِ پایه. اعداد عمداً غیررند (اشتباهِ رایج #7).
>
> اجرا:  python3 strategies/s313e_squeeze_breakeven_grid.py XAUUSD_H1
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


def base_variants(tf):
    """پایه‌های امیدوارکننده (WR بالا) که breakeven رویشان اعمال می‌شود."""
    if tf.endswith('_H1'):
        return [
            dict(sqz_pct=0.25, max_hold=48, sl_atr=3.2, tp_atr=2.15, closepos_min=0.55),
            dict(sqz_pct=0.25, max_hold=36, sl_atr=3.2, tp_atr=2.15, closepos_min=0.55),
            dict(sqz_pct=0.30, max_hold=24, sl_atr=3.2, tp_atr=2.15),
            dict(sqz_pct=0.25, max_hold=48, sl_atr=2.6, tp_atr=1.7, closepos_min=0.55),
        ]
    elif tf.endswith('_M30'):
        return [
            dict(sqz_pct=0.25, max_hold=48, sl_atr=3.2, tp_atr=2.15, closepos_min=0.55),
            dict(sqz_pct=0.25, max_hold=36, sl_atr=3.2, tp_atr=2.15),
        ]
    else:
        return [dict(sqz_pct=0.20, max_hold=48, sl_atr=3.2, tp_atr=2.15)]


def main():
    tf = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD_H1'
    asset = tf.split('_')[0]
    df = TS.load_data(tf)
    print(f"\n{'#'*74}\n# S313e Squeeze Breakeven-Trailing — {tf} (rows={len(df)})\n{'#'*74}")

    # جارویِ breakeven (عمداً غیررند)
    trig_grid = [0.8, 1.1, 1.5, 2.0]     # آستانهٔ سود (× ATR) برای فعال‌شدنِ BE
    off_grid = [0.0, 0.15, 0.4]          # SL به entry + off×ATR

    best = None
    passed = []
    tested = 0
    rows = []
    for base in base_variants(tf):
        # ابتدا بدونِ breakeven (مرجع)
        for trig, off in [(0.0, 0.0)] + list(itertools.product(trig_grid, off_grid)):
            kw = dict(base, be_trigger_atr=trig, be_offset_atr=off)
            tr = run(df, asset, tf, **kw)
            s = stats(tr, asset)
            tested += 1
            rec_line = dict(kw=kw, s=s)
            rows.append(rec_line)
            if s['n'] >= 30 and s['wr'] >= 55 and s['pf'] >= 1.2:
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
              f"sl={k['sl_atr']} tp={k['tp_atr']} BE(trig={k['be_trigger_atr']},off={k['be_offset_atr']})")

    print("\n  ۸ ترکیبِ برترِ PF (تشخیصی — اثرِ breakeven):")
    for r in sorted(rows, key=lambda x: -x['s']['pf'])[:8]:
        k = r['kw']; s = r['s']
        print(f"    PF={s['pf']:.2f} WR={s['wr']:.1f}% net={s['net']:+.0f} n={s['n']} DD={s['dd']}% | "
              f"sl={k['sl_atr']} tp={k['tp_atr']} BE(trig={k['be_trigger_atr']},off={k['be_offset_atr']})")

    if best is not None:
        print("\n  بهترین کاندیدِ RQS:")
        rec = best[1]; k = rec['kw']
        tr = run(df, asset, tf, **k)
        sl_med = float(np.median(tr['sl_pip'].values)); tp_med = float(np.median(tr['tp_pip'].values))
        r = RQS.compute_rqs(tr, asset, sl_pip=sl_med, tp_pip=tp_med)
        print("   ", RQS.format_report(f"S313e-{tf}-best", r))
        print("    kw:", k)

    out = dict(tf=tf, tested=tested,
               passed=[dict(kw=p['kw'], rqs=p['rqs'], s=p['s'],
                            gates=p['gates'], metrics=p['metrics']) for p in passed],
               top_pf=[dict(pf=r['s']['pf'], wr=r['s']['wr'], net=r['s']['net'],
                            dd=r['s']['dd'], n=r['s']['n'], kw=r['kw'])
                       for r in sorted(rows, key=lambda x: -x['s']['pf'])[:12]],
               best=(dict(kw=best[1]['kw'], rqs=best[1]['rqs'], s=best[1]['s'],
                          gates=best[1]['gates'], metrics=best[1]['metrics'])
                     if best else None))
    outp = os.path.join(ROOT, 'results', f'_s313e_breakeven_{tf}.json')
    with open(outp, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\n  ⇒ saved {outp}")


if __name__ == '__main__':
    main()
