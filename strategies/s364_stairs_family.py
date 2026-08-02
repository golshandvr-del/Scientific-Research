# -*- coding: utf-8 -*-
"""
S364 — Al Brooks «Stairs: Broad Channel Trend» (فصلِ ۲۶، آخرین فصلِ محتواییِ کتاب)
====================================================================================
منبع: Telegram-Resource/telegram_source_1/pdfs/1 Trading Price Action - Trends.pdf
CHAPTER 26 (pdf idx 462–467 = صفحاتِ کتاب ۴۳۱–۴۳۶).
پیش‌ثبتِ مسیرِ چندگانگی: results/S364_PREREG_multiplicity_route.md  (commit پیش از اجرا)

تزِ مرکزیِ فصل — و چرا این فصل ارزشِ یک نشستِ کامل دارد
--------------------------------------------------------
Brooks در ص ۴۳۲ مکانیکی‌ترین قاعدهٔ کلِ کتاب را می‌دهد:
  «Traders pay attention to **how many ticks breakouts run past the most recent swing
   point**, and then use that number to **fade subsequent breakouts**… if the last swing
   low fell **۱۴ ticks** below the swing low before it, traders will look to scale into
   longs beginning around **۱۰ ticks** below the most recent swing low… if the pullback
   was about **۱۵ ticks**, they take profits around **۱۰ تا ۱۵ ticks** up.»
و همان را در ص ۴۳۳ با اعدادِ دیگر تکرار می‌کند (۴ points شکست ⇒ ورودِ ۳–۴ points پایین‌تر؛
rallyهای ۴ points ⇒ سودِ ۳ points).

دو نمونهٔ مستقل با اعدادِ خام متفاوت ولی **نسبت‌های یکسان** ⇒ قاعده ترجمه‌پذیر است:
      entry_offset = f · ext        f ≈ 10/14 … 4/4      ⇒ f ∈ {0.70, 1.00}
      take_profit  = g · pull       g ≈ 10/15 … 3/4      ⇒ g ∈ {0.67, 0.75, 1.00}
هیچ عددِ ثابت، هیچ ATR، هیچ pipِ رند: هندسهٔ معامله **per-trade** از دو اندازه‌گیریِ
اخیرِ خودِ بازار مشتق می‌شود ⇒ پادزهرِ ساختاریِ اشتباهِ رایجِ #۶ و #۷.

تعریفِ زمینهٔ الگو (causal، هیچ نگاهِ آینده)
-------------------------------------------
pivotها با بازوی k تشخیص و در بارِ p+k **تأیید** می‌شوند؛ سپس یک zigzagِ متناوب ساخته
می‌شود. زمینهٔ خرسیِ stairs = پنج pivotِ آخر با الگوی [L1,H1,L2,H2,L3] و:
    L1 > L2 > L3            «at least three trading ranges» (سه push)
    H1 > H2                 کانالِ رو به پایین
    H2 > L1   ⭐            «every breakout to a new low is followed by a rally that goes
                             back **above the breakout point** but stays below the most
                             recent swing high»
    ext  = L2 − L3          «how many ticks the breakout ran past the most recent swing»
    pull = H2 − L2          «the pullback from the most recent breakout»
زمینهٔ گاوی آینهٔ کامل است: [H1,L1,H2,L2,H3] با H1<H2<H3، L1<L2، و L2 < H1.

⚠️ **تصحیحِ یک اشتباهِ خودم در فایلِ فصل:** در MDِ کتاب قیدِ همپوشانی را «H2 > L2»
نوشته بودم که با ترتیبِ زمانیِ L2→H2 **بدیهیاً درست** است و هیچ چیزی را فیلتر نمی‌کند.
قیدِ واقعیِ متن «بازگشت به بالای *نقطهٔ شکست*» است و نقطهٔ شکست L1 است، نه L2.
اینجا شکلِ درست (H2 > L1) پیاده شده و تصحیح در MDِ فصل ثبت می‌شود. اگر شکلِ بدیهی
می‌ماند، الگو از «stairs» به «هر سه کفِ نزولی» تنزل می‌کرد و تمایزش با micro-channelِ
فصلِ ۱۶ (S340) از بین می‌رفت.

ماشه و بریکت
-------------
LONG (fade در کانالِ خرسی):  close[t] ≤ L3 − f·ext   +   کندلِ روندیِ خرسی
                              (body ≥ body_k×range) ⇐ «fade the close of every strong
                              trend bar breakout … buy every bear trend bar that closes
                              below a prior bear stair»
SHORT: آینه.
entry_mode = 'close' : همان بارِ ماشه (ورود در open بارِ بعد).
entry_mode = 'stop'  : سبکِ محافظه‌کارِ خودِ Brooks — پس از ماشه «مسلح» می‌شویم و ورود
                       وقتی است که بازار برگردد: close[u] > high[u−1] (برای LONG).
                       تسلیح تا وقتی زمینهٔ stairs عوض نشده معتبر است ⇒ بدونِ پارامترِ نو.
SL = s · ext        TP = g · pull        ⇒ RR خودش شناور است (per-trade).

قیدهای امکان‌پذیریِ اجرا (نه پارامترِ تنظیم‌شونده):
    tp_pip ≥ 2×cost_pip  و  sl_pip ≥ cost_pip
معامله‌ای که هدفش از اسپرد کوچک‌تر است اصلاً قابلِ اجرا نیست؛ این قید ریزساختارِ بازار
است نه درجهٔ آزادی.

آزمونِ سطحِ خانواده (مسیرِ B پیش‌ثبت‌شده)
------------------------------------------
۷۲ عضو = k(3) × f(2) × g(3) × s(2) × entry_mode(2). **هیچ عضوی گزینش نمی‌شود.**
آماره = میانگینِ WR روی اعضای زنده. مدلِ صفر = جای‌گشتِ زمانی: همان تعدادِ ورود،
همان نسبتِ long/short، همان **مجموعهٔ بریکت‌های شناور** (برچسب‌ها جابه‌جا می‌شوند)،
همان صفِ بی‌همپوشانی. سدِ عبور: z ≥ 3.09σ (p_perm ≤ 0.001).

اجرا:
    python3 strategies/s364_stairs_family.py --asset XAUUSD --tf M5
    python3 strategies/s364_stairs_family.py --all          # همهٔ کارت‌ها، ذخیرهٔ مرحله‌به‌مرحله
"""
import os
import sys
import json
import argparse
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se          # noqa: E402

