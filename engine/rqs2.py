# -*- coding: utf-8 -*-
"""
RQS2 — معیارِ رسمیِ نسلِ دومِ پذیرشِ لایه‌ها
================================================================================
سندِ مرجع: `docs/RQS2_SPEC.md`

RQS+ (`engine/rqs.py`) دست‌نخورده می‌ماند تا نتایجِ تاریخی بازتولیدپذیر بمانند.
**معیارِ پذیرشِ لایه‌های جدید از این پس RQS2 است.**

تفاوتِ بنیادی با RQS+
---------------------
RQS+ لبه را نسبت به **نقطهٔ صفرِ نظری** `SL/(SL+TP)` می‌سنجید که تنها تحتِ
فرضِ «گشتِ تصادفیِ بی‌رانش و بی‌هزینه» درست است. RQS2 لبه را نسبت به
**نقطهٔ صفرِ اندازه‌گیری‌شده** می‌سنجد: همان براکت روی همان داده، یک‌بار
بدونِ هیچ سیگنالی و یک‌بار با زمان‌بندیِ جای‌گشت‌شده.

اصلِ حاکم
---------
    «نبودِ آزمونِ کنترل، شاهدِ وجودِ مهارت نیست.»

هر دروازه‌ای که دادهٔ لازمش موجود نباشد `None` (=UNKNOWN) می‌شود و حکمِ کل
`INCOMPLETE` است — **هرگز** `ACCEPT`. این سومین حکم، حفرهٔ اصلیِ RQS+ را
می‌بندد: در RQS+ «کنترل اجرا نشده» و «کنترل پاس شده» یک عدد می‌گرفتند.

ده دروازه
---------
  H0 کفایتِ نمونه و استقلال      H5 بقا در آزمونِ چندگانه
  H1 کیفیتِ خام                  H6 پایداریِ تقویمی
  H2 لبهٔ هندسیِ هزینه‌دار        H7 خارج از نمونه
  H3 ⭐ مهارت نسبت به مدلِ صفر    H8 ریسکِ دنباله و بازیافت
  H4 مهارتِ هر سمت               H9 مقاومتِ هزینه
"""
import numpy as np
import pandas as pd
from math import comb, erfc, sqrt

from engine import scalp_engine as se

# ============================ آستانه‌های رسمیِ RQS2 ============================
# H0 — کفایتِ نمونه و استقلال
N_FLOOR          = 30       # حداقلِ کلِ معاملات
N_SIDE_FLOOR     = 15       # حداقلِ معاملاتِ هر سمت (اگر لایه دوسویه است)
MAX_CONCURRENCY  = 1        # معاملاتِ هم‌پوشان ⇒ p-valueِ دوجمله‌ای نامعتبر

# H1 — کیفیتِ خام
WR_FLOOR         = 60.0
PF_MIN           = 1.3

# H2 — لبهٔ هندسیِ هزینه‌دار (ضدِ تقلبِ اشتباهِ رایجِ #۸)
WR_EXCESS_MIN    = 3.0      # درصد، نسبت به سربه‌سرِ **هزینه‌دار**
RR_MIN           = 0.5      # TP/SL — سپرِ صریحِ «TP کوچک ⇒ WR جعلی»

# H3 — ⭐ مهارت نسبت به مدلِ صفرِ اندازه‌گیری‌شده
SKILL_LIFT_MIN   = 4.0      # pp، نسبت به قوی‌ترین خطِ مبنا
SKILL_Z_MIN      = 3.0      # سیگما، نسبت به sdِ جای‌گشت
PERM_K_MIN       = 10       # حداقل تعدادِ جای‌گشت برای معنادار بودنِ sd

# H4 — مهارتِ هر سمت (هیچ سمتی سوارِ رانش نشود)
SIDE_LIFT_MIN    = 2.0      # pp

# H5 — بقا در آزمونِ چندگانه
P_ADJ_MAX        = 0.05

