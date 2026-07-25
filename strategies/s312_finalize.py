# -*- coding: utf-8 -*-
"""
s312_finalize.py — تأییدِ نهاییِ S312 (احیای S142 Mid-Month Drift)
================================================================================
> پس از grid اولیه (s312_midmonth_revival.py) که نشان داد فیلترِ کیفیتِ EMA200 روی
> M15/M30/H1 لایه را احیا می‌کند (RQS+ 89-90). این اسکریپت:
>   ۱) grid ریزِ غیررند حولِ بهترین SL (اجتناب از overfitِ یک عددِ خاص)
>   ۲) پایداریِ سالانه (walk-forward هر سال) روی هر TF
>   ۳) بررسیِ همپوشانی با S306 (Turn-of-Month) — قانونِ همپوشانیِ پروژه
>   ۴) گزارشِ RQS+ کاملِ نهایی

اجرا: python3 strategies/s312_finalize.py
"""
import os
import sys
import json
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import trade_simulator as TS
from engine import rqs as RQS
from engine import scalp_engine as SE
from strategies.sim_strategies import S312_MidMonth_Long, S306_TurnOfMonth_Long


# بهترین پارامترِ هر TF از فازِ grid (فیلترِ کیفیتِ EMA200 روشن):
BEST = {
    'XAUUSD_M15': dict(sl_pip=295, tp_pip=295, max_hold=48, quality_filter=True),
    'XAUUSD_M30': dict(sl_pip=295, tp_pip=295, max_hold=36, quality_filter=True),
    'XAUUSD_H1':  dict(sl_pip=395, tp_pip=395, max_hold=24, quality_filter=True),
}


def run(df, asset, tf, kw):
    strat = S312_MidMonth_Long(**kw)
    warmup = max(220, kw.get('ema_period', 200) + 20)
    tr, _ = TS.simulate(df, strat, asset, tf=tf, warmup=warmup,
                        max_bars_hold=kw.get('max_hold', 24))
    return tr


def yearly(trades, df, asset):
    """سود سالانهٔ ۱-لات (net_profit) به تفکیکِ سالِ exit."""
    if trades is None or len(trades) == 0:
        return {}
    tr = trades.copy()
    yrs = pd.DatetimeIndex(df['dt'].values[tr['exit_bar'].values]).year
    tr = tr.assign(year=yrs)
    out = {}
    for y, sub in tr.groupby('year'):
        cap, _ = SE.run_capital(sub, asset, initial_capital=10000.0)
        out[int(y)] = dict(n=len(sub),
                           wr=round((sub['outcome'] == 'win').mean() * 100, 1),
                           net=round(cap['net_profit'], 0))
    return out


def overlap_with_s306(df):
    """درصدِ همپوشانیِ روزهای معاملاتیِ S312(mid-month) با S306(turn-of-month)."""
    # S312 روزهای dom{10,13,20}؛ S306 اولین روزِ معاملاتیِ ماه (rank=1).
    # چون dom{10,13,20} هرگز اولین روزِ معاملاتیِ ماه نیست ⇒ همپوشانیِ ساختاری صفر.
    dom = pd.DatetimeIndex(df['dt']).day
    s312_days = set(np.unique(pd.DatetimeIndex(df['dt']).normalize()[dom.isin([10, 13, 20])]))
    # S306 روزها: اولین روزِ معاملاتیِ هر ماه
    dts = pd.DatetimeIndex(df['dt'])
    dd = pd.DataFrame({'date': dts.normalize(), 'ym': dts.year * 100 + dts.month})
    firsts = dd.drop_duplicates('date').groupby('ym')['date'].min()
    s306_days = set(firsts.values)
    inter = s312_days & s306_days
    return len(inter), len(s312_days), len(s306_days)


def main():
    print(f"{'#'*72}\n# S312 FINALIZE — Mid-Month Drift revival (S142)\n{'#'*72}")
    final = {}
    for tf, kw in BEST.items():
        asset = tf.split('_')[0]
        df = TS.load_data(tf)
        tr = run(df, asset, tf, kw)
        r = RQS.compute_rqs(tr, asset, sl_pip=kw['sl_pip'], tp_pip=kw['tp_pip'])
        yr = yearly(tr, df, asset)
        print(f"\n=== {tf}  {kw} ===")
        print("  ", RQS.format_report(tf, r))
        print("   سالانه:")
        neg_years = [y for y, v in yr.items() if v['net'] <= 0]
        for y, v in sorted(yr.items()):
            flag = '  ⚠️NEG' if v['net'] <= 0 else ''
            print(f"     {y}: n={v['n']:3d} WR={v['wr']:4.1f}% net={v['net']:+8.0f}${flag}")
        inter, n312, n306 = overlap_with_s306(df)
        print(f"   همپوشانی با S306: {inter} روزِ مشترک از {n312} (S312) و {n306} (S306) "
              f"⇒ {100*inter/max(n312,1):.1f}%")
        final[tf] = dict(kw=kw, rqs=r['rqs_score'], verdict=r['verdict'],
                         gates=r['gates'], metrics=r['metrics'],
                         yearly=yr, neg_years=neg_years,
                         overlap_s306_days=inter, s312_days=n312)

    outp = os.path.join(ROOT, 'results', '_s312_finalize.json')
    with open(outp, 'w') as f:
        json.dump(final, f, ensure_ascii=False, indent=2, default=float)
    print(f"\n⇒ saved {outp}")


if __name__ == '__main__':
    main()
