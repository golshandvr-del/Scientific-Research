"""
موتور بک‌تست با «مدیریت پویای معامله» (Dynamic Trade Management) — طرح P26 نقشه‌راه.

پاسخ مستقیم به User Note جدید کاربر:
  «به‌جای TP/SL ثابت، ربات SL را با افزایش سود جابه‌جا کند (بریک‌ایون سپس تریلینگ)،
   و بخشی از معامله را زودتر ببندد (scale-out) تا سود قفل شود.»

معیار «برد» در این موتور دیگر شمارشی نیست؛ بلکه **PnL دلاری هر معامله** است. و
سنجهٔ نهاییِ کاربر، **سود خالص روزانه (daily net PnL)** است (نه WR شمارشی).

--- شبیه‌سازی کندل‌به‌کندل (بدون look-ahead) ---
هر معامله در open کندل بعدِ سیگنال باز می‌شود (مثل موتور استاندارد). سپس برای هر
کندلِ بعد، مسیر قیمت به‌ترتیبِ زیر و به‌صورت «بدترین حالت اول» بررسی می‌شود:

  1. اگر SL جاری لمس شود → آن بخشِ باقی‌ماندهٔ پوزیشن با SL بسته می‌شود (خروج).
     (ابهامِ لمسِ هم‌زمانِ SL و TP1 در یک کندل ⇒ محافظه‌کارانه: اول SL.)
  2. اگر هنوز scale-out نشده و TP1 لمس شود → نیمی (یا کسرِ `scale_frac`) از پوزیشن
     در TP1 بسته می‌شود و SL به بریک‌ایون (قیمت ورود) منتقل می‌شود.
  3. پس از scale-out، برای نیمهٔ باقی‌مانده یک **تریلینگ‌استاپ ATR** فعال می‌شود:
     SL = بیشترین(SL فعلی، extreme قیمت مطلوب − trail_mult·ATR). این SL فقط در جهت
     سود حرکت می‌کند (هرگز به عقب برنمی‌گردد).
  4. اگر تا max_hold کندل هیچ‌کدام رخ نداد → با close آخرین کندل بسته می‌شود.

PnL هر معامله = مجموع PnL نیمه‌ها (هرکدام با قیمت خروج و کسرِ حجمِ خودش)، منهای اسپرد.
همه بر حسب دلار روی «۱ واحد کاملِ اولیه» (نرمال‌شده) گزارش می‌شود؛ scale_frac حجمِ
بستهٔ زودهنگام است (مثلاً 0.5).
"""
import numpy as np
import pandas as pd
from numba import njit


