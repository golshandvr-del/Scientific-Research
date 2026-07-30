# -*- coding: utf-8 -*-
"""
S346 — موتورِ سریعِ سدِ دوطرفه (vectorized barrier engine) برای اکتشافِ فضای بزرگ
================================================================================
چرا؟ برای پاسخ به «قانونِ بی‌نهایت بهبود» باید بتوانیم **هزاران** ترکیبِ
(هندسه × SL/TP × چند فیلترِ همزمان) را بسنجیم. `scalp_engine.simulate_trades`
حلقهٔ پایتونی روی هر معامله دارد (دقیق ولی کند). این ماژول همان قواعد را
**برداری روی همهٔ رویدادها به‌طورِ همزمان** اجرا می‌کند:

  • ورود در `open` کندلِ بعد از سیگنال + اسلیپیجِ ورود (بدترین جهت).
  • بررسیِ لمسِ SL/TP در هر کندل؛ **ابهامِ هم‌کندلی ⇒ باختِ SL** (همان قاعدهٔ موتورِ اصلی).
  • خروجِ زمانی با `close` کندلِ آخر پس از max_hold.
  • هزینه: `pnl_pip = Δprice/pip − spread` و اسلیپیجِ دو طرف در fill/exit_fill.
  • برچسبِ برد/باخت بر اساسِ **سود/زیانِ واقعی** (همان اصلاحِ s117/s118 موتور).

تفاوتِ عمدی: این موتور `allow_overlap=True` است (همهٔ رویدادها را می‌سنجد) تا
آمارِ شرطیِ بی‌سوگیری بدهد. **داوریِ نهایی و RQS+ همیشه با موتورِ اصلی
(`simulate_trades` با `allow_overlap=False`) انجام می‌شود** — این ماژول فقط اکتشاف است.
تستِ برابری در `s346_parity_fast.py`.
"""
import numpy as np


def barrier_outcomes(df, sig_idx, is_long, sl_dist, tp_dist, max_hold,
                     pip, spread_pip, slip_pip):
    """
    sig_idx : اندیس‌های کندلِ سیگنال (ورود در sig_idx+1)
    is_long : آرایهٔ بولین هم‌طولِ sig_idx
    sl_dist, tp_dist : فاصله بر حسبِ **قیمت** (نه pip)، هم‌طولِ sig_idx
    خروجی: dict(pnl_pip, win, exit_off, entry_bar)
    """
    o = df['open'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    n = len(o)

    sig_idx = np.asarray(sig_idx, dtype=np.int64)
    keep = (sig_idx + 1 + max_hold) < n
    sig_idx = sig_idx[keep]
    is_long = np.asarray(is_long, dtype=bool)[keep]
    sl_dist = np.asarray(sl_dist, dtype=np.float64)[keep]
    tp_dist = np.asarray(tp_dist, dtype=np.float64)[keep]

    eb = sig_idx + 1
    sgn = np.where(is_long, 1.0, -1.0)
    fill = o[eb] + sgn * slip_pip * pip           # ورود بدتر
    sl_price = fill - sgn * sl_dist
    tp_price = fill + sgn * tp_dist

    m = len(eb)
    done = np.zeros(m, dtype=bool)
    exit_price = np.full(m, np.nan)
    exit_off = np.full(m, max_hold - 1, dtype=np.int64)
    hit_tp_flag = np.zeros(m, dtype=bool)

    for j in range(max_hold):
        idx = eb + j
        hi = h[idx]
        lo = l[idx]
        hit_sl = np.where(is_long, lo <= sl_price, hi >= sl_price)
        hit_tp = np.where(is_long, hi >= tp_price, lo <= tp_price)
        # ابهام (هر دو در یک کندل) ⇒ SL (بدترین حالت)
        new_sl = (~done) & hit_sl
        new_tp = (~done) & hit_tp & (~hit_sl)
        exit_price[new_sl] = sl_price[new_sl]
        exit_price[new_tp] = tp_price[new_tp]
        exit_off[new_sl | new_tp] = j
        hit_tp_flag[new_tp] = True
        done |= (new_sl | new_tp)
        if done.all():
            break

    # خروجِ زمانی
    rest = ~done
    if rest.any():
        exit_price[rest] = c[eb[rest] + max_hold - 1]
        exit_off[rest] = max_hold - 1

    exit_fill = exit_price - sgn * slip_pip * pip
    pnl_pip = sgn * (exit_fill - fill) / pip - spread_pip
    win = pnl_pip > 0
    return dict(pnl_pip=pnl_pip, win=win, exit_off=exit_off, entry_bar=eb,
                sig_idx=sig_idx, is_long=is_long, hit_tp=hit_tp_flag,
                sl_pip=sl_dist / pip, tp_pip=tp_dist / pip)


def stats(pnl_pip, win, cost_pip):
    """آمارِ سریعِ pip-محور (بدونِ لایهٔ سرمایه)."""
    n = len(pnl_pip)
    if n == 0:
        return dict(n=0, wr=0.0, exp=0.0, pf=0.0, gross_win=0.0, gross_loss=0.0)
    gw = pnl_pip[pnl_pip > 0].sum()
    gl = -pnl_pip[pnl_pip <= 0].sum()
    return dict(n=int(n), wr=float(win.mean() * 100),
                exp=float(pnl_pip.mean()),
                pf=float(gw / gl) if gl > 0 else 999.0,
                gross_win=float(gw), gross_loss=float(gl))
