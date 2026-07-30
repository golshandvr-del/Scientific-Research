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

# H10 — ⭐ مقاومتِ رژیمی (لبه در **خلافِ جریان** هم زنده است؟)
#   چرا این دروازه جای خالیِ همهٔ دروازه‌های دیگر را پر می‌کند: آزمونِ جای‌گشت
#   (H3) رانشِ کلِ نمونه را **حفظ** می‌کند، پس هرگز نمی‌پرسد «اگر رانش نبود چه؟».
#   H10 معاملات را به دو دستهٔ «هم‌سو با رانشِ حاکم» و «خلافِ آن» می‌شکند و
#   می‌خواهد لایه در دستهٔ خلاف‌جریان هم مثبت بماند. لایه‌ای که فقط هم‌سو سود
#   می‌دهد، سرمایه‌اش را از رانش قرض گرفته، نه از الگو.
REGIME_LOOKBACK  = 200      # کندل، برای تعیینِ رانشِ حاکم در لحظهٔ ورود
REGIME_N_FLOOR   = 20       # حداقلِ معاملهٔ خلاف‌جریان برای داوریِ معتبر

# کفِ پذیرشِ پروژه
RQS2_ACCEPT_FLOOR = 80.0

GATE_NAMES = {
    'H0': 'sample+independence', 'H1': 'raw quality',
    'H2': 'cost-adj geometric edge', 'H3': 'skill vs measured null',
    'H4': 'per-side skill', 'H5': 'multiple-testing survival',
    'H6': 'calendar stability', 'H7': 'out-of-sample',
    'H8': 'tail risk + recovery', 'H9': 'cost robustness',
    'H10': 'regime robustness (counter-drift)',
}


def counter_drift_mask(trades, close, lookback=REGIME_LOOKBACK):
    """ماسکِ معاملاتی که **خلافِ رانشِ حاکم** باز شده‌اند.

    رانشِ حاکم در لحظهٔ ورود = علامتِ بازدهِ `lookback` کندلِ گذشته.
    یک معامله «خلاف‌جریان» است اگر:
        long  و رانش ≤ 0   یا   short و رانش ≥ 0

    نکتهٔ ظریفِ طراحی: مرجع، رانشِ **خودِ دارایی** است نه بازار کلی، و در
    لحظهٔ ورود محاسبه می‌شود (کاملاً causal، بدونِ نگاه به آینده).
    """
    if trades is None or len(trades) == 0 or close is None:
        return None
    c = np.asarray(close, dtype='float64')
    if len(c) < lookback + 2:
        return None
    eb = np.clip(trades['entry_bar'].values.astype(int), 0, len(c) - 1)
    prev = np.clip(eb - int(lookback), 0, len(c) - 1)
    with np.errstate(divide='ignore', invalid='ignore'):
        drift = np.where(c[prev] > 0, c[eb] / c[prev] - 1.0, 0.0)
    if 'direction' in trades.columns:
        is_long = (trades['direction'].values == 'long')
    else:
        is_long = np.ones(len(trades), bool)
    return np.where(is_long, drift <= 0.0, drift >= 0.0)


# ================================ توابعِ کمکی ================================
def _clip01(x):
    return float(min(1.0, max(0.0, x)))


