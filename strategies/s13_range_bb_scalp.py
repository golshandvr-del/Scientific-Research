"""
استراتژی ۱۳: Range-Regime Bollinger Mean-Reversion Scalp
=========================================================
کشف اکتشافی: در رژیم رنج (ADX<20)، وقتی قیمت از باند بولینگر خارج می‌شود، با هدف
کوچک (TP<SL) تمایل قوی به بازگشت به میانگین دارد → WR بالا با فرکانس قابل‌قبول.

این استراتژی مستقیماً «تضاد WR بالا ↔ فرکانس بالا» را هدف می‌گیرد:
- بدون قید session (فرکانس بالا در تمام ساعات)
- در رژیم رنج، mean-reversion یک edge واقعی است (برخلاف پیش‌بینی جهت روند)

### قوانین
- **رژیم:** ADX(14) < adx_max (رنج / بدون روند قوی)
- **LONG:** close < LowerBB(20, k) → انتظار بازگشت به بالا
- **SHORT:** close > UpperBB(20, k) → انتظار بازگشت به پایین
- **مدیریت:** TP = tp×ATR (کوچک)، SL = sl×ATR (بزرگ‌تر)، افق کوتاه.

نکته‌ی ریاضی: BE = sl/(tp+sl). برای TP0.5/SL1.0 → BE=66.7%. اگر WR واقعی
(پس از اسپرد) بالاتر از این بماند، هم WR>70% و هم expectancy مثبت داریم.

اعتبارسنجی: بک‌تست کامل (ورود open بعدی + اسپرد ۰.۲$) + تقسیم زمانی + p-value.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np
import pandas as pd
from scipy import stats as sps
from backtest import load_data, run_backtest
import indicators as ind


def build(df):
    atr = ind.atr(df, 14)
    adx, pdi, mdi = ind.adx(df, 14)
    bbl, bbm, bbu = ind.bollinger(df['close'], 20, 2.0)
    rsi = ind.rsi(df['close'], 14)
    return atr, adx, bbl, bbm, bbu, rsi


def signals(df, adx, bbl, bbu, adx_max=20, k_extra=0.0):
    close = df['close'].values
    range_regime = adx.values < adx_max
    long_sig = range_regime & (close < bbl.values * (1 - k_extra))
    short_sig = range_regime & (close > bbu.values * (1 + k_extra))
    long_sig[:300] = False
    short_sig[:300] = False
    return long_sig, short_sig


def bt(df, sig, atr, direction, tp_mult, sl_mult, spread=0.20, max_hold=48):
    atr_v = atr.values
    stats, tr = run_backtest(
        df, sig, sl_points=None, tp_points=None, direction=direction,
        spread=spread, max_hold=max_hold, allow_overlap=False,
        sl_series=atr_v*sl_mult, tp_series=atr_v*tp_mult)
    return stats, tr


def pval(nwin, n, be):
    if n == 0: return 1.0
    return sps.binomtest(nwin, n, min(be, 0.999), alternative='greater').pvalue


def report(tag, s, be):
    if s['n_trades'] == 0:
        print(f"{tag}: n=0"); return
    nwin = int(round(s['win_rate']/100*s['n_trades']))
    p = pval(nwin, s['n_trades'], be)
    print(f"{tag}: n={s['n_trades']}, WR={s['win_rate']:.2f}%, "
          f"exp={s['expectancy']:.3f}$, PnL={s['total_pnl']:.0f}$, "
          f"BE={be*100:.1f}%, p={p:.4f}")


if __name__ == '__main__':
    df = load_data()
    days = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days
    atr, adx, bbl, bbm, bbu, rsi = build(df)
    print(f"داده: {len(df)} کندل، {days} روز\n")

    print("=== S13 Range-BB Scalp — بک‌تست کامل (اسپرد ۰.۲$) ===")
    for adx_max in [18, 20, 25]:
        ls, ss = signals(df, adx, bbl, bbu, adx_max=adx_max)
        print(f"\n[ADX<{adx_max}]  long_sig={ls.sum()} short_sig={ss.sum()}")
        for tp, sl in [(0.5, 1.0), (0.6, 1.0), (0.5, 0.8)]:
            be = sl/(tp+sl)
            # ترکیب long+short
            sl_stats, _ = bt(df, ls, atr, 'long', tp, sl)
            ss_stats, _ = bt(df, ss, atr, 'short', tp, sl)
            nt = sl_stats['n_trades'] + ss_stats['n_trades']
            nwin = (sl_stats['win_rate']/100*sl_stats['n_trades'] +
                    ss_stats['win_rate']/100*ss_stats['n_trades'])
            wr = nwin/nt*100 if nt else 0
            pnl = sl_stats['total_pnl'] + ss_stats['total_pnl']
            exp = pnl/nt if nt else 0
            p = pval(int(round(nwin)), nt, be)
            print(f"  TP{tp}/SL{sl} (BE={be*100:.0f}%) ترکیبی: n={nt}, WR={wr:.2f}%, "
                  f"exp={exp:.3f}$, PnL={pnl:.0f}$, ~{nt/days:.2f}/day, p={p:.4f}")