OUT = "results/_scan_S364"

# ---------------------- خانوادهٔ پیش‌ثبت‌شده (تغییرناپذیر) ----------------------
FAM_K = (2, 3, 5)                  # بازوی pivot
FAM_F = (0.70, 1.00)               # ورود = L3 − f·ext
FAM_G = (0.67, 0.75, 1.00)         # TP = g·pull
FAM_S = (1.00, 1.618)              # SL = s·ext   (تنها محورِ بیرونِ متن ⇒ عمداً غیررند)
FAM_MODE = ("close", "stop")
BODY_K = 0.50                      # «strong trend bar» = بدنه ≥ نصفِ دامنه (ثابت)

N_PERM = 500                       # کفِ v2.4
Z_BAR = 3.09                       # p_perm ≤ 0.001
MIN_TRADES = 15                    # کفِ زنده‌بودنِ یک عضو (نه کفِ H0؛ آن در RQS2 است)

TF_MAX_HOLD = {"M1": 200, "M5": 96, "M15": 40, "M30": 28,
               "H1": 20, "H4": 10, "D1": 8, "W1": 6}

CARDS = [("XAUUSD", tf) for tf in ("M5", "M15", "M30", "H1", "H4", "D1", "W1")] + \
        [("EURUSD", tf) for tf in ("M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1")]


# ------------------------------- تشخیصِ pivot -------------------------------
def _roll_max_prev(a, k):
    """max(a[i-k:i]) — فقط گذشته."""
    return pd.Series(a).rolling(k).max().shift(1).values


def _roll_min_prev(a, k):
    return pd.Series(a).rolling(k).min().shift(1).values


def _roll_max_next(a, k):
    """max(a[i+1:i+k+1]) — آینده؛ فقط برای *تعریفِ* pivot، و pivot تازه در بارِ i+k
    «تأیید» می‌شود، پس هیچ نگاهِ آینده‌ای به سیگنال نشت نمی‌کند."""
    return _roll_max_prev(a[::-1], k)[::-1]


