# -*- coding: utf-8 -*-
"""
s311_nfp_explore.py — اکتشافِ اولیهٔ رفتارِ طلا حولِ NFP (جمعهٔ اولِ ماه)
================================================================================
> نشستِ احیا: کاندیدِ لایهٔ نو/احیا = «NFP-day drift» (بُعدِ تقویمیِ بکر).
> در PARADIGM (S142) NFP فقط در یک اسکنِ کلی دیده شد ولی هرگز به لایهٔ مستقل تبدیل
> نشد (mid-month قوی‌تر بود). این‌جا صرفاً «آیا لبه‌ای هست؟» را می‌سنجیم — بدونِ فرضِ
> جهت. اگر لبه دید، در فایلِ بعد با advise() + بهبودها به RQS+ می‌سپاریم.

منطقِ علمیِ NFP:
  گزارشِ Non-Farm Payrolls آمریکا: جمعهٔ اولِ هر ماه، 12:30 UTC. بزرگ‌ترین شوکِ
  نقدینگی/نوسانِ ماهانهٔ طلا. سه فرضیهٔ رقیب:
    (H1) drift جهت‌دار پیش از انتشار (position-squaring)
    (H2) واکنشِ mean-reversion پس از اسپایکِ اولیه (over-reaction fade)
    (H3) ادامهٔ مومنتومِ پس از انتشار (breakout)
  این اسکن هر سه را به‌صورتِ توصیفی می‌سنجد.

اجرا:
  python3 strategies/s311_nfp_explore.py
"""
import os
import sys
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def first_friday_flag(dt_series):
    """آرایهٔ بولین: آیا این کندل در جمعهٔ اولِ ماه است؟ (جمعه = dayofweek 4)"""
    dt = pd.DatetimeIndex(dt_series)
    is_fri = dt.dayofweek == 4
    day = dt.day
    # جمعهٔ اول = اولین جمعه ⇒ روزِ ماه بین 1..7
    return is_fri & (day <= 7)


def hourly_drift_profile(df, is_nfp):
    """میانگینِ حرکتِ close-to-close (pip) در هر ساعتِ UTC روی روزهای NFP vs غیر."""
    pip = 0.10
    ret = (df['close'].diff() / pip).values  # حرکتِ هر کندل بر حسبِ pip
    hour = pd.DatetimeIndex(df['dt']).hour.values
    rows = []
    for h in range(24):
        m_nfp = is_nfp & (hour == h)
        m_oth = (~is_nfp) & (hour == h)
        if m_nfp.sum() < 5:
            continue
        rows.append(dict(
            hour=h,
            nfp_mean=np.nanmean(ret[m_nfp]),
            nfp_n=int(m_nfp.sum()),
            oth_mean=np.nanmean(ret[m_oth]),
            diff=np.nanmean(ret[m_nfp]) - np.nanmean(ret[m_oth]),
        ))
    return pd.DataFrame(rows)


def window_drift(df, is_nfp, h_start, h_end):
    """حرکتِ تجمعیِ pip از ساعتِ h_start تا h_end در روزهای NFP (open->close آن پنجره)."""
    pip = 0.10
    dt = pd.DatetimeIndex(df['dt'])
    hour = dt.hour.values
    date = dt.date
    o = df['open'].values
    c = df['close'].values
    moves = []
    dates = np.unique(date[is_nfp])
    for d in dates:
        mask_day = (date == d)
        m_win = mask_day & (hour >= h_start) & (hour <= h_end)
        if m_win.sum() == 0:
            continue
        idx = np.where(m_win)[0]
        entry = o[idx[0]]
        exit_ = c[idx[-1]]
        moves.append((exit_ - entry) / pip)
    moves = np.array(moves)
    if len(moves) == 0:
        return None
    mean = moves.mean()
    std = moves.std(ddof=1) if len(moves) > 1 else 0.0
    t = mean / (std / np.sqrt(len(moves))) if std > 0 else 0.0
    wr_long = (moves > 0).mean() * 100
    return dict(h_start=h_start, h_end=h_end, n=len(moves),
                mean_pip=round(mean, 1), t=round(t, 2),
                wr_long=round(wr_long, 1), wr_short=round(100 - wr_long, 1))


def main():
    for name in ['XAUUSD_M15', 'XAUUSD_M5']:
        path = os.path.join(ROOT, 'data', name + '.csv')
        df = pd.read_csv(path)
        df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
        is_nfp = first_friday_flag(df['dt'])
        print(f"\n{'='*70}\n{name}  |  NFP candles: {int(is_nfp.sum())}  "
              f"({len(np.unique(pd.DatetimeIndex(df['dt']).date[is_nfp]))} NFP days)")
        print('='*70)

        # پروفایلِ ساعتی
        prof = hourly_drift_profile(df, is_nfp)
        prof = prof.sort_values('diff', key=abs, ascending=False)
        print("\n-- Hourly NFP-vs-other drift (top |diff|, pip/candle) --")
        print(prof.head(10).to_string(index=False))

        # پنجره‌های کاندید (pre/post NFP release @12:30 UTC)
        print("\n-- Window drift on NFP days (open@Hs -> close@He) --")
        cand_windows = [
            (8, 12),   # pre-release London/US morning
            (10, 12),  # tight pre-release
            (13, 16),  # post-release US session
            (12, 15),  # release + immediate reaction
            (8, 16),   # whole NFP day
            (13, 20),  # post-release extended
        ]
        for hs, he in cand_windows:
            r = window_drift(df, is_nfp, hs, he)
            if r:
                print(f"  h{hs:02d}-h{he:02d}: n={r['n']:3d}  mean={r['mean_pip']:+7.1f}pip  "
                      f"t={r['t']:+5.2f}  WR_long={r['wr_long']:4.1f}%  WR_short={r['wr_short']:4.1f}%")


if __name__ == '__main__':
    main()
