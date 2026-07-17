"""
S74 — Visual/Geometric Pattern Confluence (کشفِ مخصوصِ User Note: «تکنیک‌های بصری»)
================================================================================
قانونِ شمارهٔ ۱ پروژه (تکرارِ الزامی در هر سند و کد): هدفِ پروژه **فقط و فقط «سودِ
خالصِ بیشتر»** است — نه Win-Rate. WR صرفاً یک عددِ گزارشی است؛ تعدادِ معامله و
Profit Factor هم هدف نیستند. **ما دنبالِ پول هستیم، نه آمارِ زیبا.**
تعریفِ فعلیِ «سودِ خالص» = مجموعِ سودِ خالصِ دو دارایی: XAUUSD + EURUSD.

--------------------------------------------------------------------------------
انگیزه (User Note — صحبتِ تریدر):
  تریدر گفت «من با چشمم شکلِ بازار را می‌فهمم» و به double-top، shooting-star،
  hammer، و الگوهای شکلیِ تکرارشونده اشاره کرد. هیچ استراتژیِ قبلیِ پروژه
  (S1..S73) این‌ها را نسنجیده بود.

کشفِ اکتشافی (explore_candle_patterns.py + explore_geometric_patterns.py):
  «چشمِ تریدر» بخشی درست است و بخشی توهم. داده نشان داد:
    ✅ لبهٔ نزولیِ واقعی و معنادار وجود دارد:
       • Double-Top: t تا -2.8 (M15 k=32) — دقیقاً همان که تریدر کشید.
       • bear_engulf: t=-3.6 (k=4), -3.8 (k=16).
       • shooting_star در رژیمِ TREND: t=-2.15 (k=4).
    ✅ لبهٔ صعودیِ ادامه‌ای:
       • Higher-High sequence: t=+3.7 (M15 k=32), +3.0 (H1 k=8).
    ❌ اما الگوهای «صعودیِ» کلاسیک (hammer/bull_engulf/pin_bull) در جهتِ صعودی
       لبه ندارند یا معکوس‌اند — توهمِ بصری.

طراحیِ استراتژی (بر پایهٔ فقط لبه‌های اثبات‌شده، نه ادبیاتِ خام):
  دو مکانیزمِ ناهمبسته که در زمان مکمل‌اند (مثلِ S36 Bull+Bear):
  ─────────────────────────────────────────────────────────────
  A) SHORT — «تلاقیِ نزولی» (Double-Top OR کندلِ نزولیِ قوی) با گیتِ رژیم.
     ورود Short وقتی:
       • یک Double-Top تازه تأیید شده (سقفِ دوقلو)، یا
       • bear_engulf/shooting_star در بالای یک swing (رد قیمت).
     TP/SL بر پایهٔ ATR (چون افقِ سودده k=8..32 است، حرکتِ بزرگ).
  B) LONG — «ادامهٔ Higher-High» (تنها لبهٔ صعودیِ اثبات‌شده).
     ورود Long وقتی یک higher-high تازه ساخته شود و مومنتومِ مثبت باشد.
  ─────────────────────────────────────────────────────────────
  همه با ورود در open کندلِ بعد (forward-safe)، سنجش با موتورِ سرمایه‌محورِ مشترک.

معیارِ سنجش: سودِ خالصِ سرمایه‌محور روی XAUUSD، و سپس افزودن به S73 (EURUSD) برای
سودِ خالصِ کل، و مقایسه با رکوردِ فعلی +44458$ (طلا S67 دست‌نخورده + یورو S73).

⚠️ توجه: این استراتژی موتورِ طلا (S67) را جایگزین نمی‌کند مگر سودِ بیشتری بسازد؛
اگر کمتر بود، به‌عنوانِ «مکانیزمِ مکمل/پرتفوی» یا «درسِ منفی» ثبت می‌شود.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from backtest import load_data, run_backtest
import indicators as ind
from capital_engine import run_capital_backtest
import warnings; warnings.filterwarnings('ignore')

# ---------------- پارامترها (از اکتشاف، محافظه‌کارانه) ----------------
PIVOT_LEFT = 4
PIVOT_RIGHT = 4
DT_GAP_MIN, DT_GAP_MAX = 8, 60        # فاصلهٔ دو قله
ATR_TP_MULT = 3.0                     # TP = 3×ATR (افقِ سودده بزرگ بود)
ATR_SL_MULT = 1.5                     # SL = 1.5×ATR → R:R ~2
MAX_HOLD = 48                         # ~12 ساعت M15
SPREAD = 0.20                         # اسپردِ XAUUSD


def build_context(df):
    df = df.copy()
    df['atr'] = ind.atr(df, 14)
    adx_val, _, _ = ind.adx(df, 14)
    df['adx'] = adx_val
    df['ema50'] = ind.ema(df['close'], 50)
    return df


def confirmed_pivots(df, left, right):
    h = df['high'].values; l = df['low'].values
    n = len(df)
    ph, pl = [], []
    for i in range(left, n - right):
        wh = h[i-left:i+right+1]; wl = l[i-left:i+right+1]
        if h[i] == wh.max() and (wh == h[i]).sum() == 1:
            ph.append((i, h[i], i + right))
        if l[i] == wl.min() and (wl == l[i]).sum() == 1:
            pl.append((i, l[i], i + right))
    return ph, pl


def candle_flags(df):
    o, h, l, c = df['open'].values, df['high'].values, df['low'].values, df['close'].values
    body = c - o; body_abs = np.abs(body)
    rng = np.maximum(h - l, 1e-9)
    up_wick = h - np.maximum(o, c); lo_wick = np.minimum(o, c) - l
    prev_body = np.zeros_like(body); prev_body[1:] = body[:-1]
    prev_o = np.zeros_like(o); prev_o[1:] = o[:-1]
    prev_c = np.zeros_like(c); prev_c[1:] = c[:-1]
    bear_engulf = (prev_body > 0) & (body < 0) & (c <= prev_o) & (o >= prev_c)
    shooting = (up_wick >= 2.0 * body_abs) & (lo_wick <= 0.5 * body_abs) & (body_abs > 0)
    return bear_engulf, shooting


def generate_signals(df):
    """آرایه‌های بولینِ ورودِ Short و Long (forward-safe: سیگنال روی کندلِ تأیید)."""
    n = len(df)
    short_entry = np.zeros(n, dtype=bool)
    long_entry = np.zeros(n, dtype=bool)
    ph, pl = confirmed_pivots(df, PIVOT_LEFT, PIVOT_RIGHT)
    atr = df['atr'].values
    close = df['close'].values
    ema50 = df['ema50'].values
    bear_engulf, shooting = candle_flags(df)

    # --- A) SHORT: Double-Top ---
    for a in range(len(ph) - 1):
        i1, p1, _ = ph[a]; i2, p2, cb2 = ph[a+1]
        gap = i2 - i1
        if not (DT_GAP_MIN <= gap <= DT_GAP_MAX):
            continue
        if cb2 >= n:
            continue
        tol = 0.5 * atr[i2] if atr[i2] > 0 else 0
        if abs(p1 - p2) <= tol:
            short_entry[cb2] = True

    # --- A) SHORT: کندلِ نزولیِ قوی نزدیکِ یک swing high، در رژیمِ روندی ---
    for i in range(n):
        if atr[i] <= 0:
            continue
        strong_bear = bear_engulf[i] or (shooting[i] and df['adx'].values[i] >= 25)
        below_context = close[i] < ema50[i] if not np.isnan(ema50[i]) else False
        if strong_bear and below_context:
            short_entry[i] = True

    # --- B) LONG: Higher-High sequence (ادامهٔ صعود) ---
    for a in range(1, len(ph)):
        ip, pp, _ = ph[a-1]; ic, pc, cb = ph[a]
        if cb >= n:
            continue
        if pc > pp and (ic - ip) <= 60:
            # فیلترِ مومنتوم: قیمت بالای EMA50 (روندِ صعودیِ زنده)
            if not np.isnan(ema50[cb]) and close[cb] > ema50[cb]:
                long_entry[cb] = True

    return short_entry, long_entry


def run_mechanism(df, entries, direction):
    """بک‌تستِ خام + سرمایه‌محور برای یک مکانیزم."""
    atr = df['atr'].values
    sl_series = ATR_SL_MULT * atr
    tp_series = ATR_TP_MULT * atr
    stats, tr = run_backtest(df, entries, None, None, direction,
                             spread=SPREAD, max_hold=MAX_HOLD,
                             allow_overlap=False,
                             sl_series=sl_series, tp_series=tp_series)
    if len(tr) == 0:
        return stats, tr, None
    # فاصلهٔ SL هر معامله (برای موتورِ سرمایه) = ATR_SL_MULT×atr روی کندلِ سیگنال
    sl_dist = ATR_SL_MULT * atr[tr['signal_bar'].values]
    cap_stats, eq = run_capital_backtest(tr, sl_dist, weights=None,
                                         initial_capital=10_000.0, risk_pct=1.0,
                                         commission_per_lot=7.0, compounding=False)
    return stats, tr, cap_stats


def main():
    print("=" * 78)
    print("  S74 — Visual/Geometric Pattern Confluence (XAUUSD M15)")
    print("=" * 78)
    df = load_data('data/XAUUSD_M15.csv')
    df = build_context(df)
    short_e, long_e = generate_signals(df)
    print(f"  سیگنال‌های Short: {short_e.sum()}   سیگنال‌های Long: {long_e.sum()}")

    # اجرای هر مکانیزم جدا
    print("\n  --- مکانیزمِ SHORT (Double-Top + کندلِ نزولی) ---")
    s_stats, s_tr, s_cap = run_mechanism(df, short_e, 'short')
    print(f"  raw: n={s_stats['n_trades']} WR={s_stats['win_rate']:.1f}% "
          f"exp={s_stats['expectancy']:.3f}$ totalPnL={s_stats['total_pnl']:.0f}$")
    if s_cap:
        print(f"  cap: netP={s_cap['net_profit']:+.0f}$ ({s_cap['return_pct']:+.1f}%) "
              f"WR={s_cap['win_rate']:.1f}% PF={s_cap['profit_factor']:.2f} "
              f"maxDD={s_cap['max_dd_pct']:.1f}% Sharpe={s_cap['sharpe']:.2f}")

    print("\n  --- مکانیزمِ LONG (Higher-High ادامه) ---")
    l_stats, l_tr, l_cap = run_mechanism(df, long_e, 'long')
    print(f"  raw: n={l_stats['n_trades']} WR={l_stats['win_rate']:.1f}% "
          f"exp={l_stats['expectancy']:.3f}$ totalPnL={l_stats['total_pnl']:.0f}$")
    if l_cap:
        print(f"  cap: netP={l_cap['net_profit']:+.0f}$ ({l_cap['return_pct']:+.1f}%) "
              f"WR={l_cap['win_rate']:.1f}% PF={l_cap['profit_factor']:.2f} "
              f"maxDD={l_cap['max_dd_pct']:.1f}% Sharpe={l_cap['sharpe']:.2f}")

    # --- پرتفویِ ترکیبی (هر دو مکانیزم روی یک سرمایه) ---
    print("\n  --- پرتفویِ ترکیبی (Short + Long روی یک equity) ---")
    all_tr = pd.concat([t for t in [s_tr, l_tr] if t is not None and len(t)], ignore_index=True)
    if len(all_tr):
        all_tr = all_tr.sort_values('exit_bar').reset_index(drop=True)
        atr = df['atr'].values
        sl_dist = ATR_SL_MULT * atr[all_tr['signal_bar'].values]
        p_cap, eq = run_capital_backtest(all_tr, sl_dist, weights=None,
                                         initial_capital=10_000.0, risk_pct=1.0,
                                         commission_per_lot=7.0, compounding=False)
        print(f"  cap: netP={p_cap['net_profit']:+.0f}$ ({p_cap['return_pct']:+.1f}%) "
              f"n={p_cap['n_trades']} WR={p_cap['win_rate']:.1f}% "
              f"PF={p_cap['profit_factor']:.2f} maxDD={p_cap['max_dd_pct']:.1f}% "
              f"Sharpe={p_cap['sharpe']:.2f}")
        # آزمونِ دو-نیمه
        mid = len(df) // 2
        for half, lbl in [(all_tr[all_tr['signal_bar'] < mid], 'H1'),
                           (all_tr[all_tr['signal_bar'] >= mid], 'H2')]:
            if len(half):
                sd = ATR_SL_MULT * atr[half['signal_bar'].values]
                hc, _ = run_capital_backtest(half.reset_index(drop=True), sd,
                                             initial_capital=10_000.0, risk_pct=1.0,
                                             commission_per_lot=7.0, compounding=False)
                print(f"    {lbl}: netP={hc['net_profit']:+.0f}$ n={hc['n_trades']} "
                      f"WR={hc['win_rate']:.1f}%")
        return p_cap
    return None


if __name__ == '__main__':
    main()
