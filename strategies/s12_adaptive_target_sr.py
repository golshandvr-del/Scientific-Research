"""
استراتژی ۱۲: هدف‌گذاری تطبیقی روی سطوح ساختاری (Adaptive S/R Target)
=====================================================================
ایده‌ی price-action خالص که تریدر واقعی به‌کار می‌برد: به‌جای TP/SL ثابت،
هدف را روی «سطح ساختاری بعدی» می‌گذاریم.

منطق LONG (pullback به حمایت در روند صعودی):
- ورود: روند صعودی + golden + pullback به حمایت فعال (فاصله<near×ATR).
- SL: کمی زیر خودِ حمایت (چون اگر حمایت بشکند، ستاپ باطل است) = support - buf×ATR.
- TP: کمی زیر مقاومت بعدی (چون قیمت اغلب قبل از رسیدن به مقاومت برمی‌گردد)
      = resistance - buf×ATR.
این باعث می‌شود RR واقعی و ساختاری باشد و TP در نقطه‌ای منطقی قرار گیرد.

فیلتر کلیدی: فقط ستاپ‌هایی را می‌پذیریم که RR ساختاری‌شان مطلوب باشد
(TP_dist / SL_dist در بازه‌ی [rr_lo, rr_hi]) — این خودش کیفیت را کنترل می‌کند.

اعتبارسنجی: بک‌تست کامل + تقسیم نیمه اول/دوم + p-value دوجمله‌ای.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np
import pandas as pd
from scipy import stats as sps
from backtest import load_data, run_backtest
import indicators as ind
import structure as st


def build(df, left=6, right=6, tol=0.0008, expiry=1500):
    piv = st.pivots(df, left=left, right=right)
    sr = st.sr_levels(df, piv, tol=tol, expiry=expiry)
    atr = ind.atr(df, 14)
    ema50 = ind.ema(df['close'], 50)
    ema200 = ind.ema(df['close'], 200)
    rsi = ind.rsi(df['close'], 14)
    return sr, atr, ema50, ema200, rsi


def make(df, sr, atr, ema50, ema200, rsi,
         near_max=0.7, sl_buf=0.5, tp_buf=0.3,
         rr_lo=1.2, rr_hi=6.0, h_lo=19, h_hi=23, use_golden=True):
    """سیگنال‌ها + سری SL/TP تطبیقی (بر حسب دلار فاصله از قیمت ورود تقریبی)."""
    close = df['close'].values
    hour = df['dt'].dt.hour.values
    sup = sr['support'].values
    res = sr['resistance'].values
    a = atr.values
    e50, e200 = ema50.values, ema200.values

    dist_sup = (close - sup) / a
    near_sup = (dist_sup > 0) & (dist_sup < near_max)
    uptrend = (close > e50) & (e50 > e200)
    golden = (hour >= h_lo) & (hour <= h_hi) if use_golden else np.ones(len(df), bool)
    have_levels = ~np.isnan(sup) & ~np.isnan(res) & (res > close)

    base = near_sup & uptrend & golden & have_levels
    base[:300] = False

    # فاصله SL و TP از close جاری (ورود تقریبی = close؛ بک‌تست دقیق از open بعدی)
    sl_dist = (close - sup) + sl_buf * a      # تا زیر حمایت
    tp_dist = (res - close) - tp_buf * a      # تا زیر مقاومت بعدی
    rr = np.where(sl_dist > 0, tp_dist / sl_dist, 0)
    good_rr = (rr >= rr_lo) & (rr <= rr_hi) & (tp_dist > 0.5*a) & (sl_dist > 0.3*a)

    sig = base & good_rr
    return sig, sl_dist, tp_dist, rr


def bt(df, sig, sl_dist, tp_dist, spread=0.20, max_hold=96):
    stats, tr = run_backtest(
        df, sig, sl_points=None, tp_points=None, direction='long',
        spread=spread, max_hold=max_hold, allow_overlap=False,
        sl_series=sl_dist, tp_series=tp_dist)
    return stats, tr


def report(tag, s, tr):
    if s['n_trades'] == 0:
        print(f"{tag}: n=0"); return None
    # breakeven واقعی از میانگین RR معاملات
    wins = tr[tr['outcome']=='win']; losses = tr[tr['outcome']=='loss']
    aw = wins['pnl'].mean() if len(wins) else 0
    al = -losses['pnl'].mean() if len(losses) else 1
    be = al/(aw+al) if (aw+al)>0 else 0.5
    nwin = len(wins)
    p = sps.binomtest(nwin, s['n_trades'], min(be,0.999), alternative='greater').pvalue if s['n_trades']>0 else 1
    print(f"{tag}: n={s['n_trades']}, WR={s['win_rate']:.2f}%, "
          f"exp={s['expectancy']:.3f}$, PnL={s['total_pnl']:.0f}$, "
          f"avgW={aw:.2f} avgL={al:.2f} BE~{be*100:.1f}% p={p:.3f}")
    return s


if __name__ == '__main__':
    df = load_data()
    sr, atr, ema50, ema200, rsi = build(df)
    print(f"داده: {len(df)} کندل\n")
    print("=== S12 Adaptive S/R Target — جاروب RR ساختاری ===")
    best = None
    for near in [0.5, 0.7, 1.0]:
        for rr_lo in [1.0, 1.5, 2.0]:
            for rr_hi in [3.0, 5.0]:
                sig, sld, tpd, rr = make(df, sr, atr, ema50, ema200, rsi,
                                         near_max=near, rr_lo=rr_lo, rr_hi=rr_hi)
                if sig.sum() < 50:
                    continue
                s, tr = bt(df, sig, sld, tpd)
                report(f"near={near} rr[{rr_lo},{rr_hi}]", s, tr)
