# -*- coding: utf-8 -*-
"""
s337_precision_diag.py — تشخیصِ «کدام لحظه‌ها ذاتاً WR بالا دارند؟»
====================================================================
چالشِ User Note: ۱ معامله/روز با WR≥۸۰٪ یا ۴ معامله/روز با WR≥۷۰٪.
درسِ S336 (DEAD): «پُرمعامله + فیلترِ نویز» شکست خورد؛ راهِ درست = سیگنالِ پُردقتِ کم‌معامله.

این اسکریپت *سیگنالِ ورود* نمی‌سازد؛ فقط می‌پرسد: اگر در جهتِ روندِ تثبیت‌شده (trend-continuation)
وارد شویم و TP کوچک/متوازن بگذاریم، در کدام رژیم WR ذاتی بالا می‌رود؟ خروجی = نقشهٔ رژیم→WR.

منطق: طلا سوگیریِ ادامه‌دهندگی دارد (hurst>0.5). فرضیه: «در روندِ تمیز (r2 بالا)، یک پول‌بکِ کوچک
(ema_dist منفیِ کوچک در روندِ صعودی) نقطهٔ ورودِ کم‌ریسکِ ادامهٔ روند است» — کلاسیکِ buy-the-dip.
اینجا هر دو جهت را می‌سنجیم چون چالش جهت را آزاد گذاشته (هرچند پروژه به SHORT محتاج‌تر است).
"""
import numpy as np
import pandas as pd
from engine import scalp_engine as se, rqs
from engine import indicator_bank as ib

TF_BARS_PER_DAY = {'M5': 288, 'M15': 96, 'M30': 48, 'H1': 24}


def load(asset, tf):
    return se.load_data(f'data/{asset}_{tf}.csv')


def wr_pf(trades):
    if trades is None or len(trades) == 0:
        return 0, 0, 0
    wr = (trades['outcome'] == 'win').mean() * 100
    wins = trades.loc[trades.pnl_pip > 0, 'pnl_pip'].sum()
    loss = -trades.loc[trades.pnl_pip <= 0, 'pnl_pip'].sum()
    pf = wins / loss if loss > 0 else 9.99
    return len(trades), wr, pf


def diag(asset='XAUUSD', tf='M5'):
    df = load(asset, tf)
    n = len(df)
    days = n / TF_BARS_PER_DAY[tf]
    print(f"=== PRECISION DIAG {asset}/{tf} === n_candles={n}  (~{days:.0f} روز)")
    print(f"هدفِ چالش: ~۱/روز→{days:.0f} معامله کل با WR≥۸۰ | ~۴/روز→{days*4:.0f} معامله با WR≥۷۰\n")

    close = df['close'].values
    # اندیکاتورهای رژیم/جهت (همه shift(1) داخلِ استفاده تا بدون look-ahead)
    hurst = ib.compute('hurst', df).shift(1).values
    r2 = ib.compute('r2_fib_55', df).shift(1).values
    ema_dist = ib.compute('ema_dist_atr', df).shift(1).values   # کششِ نرمال به ATR
    hma = ib.compute('hma_fib_34', df)
    hma_slope = (hma - hma.shift(3)).shift(1).values            # شیبِ جهت
    adx_like = ib.compute('r2', df).shift(1).values

    def sim(sig_long, sig_short, sl, tp, mh):
        tr = se.simulate_trades(df, sig_long, sig_short, sl, tp, asset, mh, False)
        if tr is not None and len(tr):
            tr = tr.copy(); tr['tp_pip'] = float(tp)
        return tr

    # فرضیهٔ ۱ (LONG): روندِ صعودیِ تمیز + پول‌بکِ کوچک (buy-the-dip در روند)
    print("--- فرضیه ۱: LONG buy-the-dip در روندِ صعودیِ تمیز (hurst>0.5 & r2 بالا & شیبِ HMA>0 & پول‌بکِ کوچک) ---")
    print(f"{'r2>':>5} {'H>':>5} {'dipMin':>7} {'SL':>4} {'TP':>4} {'n':>4} {'WR':>5} {'PF':>5} {'/day':>5}")
    for r2t in [0.45, 0.60, 0.75]:
        for hut in [0.50, 0.55]:
            base = (r2 > r2t) & (hurst > hut) & (hma_slope > 0)
            for dip in [-0.5, -1.0, -1.5]:   # پول‌بکِ کوچک: قیمت کمی زیرِ EMA
                mask = base & (ema_dist < dip) & (ema_dist > dip - 1.0)
                sig = np.nan_to_num(mask, nan=False).astype(bool)
                for sl, tp in [(55, 55), (89, 89), (55, 89), (89, 55)]:
                    tr = sim(sig, np.zeros(n, bool), sl, tp, 48)
                    nt, wr, pf = wr_pf(tr)
                    if nt >= 20:
                        print(f"{r2t:>5.2f} {hut:>5.2f} {dip:>7.1f} {sl:>4d} {tp:>4d} "
                              f"{nt:>4d} {wr:>5.1f} {pf:>5.2f} {nt/days:>5.2f}")


if __name__ == '__main__':
    import sys
    diag('XAUUSD', sys.argv[1] if len(sys.argv) > 1 else 'M5')
