# -*- coding: utf-8 -*-
"""
غربالِ سه‌مرحله‌ایِ «کدام لایهٔ روی سایت شانسِ واقعیِ عبور از RQS2 v2.4 را دارد؟»
================================================================================

چرا این ابزار لازم است
----------------------
`user note` می‌خواهد **همهٔ** لایه‌های روی سایت زیرِ معیارِ RQS2 بازداوری شوند و
بعد بپرسد «کدام شانسِ بیشتری برای احیا دارد؟». بازداوریِ کاملِ هر لایه گران است
(هر کارت = بازتولیدِ سیگنال + نولِ ۲۰۰۰ قرعه‌ای + هر ۱۱ دروازه). پس اولویت‌بندی
لازم است — ولی اولویت‌بندی **با حدس زدن** دقیقاً همان اشتباهی است که این پروژه
بارها تاوانش را داده (پذیرشِ ۹۷.۶ برای لایه‌ای که ۲۸.۸ بود).

بنابراین این ابزار اولویت را **اندازه می‌گیرد**، نه حدس. و فقط دو چیز را
اندازه می‌گیرد که بیشترین کشتار را دارند و **بدونِ بازتولیدِ منطقِ سیگنال**
قابلِ محاسبه‌اند:

  ① `H2` — لبهٔ هندسیِ هزینه‌دار.  ریاضیِ محض، صفر ابهام:
        RR = TP/SL ≥ 0.5           (کفِ صریحِ اسپک)
        WR − (SL+c)/(SL+TP) ≥ 3pp  (مازادِ سربه‌سرِ هزینه‌دار)
     این دروازه فقط به هندسه و WRِ **بایگانی‌شده** نیاز دارد. هر لایه‌ای که
     اینجا بیفتد، **حسابیاً** مرده است و خرج کردنِ محاسبه رویش اتلاف است —
     همان درسی که S327 با RR=0.371 و S326 با RR≈0.30 به پروژه داد.

  ② `H3` — مهارت نسبت به مدلِ صفرِ **اندازه‌گیری‌شده**.  این گلوگاهِ واقعیِ
     پروژه است. نکتهٔ کلیدی: مدلِ صفر **به منطقِ سیگنال کاری ندارد** — فقط به
     (کارت، سمت، هندسه، افقِ نگهداری) وابسته است. پس می‌توان آن را برای هر
     لایه محاسبه کرد بدونِ اینکه یک خط از کدِ آن لایه اجرا شود:
        · مبنای بی‌قید = برآمدِ همان براکت روی **هر** کندلِ کارت
        · جای‌گشت      = K قرعهٔ تصادفیِ ناهم‌پوشان به اندازهٔ n
        · lift = WR_بایگانی − max(بی‌قید، میانگینِ جای‌گشت)
        · z    = lift / sd_جای‌گشت    ،   p_perm = سهمِ قرعه‌هایی که ≥ WR شدند
     سدِ v2.4: `lift ≥ 4pp` و `p_perm ≤ 0.001` و `perm_k ≥ 500`.

⚠️ آنچه این ابزار **ادعا نمی‌کند**
---------------------------------
این یک **غربال** است، نه یک حکم. عبور از این غربال یعنی «ارزشِ خرج‌کردنِ
بازداوریِ کامل را دارد»، نه «پذیرفته است». نُه دروازهٔ دیگر (`H5` چندگانگی،
`H6` تقویمی، `H7` خارج‌ازنمونه، `H8` ریسکِ دنباله، `H10` رژیمی) اینجا سنجیده
**نمی‌شوند** و هر کدام می‌توانند لایه را بکشند. برعکسش اما قاطع است: افتادن در
`H2` یا `H3` در این غربال، با هیچ دروازهٔ دیگری جبران نمی‌شود، چون دروازه‌ها
جبران‌ناپذیرند.

⚠️ و یک صداقتِ آماریِ دوم: `WR` و `n` از **بایگانی** خوانده می‌شوند، یعنی از
پیکربندی‌ای که با جست‌وجو انتخاب شده. پس `z`ِ این غربال یک برآوردِ **خوش‌بین**
است (همان هشداری که حسابرسیِ §۵.۲ دربارهٔ `z_oos` داد). لایه‌ای که **حتی با
برآوردِ خوش‌بین** به سد نرسد، با برآوردِ صادقانه قطعاً نمی‌رسد ⇒ غربال در جهتِ
درست خطا می‌کند: کسی را به‌ناحق حذف نمی‌کند.

اجرا:
    python3 tools/rqs2_site_triage.py --k 500
    python3 tools/rqs2_site_triage.py --k 2000 --only S323,S344,S345
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se   # noqa: E402

OUT_DIR = "results/_triage_site_v24"


# ═══════════════════════════════════════════════════════════════════════════
# فهرستِ رسمیِ لایه‌های روی سایت — از `web_tool/src/strategy_registry.ts`
# استخراج شده، نه از حافظه. هر ردیف: (لایه، کارت، سمت، هندسه، افق).
#
# «هندسه» دو شکل دارد و هر دو عیناً همان چیزی است که در پیکربندیِ TSِ مستقر
# نوشته شده — چون سؤال این است که «آن چیزی که کاربر واقعاً می‌گیرد چقدر
# می‌ارزد»، نه «بهترین نسخهٔ ممکنِ این ایده».
#     ('pip',  sl_pip, tp_pip)      هندسهٔ ثابت
#     ('atr',  sl_mult, tp_mult, p) هندسهٔ شناور بر حسبِ ATR(p)
# ═══════════════════════════════════════════════════════════════════════════
SITE_LAYERS = [
    # ── XAUUSD-M5 ────────────────────────────────────────────────────────
    dict(layer="S330", card="XAUUSD-M5", side="both", geom=("atr", 2.2, 2.2, 14),
         hold=48, n=49, wr=69.4, pf=1.91,
         src="revived_strategies.ts:264 kSl=1.0 kTp=1.0×OR(12bar) ⇒ RR=1.00 دقیق؛ عرضِ براکت تقریبی"),
    dict(layer="S328", card="XAUUSD-M5", side="short", geom=("pip", 62.0, 43.0),
         hold=24, n=41, wr=78.0, pf=2.33, src="revived_strategies.ts:188"),
    dict(layer="S334", card="XAUUSD-M5", side="short", geom=("pip", 110.0, 125.0),
         hold=20, n=47, wr=61.7, pf=1.61, src="revived_strategies.ts:852"),
    dict(layer="S335", card="XAUUSD-M5", side="long", geom=("pip", 170.0, 255.0),
         hold=60, n=51, wr=62.7, pf=2.22, src="s335_reflex_cycle.ts:184"),
    dict(layer="S326", card="XAUUSD-M5", side="both", geom=("atr", 3.1, 1.15, 14),
         hold=24, n=77, wr=84.4, pf=1.66, src="streak_reversal_s326.ts:44"),

    # ── XAUUSD-M15 ───────────────────────────────────────────────────────
    dict(layer="S333", card="XAUUSD-M15", side="long", geom=("pip", 200.0, 240.0),
         hold=96, n=51, wr=62.8, pf=2.30, src="s333_pullback.ts:72"),
    dict(layer="S332", card="XAUUSD-M15", side="both", geom=("pip", 190.0, 285.0),
         hold=64, n=53, wr=60.4, pf=1.90, src="squeeze_s332.ts:118"),
    dict(layer="S324", card="XAUUSD-M15", side="long", geom=("atr", 2.4, 0.8, 14),
         hold=48, n=62, wr=87.1, pf=1.92, src="revived_strategies.ts:496"),
    dict(layer="S322", card="XAUUSD-M15", side="long", geom=("atr", 2.5, 3.3, 14),
         hold=56, n=51, wr=60.8, pf=1.89, src="revived_strategies.ts:382"),
    dict(layer="S323", card="XAUUSD-M15", side="long", geom=("atr", 1.8, 1.5, 14),
         hold=96, n=92, wr=69.6, pf=1.64, src="revived_strategies.ts:730"),
    dict(layer="S335", card="XAUUSD-M15", side="long", geom=("pip", 200.0, 340.0),
         hold=64, n=51, wr=62.7, pf=2.22, src="s335_reflex_cycle.ts:190"),
    dict(layer="S344", card="XAUUSD-M15", side="short", geom=("pip", 220.0, 340.0),
         hold=32, n=92, wr=64.13, pf=2.078, src="trend_from_open_s344.ts:56"),
    dict(layer="S345", card="XAUUSD-M15", side="long", geom=("pip", 240.0, 400.0),
         hold=40, n=101, wr=62.38, pf=2.299, src="reversal_day_s345.ts:75"),
    dict(layer="S310", card="XAUUSD-M15", side="long", geom=("pip", 170.0, 250.0),
         hold=32, n=45, wr=60.0, pf=1.74, src="end_of_month_drift.ts:27"),
    dict(layer="S312", card="XAUUSD-M15", side="long", geom=("pip", 295.0, 295.0),
         hold=48, n=68, wr=60.9, pf=2.50, src="strategy_registry.ts:328 s312Layer(295,295,48)"),

    # ── XAUUSD-M30 ───────────────────────────────────────────────────────
    dict(layer="S333", card="XAUUSD-M30", side="long", geom=("pip", 380.0, 420.0),
         hold=80, n=42, wr=66.7, pf=2.48, src="s333_pullback.ts:74"),
    dict(layer="S313", card="XAUUSD-M30", side="both", geom=("atr", 3.2, 2.15, 14),
         hold=48, n=67, wr=67.8, pf=3.27, src="squeeze_revival_s313.ts:59+64"),
    dict(layer="S324", card="XAUUSD-M30", side="short", geom=("atr", 3.1, 1.2, 14),
         hold=48, n=75, wr=82.7, pf=1.59, src="revived_strategies.ts:497"),
    dict(layer="S321", card="XAUUSD-M30", side="both", geom=("atr", 2.7, 2.7, 14),
         hold=36, n=78, wr=65.4, pf=1.75, src="revived_strategies.ts:613"),
    dict(layer="S326", card="XAUUSD-M30", side="both", geom=("atr", 3.5, 1.30, 14),
         hold=48, n=54, wr=79.6, pf=1.42, src="streak_reversal_s326.ts:45"),
    dict(layer="S323", card="XAUUSD-M30", side="long", geom=("atr", 2.1, 1.3, 14),
         hold=48, n=140, wr=77.1, pf=1.75, src="revived_strategies.ts:731"),
    dict(layer="S312", card="XAUUSD-M30", side="long", geom=("pip", 295.0, 295.0),
         hold=36, n=148, wr=61.6, pf=1.94, src="strategy_registry.ts s312Layer(295,295,36)"),

    # ── XAUUSD-H1 ────────────────────────────────────────────────────────
    dict(layer="S333", card="XAUUSD-H1", side="long", geom=("pip", 450.0, 520.0),
         hold=64, n=74, wr=62.2, pf=1.85, src="s333_pullback.ts:76"),
    dict(layer="S313", card="XAUUSD-H1", side="both", geom=("atr", 3.2, 2.15, 14),
         hold=48, n=59, wr=67.8, pf=3.27, src="squeeze_revival_s313.ts:59"),
    dict(layer="S328", card="XAUUSD-H1", side="short", geom=("pip", 195.0, 210.0),
         hold=24, n=34, wr=70.6, pf=2.43, src="revived_strategies.ts:189"),
    dict(layer="S323", card="XAUUSD-H1", side="long", geom=("atr", 1.8, 1.7, 14),
         hold=36, n=35, wr=71.4, pf=2.14, src="revived_strategies.ts:732"),
    dict(layer="S335", card="XAUUSD-H1", side="long", geom=("pip", 480.0, 720.0),
         hold=40, n=49, wr=61.2, pf=1.85, src="s335_reflex_cycle.ts:196"),
    dict(layer="S312", card="XAUUSD-H1", side="long", geom=("pip", 395.0, 395.0),
         hold=24, n=125, wr=60.9, pf=2.04, src="strategy_registry.ts s312Layer(395,395,24)"),

    # ── XAUUSD-H4 ────────────────────────────────────────────────────────
    dict(layer="S340", card="XAUUSD-H4", side="both", geom=("pip", 520.0, 780.0),
         hold=20, n=61, wr=65.6, pf=2.13, src="micro_channel_s340.ts:51"),
    dict(layer="S332", card="XAUUSD-H4", side="both", geom=("pip", 350.0, 500.0),
         hold=24, n=70, wr=65.7, pf=1.99, src="squeeze_s332.ts:110"),

    # ── EURUSD ───────────────────────────────────────────────────────────
    dict(layer="S334", card="EURUSD-M5", side="short", geom=("pip", 12.2, 13.7),
         hold=24, n=45, wr=66.7, pf=1.62, src="revived_strategies.ts:854"),
    dict(layer="S326", card="EURUSD-M15", side="both", geom=("atr", 3.5, 1.30, 14),
         hold=48, n=98, wr=81.6, pf=1.32, src="streak_reversal_s326.ts:46"),
    dict(layer="S345", card="EURUSD-M30", side="short", geom=("pip", 20.0, 33.0),
         hold=28, n=40, wr=62.50, pf=2.382, src="reversal_day_s345.ts:82"),
]


# ═══════════════════════════════════════════════════════════════════════════
def atr_series(df, p=14):
    """ATRِ وایلدر — کاملاً causal (فقط از کندل‌های تا `i`)."""
    h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    pc = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    out = np.full(len(tr), np.nan)
    if len(tr) <= p:
        return out
    out[p - 1] = tr[:p].mean()
    a = 1.0 / p
    for i in range(p, len(tr)):
        out[i] = out[i - 1] + a * (tr[i] - out[i - 1])
    return out


def outcome_table(df, asset, sl_pip_arr, tp_pip_arr, mh, side):
    """
    برآمدِ یک ورودِ فرضی در **هر** کندل، یک‌بار و برداری.

    قراردادِ اجرا عیناً همان `simulate_trades` است تا مبنا با لایه قابلِ مقایسه
    بماند: ورود در `open` کندلِ i+1؛ در هر کندل اول SL بعد TP بررسی می‌شود
    (اگر هر دو در یک کندل بخورند ⇒ **باخت**، محافظه‌کارانه)؛ نرسیدن تا `mh`
    ⇒ خروجِ زمانی روی `close` با کسرِ هزینهٔ کاملِ رفت‌وبرگشت.

    چرا «اول SL بعد TP»: چون در کندلِ واحد ترتیبِ واقعیِ برخورد نامعلوم است و
    هر فرضِ خوش‌بینانه‌ای در سمتِ *مبنا* سدِ مهارت را مصنوعاً بالا و در سمتِ
    *لایه* آن را مصنوعاً پایین می‌برد. یک قراردادِ واحد برای هر دو = مقایسهٔ منصفانه.
    """
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    n = len(df)
    cfg = se.ASSETS[asset]
    pip = cfg["pip"]
    cost = cfg["spread_pip"] + 2 * cfg.get("slip_pip", 0.0)

    sl_d = sl_pip_arr * pip
    tp_d = tp_pip_arr * pip

    eb = np.arange(n) + 1
    live = (eb < n) & np.isfinite(sl_d) & np.isfinite(tp_d) & (sl_d > 0) & (tp_d > 0)
    ent = np.where(live, o[np.minimum(eb, n - 1)], np.nan)

    res = np.zeros(n, dtype=np.int8)
    if side == "long":
        sl_lv, tp_lv = ent - sl_d, ent + tp_d
    else:
        sl_lv, tp_lv = ent + sl_d, ent - tp_d

    for j in range(mh):
        k = eb + j
        openslot = live & (res == 0) & (k < n)
        if not openslot.any():
            break
        kk = np.minimum(k, n - 1)
        if side == "long":
            lose = openslot & (l[kk] <= sl_lv)
            win = openslot & (~lose) & (h[kk] >= tp_lv)
        else:
            lose = openslot & (h[kk] >= sl_lv)
            win = openslot & (~lose) & (l[kk] <= tp_lv)
        res[lose] = -1
        res[win] = 1

    kend = np.minimum(eb + mh, n)
    to = live & (res == 0) & (kend > eb)
    if to.any():
        last = c[np.maximum(kend - 1, 0)]
        gain = (last - ent) / pip if side == "long" else (ent - last) / pip
        res[to] = np.where((gain - cost)[to] > 0, 1, -1)
    return res


def hold_bars(res, df, sl_pip_arr, tp_pip_arr, mh, asset, side):
    """افقِ اشغالِ هر ورود (برای اعمالِ قاعدهٔ ناهم‌پوشانی در قرعه‌ها).

    تقریبِ محافظه‌کار: `mh` کندل. این تقریب تعدادِ ورودهای ممکنِ یک قرعه را
    **کم‌تر** می‌کند، پس قرعه‌ها را از لایه سخت‌تر نمی‌گیرد و سدِ مهارت را
    مصنوعاً پایین نمی‌آورد.
    """
    return int(mh)


def permutation_null(res, n_draw, hold, k, rng):
    """
    K قرعهٔ ناهم‌پوشانِ تصادفی به اندازهٔ `n_draw` ⇒ توزیعِ WRِ «بی‌مهارت».

    نکتهٔ طراحی: قرعه فقط **زمان‌بندی** را تصادفی می‌کند و همه‌چیزِ دیگر
    (سمت، هندسه، افق، خودِ سریِ قیمت و رانشش) را دست‌نخورده نگه می‌دارد. پس
    اختلافِ لایه با این توزیع، دقیقاً «مهارتِ زمان‌بندی» است و نه رانشِ دارایی —
    همان چیزی که RQS+ نمی‌دید و RQS2 برای دیدنش ساخته شد.
    """
    valid = np.where(res != 0)[0]
    if len(valid) < n_draw * 2:
        return None
    out = np.empty(k, dtype=float)
    hi = len(res)
    for t in range(k):
        # نمونه‌گیریِ ناهم‌پوشان: نقاطِ شروعِ تصادفی، سپس حذفِ برخوردها
        cand = rng.choice(valid, size=min(len(valid), n_draw * 6), replace=False)
        cand.sort()
        picked = []
        last_end = -1
        for s in cand:
            if s > last_end:
                picked.append(s)
                last_end = s + hold
                if len(picked) == n_draw:
                    break
        if len(picked) < n_draw:
            # داده برای ناهم‌پوشانیِ کامل کوتاه است ⇒ با آنچه هست ادامه بده
            if not picked:
                return None
        p = np.asarray(picked)
        out[t] = float((res[p] == 1).mean() * 100.0)
    return out


def be_cost(sl, tp, c):
    d = sl + tp
    return None if d <= 0 else (sl + c) / d * 100.0


# ═══════════════════════════════════════════════════════════════════════════
def run_one(spec, k, rng, cache):
    card = spec["card"]
    asset, tf = card.split("-")
    path = f"data/{asset}_{tf}.csv"
    if not os.path.exists(path):
        return dict(**{q: spec[q] for q in ("layer", "card", "side")},
                    status="NO_DATA")
    if card not in cache:
        cache[card] = se.load_data(path)
    df = cache[card]
    n_bars = len(df)

    g = spec["geom"]
    pip = se.ASSETS[asset]["pip"]
    if g[0] == "pip":
        sl_arr = np.full(n_bars, float(g[1]))
        tp_arr = np.full(n_bars, float(g[2]))
        sl_med, tp_med = float(g[1]), float(g[2])
    else:
        a = atr_series(df, int(g[3])) / pip          # ATR بر حسبِ pip
        sl_arr = a * float(g[1])
        tp_arr = a * float(g[2])
        fin = np.isfinite(sl_arr)
        sl_med = float(np.nanmedian(sl_arr[fin]))
        tp_med = float(np.nanmedian(tp_arr[fin]))

    cost = se.ASSETS[asset]["spread_pip"] + 2 * se.ASSETS[asset].get("slip_pip", 0.0)
    rr = tp_med / sl_med if sl_med > 0 else 0.0
    be = be_cost(sl_med, tp_med, cost)
    excess = None if be is None else spec["wr"] - be

    # مدلِ صفر: برای لایهٔ دوسویه، مبنا با وزنِ ۵۰/۵۰ ترکیب می‌شود (سهمِ واقعیِ
    # سمت‌ها در بایگانی ثبت نشده؛ ۵۰/۵۰ خنثی‌ترین فرضِ ممکن است و در گزارش
    # صریحاً علامت می‌خورد).
    sides = ["long", "short"] if spec["side"] == "both" else [spec["side"]]
    mh = int(spec["hold"])
    uncond, perm_mean, perm_sd, pvals = [], [], [], []
    for sd_ in sides:
        res = outcome_table(df, asset, sl_arr, tp_arr, mh, sd_)
        v = res[res != 0]
        if len(v) == 0:
            return dict(**{q: spec[q] for q in ("layer", "card", "side")}, status="NO_OUTCOME")
        uncond.append(float((v == 1).mean() * 100.0))
        draws = permutation_null(res, int(spec["n"]), mh, k, rng)
        if draws is None:
            return dict(**{q: spec[q] for q in ("layer", "card", "side")}, status="SHORT_DATA")
        perm_mean.append(float(draws.mean()))
        perm_sd.append(float(draws.std(ddof=1)))
        pvals.append(float((draws >= spec["wr"]).sum() + 1) / (k + 1))

    u = float(np.mean(uncond))
    pm = float(np.mean(perm_mean))
    ps = float(np.mean(perm_sd))
    pv = float(np.mean(pvals))
    ref = max(u, pm)
    lift = spec["wr"] - ref
    z = lift / ps if ps > 0 else 0.0

    h2 = (rr >= 0.5) and (excess is not None and excess >= 3.0)
    h3 = (lift >= 4.0) and (pv <= 0.001) and (k >= 500)

    return dict(
        layer=spec["layer"], card=card, side=spec["side"], n=spec["n"],
        wr=spec["wr"], pf=spec["pf"], sl_pip=round(sl_med, 1), tp_pip=round(tp_med, 1),
        rr=round(rr, 3), be_cost=None if be is None else round(be, 2),
        excess_pp=None if excess is None else round(excess, 2),
        uncond_wr=round(u, 2), perm_mean=round(pm, 2), perm_sd=round(ps, 3),
        lift_pp=round(lift, 2), z=round(z, 3), p_perm=round(pv, 5), perm_k=k,
        H2=h2, H3=h3, status="OK", src=spec["src"],
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=500)
    ap.add_argument("--only", default="")
    ap.add_argument("--seed", type=int, default=20260802)
    a = ap.parse_args()

    keep = set(x.strip() for x in a.only.split(",") if x.strip())
    rng = np.random.default_rng(a.seed)
    os.makedirs(OUT_DIR, exist_ok=True)
    cache, rows = {}, []

    for spec in SITE_LAYERS:
        if keep and spec["layer"] not in keep:
            continue
        r = run_one(spec, a.k, rng, cache)
        rows.append(r)
        if r.get("status") != "OK":
            print(f"{r['layer']:5s} {r['card']:12s} -> {r['status']}", flush=True)
            continue
        flag = "PASS" if (r["H2"] and r["H3"]) else ("H2✗" if not r["H2"] else "H3✗")
        print(f"{r['layer']:5s} {r['card']:12s} {r['side']:5s} n={r['n']:4d} "
              f"WR={r['wr']:5.2f} RR={r['rr']:5.3f} exc={str(r['excess_pp']):>7s} "
              f"null={r['perm_mean']:5.2f} lift={r['lift_pp']:6.2f} z={r['z']:5.2f} "
              f"p={r['p_perm']:.5f}  {flag}", flush=True)

    ok = [r for r in rows if r.get("status") == "OK"]
    ok.sort(key=lambda r: -r["z"])
    path = os.path.join(OUT_DIR, f"triage_k{a.k}.json")
    with open(path, "w") as f:
        json.dump(dict(k=a.k, seed=a.seed, rows=rows), f, indent=1, ensure_ascii=False)
    print(f"\n--- رتبه‌بندیِ نهایی بر اساسِ z (سدِ v2.4: z≥3.09 و p≤0.001) ---")
    for r in ok[:12]:
        print(f"  {r['z']:6.2f}σ  p={r['p_perm']:.5f}  {r['layer']} {r['card']} "
              f"(n={r['n']}, lift={r['lift_pp']}pp, H2={'✓' if r['H2'] else '✗'})")
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