def expected_max_z(n_trials):
    """E[بیشینهٔ N نمونهٔ مستقلِ نرمالِ استاندارد] — قضیهٔ «استراتژیِ کاذب».

    مرجع: Bailey & López de Prado (2014), *The Deflated Sharpe Ratio*؛ و
    Bailey, Borwein, López de Prado & Zhu (2014), *Pseudo-Mathematics and
    Financial Charlatanism* (Notices of the AMS 61(5)).

        E[max_N] ≈ (1−γ)·Φ⁻¹(1 − 1/N) + γ·Φ⁻¹(1 − 1/(N·e))
        γ = 0.5772156649…  (ثابتِ اویلر–ماسکرونی)

    ⭐ **چرا این جای Bonferroni را می‌گیرد؟**
    پرسشِ واقعیِ ما این نیست که «آیا این آزمونِ خاص معنادار است؟» بلکه این است
    که «من **بهترینِ N تلاش** را برداشتم؛ شانس به‌تنهایی چقدر خوب ظاهر می‌شد؟».
    این دقیقاً همان آماره‌ای است که فرایندِ جست‌وجوی ما بیشینه می‌کند، پس آزمون
    باید روی *همان* آماره بسته شود.

    نکتهٔ ظریفِ کمّی: این کران با `√(2·ln N)` رشد می‌کند — یعنی **لگاریتمی**.
    برای فضای جست‌وجوی واقعیِ ما (۱۲۹۶ هندسه × ۴۰۱ اندیکاتور × ~۱۰ آستانه ≈
    ۵.۲ میلیون) کرانِ لازم ≈ ۵.۳σ می‌شود؛ برای ۱۹۳٬۰۰۰ آزمون ≈ ۴.۹σ. یعنی
    برخلافِ تصورِ اولیه‌ام، جریمه **خفه‌کننده نیست** ولی سخت‌گیرانه است: یک
    یافتهٔ ۳σ که در RQS+ «معنادار» بود، اینجا صریحاً در ردهٔ «بهترینِ شانس»
    می‌افتد و رد می‌شود.
    """
    N = max(2, int(n_trials))
    g = 0.5772156649015329
    try:
        from scipy.stats import norm as _norm
        a = float(_norm.ppf(1.0 - 1.0 / N))
        b = float(_norm.ppf(1.0 - 1.0 / (N * np.e)))
    except Exception:                                    # پس‌گردِ بی‌وابستگی
        a = _ppf_approx(1.0 - 1.0 / N)
        b = _ppf_approx(1.0 - 1.0 / (N * np.e))
    return (1.0 - g) * a + g * b


def _ppf_approx(p):
    """تقریبِ Φ⁻¹ (Acklam) — تنها برای حالتی که scipy در دسترس نباشد."""
    p = min(max(float(p), 1e-12), 1 - 1e-12)
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    pl = 0.02425
    if p < pl:
        q = (-2 * np.log(p)) ** 0.5
        return (((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
               ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)
    if p > 1 - pl:
        q = (-2 * np.log(1 - p)) ** 0.5
        return -(((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
                ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r + a[1])*r + a[2])*r + a[3])*r + a[4])*r + a[5])*q / \
           (((((b[0]*r + b[1])*r + b[2])*r + b[3])*r + b[4])*r + 1)