# H6 — پایداریِ تقویمی
CAL_WINDOWS      = 4
CAL_POS_MIN      = 3        # حداقل تعدادِ بازهٔ تقویمیِ سودده
CAL_OCCUPIED_MIN = 3        # حداقل تعدادِ بازهٔ دارای معامله (ضدِ خوشه‌ای‌شدن)
CAL_WORST_FRAC   = 0.25     # زیانِ بدترین بازه ≤ ۲۵٪ نتِ کل

# H7 — خارج از نمونه
OOS_N_FLOOR      = 15
OOS_WR_FLOOR     = 57.0     # کف با تحملِ ۳pp
OOS_PF_MIN       = 1.2

# H8 — ریسکِ دنباله و بازیافت
MAXDD_MAX_PCT    = 8.0
MCL_MAX          = 8
RECOVERY_MIN     = 3.0      # net / |maxDD$|

# H9 — مقاومتِ هزینه
EXP_COST_MULT    = 0.5      # exp > 0.5 × spread
COST_STRESS_X    = 2.0      # exp@2×spread باید هنوز > 0 باشد

# کفِ پذیرشِ پروژه
RQS2_ACCEPT_FLOOR = 80.0

GATE_NAMES = {
    'H0': 'sample+independence', 'H1': 'raw quality',
    'H2': 'cost-adj geometric edge', 'H3': 'skill vs measured null',
    'H4': 'per-side skill', 'H5': 'multiple-testing survival',
    'H6': 'calendar stability', 'H7': 'out-of-sample',
    'H8': 'tail risk + recovery', 'H9': 'cost robustness',
}


# ================================ توابعِ کمکی ================================
def _clip01(x):
    return float(min(1.0, max(0.0, x)))


def binom_p_one_sided(wins, n, p0):
    """P(X ≥ wins) تحتِ Binomial(n, p0). n≤300 جمعِ دقیق، وگرنه تقریبِ نرمال."""
    if n <= 0:
        return 1.0
    wins = int(round(wins))
    p0 = min(max(float(p0), 1e-9), 1 - 1e-9)
    if wins <= 0:
        return 1.0
    if wins > n:
        return 0.0
    if n <= 300:
        tail = 0.0
        for k in range(wins, n + 1):
            tail += comb(n, k) * (p0 ** k) * ((1 - p0) ** (n - k))
        return float(min(1.0, tail))
    mu = n * p0
    sigma = (n * p0 * (1 - p0)) ** 0.5
    if sigma <= 0:
        return 1.0 if wins <= mu else 0.0
    z = (wins - 0.5 - mu) / sigma
    return float(min(1.0, max(0.0, 0.5 * erfc(z / sqrt(2)))))


def max_concurrency(trades):
    """بیشترین تعدادِ معاملهٔ باز به‌طورِ هم‌زمان (روی محورِ کندل).

    اهمیت: p-valueِ دوجمله‌ای استقلالِ آزمون‌ها را فرض می‌کند. اگر دو معامله
    هم‌پوشان باشند، نتیجهٔ آنها به حرکتِ یک بازهٔ قیمتیِ مشترک وابسته است و
    n «مؤثر» از n «شمارشی» کمتر است ⇒ p-value خوش‌بینانه می‌شود.
    """
    if trades is None or len(trades) == 0:
        return 0
    if 'entry_bar' not in trades.columns or 'exit_bar' not in trades.columns:
        return -1  # نامعلوم
    ev = []
    for a, b in zip(trades['entry_bar'].values, trades['exit_bar'].values):
        ev.append((int(a), 1))
        ev.append((int(b) + 1, -1))   # بازهٔ بسته [entry, exit]
    ev.sort()
    cur = mx = 0
    for _, d in ev:
        cur += d
        mx = max(mx, cur)
    return int(mx)