@njit(cache=True)
def _sim_dynamic(o, h, l, c, sig_idx, entry_bars,
                 sl_dist, tp1_dist, atr_arr,
                 is_long, spread, scale_frac, trail_mult, be_offset, max_hold):
    """
    شبیه‌سازیِ عددیِ سریع (numba). خروجی: آرایه‌ی PnL دلاری هر معامله + exit_bar.
    sl_dist/tp1_dist: فاصلهٔ اولیهٔ SL و TP1 بر حسب دلار (هم‌طول sig_idx).
    scale_frac: کسرِ پوزیشن که در TP1 بسته می‌شود (0..1). بقیه تریلینگ می‌شود.
    trail_mult: ضریب ATR برای تریلینگ نیمهٔ دوم.
    be_offset : افستِ بریک‌ایون بر حسب دلار (SL کمی بالای/زیرِ ورود برای پوششِ اسپرد).
    """
    m = len(sig_idx)
    n = len(c)
    pnl = np.zeros(m)
    exit_bar_out = np.zeros(m, dtype=np.int64)
    r_mult = np.zeros(m)  # PnL بر حسب R (نسبت به ریسک اولیه = sl_dist)

    for k in range(m):
        eb = entry_bars[k]
        if eb >= n:
            exit_bar_out[k] = -1
            continue
        entry = o[eb]
        if is_long:
            fill = entry + spread
        else:
            fill = entry - spread

        risk = sl_dist[k]
        if risk <= 0:
            exit_bar_out[k] = -1
            continue

        # سطوح اولیه
        if is_long:
            sl = fill - sl_dist[k]
            tp1 = fill + tp1_dist[k]
        else:
            sl = fill + sl_dist[k]
            tp1 = fill - tp1_dist[k]

        scaled = False           # آیا نیمهٔ اول در TP1 بسته شده؟
        remaining = 1.0          # حجم باقی‌مانده (نرمال‌شده)
        realized = 0.0           # PnL دلاریِ قفل‌شده تا کنون
        best = fill              # بهترین قیمتِ مطلوب دیده‌شده (برای تریلینگ)

        end = eb + max_hold
        if end > n:
            end = n

        closed = False
        j = eb
        while j < end:
            hi = h[j]; lo = l[j]
            a = atr_arr[sig_idx[k]]
            if a != a:  # NaN
                a = risk  # پشتیبان

            # به‌روزرسانی بهترین قیمت مطلوب
            if is_long:
                if hi > best:
                    best = hi
            else:
                if lo < best:
                    best = lo

            # --- ۱) بررسی SL (بدترین حالت اول) ---
            if is_long:
                hit_sl = lo <= sl
            else:
                hit_sl = hi >= sl
            if hit_sl:
                # کل باقی‌مانده با SL بسته می‌شود
                if is_long:
                    part = (sl - fill) * remaining
                else:
                    part = (fill - sl) * remaining
                realized += part
                closed = True
                exit_bar_out[k] = j
                break

            # --- ۲) scale-out در TP1 (فقط یک‌بار) ---
            if not scaled:
                if is_long:
                    hit_tp1 = hi >= tp1
                else:
                    hit_tp1 = lo <= tp1
                if hit_tp1:
                    if is_long:
                        part = (tp1 - fill) * scale_frac
                    else:
                        part = (fill - tp1) * scale_frac
                    realized += part
                    remaining -= scale_frac
                    scaled = True
                    # SL → بریک‌ایون (با افستِ کوچک به نفعِ معامله)
                    if is_long:
                        sl = fill + be_offset
                    else:
                        sl = fill - be_offset
                    # اگر چیزی باقی نمانده، تمام
                    if remaining <= 1e-9:
                        closed = True
                        exit_bar_out[k] = j
                        break

            # --- ۳) تریلینگِ ATR برای نیمهٔ باقی‌مانده (پس از scale) ---
            if scaled:
                if is_long:
                    new_sl = best - trail_mult * a
                    if new_sl > sl:
                        sl = new_sl
                else:
                    new_sl = best + trail_mult * a
                    if new_sl < sl:
                        sl = new_sl

            j += 1

        if not closed:
            # بستن با close آخرین کندل بازه
            jx = end - 1
            if jx < eb:
                jx = eb
            px = c[jx]
            if is_long:
                part = (px - fill) * remaining
            else:
                part = (fill - px) * remaining
            realized += part
            exit_bar_out[k] = jx

        pnl[k] = realized
        r_mult[k] = realized / risk

    return pnl, exit_bar_out, r_mult


