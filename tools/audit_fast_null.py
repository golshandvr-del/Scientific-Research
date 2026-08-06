# -*- coding: utf-8 -*-
"""
حل‌کنندهٔ **برداریِ** مدلِ صفر — گلوگاهِ محاسباتیِ ماموریتِ ممیزی
================================================================================
چرا این فایل وجود دارد (مسئلهٔ واقعی، نه بهینه‌سازیِ زودهنگام)
--------------------------------------------------------------------------------
`H3` سنگین‌ترین دروازهٔ RQS2 است و v2.4 برایش `perm_k ≥ 500` را **اجباری** کرد،
وگرنه `perm_sd` همگرا نیست و حکم `UNKNOWN` می‌شود. یعنی داوریِ هر (کارت، سمت)
یعنی ≥۵۰۰ بار شبیه‌سازیِ کاملِ براکت. `se.simulate_trades` برای هر معامله یک
حلقهٔ پایتونیِ درونی روی کندل‌ها می‌زند ⇒ هزینهٔ نول برای یک کارت M15 حدودِ
دو تا پنج دقیقه است. با ۱۷۵ لایه × چند کارت × دو سمت، ماموریت در عمرِ سندباکس
تمام نمی‌شود. نشستِ قبلی **دقیقاً همین‌جا** ایستاد: هارنس کالیبره شد و صفر حکم
تولید کرد.

راهِ حل، **کم‌کردنِ K یا شل‌کردنِ آستانه نیست** (که تقلبِ آماری است). راهِ حل
این است که بفهمیم نول یک محاسبهٔ **بی‌حافظه به ازای هر کندل** است:

    برای هر کندلِ i و هر (sl, rr) : نتیجهٔ معاملهٔ ورودی در i **یکتا** است.

قیدِ عدمِ همپوشانی هم به نتیجهٔ تکِ معامله کاری ندارد؛ فقط انتخاب می‌کند کدام
ورودها **زنده** می‌مانند. پس اگر `outcome(i)` و `exit_bar(i)` را **یک‌بار** برای
همهٔ کندل‌ها حساب کنیم، هر جای‌گشت فقط یک عبورِ خطیِ ارزان روی آرایه است.

════════════════════════════════════════════════════════════════════════════
قیدِ صحتِ غیرقابلِ‌مذاکره
════════════════════════════════════════════════════════════════════════════
این ماژول **مجاز نیست** مکانیکِ متفاوتی داشته باشد. هر انحراف از
`se.simulate_trades` مستقیماً واردِ `H3` می‌شود و لیفت را جعل می‌کند. پس چهار
جزئیاتِ ظریفِ موتورِ رسمی مو‌به‌مو تکرار شده‌اند:

  ① ورود روی `open[i+1]` (نه `close[i]`) — همان یافتهٔ `CALIBRATION_FINDING.md`.
  ② اسلیپیجِ ورود در جهتِ بدتر، و اسلیپیجِ خروج هم در جهتِ بدتر.
  ③ **ابهامِ درون‌کندلی ⇒ باخت** (اگر در یک کندل هم SL و هم TP لمس شود).
  ④ برچسبِ `outcome` بر اساسِ **علامتِ pnl واقعی** است، نه اینکه کدام سطح خورد
     (باگِ گزارشیِ s117/s118 که موتورِ رسمی رفعش کرده).

⚠️ محدودیتِ اعلام‌شده: این ماژول `be_trigger_pip` و `trail_pip` را پیاده
**نمی‌کند** و اگر بخواهی‌شان `NotImplementedError` می‌دهد. مدلِ صفرِ کانونیِ
اسپک براکتِ ساده است، پس نیازی نیست؛ ولی سکوت‌کردن در برابرِ ورودیِ
پیاده‌نشده، همان «تخریبِ خاموش» است که اسپکِ v2.2 ممنوعش کرد.

اعتبارسنجی: `tools/audit_fast_null_verify.py` این حل‌کننده را روی دادهٔ واقعی
با `se.simulate_trades` تطبیق می‌دهد و **هم‌ارزیِ دقیق** را می‌سنجد. تا وقتی
آن آزمون پاس نشده، این ماژول در هیچ داوری‌ای استفاده نمی‌شود.
"""
from __future__ import annotations