def _roll_min_next(a, k):
    return _roll_min_prev(a[::-1], k)[::-1]


def pivot_flags(h, l, k):
    lmax = _roll_max_prev(h, k)
    rmax = _roll_max_next(h, k)
    lmin = _roll_min_prev(l, k)
    rmin = _roll_min_next(l, k)
    ph = np.nan_to_num(h > lmax, nan=False) & np.nan_to_num(h >= rmax, nan=False)
    pl = np.nan_to_num(l < lmin, nan=False) & np.nan_to_num(l <= rmin, nan=False)
    return ph.astype(bool), pl.astype(bool)


# --------------------- زمینهٔ stairs (یک‌بار به‌ازای هر k) ---------------------
def stairs_context(df, k):
    """
    خروجی: دیکشنری از آرایه‌های هم‌طولِ df —
      bear_ok, bear_ref(=L3), bear_ext, bear_pull, bear_seg
      bull_ok, bull_ref(=H3), bull_ext, bull_pull, bull_seg
    seg = شناسهٔ صحیحِ «زمینهٔ جاری»؛ با هر تغییرِ zigzag عوض می‌شود (برای حالتِ stop
    و برای «فقط اولین ماشه در هر زمینه»).
    """
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    n = len(df)
    ph, pl = pivot_flags(h, l, k)

    ev = []
    for i in np.flatnonzero(ph):
        ev.append((i + k, i, "H", h[i]))
    for i in np.flatnonzero(pl):
        ev.append((i + k, i, "L", l[i]))
    ev.sort(key=lambda e: (e[0], e[1]))

    out = {}
    for tag in ("bear", "bull"):
        out[f"{tag}_ok"] = np.zeros(n, dtype=bool)
        out[f"{tag}_ref"] = np.full(n, np.nan)
        out[f"{tag}_ext"] = np.full(n, np.nan)
        out[f"{tag}_pull"] = np.full(n, np.nan)
        out[f"{tag}_seg"] = np.full(n, -1, dtype=np.int64)

    piv = []          # zigzagِ متناوب: [(typ, px)]
    ptr = 0
    n_ev = len(ev)
    cur_bear = None
    cur_bull = None
    seg_bear = -1
    seg_bull = -1

    for t in range(n):
        changed = False
        while ptr < n_ev and ev[ptr][0] <= t:
            _, _, typ, px = ev[ptr]
            ptr += 1
            if piv and piv[-1][0] == typ:
                if (typ == "H" and px > piv[-1][1]) or (typ == "L" and px < piv[-1][1]):
                    piv[-1] = (typ, px)
                    changed = True
            else:
                piv.append((typ, px))
                changed = True
                if len(piv) > 8:
                    del piv[0]

        if changed:
            nb = _check_bear(piv)
            if nb != cur_bear:
                cur_bear = nb
                if nb is not None:
                    seg_bear += 1
            nu = _check_bull(piv)
            if nu != cur_bull:
                cur_bull = nu
                if nu is not None:
                    seg_bull += 1

        if cur_bear is not None:
            out["bear_ok"][t] = True
            out["bear_ref"][t] = cur_bear[0]
            out["bear_ext"][t] = cur_bear[1]
            out["bear_pull"][t] = cur_bear[2]
            out["bear_seg"][t] = seg_bear
        if cur_bull is not None:
            out["bull_ok"][t] = True
            out["bull_ref"][t] = cur_bull[0]
            out["bull_ext"][t] = cur_bull[1]
            out["bull_pull"][t] = cur_bull[2]
            out["bull_seg"][t] = seg_bull
    return out


def _check_bear(piv):
    """[L1,H1,L2,H2,L3] با L1>L2>L3، H1>H2، H2>L1 ⇒ (L3, ext, pull)."""
    if len(piv) < 5:
        return None
    t5 = [p[0] for p in piv[-5:]]
    if t5 != ["L", "H", "L", "H", "L"]:
        return None
    L1, H1, L2, H2, L3 = [p[1] for p in piv[-5:]]
    if not (L1 > L2 > L3):
        return None
    if not (H1 > H2):
        return None
    if not (H2 > L1):            # ⭐ قیدِ همپوشانیِ واقعیِ متن
        return None
    ext = L2 - L3
    pull = H2 - L2
    if ext <= 0 or pull <= 0:
        return None
    return (L3, ext, pull)