def breakeven_wr_cost(sl_pip, tp_pip, cost_pip):
    """نقطهٔ سربه‌سرِ **هزینه‌دار** بر حسبِ درصد.

    برای یک براکت: سودِ برد = TP − c ، زیانِ باخت = SL + c
        WR·(TP−c) = (1−WR)·(SL+c)  ⇒  WR = (SL+c) / (SL+TP)

    نکته: مخرج `SL+TP` است نه `SL+TP−2c`؛ جبر را ساده کنید تا ببینید.
    این عدد **همیشه ≥** نسخهٔ بی‌هزینهٔ `SL/(SL+TP)` است، پس RQS+ سربه‌سر را
    سیستماتیک کم‌برآورد می‌کرد.
    """
    den = float(sl_pip) + float(tp_pip)
    if den <= 0:
        return 50.0
    return float((float(sl_pip) + float(cost_pip)) / den * 100.0)


def calendar_windows(trades, bar_time, k=CAL_WINDOWS):
    """تقسیمِ معاملات به k بازهٔ **تقویمیِ هم‌طول** (نه هم‌تعداد).

    چرا مهم است: `np.linspace(0, n_trades, k+1)` بازه‌ها را بر تعدادِ معامله
    می‌شکند. اگر معاملات در یک رژیمِ زمانیِ خاص خوشه شوند، هر ۴ «ربع» می‌توانند
    درونِ یک بازهٔ شش‌ماهه بیفتند و آزمونِ پایداری بی‌معنا شود. بازهٔ تقویمی
    این حفره را می‌بندد و افزون بر آن «اشغال‌بودنِ بازه‌ها» را قابلِ سنجش
    می‌کند (ضدِ خوشه‌ای‌شدن).

    ورودی `bar_time`: آرایهٔ زمانِ هر کندل (unix یا هر معیارِ صعودی).
    خروجی: فهرستِ k آرایهٔ بولین روی ردیف‌های `trades`.
    """
    if trades is None or len(trades) == 0:
        return [np.zeros(0, bool) for _ in range(k)]
    n = len(trades)
    if bar_time is None:
        # پس‌گردِ صادقانه: محورِ exit_bar به‌عنوانِ تقریبِ زمان (کندل‌ها هم‌فاصله‌اند)
        t = trades['exit_bar'].values.astype('float64')
    else:
        bt = np.asarray(bar_time, dtype='float64')
        idx = np.clip(trades['exit_bar'].values.astype(int), 0, len(bt) - 1)
        t = bt[idx]
    lo, hi = float(np.min(t)), float(np.max(t))
    if hi <= lo:
        m = np.ones(n, bool)
        return [m] + [np.zeros(n, bool) for _ in range(k - 1)]
    edges = np.linspace(lo, hi, k + 1)
    out = []
    for i in range(k):
        a, b = edges[i], edges[i + 1]
        m = (t >= a) & (t < b) if i < k - 1 else (t >= a) & (t <= b)
        out.append(m)
    return out


def _net_of(trades, asset, mask=None, initial_capital=10000.0):
    """نتِ دلاریِ زیرمجموعه‌ای از معاملات (۰ اگر خالی)."""
    sub = trades if mask is None else trades[mask]
    if sub is None or len(sub) == 0:
        return 0.0
    s, _ = se.run_capital(sub, asset, initial_capital=initial_capital)
    return float(s['net_profit'])


def max_consec_losses(outcomes):
    mcl = cur = 0
    for o in outcomes:
        if o == 'win':
            cur = 0
        else:
            cur += 1
            mcl = max(mcl, cur)
    return int(mcl)


def null_from_s346(row):
    """تبدیلِ یک ردیفِ خروجیِ `strategies/s346_null.py` به ساختارِ کانونیِ RQS2.

    ساختارِ کانونی:
        {'long':  {'uncond_wr','perm_mean','perm_sd','perm_max','perm_k'},
         'short': {...}}
    """
    out = {}
    for side, nk in (('long', 'null_long'), ('short', 'null_short')):
        p = (row.get('perm') or {}).get(side) or {}
        nm = (row.get(nk) or {}).get('metrics') or {}
        out[side] = dict(
            uncond_wr=nm.get('win_rate'),
            perm_mean=p.get('mean'), perm_sd=p.get('sd'),
            perm_max=p.get('hi'), perm_k=p.get('k'),
        )
    return out
