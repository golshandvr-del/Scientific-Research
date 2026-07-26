# -*- coding: utf-8 -*-
"""
s330m_mtf.py — تستِ مولتی‌تایم‌فریمِ لایهٔ احیاشدهٔ Asia-fade (قانونِ اولِ پروژه).
================================================================================
منطق: fade شکستِ کاذبِ بازهٔ افتتاحیهٔ سشنِ آسیا (h=0 UTC) + فیلترِ رژیمِ نوسان.
اشتباهِ رایجِ #۶ (TP/SL یکسانِ همهٔ TF): برای هر TF، طولِ بازهٔ افتتاحیه (or_bars) و
پنجره و SMAِ رژیم را *متناسب با آن TF* تنظیم می‌کنیم:
  M5 : ۱ ساعت = ۱۲ کندل  (مرجعِ برنده)
  M15: ۱ ساعت = ۴ کندل ؛ ۱.۵ ساعت = ۶ کندل
  M30: ۱ ساعت = ۲ کندل ؛ ۲ ساعت = ۴ کندل
  H1 : ۲–۳ کندل (۲–۳ ساعت اولِ آسیا)
  H4 : بازهٔ افتتاحیهٔ سشن با کندلِ ۴ساعته بی‌معناست ⇒ فقط برای کامل بودنِ گزارش تست.
هر TF چند آستانهٔ رژیم را می‌سنجد؛ بهترین ACCEPT گزارش می‌شود.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import trade_simulator as TS
from engine import rqs as RQS
from strategies.sim_orb import SessionORB

# برای هر TF: (or_bars گزینه‌ها, window, max_hold, regime_ma, k_sl, k_tp)
TF_PLANS = {
    'XAUUSD_M15': dict(obs=(4, 6), window=16, hold=16, ma=170, k_sl=1.0, k_tp=1.0),
    'XAUUSD_M30': dict(obs=(2, 4), window=10, hold=10, ma=85,  k_sl=1.0, k_tp=1.0),
    'XAUUSD_H1':  dict(obs=(2, 3), window=8,  hold=8,  ma=42,  k_sl=1.0, k_tp=1.0),
    'XAUUSD_H4':  dict(obs=(1, 2), window=6,  hold=6,  ma=20,  k_sl=1.0, k_tp=1.0),
}
REGIMES = (1.0, 1.1, 1.2)


def run(tf, ob, plan, thr):
    df = TS.load_data(tf)
    strat = SessionORB(session_start_hour=0, or_bars=ob, trade_window_bars=plan['window'],
                       side='FADE', atr_max=99, trend_ema=0,
                       k_sl=plan['k_sl'], k_tp=plan['k_tp'], max_hold=plan['hold'],
                       regime_atr_ratio_max=thr, regime_atr_ma=plan['ma'])
    tr, eq = TS.simulate(df, strat, 'XAUUSD', warmup=max(600, plan['ma'] + 100))
    rep = RQS.compute_rqs(tr, 'XAUUSD')
    m = rep['metrics']; g = rep['gates']
    gates = ''.join('1' if g.get(f'G{i}') else '0' for i in range(6))
    print(f"  {tf} ob={ob} reg<={thr} | {rep['verdict']:6s} RQS={rep['rqs_score']:5.1f} "
          f"n={m.get('n_trades',0):4d} WR={m.get('win_rate',0):4.1f}% "
          f"PF={m.get('profit_factor',0):.2f} | {gates}")
    return rep


if __name__ == '__main__':
    print("=" * 100)
    print("S330m — مولتی‌تایم‌فریمِ Asia-fade (XAUUSD). هر TF با or_bars/رژیمِ متناسبِ خود.")
    print("=" * 100)
    for tf, plan in TF_PLANS.items():
        print(f"\n### {tf} (window={plan['window']}, ma={plan['ma']}) ###")
        for ob in plan['obs']:
            for thr in REGIMES:
                try:
                    run(tf, ob, plan, thr)
                except Exception as e:
                    print(f"  {tf} ob={ob} reg<={thr} | ERROR: {e}")