def _check_bull(piv):
    """[H1,L1,H2,L2,H3] با H1<H2<H3، L1<L2، L2<H1 ⇒ (H3, ext, pull)."""
    if len(piv) < 5:
        return None
    t5 = [p[0] for p in piv[-5:]]
    if t5 != ["H", "L", "H", "L", "H"]:
        return None
    H1, L1, H2, L2, H3 = [p[1] for p in piv[-5:]]
    if not (H1 < H2 < H3):
        return None
    if not (L1 < L2):
        return None
    if not (L2 < H1):            # ⭐ آینهٔ قیدِ همپوشانی
        return None
    ext = H3 - H2
    pull = H2 - L2
    if ext <= 0 or pull <= 0:
        return None
    return (H3, ext, pull)


# ------------------------- ساختِ سیگنالِ یک عضوِ خانواده -------------------------
def _first_per_segment(trigger, seg):
    """فقط اولین ماشه در هر زمینهٔ stairs (بدونِ پارامترِ نو)."""
    idx = np.arange(len(trigger))
    seg_change = np.empty(len(trigger), dtype=bool)
    seg_change[0] = True
    seg_change[1:] = seg[1:] != seg[:-1]
    last_start = np.maximum.accumulate(np.where(seg_change, idx, -1))
    prev_trig = np.maximum.accumulate(np.where(trigger, idx, -1))
    # اولین ماشه = ماشه‌ای که هیچ ماشهٔ قبلی در همین زمینه ندارد
    prev_before = np.concatenate(([-1], prev_trig[:-1]))
    return trigger & (prev_before < last_start)


def _armed_fire(trigger, ref, ext, pull, c, opp, long_side):
    """
    حالتِ stop (سبکِ محافظه‌کارِ خودِ Brooks): «enter on a stop **as the market reverses**».

    ⚠️ درسِ یک باگ: نسخهٔ اولِ این تابع تسلیح را به «شناسهٔ زمینهٔ stairs» گره زده بود.
    نتیجه‌اش این شد که **هیچ‌کدام از ۳۶ عضوِ حالتِ stop حتی یک معامله هم نساختند** —
    و علتش بازار نبود، خودِ کد بود: وقتی قیمت کفِ تازه‌ای می‌سازد (که دقیقاً همان
    چیزی است که ماشه را روشن می‌کند)، همان کف چند بار بعد به‌عنوان pivotِ تازه تأیید
    می‌شود، zigzag به‌روز می‌شود و شناسهٔ زمینه عوض می‌شود ⇒ تسلیح پیش از رسیدنِ
    چرخش نابود می‌شد. یعنی شرطِ نگهبانی، خودِ رویدادی را می‌کُشت که قرار بود منتظرش
    بماند. اگر این را نمی‌دیدم، «نیمی از خانواده مرده است» را به‌عنوان یافتهٔ بازار
    گزارش کرده بودم، در حالی که یافتهٔ ویرایشگر بود.

    تسلیحِ درست، بدونِ افزودنِ هیچ پارامترِ عددیِ نو:
      · با ماشه مسلح می‌شویم و سطحِ مرجع (پلهٔ قبلی، L3 یا H3) را **منجمد** می‌کنیم.
      · ورود در اولین باری که بازار می‌چرخد: close > high[t−1] (لانگ) / close < low[t−1].
      · اگر قیمت بدونِ چرخش به داخلِ کانال برگردد (close از سطحِ منجمد رد کند)،
        آزمونِ شکست بدونِ ما تمام شده ⇒ خلعِ سلاح.

    ⭐ `ext`/`pull` هم در **همان لحظهٔ ماشه** منجمد می‌شوند. اگر به‌جایش از زمینهٔ
    بارِ ورود خوانده می‌شدند، همان تلهٔ قبلی از درِ دیگر برمی‌گشت: زمینه تا لحظهٔ
    چرخش عوض شده و بریکتِ شناور صفر/نامعتبر می‌شد.
    """
    n = len(trigger)
    out = np.zeros(n, dtype=bool)
    ext_at = np.zeros(n)
    pull_at = np.zeros(n)
    armed = False
    frozen = f_ext = f_pull = np.nan
    for t in range(1, n):
        if armed:
            if (long_side and c[t] > opp[t - 1]) or ((not long_side) and c[t] < opp[t - 1]):
                out[t] = True
                ext_at[t] = f_ext
                pull_at[t] = f_pull
                armed = False
            elif (long_side and c[t] > frozen) or ((not long_side) and c[t] < frozen):
                armed = False
        if trigger[t]:
            armed = True
            frozen = ref[t]
            f_ext = ext[t]
            f_pull = pull[t]
    return out, ext_at, pull_at