import numpy as np

from engine import scalp_engine as se


# ═══════════════════════════════════════════════════════════════════════════
#  گامِ ①: نتیجهٔ معاملهٔ «اگر در کندلِ i وارد می‌شدم» برای همهٔ i
# ═══════════════════════════════════════════════════════════════════════════
def resolve_all_entries(df, asset: str, sl_pip: float, tp_pip: float,
                        max_hold: int, direction: str):
    """
    برای **هر** کندلِ سیگنالِ ممکن `i`، نتیجهٔ معاملهٔ متناظر را حل می‌کند.

    خروجی (همه هم‌طولِ `n`، و برای `i` های نامعتبر `NaN`/`-1`):
      · `pnl_pip[i]`  : سود/زیانِ خالصِ pip (پس از اسپرد و اسلیپیج)
      · `exit_bar[i]` : کندلِ خروج (برای قیدِ عدمِ همپوشانی)
      · `win[i]`      : برچسبِ برد بر اساسِ علامتِ pnl

    پیچیدگی: `O(n · max_hold)` ولی **کاملاً برداری روی محورِ کندل**، و مهم‌تر
    اینکه **یک‌بار** برای کلِ K جای‌گشت انجام می‌شود، نه K بار.
    """
    cfg = se.ASSETS[asset]
    pip = cfg['pip']
    spread = cfg['spread_pip']
    slip = cfg['slip_pip']

    o = df['open'].to_numpy(np.float64)
    h = df['high'].to_numpy(np.float64)
    l = df['low'].to_numpy(np.float64)
    c = df['close'].to_numpy(np.float64)
    n = len(o)

    is_long = (direction == 'long')
    sl_d = float(sl_pip) * pip
    tp_d = float(tp_pip) * pip

    # ورود روی open کندلِ بعدی + اسلیپیجِ بدتر  (جزئیاتِ ① و ②)
    fill = np.full(n, np.nan)
    fill[:-1] = o[1:] + (slip * pip if is_long else -slip * pip)

    if is_long:
        sl_price = fill - sl_d
        tp_price = fill + tp_d
    else:
        sl_price = fill + sl_d
        tp_price = fill - tp_d

    exit_bar = np.full(n, -1, np.int64)
    exit_price = np.full(n, np.nan)
    resolved = np.zeros(n, bool)

    # پیمایشِ افق: در هر گامِ `k` همهٔ معاملاتِ حل‌نشده را هم‌زمان چک می‌کنیم.
    # این جایگزینِ حلقهٔ درونیِ پایتونیِ موتورِ رسمی است و همان قواعد را دارد.
    idx = np.arange(n)
    for k in range(0, max_hold):
        j = idx + 1 + k                      # کندلِ جاریِ نگه‌داری
        alive = (~resolved) & (j < n) & np.isfinite(fill)
        if not alive.any():
            break
        ja = j[alive]
        if is_long:
            hit_sl = l[ja] <= sl_price[alive]
            hit_tp = h[ja] >= tp_price[alive]
        else:
            hit_sl = h[ja] >= sl_price[alive]
            hit_tp = l[ja] <= tp_price[alive]

        # جزئیاتِ ③ — ابهام ⇒ بدترین حالت (SL مقدم)
        take_sl = hit_sl
        take_tp = hit_tp & (~hit_sl)
        done = take_sl | take_tp
        if done.any():
            pos = idx[alive][done]
            jj = ja[done]
            exit_bar[pos] = jj
            px = np.where(take_sl[done], sl_price[pos], tp_price[pos])
            exit_price[pos] = px
            resolved[pos] = True

    # پایانِ افق بدونِ برخورد ⇒ بستن روی close آخرین کندلِ افق
    tail = (~resolved) & np.isfinite(fill)
    if tail.any():
        end = np.minimum(idx + 1 + max_hold, n) - 1
        pos = idx[tail]
        eb = end[tail]
        ok = eb >= (pos + 1)
        pos, eb = pos[ok], eb[ok]
        exit_bar[pos] = eb
        exit_price[pos] = c[eb]

    # اسلیپیجِ خروج (جزئیاتِ ②) و pnl خالص
    valid = exit_bar >= 0
    pnl = np.full(n, np.nan)
    if is_long:
        exit_fill = exit_price - slip * pip
        gross = exit_fill - fill
    else:
        exit_fill = exit_price + slip * pip
        gross = fill - exit_fill
    pnl[valid] = gross[valid] / pip - spread

    # جزئیاتِ ④ — برچسب از علامتِ pnl، نه از سطحِ خورده
    win = np.zeros(n, bool)
    win[valid] = pnl[valid] > 0
    return pnl, exit_bar, win, valid


