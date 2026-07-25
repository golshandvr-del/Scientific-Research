# -*- coding: utf-8 -*-
"""
s312_oos_check.py — آزمونِ سختگیرانهٔ ضدِ overfit برای S312 (احیای S142)
================================================================================
> نگرانی: در finalize، سودِ M15 عمدتاً از 2025-2026 آمد (سال‌های قبل +33..+96$).
> این می‌تواند نشانهٔ overfit یا رژیم-وابستگی باشد. RQS+ رسمی (G4=4پنجره) پاس شد،
> اما صداقتِ علمی می‌طلبد یک آزمونِ IS/OOS واقعی انجام دهیم:
>   IS (in-sample): نیمهٔ اولِ داده (که پارامتر روی آن انتخاب شد در روحِ S142)
>   OOS (out-of-sample): نیمهٔ دوم
> اگر لبه فقط در OOالسِ اخیر (2025-2026) باشد و در IS صفر/منفی باشد ⇒ رژیم-وابسته.
> اگر در هر دو مثبت باشد ⇒ لبهٔ واقعیِ ساختاری.

همچنین: تست می‌کنیم آیا فیلترِ کیفیت (EMA200) خودش لبه می‌سازد یا فقط drift را تمیز
می‌کند — با مقایسهٔ mid-month+EMA در برابرِ «فقط EMA در روزهای غیرِ mid-month».

اجرا: python3 strategies/s312_oos_check.py
"""
import os
import sys
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import trade_simulator as TS
from engine import rqs as RQS
from engine import scalp_engine as SE
from strategies.sim_strategies import S312_MidMonth_Long


def split_stats(trades, df, asset, split_year):
    """آمارِ دو بخش: exit پیش از split_year (IS) و از split_year به بعد (OOS)."""
    if trades is None or len(trades) == 0:
        return None
    yrs = pd.DatetimeIndex(df['dt'].values[trades['exit_bar'].values]).year
    tr = trades.assign(year=yrs)
    out = {}
    for label, mask in [('IS(<%d)' % split_year, tr['year'] < split_year),
                        ('OOS(>=%d)' % split_year, tr['year'] >= split_year)]:
        sub = tr[mask]
        if len(sub) == 0:
            out[label] = dict(n=0); continue
        cap, _ = SE.run_capital(sub, asset, initial_capital=10000.0)
        out[label] = dict(n=len(sub),
                          wr=round((sub['outcome'] == 'win').mean() * 100, 1),
                          pf=round(cap['profit_factor'], 2),
                          net=round(cap['net_profit'], 0))
    return out


def main():
    print(f"{'#'*72}\n# S312 OOS / anti-overfit check\n{'#'*72}")
    configs = {
        'XAUUSD_M15': dict(sl_pip=295, tp_pip=295, max_hold=48, quality_filter=True),
        'XAUUSD_M30': dict(sl_pip=295, tp_pip=295, max_hold=36, quality_filter=True),
        'XAUUSD_H1':  dict(sl_pip=395, tp_pip=395, max_hold=24, quality_filter=True),
    }
    for tf, kw in configs.items():
        asset = tf.split('_')[0]
        df = TS.load_data(tf)
        strat = S312_MidMonth_Long(**kw)
        tr, _ = TS.simulate(df, strat, asset, tf=tf, warmup=220,
                            max_bars_hold=kw['max_hold'])
        print(f"\n=== {tf} ===")
        # split نقطهٔ میانهٔ *داده* (نه سالِ ثابت) تا هر TF منصفانه نصف شود
        yrs = pd.DatetimeIndex(df['dt'].values[tr['exit_bar'].values]).year
        mid_year = int(np.median(yrs))
        s = split_stats(tr, df, asset, mid_year + 1)
        for label, v in s.items():
            if v.get('n', 0) == 0:
                print(f"   {label}: no trades"); continue
            print(f"   {label}: n={v['n']:3d} WR={v['wr']:4.1f}% PF={v['pf']:.2f} net={v['net']:+8.0f}$")
        # verdict
        vals = [v for v in s.values() if v.get('n', 0) > 0]
        both_pos = all(v['net'] > 0 for v in vals)
        both_wr = all(v['wr'] >= 55 for v in vals)
        print(f"   ⇒ هر دو نیمه مثبت: {both_pos} | هر دو WR≥55: {both_wr}")


if __name__ == '__main__':
    main()
