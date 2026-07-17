"""
S78 — تستِ صحتِ موتورِ نو (scalp_engine) با بازتولیدِ منطقِ برندهٔ S73
================================================================================
> قانونِ شمارهٔ ۱: معیار فقط «سودِ خالصِ کلِ چهار ارز» است، نه WR.

هدف: قبل از اعتماد به موتورِ نو برای کشفِ استراتژیِ جدید، باید ثابت کنیم موتورِ نو
لبهٔ شناخته‌شدهٔ S73 (EURUSD Session-Open Drift) را بازتولید می‌کند. اگر موتورِ نو
هم روی همان منطق یورو را سودده نشان دهد (با هزینهٔ سخت‌گیرانه‌ترِ اسپرد+اسلیپیج)،
آنگاه موتور قابل‌اعتماد است.

منطقِ S73 که بازتولید می‌کنیم:
  • EURUSD، سیگنالِ Long روی کندلی که کندلِ بعدش ساعتِ 0 UTC است (session-open).
  • فیلترِ pullback: تفاضلِ close نسبت به ۴ کندلِ قبل منفی باشد (buy-the-dip).
  • SL=TP=12 pip ثابت، max_hold=16، ریسکِ ۱٪ غیرِمرکب.
  • تفاوت: موتورِ نو spread=1pip + slip=0.3pip دو طرف را اعمال می‌کند (سخت‌گیرانه‌تر).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np
import pandas as pd
from scalp_engine import load_data, simulate_trades, run_capital, summary_line, ASSETS
import warnings; warnings.filterwarnings('ignore')

EVAL_START = 24000
LONG_ENTRY_HOUR = 0
PULLBACK_LOOKBACK = 4


def s73_signals(df):
    n = len(df)
    dt = pd.to_datetime(df['time'], unit='s')
    hour = dt.dt.hour.values
    c = df['close'].values
    eval_mask = np.zeros(n, dtype=bool); eval_mask[EVAL_START:] = True
    is_last_before_h0 = np.zeros(n, dtype=bool)
    is_last_before_h0[:-1] = (hour[1:] == LONG_ENTRY_HOUR) & (hour[:-1] != LONG_ENTRY_HOUR)
    long_sig = is_last_before_h0 & eval_mask
    prior = np.zeros(n)
    prior[PULLBACK_LOOKBACK:] = c[PULLBACK_LOOKBACK:] - c[:-PULLBACK_LOOKBACK]
    long_sig = long_sig & (prior < 0)
    short_sig = np.zeros(n, dtype=bool)
    return long_sig, short_sig


def main():
    print("=" * 82)
    print("  S78 — تستِ صحتِ موتورِ نو (بازتولیدِ منطقِ S73 روی EURUSD)")
    print("=" * 82)
    asset = 'EURUSD'
    df = load_data(ASSETS[asset]['file'])
    longS, shortS = s73_signals(df)
    print(f"  کندل‌ها={len(df)}  Long-sig={int(longS.sum())}")

    tr = simulate_trades(df, longS, shortS, sl_pip=12.0, tp_pip=12.0,
                         asset=asset, max_hold=16, allow_overlap=False)
    stats, _ = run_capital(tr, asset, initial_capital=10000.0, risk_pct=1.0,
                           compounding=False)
    print("  " + summary_line(asset, stats))
    print("-" * 82)
    print(f"  رکوردِ S73 روی موتورِ قدیم (EURUSD) = +7,302$")
    print(f"  موتورِ نو (با اسپرد+اسلیپیجِ سخت‌گیرانه‌تر) = {stats['net_profit']:+.0f}$")
    verdict = "✅ موتور معتبر است (لبهٔ S73 بازتولید شد)" if stats['net_profit'] > 2000 \
              else "⚠️ اختلافِ زیاد — بررسیِ بیشتر لازم است"
    print(f"  نتیجه: {verdict}")
    print("=" * 82)


if __name__ == '__main__':
    main()