# ═══════════════════════════════════════════════════════════════════════════
#  گامِ ②: اعمالِ قیدِ عدمِ همپوشانی روی یک مجموعهٔ ورودِ دلخواه
# ═══════════════════════════════════════════════════════════════════════════
def wr_of_positions(pos_sorted: np.ndarray, exit_bar: np.ndarray,
                    win: np.ndarray, valid: np.ndarray, min_n: int = 10):
    """
    از میانِ کندل‌های سیگنالِ `pos_sorted` (که باید صعودی باشند)، همان
    زیرمجموعه‌ای را نگه می‌دارد که موتورِ رسمی نگه می‌داشت (FIFO، بدونِ
    همپوشانی) و `WR` را برمی‌گرداند.

    منطقِ عیناً موتورِ رسمی: `entry_bar = si + 1`، و ورود رد می‌شود اگر
    `entry_bar <= busy_until` که `busy_until = exit_bar` معاملهٔ جاری است.
    """
    busy = -1
    kept = 0
    wins = 0
    for si in pos_sorted:
        if not valid[si]:
            continue
        eb = si + 1
        if eb <= busy:
            continue
        busy = exit_bar[si]
        kept += 1
        if win[si]:
            wins += 1
    if kept < min_n:
        return None, kept
    return 100.0 * wins / kept, kept


def build_null_fast(df, asset, sl_pip, tp_pip, max_hold, side, n_sig,
                    k=600, seed=20260806, stride=3):
    """
    همان قراردادِ خروجیِ `audit_rqs2_rejudge.build_null`، ولی با حل‌کنندهٔ
    پیش‌محاسبه‌شده. اعدادش باید **در حدِ نویزِ نمونه‌گیری** با نسخهٔ کند یکی
    باشد؛ و «در حدِ نویز» یعنی با **همان بذر** عیناً یکی، چون هر دو از یک
    توزیعِ ورودِ یکسان نمونه می‌گیرند.
    """
    n = len(df)
    rng = np.random.default_rng(seed)
    lo, hi = 210, n - 2
    if hi <= lo:
        return None

    pnl, xb, win, valid = resolve_all_entries(
        df, asset, sl_pip, tp_pip, max_hold, side)

    m = np.arange(lo, hi, stride)
    uncond_wr, uncond_n = wr_of_positions(m, xb, win, valid)

    n_sig = int(max(1, min(int(n_sig), hi - lo - 1)))
    pool = np.arange(lo, hi)
    wrs = []
    for _ in range(k):
        pos = np.sort(rng.choice(pool, size=n_sig, replace=False))
        w, _cnt = wr_of_positions(pos, xb, win, valid)
        if w is not None:
            wrs.append(w)
    if len(wrs) < 50:
        return None
    a = np.asarray(wrs, float)
    return {
        'uncond_wr': uncond_wr, 'uncond_n': uncond_n, 'stride': stride,
        'perm_mean': float(a.mean()), 'perm_sd': float(a.std(ddof=1)),
        'perm_max': float(a.max()), 'perm_k': int(len(a)),
        'side': side, 'solver': 'vectorized',
    }