def member_signals(df, ctx, f, g, s, mode, asset):
    """خروجی: long_sig, short_sig, sl_pip(array), tp_pip(array)."""
    o = df["open"].values.astype(float)
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    c = df["close"].values.astype(float)
    n = len(df)
    pip = se.ASSETS[asset]["pip"]
    cfg = se.ASSETS[asset]
    cost = cfg["spread_pip"] + 2.0 * cfg.get("slip_pip", 0.0)

    rng_bar = h - l
    bear_bar = (o - c) >= BODY_K * np.where(rng_bar > 0, rng_bar, np.inf)
    bull_bar = (c - o) >= BODY_K * np.where(rng_bar > 0, rng_bar, np.inf)

    # --- سمتِ LONG (fade در کانالِ خرسی) ---
    bok = ctx["bear_ok"]
    btrig = bok & bear_bar & (c <= (ctx["bear_ref"] - f * ctx["bear_ext"]))
    btrig = np.nan_to_num(btrig, nan=False).astype(bool)
    ext_l = np.nan_to_num(ctx["bear_ext"], nan=0.0)
    pull_l = np.nan_to_num(ctx["bear_pull"], nan=0.0)
    if mode == "close":
        long_sig = _first_per_segment(btrig, ctx["bear_seg"])
    else:
        long_sig, ext_l, pull_l = _armed_fire(
            btrig, np.nan_to_num(ctx["bear_ref"], nan=-np.inf),
            ext_l, pull_l, c, h, True)

    # --- سمتِ SHORT (fade در کانالِ گاوی) ---
    uok = ctx["bull_ok"]
    utrig = uok & bull_bar & (c >= (ctx["bull_ref"] + f * ctx["bull_ext"]))
    utrig = np.nan_to_num(utrig, nan=False).astype(bool)
    ext_s = np.nan_to_num(ctx["bull_ext"], nan=0.0)
    pull_s = np.nan_to_num(ctx["bull_pull"], nan=0.0)
    if mode == "close":
        short_sig = _first_per_segment(utrig, ctx["bull_seg"])
    else:
        short_sig, ext_s, pull_s = _armed_fire(
            utrig, np.nan_to_num(ctx["bull_ref"], nan=np.inf),
            ext_s, pull_s, c, l, False)

    # --- بریکتِ شناورِ per-trade ---
    sl_pip = np.zeros(n)
    tp_pip = np.zeros(n)
    sl_pip[long_sig] = (s * ext_l[long_sig]) / pip
    tp_pip[long_sig] = (g * pull_l[long_sig]) / pip
    sl_pip[short_sig] = (s * ext_s[short_sig]) / pip
    tp_pip[short_sig] = (g * pull_s[short_sig]) / pip

    feasible = (tp_pip >= 2.0 * cost) & (sl_pip >= cost)
    long_sig = long_sig & feasible
    short_sig = short_sig & feasible
    return long_sig, short_sig, sl_pip, tp_pip


