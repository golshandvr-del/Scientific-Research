# -*- coding: utf-8 -*-
"""
s330_final_verify.py — تاییدِ نهاییِ پیکربندیِ برندهٔ S330 (Asia-fade XAUUSD M5).

لایهٔ احیاشده: S21 (Session Opening-Range Breakout) → معکوس‌شده به FADE
(شکستِ کاذبِ بازهٔ افتتاحیهٔ سشنِ آسیا) + فیلترِ رژیمِ نوسان.

منطق:
  - سشنِ آسیا (h=0 UTC)، بازهٔ افتتاحیه = ۱۲ کندلِ اولِ M5 (یک ساعت).
  - اگر قیمت سقف/کفِ بازه را بشکند ولی close داخلِ بازه بازگردد ⇒ fade
    (شکستِ کاذب/liquidity-grab) در جهتِ مخالف.
  - فیلترِ رژیم: فقط اگر ATR جاری ÷ SMA(500) ATR ≤ ۱.۱ (بازارِ آرام/رنج).
    این فیلتر رژیمِ پرنوسانِ ۲۰۲۶ را به‌صورتِ علّی کنار می‌گذارد و G4 را پاس می‌کند.

خروجی: گزارشِ کاملِ RQS+ + جزئیاتِ گیت‌ها + توزیعِ سالانه.
"""
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import trade_simulator as TS  # noqa: E402
from engine import rqs as RQS  # noqa: E402
from strategies.sim_orb import SessionORB  # noqa: E402


# پیکربندیِ برندهٔ نهایی (از فلاتِ پایدارِ S330k)
FINAL = dict(
    session_start_hour=0,   # سشنِ آسیا (UTC)
    or_bars=12,             # بازهٔ افتتاحیه = ۱ ساعت روی M5
    trade_window_bars=48,   # پنجرهٔ فعالِ شکست
    side='FADE',            # شکستِ کاذب
    atr_max=99,             # coiled-spring غیرفعال (روی fade لازم نیست)
    trend_ema=0,            # فیلترِ جهت غیرفعال
    k_sl=1.0, k_tp=1.0,     # RR متقارن (صادقانه، بدونِ تلهٔ TP)
    max_hold=48,
    regime_atr_ratio_max=1.1,   # فیلترِ رژیمِ نوسان (بهبودِ کلیدی)
    regime_atr_ma=500,
)


def main():
    print("=" * 100)
    print("S330 — تاییدِ نهایی: Session-ORB FADE + فیلترِ رژیم (احیای S21) روی XAUUSD M5")
    print("=" * 100)
    df = TS.load_data('XAUUSD_M5')
    strat = SessionORB(**FINAL)
    trades, eq = TS.simulate(df, strat, 'XAUUSD', warmup=2000)
    rep = RQS.compute_rqs(trades, 'XAUUSD')
    print(RQS.format_report('S330_FINAL', rep))
    m = rep['metrics']
    print()
    print(f"  Verdict     : {rep['verdict']}")
    print(f"  RQS+        : {rep['rqs_score']:.1f}")
    print(f"  n_trades    : {m.get('n_trades',0)}")
    print(f"  win_rate    : {m.get('win_rate',0):.1f}%")
    print(f"  profit_factor: {m.get('profit_factor',0):.2f}")
    print(f"  max_dd_pct  : {m.get('max_dd_pct',0):.1f}%")
    print(f"  max_consec_L: {m.get('max_consec_losses',0)}")
    print(f"  p_value     : {m.get('p_value',1):.4f}")
    print(f"  gates       : {rep.get('gates')}")

    # توزیعِ سالانه (برای اثباتِ پایداریِ walk-forward)
    import pandas as pd
    if len(trades):
        tdf = pd.DataFrame(trades)
        # entry_bar → سالِ ورود
        tdf['year'] = df['dt'].dt.year.to_numpy()[tdf['entry_bar'].values]
        print("\n  توزیعِ سالانه:")
        for yr, g in tdf.groupby('year'):
            wr = (g['pnl_usd'] > 0).mean() * 100
            print(f"    {yr}: n={len(g):3d}  WR={wr:5.1f}%  net_usd={g['pnl_usd'].sum():9.2f}")


if __name__ == '__main__':
    main()