def run_dynamic_backtest(df, entries, direction, atr,
                         sl_mult=1.5, tp1_mult=1.0,
                         scale_frac=0.5, trail_mult=1.5, be_offset=0.15,
                         spread=0.20, max_hold=200, allow_overlap=False):
    """
    df       : دیتافریم open/high/low/close/dt
    entries  : بولین هم‌طول df؛ True = سیگنال (ورود در open کندل بعد)
    direction: 'long' یا 'short'
    atr      : سری ATR هم‌طول df (برای فاصله‌ها و تریلینگ)
    sl_mult/tp1_mult: ضرایب ATR برای SL و TP1 اولیه
    scale_frac: کسری از پوزیشن که در TP1 بسته می‌شود
    trail_mult: ضریب ATR تریلینگ برای باقی‌مانده
    be_offset : افست بریک‌ایون (دلار)

    خروجی: (stats, trades_df)
    """
    o = df['open'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    atr_arr = atr.values.astype(np.float64)
    n = len(df)

    entries = np.asarray(entries, dtype=bool)
    sig_all = np.where(entries)[0]

    # اعمال no-overlap: با شبیه‌سازی سریال (busy_until) — نیازمند exit_bar، پس
    # ابتدا بدون overlap فیلتر تقریبی نمی‌کنیم؛ در عوض دو-پاسه عمل می‌کنیم:
    # پاس اول همهٔ سیگنال‌ها را با entry=si+1 شبیه‌سازی کن، سپس اگر no-overlap،
    # به‌ترتیب زمانی معاملاتِ هم‌پوشان را حذف کن.
    entry_bars = sig_all + 1
    sl_dist = sl_mult * atr_arr[sig_all]
    tp1_dist = tp1_mult * atr_arr[sig_all]

    is_long = (direction == 'long')
    pnl, exit_bars, r_mult = _sim_dynamic(
        o, h, l, c, sig_all.astype(np.int64), entry_bars.astype(np.int64),
        sl_dist, tp1_dist, atr_arr, is_long, spread,
        scale_frac, trail_mult, be_offset, max_hold)

    rows = []
    busy_until = -1
    for idx in range(len(sig_all)):
        si = sig_all[idx]
        eb = entry_bars[idx]
        xb = exit_bars[idx]
        if xb < 0 or eb >= n:
            continue
        if not allow_overlap and eb <= busy_until:
            continue
        busy_until = xb
        rows.append({
            'signal_bar': int(si),
            'entry_bar': int(eb),
            'exit_bar': int(xb),
            'dt': df['dt'].values[eb],
            'direction': direction,
            'pnl': pnl[idx],
            'r_mult': r_mult[idx],
            'outcome': 'win' if pnl[idx] > 0 else 'loss',
            'bars_held': int(xb - eb),
        })

    tr = pd.DataFrame(rows)
    if len(tr) == 0:
        return {'n_trades': 0, 'win_rate': 0.0, 'total_pnl': 0.0,
                'expectancy': 0.0, 'profit_factor': 0.0}, tr

    wins = tr[tr['pnl'] > 0]
    losses = tr[tr['pnl'] <= 0]
    gross_win = wins['pnl'].sum()
    gross_loss = -losses['pnl'].sum()
    stats = {
        'n_trades': len(tr),
        'win_rate': len(wins) / len(tr) * 100,
        'total_pnl': tr['pnl'].sum(),
        'expectancy': tr['pnl'].mean(),
        'avg_win': wins['pnl'].mean() if len(wins) else 0.0,
        'avg_loss': losses['pnl'].mean() if len(losses) else 0.0,
        'profit_factor': (gross_win / gross_loss) if gross_loss > 1e-9 else np.inf,
        'avg_bars_held': tr['bars_held'].mean(),
        'avg_r': tr['r_mult'].mean(),
    }
    return stats, tr


def daily_pnl_stats(trades_df):
    """
    سنجهٔ اصلیِ User Note: سود خالصِ روزانه.
    برای هر روزِ تقویمی، مجموع PnL معاملاتِ آن روز محاسبه و آماره‌ها گزارش می‌شود:
      - نسبت روزهای سودده (daily win rate واقعیِ کاربر)
      - میانگین سود خالصِ روزانه، انحراف معیار، Sharpe روزانه
      - profit factor روزانه (مجموع روزهای مثبت / |مجموع روزهای منفی|)
    """
    if len(trades_df) == 0:
        return {}
    tr = trades_df.copy()
    tr['day'] = pd.to_datetime(tr['dt']).dt.date
    daily = tr.groupby('day')['pnl'].agg(['sum', 'count'])
    pos_days = daily[daily['sum'] > 0]
    neg_days = daily[daily['sum'] < 0]
    gross_pos = pos_days['sum'].sum()
    gross_neg = -neg_days['sum'].sum()
    n_days = len(daily)
    total_days_span = (tr['day'].max() - tr['day'].min()).days + 1
    return {
        'n_active_days': n_days,
        'calendar_days': total_days_span,
        'daily_win_rate': len(pos_days) / n_days * 100 if n_days else 0.0,
        'avg_daily_pnl': daily['sum'].mean(),
        'std_daily_pnl': daily['sum'].std(),
        'daily_sharpe': (daily['sum'].mean() / (daily['sum'].std() + 1e-12)),
        'daily_profit_factor': (gross_pos / gross_neg) if gross_neg > 1e-9 else np.inf,
        'trades_per_active_day': daily['count'].mean(),
        'trades_per_calendar_day': len(tr) / total_days_span if total_days_span else 0.0,
    }