# ------------------------------ شبیه‌سازیِ برداری ------------------------------
def _sim_vec(o, h, l, c, picks, is_long, sl_v, tp_v, pip, mh, cost, n):
    """برداری: برای مجموعه‌ای از بارهای سیگنال، برد/باخت و بارِ خروج."""
    eb = picks + 1
    keep = eb < n - 1
    eb = eb[keep]; is_long = is_long[keep]; sl_v = sl_v[keep]; tp_v = tp_v[keep]
    picks = picks[keep]
    if eb.size == 0:
        return None
    off = np.arange(mh)
    idx = np.minimum(eb[:, None] + off[None, :], n - 1)
    H = h[idx]; L = l[idx]; C = c[idx]
    ent = o[eb]
    sl_d = sl_v * pip
    tp_d = tp_v * pip
    sl_lvl = np.where(is_long, ent - sl_d, ent + sl_d)[:, None]
    tp_lvl = np.where(is_long, ent + tp_d, ent - tp_d)[:, None]
    ilong = is_long[:, None]
    hit_sl = np.where(ilong, L <= sl_lvl, H >= sl_lvl)
    hit_tp = np.where(ilong, H >= tp_lvl, L <= tp_lvl)
    BIG = mh + 5
    f_sl = np.where(hit_sl.any(1), hit_sl.argmax(1), BIG)
    f_tp = np.where(hit_tp.any(1), hit_tp.argmax(1), BIG)
    win = f_tp < f_sl                       # مساوی ⇒ SL مقدم (بدترین‌حالت)
    timeout = (f_sl >= BIG) & (f_tp >= BIG)
    if timeout.any():
        last = C[:, -1]
        pnl = np.where(is_long, last - ent, ent - last) / pip - cost
        win = np.where(timeout, pnl > 0, win)
    exit_off = np.minimum(np.minimum(f_sl, f_tp), mh - 1)
    exit_bar = eb + exit_off
    return picks, win, exit_bar


def _wr_no_overlap(picks, win, exit_bar):
    order = np.argsort(picks, kind="stable")
    last_exit = -1
    wins = used = 0
    for i in order:
        p = picks[i]
        if p <= last_exit:
            continue
        used += 1
        if win[i]:
            wins += 1
        last_exit = exit_bar[i]
    if used == 0:
        return None, 0
    return 100.0 * wins / used, used


