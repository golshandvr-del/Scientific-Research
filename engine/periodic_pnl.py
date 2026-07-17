"""
periodic_pnl.py — تحلیلِ «سودِ خالصِ روزانه / هفتگی / ماهانه» (پاسخ به User Note)
================================================================================
قانونِ شمارهٔ ۱ پروژه (تکرارِ الزامی): هدفِ پروژه **فقط و فقط «سودِ خالصِ بیشتر»**
است — نه Win-Rate. تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز XAUUSD + EURUSD.
WR صرفاً یک عددِ گزارشی است.

------------------------------------------------------------------------------
انگیزه (User Note):
  «تا الان فقط یک عددِ سودِ خالصِ کل داشتیم. حالا می‌خواهم تست‌ها را طوری گسترش
   بدهی که سودِ خالصِ روزانه / هفتگی / ماهانه هم حساب شود. سپس استراتژیِ برندهٔ
   فعلی را در این تست ببینی: آیا همیشه سودِ خالصِ روزانه/هفتگی/ماهانه مثبت است؟»

این ماژول یک تابعِ عمومی می‌دهد که ورودی‌اش «رویدادهای سود/زیانِ دلاریِ زمان‌دار»
است (هر رویداد = یک معاملهٔ بسته‌شده با: زمانِ بسته‌شدن + سود/زیانِ دلاریِ خالص)
و خروجی‌اش تجمیعِ سود به سطل‌های روزانه/هفتگی/ماهانه + آماری از «نسبتِ دوره‌های
مثبت» است.

نکتهٔ روش‌شناختی مهم:
  سود در سطلِ زمانی بر اساسِ **زمانِ بسته‌شدنِ معامله** (exit time) تجمیع می‌شود،
  چون سود/زیان در همان لحظه realize می‌شود. این با منحنیِ equity سازگار است.
"""
import numpy as np
import pandas as pd


def build_pnl_events(trades, pnl_col, time_col, df=None, bar_index_col=None):
    """
    یک DataFrame از رویدادهای سود/زیانِ زمان‌دار می‌سازد.

    دو حالت پشتیبانی می‌شود:
      1) trades ستونِ زمانِ واقعی دارد (time_col یک datetime/unix است).
      2) trades فقط ایندکسِ کندل دارد (bar_index_col)، و df ستونِ 'time' (unix) دارد
         → زمان از df استخراج می‌شود.

    خروجی: DataFrame با ستون‌های ['dt', 'pnl'] مرتب‌شده بر اساسِ زمان.
    """
    t = trades.copy().reset_index(drop=True)
    if bar_index_col is not None and df is not None:
        idx = t[bar_index_col].astype(int).values
        idx = np.clip(idx, 0, len(df) - 1)
        unix = df['time'].values[idx]
        dt = pd.to_datetime(unix, unit='s', utc=True)
    else:
        col = t[time_col]
        if np.issubdtype(col.dtype, np.number):
            dt = pd.to_datetime(col, unit='s', utc=True)
        else:
            dt = pd.to_datetime(col, utc=True)
    out = pd.DataFrame({'dt': dt, 'pnl': t[pnl_col].astype(float).values})
    out = out.sort_values('dt').reset_index(drop=True)
    return out


def periodic_summary(events, label=''):
    """
    events: DataFrame با ['dt', 'pnl'] (خروجیِ build_pnl_events).
    سودِ خالص را روی سطل‌های روزانه/هفتگی/ماهانه تجمیع و آمار می‌دهد.
    """
    if len(events) == 0:
        return None
    ev = events.copy()
    ev = ev.set_index('dt')

    periods = {
        'روزانه (D)': ('D', 'روز'),
        'هفتگی (W)': ('W-MON', 'هفته'),
        'ماهانه (M)': ('ME', 'ماه'),
    }
    result = {'label': label, 'total_net': float(ev['pnl'].sum()),
              'n_trades': int(len(ev)), 'periods': {}}

    for name, (freq, unit) in periods.items():
        try:
            g = ev['pnl'].resample(freq).sum()
        except Exception:
            g = ev['pnl'].resample(freq.replace('ME', 'M')).sum()
        # فقط دوره‌هایی که حداقل یک معامله داشتند (سطل‌های خالی را کنار می‌گذاریم)
        counts = ev['pnl'].resample(freq if 'ME' not in freq else 'ME').count() \
            if False else None
        active = g[g != 0.0]
        # برای شمارشِ دقیق دوره‌های دارای معامله، از count استفاده می‌کنیم:
        cnt = ev['pnl'].resample(freq if freq != 'ME' else 'ME').count()
        g_active = g[cnt > 0]
        n_periods = int((cnt > 0).sum())
        if n_periods == 0:
            continue
        n_pos = int((g_active > 0).sum())
        n_neg = int((g_active < 0).sum())
        n_flat = int((g_active == 0).sum())
        result['periods'][name] = {
            'unit': unit,
            'n_periods': n_periods,
            'n_positive': n_pos,
            'n_negative': n_neg,
            'n_flat': n_flat,
            'pct_positive': 100.0 * n_pos / n_periods,
            'best': float(g_active.max()),
            'worst': float(g_active.min()),
            'mean': float(g_active.mean()),
            'median': float(g_active.median()),
            'std': float(g_active.std()),
            'series': g_active,
        }
    return result


def print_periodic_report(result):
    """چاپِ گزارشِ خوانا از خروجیِ periodic_summary."""
    if result is None:
        print('  (هیچ رویدادِ سود/زیانی برای تحلیل نبود.)')
        return
    print('=' * 86)
    print(f'  تحلیلِ سودِ خالصِ دوره‌ای — {result["label"]}')
    print('=' * 86)
    print(f'  سودِ خالصِ کل: {result["total_net"]:+,.1f}$   |   تعدادِ معاملات: {result["n_trades"]}')
    print()
    hdr = f'  {"دوره":<14}{"#دوره":>7}{"مثبت":>7}{"منفی":>7}{"%مثبت":>8}{"بهترین$":>12}{"بدترین$":>12}{"میانگین$":>11}'
    print(hdr)
    print('  ' + '-' * 82)
    for name, p in result['periods'].items():
        print(f'  {name:<14}{p["n_periods"]:>7}{p["n_positive"]:>7}{p["n_negative"]:>7}'
              f'{p["pct_positive"]:>7.1f}%{p["best"]:>12,.0f}{p["worst"]:>12,.0f}{p["mean"]:>11,.1f}')
    print('=' * 86)


def worst_streak(series):
    """طولانی‌ترین دنبالهٔ متوالیِ دوره‌های منفی (drawdown دوره‌ای) و بدترین جمعِ متوالی."""
    vals = series.values
    max_neg_streak = 0; cur = 0
    worst_sum = 0.0; cur_sum = 0.0
    for v in vals:
        if v < 0:
            cur += 1; cur_sum += v
        else:
            max_neg_streak = max(max_neg_streak, cur)
            cur = 0
            worst_sum = min(worst_sum, cur_sum)
            cur_sum = 0.0
    max_neg_streak = max(max_neg_streak, cur)
    worst_sum = min(worst_sum, cur_sum)
    return max_neg_streak, worst_sum