def binom_z(wins, n, p0):
    """آمارهٔ zِ دوجمله‌ای: چند خطای استاندارد بالاتر از نرخِ مبنای `p0`.

    این **همان** آماره‌ای است که جست‌وجوی ما روی فضای هندسه×اندیکاتور بیشینه
    می‌کند، پس مقایسه‌اش با `expected_max_z` سازگار است (مقایسهٔ سیب با سیب).
    """
    if n <= 0:
        return 0.0
    p0 = min(max(float(p0), 1e-9), 1 - 1e-9)
    se = (p0 * (1.0 - p0) / n) ** 0.5
    if se <= 0:
        return 0.0
    return float((wins / n - p0) / se)


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

    ⚠️ **باگی که تستِ واحد (`T7`) گرفت:** نسخهٔ اولِ این تابع دامنهٔ تقسیم را از
    `min/max` خودِ **معاملات** می‌گرفت. نتیجه: اگر همهٔ معاملات در ربعِ اولِ
    تاریخِ داده خوشه می‌شدند، همان خوشه به‌عنوانِ «کلِ تقویم» نرمال می‌شد و
    خوشه‌ای‌شدن **نامرئی** می‌ماند — یعنی دقیقاً چیزی که این دروازه برای
    گرفتنش ساخته شده بود. اصلاح: وقتی `bar_time` داده شود، دامنه = **افقِ
    کاملِ دادهٔ کارت** `[bar_time[0], bar_time[-1]]`.
    """
    if trades is None or len(trades) == 0:
        return [np.zeros(0, bool) for _ in range(k)]
    n = len(trades)
    if bar_time is None:
        # پس‌گردِ تنزل‌یافته: بدونِ محورِ زمان، خوشه‌ای‌شدن قابلِ تشخیص نیست.
        # (compute_rqs2 در این حالت H6 را UNKNOWN می‌کند، نه «پاس».)
        t = trades['exit_bar'].values.astype('float64')
        lo, hi = float(np.min(t)), float(np.max(t))
    else:
        bt = np.asarray(bar_time, dtype='float64')
        idx = np.clip(trades['exit_bar'].values.astype(int), 0, len(bt) - 1)
        t = bt[idx]
        lo, hi = float(bt[0]), float(bt[-1])      # ⭐ افقِ کاملِ داده
    if hi <= lo:
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


def _side_null_ref(nd):
    """قوی‌ترین خطِ مبنای یک سمت = max(بی‌قید، میانگینِ جای‌گشت).

    «قوی‌ترین» انتخاب می‌شود نه میانگین، چون آزمون باید **محافظه‌کارانه** باشد:
    اگر سیگنال از سخت‌ترین رقیبِ بی‌مهارت هم بهتر بود، مهارت اثبات‌شده است.
    """
    if not nd:
        return None
    vals = [v for v in (nd.get('uncond_wr'), nd.get('perm_mean')) if v is not None]
    return float(max(vals)) if vals else None


def blend_null(null, n_by_side):
    """ترکیبِ خطوطِ مبنا با **وزنِ تعدادِ معاملهٔ همان سمت**.

    منطق: پرسشِ درست این است «معامله‌گری که *همان ترکیبِ جهت* را دارد ولی
    هیچ سیگنالی ندارد، چه WR می‌گیرد؟». پس مبنا باید با سهمِ واقعیِ
    long/shortِ خودِ لایه وزن شود — مقایسه با مبنای صرفاً لانگ برای لایهٔ
    دوسویه سوگیریِ آشکار دارد.

    برای `sd` از Σw·sd استفاده می‌شود (نه √Σw²sd²) که طبقِ نامساویِ مثلثی
    **کران بالا** است ⇒ z کوچک‌تر ⇒ آزمونِ سخت‌گیرانه‌تر.
    """
    if not null:
        return None
    tot = float(sum(n_by_side.get(s, 0) for s in ('long', 'short')))
    if tot <= 0:
        return None
    ref = sd = mx = 0.0
    kmin = None
    for s in ('long', 'short'):
        ns = float(n_by_side.get(s, 0))
        if ns <= 0:
            continue
        nd = null.get(s) or {}
        r = _side_null_ref(nd)
        if r is None:
            return None
        w = ns / tot
        ref += w * r
        sd += w * float(nd.get('perm_sd') or 0.0)
        mx += w * float(nd.get('perm_max') if nd.get('perm_max') is not None else r)
        k = nd.get('perm_k')
        kmin = int(k) if kmin is None else min(kmin, int(k or 0))
    return dict(ref_wr=ref, perm_sd=sd, perm_max=mx, perm_k=kmin or 0)


# ============================== هستهٔ محاسبهٔ RQS2 ==============================
def compute_rqs2(trades, asset, *, sl_pip=None, tp_pip=None, bar_time=None,
                 null=None, n_trials=None, holdout_mask=None, split_bar=None,
                 close=None, initial_capital=10000.0, allow_overlap=False):
    """
    ورودیِ اجباری
    -------------
      trades : DataFrameِ `simulate_trades` (ستون‌های pnl_pip, outcome, sl_pip,
               entry_bar, exit_bar, direction)
      asset  : کلیدِ `se.ASSETS`

    ورودیِ لازم برای «پذیرش» (نبودشان ⇒ `INCOMPLETE`، نه `ACCEPT`)
    ----------------------------------------------------------------
      tp_pip      : فاصلهٔ TP بر حسبِ pip. ⚠️ `simulate_trades` این ستون را
                    **نمی‌سازد**؛ اگر پاس داده نشود RQS2 حدس نمی‌زند و `H2`
                    را `UNKNOWN` می‌کند. (در RQS+ به‌غلط `tp=sl` فرض می‌شد و
                    سپرِ ضدِ تقلبِ TP<SL خودبه‌خود خاموش می‌گشت.)
      null        : ساختارِ کانونیِ مدلِ صفر (`null_from_s346`) ⇒ `H3`,`H4`,`H5`
      n_trials    : اندازهٔ فضای جست‌وجویی که واقعاً پیمایش شد ⇒ `H5`
      holdout_mask یا split_bar : تقسیمِ اکتشاف/خارج‌ازنمونه ⇒ `H7`
      bar_time    : آرایهٔ زمانِ کندل‌ها ⇒ پنجره‌بندیِ تقویمیِ `H6`

    خروجی
    ------
      dict با کلیدهای gates (True/False/None)، metrics، verdict
      ('ACCEPT'|'REJECT'|'INCOMPLETE')، rqs2_score، notes
    """
    res = {'asset': asset, 'gates': {}, 'metrics': {}, 'notes': [],
           'passed': False, 'rqs2_score': 0.0, 'verdict': 'REJECT'}

    if trades is None or len(trades) == 0:
        res['metrics']['n_trades'] = 0
        res['gates'] = {g: False for g in GATE_NAMES}
        res['verdict'] = 'REJECT (no trades)'
        return res

    tr = trades.sort_values('exit_bar').reset_index(drop=True)
    n = len(tr)
    outcomes = tr['outcome'].tolist()
    wins = sum(1 for o in outcomes if o == 'win')
    wr = wins / n * 100.0
    pnl = tr['pnl_pip'].values.astype('float64')
    exp_pip = float(np.mean(pnl))

    cfg = se.ASSETS[asset]
    spread = float(cfg['spread_pip'])
    slip = float(cfg.get('slip_pip', 0.0))
    cost_pip = spread + 2.0 * slip     # هزینهٔ کاملِ رفت‌وبرگشت

    if sl_pip is None:
        sl_pip = float(np.median(tr['sl_pip'].values))

    cap, _ = se.run_capital(tr, asset, initial_capital=initial_capital)
    net = float(cap['net_profit'])
    pf = float(cap['profit_factor'])
    maxdd_pct = abs(float(cap['max_dd_pct']))
    recovery = float(cap.get('net_over_dd', 0.0))
    ruined = bool(cap.get('ruined', False))

    # سمت‌ها
    has_dir = 'direction' in tr.columns
    n_by_side, wr_by_side, exp_by_side = {}, {}, {}
    for s in ('long', 'short'):
        m = (tr['direction'] == s).values if has_dir else np.zeros(n, bool)
        ns = int(m.sum())
        n_by_side[s] = ns
        if ns > 0:
            wr_by_side[s] = float(sum(1 for o, k in zip(outcomes, m) if k and o == 'win')
                                  / ns * 100.0)
            exp_by_side[s] = float(np.mean(pnl[m]))
    active_sides = [s for s in ('long', 'short') if n_by_side[s] > 0]

    # ---------------------------- H0 نمونه و استقلال ----------------------------
    conc = max_concurrency(tr)
    h0_reasons = []
    if n < N_FLOOR:
        h0_reasons.append(f"n={n}<{N_FLOOR}")
    if conc > MAX_CONCURRENCY and not allow_overlap:
        h0_reasons.append(f"concurrency={conc}>{MAX_CONCURRENCY}")
    for s in active_sides:
        if len(active_sides) > 1 and n_by_side[s] < N_SIDE_FLOOR:
            h0_reasons.append(f"n_{s}={n_by_side[s]}<{N_SIDE_FLOOR}")
    if ruined:
        h0_reasons.append("account ruined")
    h0 = (len(h0_reasons) == 0)

    # ------------------------------ H1 کیفیتِ خام ------------------------------
    h1 = (wr >= WR_FLOOR) and (pf >= PF_MIN)

    # -------------------- H2 لبهٔ هندسیِ هزینه‌دار (ضدِ تقلب) --------------------
    if tp_pip is None or float(tp_pip) <= 0:
        h2 = None
        be_cost = rr = wr_excess = None
        res['notes'].append("H2 UNKNOWN: tp_pip not supplied — RQS2 refuses the "
                            "tp=sl assumption that silently disabled RQS+'s "
                            "anti-gaming guard")
    else:
        tp_pip = float(tp_pip)
        be_cost = breakeven_wr_cost(sl_pip, tp_pip, cost_pip)
        wr_excess = wr - be_cost
        rr = tp_pip / float(sl_pip) if sl_pip > 0 else 0.0
        h2 = (wr_excess >= WR_EXCESS_MIN) and (rr >= RR_MIN) and (exp_pip > 0)

    # ------------------- H3 ⭐ مهارت نسبت به مدلِ صفرِ اندازه‌گیری‌شده -------------------
    nb = blend_null(null, n_by_side)
    if nb is None:
        h3 = None
        lift = z_skill = None
        res['notes'].append("H3 UNKNOWN: no measured null model supplied — "
                            "absence of a control is not evidence of skill")
    else:
        lift = wr - nb['ref_wr']
        z_skill = (lift / nb['perm_sd']) if nb['perm_sd'] > 0 else float('inf')
        h3 = (lift >= SKILL_LIFT_MIN and z_skill >= SKILL_Z_MIN
              and wr > nb['perm_max'] and nb['perm_k'] >= PERM_K_MIN)

    # ---------------------------- H4 مهارتِ هر سمت ----------------------------
    side_lift, prune_sides = {}, []
    if not null:
        h4 = None
    else:
        h4 = True
        for s in active_sides:
            r = _side_null_ref(null.get(s) or {})
            if r is None:
                h4 = None
                break
            L = wr_by_side[s] - r
            side_lift[s] = round(L, 2)
            if L < SIDE_LIFT_MIN or exp_by_side[s] <= 0:
                h4 = False
                prune_sides.append(s)

    # ------------------------ H5 بقا در آزمونِ چندگانه ------------------------
    # ⭐ آزمونِ اصلی = **قضیهٔ استراتژیِ کاذب**، نه Bonferroni.
    #   پرسش: «بهترینِ N تلاش را برداشتم؛ شانسِ محض چقدر خوب ظاهر می‌شد؟»
    #   کران = E[max_N]. آمارهٔ سنجیده = همان zِ دوجمله‌ای که جست‌وجو بیشینه کرد.
    #   Bonferroni تنها به‌عنوان **تشخیصِ گزارشی** نگه داشته می‌شود.
    if nb is None or not n_trials:
        h5 = None
        p_emp = p_adj = z_obs = z_bar = None
        if not n_trials:
            res['notes'].append("H5 UNKNOWN: n_trials not supplied — the size of "
                                "the space actually searched must be declared; a "
                                "finding cannot be judged without knowing how many "
                                "chances luck was given")
    else:
        p0 = nb['ref_wr'] / 100.0
        p_emp = binom_p_one_sided(wins, n, p0)
        p_adj = float(min(1.0, p_emp * float(n_trials)))   # فقط تشخیصی
        z_obs = binom_z(wins, n, p0)
        z_bar = expected_max_z(n_trials)
        h5 = (z_obs > z_bar)

    # -------------------------- H6 پایداریِ تقویمی --------------------------
    wins_cal = calendar_windows(tr, bar_time, CAL_WINDOWS)
    cal_nets = [_net_of(tr, asset, m, initial_capital) for m in wins_cal]
    cal_counts = [int(m.sum()) for m in wins_cal]
    occupied = sum(1 for c in cal_counts if c > 0)
    positives = sum(1 for x in cal_nets if x > 0)
    worst = min(cal_nets) if cal_nets else 0.0
    worst_ok = (worst >= 0) or (net > 0 and abs(worst) <= CAL_WORST_FRAC * net)
    halves = calendar_windows(tr, bar_time, 2)
    half_nets = [_net_of(tr, asset, m, initial_capital) for m in halves]
    if bar_time is None:
        # بدونِ محورِ زمان، «پایداریِ تقویمی» ادعاپذیر نیست: نمی‌دانیم معاملات
        # کلِ افقِ داده را پوشش می‌دهند یا در یک رژیمِ کوتاه خوشه شده‌اند.
        # طبقِ اصلِ حاکم، ادعاِ نشده ⇒ UNKNOWN، نه «پاس».
        h6 = None
        res['notes'].append("H6 UNKNOWN: bar_time not supplied — calendar "
                            "coverage cannot be verified (pass np.arange(len(df)) "
                            "or df['time'].values)")
    else:
        h6 = (positives >= CAL_POS_MIN and occupied >= CAL_OCCUPIED_MIN
              and worst_ok and all(x > 0 for x in half_nets))

    # --------------------------- H7 خارج از نمونه ---------------------------
    hm = None
    if holdout_mask is not None:
        hm = np.asarray(holdout_mask, bool)
        if len(hm) != n:
            hm = None
            res['notes'].append("H7: holdout_mask length mismatch — ignored")
    elif split_bar is not None:
        hm = (tr['entry_bar'].values >= int(split_bar))
    if hm is None or hm.sum() == 0:
        h7 = None
        oos = {}
        res['notes'].append("H7 UNKNOWN: no discovery/holdout split supplied")
    else:
        sub = tr[hm]
        no = len(sub)
        wo = sum(1 for o in sub['outcome'] if o == 'win')
        wro = wo / no * 100.0
        so, _ = se.run_capital(sub, asset, initial_capital=initial_capital)
        pfo = float(so['profit_factor'])
        oos = dict(n=no, wr=round(wro, 2), pf=round(pfo, 3),
                   net=round(float(so['net_profit']), 1))
        h7 = (no >= OOS_N_FLOOR and wro >= OOS_WR_FLOOR and pfo >= OOS_PF_MIN)

    # --------------------- H8 ریسکِ دنباله و ضریبِ بازیافت ---------------------
    mcl = max_consec_losses(outcomes)
    h8 = (maxdd_pct <= MAXDD_MAX_PCT and mcl <= MCL_MAX
          and (recovery >= RECOVERY_MIN or not np.isfinite(recovery)))

    # -------------------------- H9 مقاومتِ هزینه --------------------------
    exp_stress = exp_pip - (COST_STRESS_X - 1.0) * cost_pip
    h9 = (exp_pip > EXP_COST_MULT * spread) and (exp_stress > 0)

    # ------------------ H10 ⭐ مقاومتِ رژیمی (خلافِ جریان) ------------------
    cdm = counter_drift_mask(tr, close, REGIME_LOOKBACK)
    cd = {}
    if cdm is None:
        h10 = None
        res['notes'].append("H10 UNKNOWN: close series not supplied — cannot "
                            "test whether the edge survives against the "
                            "prevailing drift, which is the one question the "
                            "permutation control structurally cannot answer")
    else:
        n_cd = int(cdm.sum())
        n_al = int((~cdm).sum())
        cd['n_counter'], cd['n_aligned'] = n_cd, n_al
        if n_cd > 0:
            sub = tr[cdm]
            wcd = sum(1 for o in sub['outcome'] if o == 'win')
            cd['wr_counter'] = round(wcd / n_cd * 100.0, 2)
            cd['exp_counter'] = round(float(np.mean(pnl[cdm])), 3)
        if n_al > 0:
            sub = tr[~cdm]
            wal = sum(1 for o in sub['outcome'] if o == 'win')
            cd['wr_aligned'] = round(wal / n_al * 100.0, 2)
            cd['exp_aligned'] = round(float(np.mean(pnl[~cdm])), 3)
        if n_cd < REGIME_N_FLOOR:
            # لایه هرگز در شرایطِ نامساعد آزموده نشده ⇒ ادعا نشده، نه تأیید شده
            h10 = None
            res['notes'].append(
                f"H10 UNKNOWN: only {n_cd} counter-drift trades "
                f"(<{REGIME_N_FLOOR}) — the layer has never actually been "
                f"tested against an adverse drift regime")
        else:
            ok_exp = cd['exp_counter'] > 0
            ok_wr = (be_cost is None) or (cd['wr_counter'] >= be_cost)
            h10 = bool(ok_exp and ok_wr)

    gates = {'H0': h0, 'H1': h1, 'H2': h2, 'H3': h3, 'H4': h4,
             'H5': h5, 'H6': h6, 'H7': h7, 'H8': h8, 'H9': h9, 'H10': h10}

    n_fail = sum(1 for v in gates.values() if v is False)
    n_unknown = sum(1 for v in gates.values() if v is None)
    all_pass = (n_fail == 0 and n_unknown == 0)

    # ------------------------------ نمرهٔ پیوسته ------------------------------
    # ⚠️ برخلافِ RQS+، هیچ مؤلفه‌ای به **WR خام** پاداش نمی‌دهد؛ مؤلفهٔ کیفیتِ
    #    ورود «مازادِ هزینه‌دار» است تا تقلبِ TP<SL خودبه‌خود بی‌اثر شود.
    c_skill = _clip01((z_skill / 6.0)) if z_skill is not None else 0.0
    c_oos   = _clip01((oos.get('pf', 0.0) - 1.0) / 0.8) if oos else 0.0
    c_stab  = (positives / float(CAL_WINDOWS)) * (1.0 if all(x > 0 for x in half_nets) else 0.5)
    c_pf    = _clip01((pf - 1.0) / 1.0) if np.isfinite(pf) else 1.0
    c_exp   = _clip01(exp_pip / (2.0 * cost_pip)) if cost_pip > 0 else 1.0
    c_tail  = _clip01(1 - maxdd_pct / MAXDD_MAX_PCT) * _clip01(1 - mcl / float(MCL_MAX))
    # مؤلفهٔ «بقای انتخاب» = چقدر **بالاتر از کرانِ بهترین‌شانس** ایستاده‌ایم.
    # (نه p تصحیح‌شده: p_adj در نمونه‌های بزرگ به صفر می‌چسبد و اشباع می‌شود،
    #  حال آنکه فاصله از کران، پیوسته و مستقیماً معنادار است.)
    c_sel   = (_clip01((z_obs - z_bar) / 2.0)
               if (z_obs is not None and z_bar is not None) else 0.0)
    c_edge  = _clip01(wr_excess / 10.0) if wr_excess is not None else 0.0

    weighted = (0.30 * c_skill + 0.15 * c_oos + 0.15 * c_stab + 0.10 * c_pf +
                0.10 * c_exp + 0.10 * c_tail + 0.05 * c_sel + 0.05 * c_edge)

    score = 40.0 + 60.0 * weighted if all_pass else min(40.0, 40.0 * weighted)

    if all_pass:
        verdict = 'ACCEPT'
    elif n_fail > 0:
        verdict = 'REJECT'
    else:
        verdict = 'INCOMPLETE'

    res['metrics'] = {
        'n_trades': n, 'win_rate': round(wr, 2), 'net_profit': round(net, 1),
        'profit_factor': round(pf, 3) if np.isfinite(pf) else 999.0,
        'max_dd_pct': round(maxdd_pct, 2), 'max_consec_losses': mcl,
        'recovery_factor': (round(recovery, 2) if np.isfinite(recovery) else 999.0),
        'expectancy_pip': round(exp_pip, 4),
        'expectancy_at_2x_cost': round(exp_stress, 4),
        'cost_pip': cost_pip, 'spread_pip': spread,
        'sl_pip': round(float(sl_pip), 3),
        'tp_pip': (round(float(tp_pip), 3) if tp_pip else None),
        'rr': (round(rr, 3) if rr is not None else None),
        'breakeven_wr_cost': (round(be_cost, 2) if be_cost is not None else None),
        'wr_excess_cost': (round(wr_excess, 2) if wr_excess is not None else None),
        'null_ref_wr': (round(nb['ref_wr'], 2) if nb else None),
        'skill_lift_pp': (round(lift, 2) if lift is not None else None),
        'skill_z': (round(z_skill, 2) if z_skill is not None else None),
        'perm_max': (round(nb['perm_max'], 2) if nb else None),
        'perm_k': (nb['perm_k'] if nb else None),
        'side_n': n_by_side, 'side_wr': {k: round(v, 2) for k, v in wr_by_side.items()},
        'side_lift_pp': side_lift, 'prune_sides': prune_sides,
        'p_emp': (round(p_emp, 6) if p_emp is not None else None),
        'p_adj_bonferroni': (round(p_adj, 6) if p_adj is not None else None),
        'z_obs': (round(z_obs, 3) if z_obs is not None else None),
        'z_luck_bound': (round(z_bar, 3) if z_bar is not None else None),
        'z_margin': (round(z_obs - z_bar, 3)
                     if (z_obs is not None and z_bar is not None) else None),
        'n_trials': n_trials,
        'cal_nets': [round(x, 1) for x in cal_nets], 'cal_counts': cal_counts,
        'cal_positive': positives, 'cal_occupied': occupied,
        'half_nets': [round(x, 1) for x in half_nets],
        'oos': oos, 'max_concurrency': conc,
        'counter_drift': cd,
    }
    res['gates'] = gates
    res['n_fail'] = n_fail
    res['n_unknown'] = n_unknown
    res['passed'] = all_pass
    res['rqs2_score'] = round(score, 1)
    res['verdict'] = verdict
    res['accepted'] = bool(all_pass and score >= RQS2_ACCEPT_FLOOR)
    return res


def format_rqs2(name, r):
    """گزارشِ تک‌خطیِ خوانا."""
    m = r['metrics']
    sym = {True: '✓', False: '✗', None: '?'}
    gline = ' '.join(f"{k}:{sym[v]}" for k, v in r['gates'].items())
    lift = m.get('skill_lift_pp')
    z = m.get('skill_z')
    return (f"{name:26s} | {r['verdict']:10s} RQS2={r['rqs2_score']:5.1f} | "
            f"n={m.get('n_trades',0):4d} WR={m.get('win_rate',0):5.2f}% "
            f"PF={m.get('profit_factor',0):.2f} "
            f"lift={('%+.2f' % lift) if lift is not None else '  n/a':>7s}pp "
            f"z={('%.1f' % z) if z is not None else 'n/a':>4s} | {gline}")