# --------------------------------- اجرای کارت ---------------------------------
def run_card(asset, tf, n_perm=N_PERM, seed=364, save=True):
    path = f"data/{asset}_{tf}.csv"
    if not os.path.exists(path):
        return dict(asset=asset, tf=tf, error="no data")
    df = se.load_data(path)
    n = len(df)
    o = df["open"].values.astype(float)
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    c = df["close"].values.astype(float)
    pip = se.ASSETS[asset]["pip"]
    cfg = se.ASSETS[asset]
    cost = cfg["spread_pip"] + 2.0 * cfg.get("slip_pip", 0.0)
    mh = TF_MAX_HOLD.get(tf, 40)
    warm = min(260, max(30, n // 8))
    rng = np.random.default_rng(seed)

    print(f"=== S364 FAMILY :: {asset}-{tf} (bars={n:,}) ===", flush=True)
    ctxs = {}
    for k in FAM_K:
        ctxs[k] = stairs_context(df, k)
        print(f"    ctx k={k}: bear_bars={int(ctxs[k]['bear_ok'].sum()):,} "
              f"bull_bars={int(ctxs[k]['bull_ok'].sum()):,}", flush=True)

    members = []
    for k in FAM_K:
        for f in FAM_F:
            for g in FAM_G:
                for s in FAM_S:
                    for mode in FAM_MODE:
                        members.append(dict(k=k, f=f, g=g, s=s, mode=mode))

    per_member = []
    prepared = []
    for mi, m in enumerate(members):
        ls, ss, slv, tpv = member_signals(df, ctxs[m["k"]], m["f"], m["g"],
                                          m["s"], m["mode"], asset)
        ls[:warm] = False; ss[:warm] = False
        ls[n - mh - 2:] = False; ss[n - mh - 2:] = False
        if int(ls.sum() + ss.sum()) < MIN_TRADES:
            continue
        tr = se.simulate_trades(df, ls, ss, slv, tpv, asset, max_hold=mh,
                                allow_overlap=False)
        if tr is None or len(tr) < MIN_TRADES:
            continue
        wr = 100.0 * float((tr["pnl_pip"] > 0).sum()) / len(tr)
        sig = np.where(ls | ss)[0]
        per_member.append(dict(**m, n=int(len(tr)), wr=round(wr, 3),
                               n_long=int(ls.sum()), n_short=int(ss.sum()),
                               med_sl=round(float(np.median(slv[sig])), 2),
                               med_tp=round(float(np.median(tpv[sig])), 2),
                               net_pip=round(float(tr["pnl_pip"].sum()), 1)))
        prepared.append(dict(k=len(sig), is_long=ls[sig].copy(),
                             sl=slv[sig].copy(), tp=tpv[sig].copy()))
        if (mi + 1) % 18 == 0:
            print(f"    ... member {mi+1}/{len(members)}", flush=True)

    if not per_member:
        res = dict(asset=asset, tf=tf, bars=n, verdict="NO_VIABLE_MEMBER",
                   n_members_alive=0, n_members_total=len(members))
        if save:
            _save(res, asset, tf)
        print("    !!! no viable member", flush=True)
        return res

    wr_obs = float(np.mean([m["wr"] for m in per_member]))
    wr_min = min(m["wr"] for m in per_member)
    wr_max = max(m["wr"] for m in per_member)
    n_tot = int(sum(m["n"] for m in per_member))
    print(f"\n  OBSERVED family mean WR = {wr_obs:.3f}%  Σn={n_tot:,} "
          f"alive={len(per_member)}/{len(members)}", flush=True)
    print(f"           member range = [{wr_min:.2f}, {wr_max:.2f}]", flush=True)

    valid_bars = np.arange(warm, n - mh - 2)
    perm_stats = []
    for b in range(n_perm):
        wrs = []
        for pr in prepared:
            kk = pr["k"]
            if valid_bars.size <= kk:
                continue
            pick = rng.choice(valid_bars, size=kk, replace=False)
            perm = rng.permutation(kk)
            out = _sim_vec(o, h, l, c, pick, pr["is_long"][perm],
                           pr["sl"][perm], pr["tp"][perm], pip, mh, cost, n)
            if out is None:
                continue
            w, used = _wr_no_overlap(*out)
            if w is not None and used >= 5:
                wrs.append(w)
        if wrs:
            perm_stats.append(float(np.mean(wrs)))
        if (b + 1) % 100 == 0:
            print(f"    perm {b+1}/{n_perm} ...", flush=True)

    perm_stats = np.array(perm_stats, dtype=float)
    pm = float(perm_stats.mean()) if perm_stats.size else float("nan")
    ps = float(perm_stats.std(ddof=1)) if perm_stats.size > 1 else float("nan")
    se_binom = float(np.sqrt(max(pm, 1e-9) * (100.0 - pm) / max(n_tot, 1)))
    sd_use = max(ps, se_binom) if np.isfinite(ps) else se_binom
    lift = wr_obs - pm
    z = lift / sd_use if sd_use > 0 else float("inf")
    p_perm = float((np.sum(perm_stats >= wr_obs) + 1) / (perm_stats.size + 1))
    verdict = "FAMILY_CONFIRMED" if z >= Z_BAR else "FAMILY_DEAD"

    print(f"\n  NULL mean={pm:.3f}%  sd_perm={ps:.3f}  sd_used={sd_use:.3f}", flush=True)
    print(f"  LIFT = {lift:+.3f}pp   z = {z:.2f}σ   p_perm = {p_perm:.4f}", flush=True)
    print(f"  >>> {verdict}\n", flush=True)

    res = dict(asset=asset, tf=tf, bars=n, warm=warm, max_hold=mh,
               n_members_total=len(members), n_members_alive=len(per_member),
               wr_obs=round(wr_obs, 3), wr_min=wr_min, wr_max=wr_max,
               n_total_trades=n_tot,
               null_mean=round(pm, 3), null_sd_perm=round(ps, 3),
               sd_used=round(sd_use, 3), lift=round(lift, 3),
               z=round(z, 3), p_perm=round(p_perm, 5), n_perm=int(perm_stats.size),
               verdict=verdict, members=per_member)
    if save:
        _save(res, asset, tf)
    return res


def _save(res, asset, tf):
    os.makedirs(OUT, exist_ok=True)
    with open(f"{OUT}/{asset}_{tf}.json", "w") as fh:
        json.dump(res, fh, indent=1, ensure_ascii=False)
    print(f"    saved -> {OUT}/{asset}_{tf}.json", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", default="XAUUSD")
    ap.add_argument("--tf", default="M5")
    ap.add_argument("--perm", type=int, default=N_PERM)
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    if a.all:
        for asset, tf in CARDS:
            try:
                run_card(asset, tf, n_perm=a.perm)
            except Exception as exc:      # noqa: BLE001
                print(f"!!! {asset}-{tf} failed: {exc}", flush=True)
                import traceback
                traceback.print_exc()
    else:
        run_card(a.asset, a.tf, n_perm=a.perm)


if __name__ == "__main__":
    main()
