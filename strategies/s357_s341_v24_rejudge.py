# -*- coding: utf-8 -*-
"""
S357 — بازداوریِ صادقانهٔ لایهٔ **S341 (Brooks Swing-Fade)** با موتورِ RQS2 v2.4
==============================================================================

پیش‌ثبت: `results/S357_PREREGISTRATION_S341_V24_REJUDGE.md` (commitِ جداگانه،
**پیش از** اجرای این اسکریپت). هیچ پارامتری در مرحلهٔ ۱ جست‌وجو نمی‌شود؛ همه از
`strategies/s341_swing_fade_h1_revived.py::CONFIG` قفل شده‌اند.

چرا این اسکریپت لازم است
------------------------
چهار عددِ روی سایت (`۹۴.۷`, `۸۹.۸`, `۸۹.۷`, `۹۴.۵`) همه **`RQS+`** هستند. `RQS+`
سه سنجهٔ حاکمِ امروز را نداشت: `H3` (مدلِ صفرِ اندازه‌گیری‌شده)، `H5` (جریمهٔ
چندگانگی) و `H10` (مقاومتِ رژیمی). پس وضعیتِ `S341` زیرِ معیارِ حاکم
**«آزموده‌نشده»** است، نه «پاس».

سه تفاوتِ مهندسیِ این اسکریپت با کدِ آرشیو (و دلیلِ هرکدام)
--------------------------------------------------------
**۱) سیگنالِ برداری‌شده + اثباتِ برابری.** کدِ آرشیو یک حلقهٔ پایتون روی هر کندل
   است. برای ۱۵ کارت × ۸۶۴ عضوِ گرید (اندازه‌گیریِ `N_eff`) این غیرعملی است. پس
   منطق **برداری** بازنویسی شد و تابعِ `parity_check()` روی هر کارت اثبات می‌کند
   خروجی **بیت‌به‌بیت** همان حلقهٔ آرشیو است. اگر برابری بشکند، اسکریپت
   **می‌شکند** و داوری نمی‌کند (سقوطِ بلند، نه تخریبِ خاموش).

**۲) جدولِ برآمدِ پیش‌محاسبه‌شده.** براکت ثابت است، پس برآمدِ یک ورودِ لانگ در
   کندلِ `si` فقط به `si` وابسته است نه به اینکه کدام ورودهای دیگر انتخاب شده‌اند.
   قاعدهٔ ناهم‌پوشانی فقط تعیین می‌کند کدام ورودها *گرفته* می‌شوند. پس برآمدِ همهٔ
   کندل‌ها یک‌بار برداری حساب می‌شود و هر قرعهٔ جای‌گشت `O(k)` می‌شود.
   معناشناسی **عیناً** از `se.simulate_trades` کپی شده: ورود در `open[si+1]` با
   اسلیپیج، ابهامِ SL/TP در یک کندل ⇒ **باخت**، خروجِ زمانی روی `close`، و برچسبِ
   برد/باخت از **علامتِ `pnl_pip`** (نه از اینکه کدام سطح خورد).

**۳) دو p-value، و پاس‌شدن نیازِ *هر دو* است.** `blend_null` کلیدِ `p_perm` را حمل
   نمی‌کند، پس موتور همیشه به `p` پارامتریکِ `0.5·erfc(z/√2)` می‌افتد. این اسکریپت
   `p` **تجربی** را از شمارشِ واقعیِ قرعه‌ها هم می‌سنجد. لایه نمی‌تواند از راهِ
   تفاوتِ دو خط‌کش «خریده» شود.

اجرا:
    python3 strategies/s357_s341_v24_rejudge.py --cards site      # چهار کارتِ سایت
    python3 strategies/s357_s341_v24_rejudge.py --cards all       # هر ۱۵ کارت
    python3 strategies/s357_s341_v24_rejudge.py --cards XAUUSD-M5
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                                  # noqa: E402
from engine import indicator_bank as ib                                # noqa: E402
from engine import rqs2 as R2                                          # noqa: E402
from strategies.s341_brooks_swing_levels import _fractal_levels        # noqa: E402
from strategies.s341_swing_fade_h1_revived import CONFIG as ARCHIVE_CFG  # noqa: E402

OUT = "results/_scan_S357"

# ───────────────── پارامترهای آماریِ پیش‌ثبت‌شده (بندِ ۴ پیش‌ثبت) ─────────────────
SEEDS = (23, 101, 777)
PERM_K = 2000
P_BAR = 0.001
SPLIT_FRAC = 0.60

N_TRIALS_HONEST = 10_368        # گریدِ خامِ همان کارت (864 × stretch 4 × exh 3)
N_TRIALS_STRESS = 82_944        # × ۸ ترکیبِ (دارایی×TF) که آرشیو جارو کرد
N_BRACKETS = 12                 # sl(2) × tp(3) × mh(2) — سیگنال را عوض نمی‌کنند
# ⚠️ `NEFF_ROW_CAP`/stride حذف شد — بندِ «چرا ماتریسِ داده ساخته نمی‌شود» در
#    `measure_neff` دلیلِ علمیِ حذف را ثبت می‌کند (نمونه‌گیریِ سطری روی سیگنالِ
#    تُنُک، جریمهٔ چندگانگی را مصنوعاً صفر می‌کرد).

# ─────────── گریدِ آرشیو، عیناً از s341c_fast.py و s341f_revive.py ───────────
W_GRID = [4, 5, 8]
BUF_GRID = [0.05, 0.15]
REGIME_GRID = [
    dict(chop_min=52, r2_max=0.40, er_max=0.30),
    dict(chop_min=58, r2_max=0.30, er_max=0.22),
    dict(chop_min=61.8, r2_max=0.22, er_max=0.16),
]
SECOND_GRID = [False, True]
STRETCH_GRID = [None, 0.7, 1.15, 1.6]
EXH_GRID = [None, 0.25, 0.5]
SIDE_GRID = ['short', 'long']

SITE_CARDS = ["XAUUSD-M5", "XAUUSD-M15", "XAUUSD-M30", "XAUUSD-H1"]

# قانونِ MTF: هر کارتی که دادهٔ آن در `data/` هست. `XAUUSD-M1` داده ندارد و
# صریحاً `NO_DATA` گزارش می‌شود — حذفِ خاموش همان اشتباهِ رایجِ #۵ است.
CARDS_ALL = SITE_CARDS + [
    "XAUUSD-M1",                       # دادهٔ آن در repo نیست ⇒ `NO_DATA`ِ صریح
    "XAUUSD-H4", "XAUUSD-D1", "XAUUSD-W1",
    "EURUSD-M1", "EURUSD-M5", "EURUSD-M15", "EURUSD-M30",
    "EURUSD-H1", "EURUSD-H4", "EURUSD-D1", "EURUSD-W1",
]

# قاعدهٔ مشتقِ پیش‌ثبت‌شده برای کارت‌های آزموده‌نشده (بندِ ۵ پیش‌ثبت) — میانهٔ
# ضرایبِ اندازه‌گیری‌شدهٔ خودِ آرشیو، بدونِ هیچ جست‌وجو ⇒ n_trials = 1.
DERIVED = dict(side='long', w=4, buf=0.05, require_second=True,
               stretch=None, exh=None, mh=29, sl_k=12.02, rr=2.21,
               chop_min=61.8, r2_max=0.22, er_max=0.16,
               chop_p=14, r2_p=20, er_name='er_lucas_11')


# ══════════════════════ ۱. فیچرهای پایه (یک‌بار در هر کارت) ══════════════════════
def base_features(df, cfg_like):
    """اندیکاتورهای پایه — عیناً همان نام/دورهٔ آرشیو."""
    return dict(
        h=df['high'].to_numpy(float),
        l=df['low'].to_numpy(float),
        c=df['close'].to_numpy(float),
        atr=ib.atr_s(df, p=14).to_numpy(),
        ch=ib.chop(df, p=cfg_like['chop_p']).to_numpy(),
        r2=ib.r2(df, p=cfg_like['r2_p']).to_numpy(),
        er=ib.compute(cfg_like['er_name'], df).to_numpy(),
        edist=ib.compute('ema_dist_atr', df).to_numpy(),
        ifr=ib.compute('ifish_rsi', df).to_numpy(),
    )


def signals_vec(F, frac, side, w, buf, regime, require_second, stretch, exh,
                second_lookback=40):
    """نسخهٔ **برداری** منطقِ آرشیو. `frac` = (last_sh, last_sl) برای همان `w`."""
    h, l, c, atr = F['h'], F['l'], F['c'], F['atr']
    n = len(h)
    ch, r2, er = F['ch'], F['r2'], F['er']

    finite = np.isfinite(ch) & np.isfinite(r2) & np.isfinite(er)
    reg = (finite & (ch >= regime['chop_min']) & (r2 <= regime['r2_max'])
           & (np.abs(er) <= regime['er_max']))
    reg &= np.isfinite(atr) & (atr > 0)

    last_sh, last_sl = frac
    bufd = buf * atr
    if side == 'short':
        lvl = last_sh
        trig = (h > lvl + bufd) & (c < lvl)
    else:
        lvl = last_sl
        trig = (l < lvl - bufd) & (c > lvl)
    cand = reg & np.isfinite(lvl) & trig

    if stretch is not None:
        ed = F['edist']
        ok = np.isfinite(ed) & ((ed <= -stretch) if side == 'long' else (ed >= stretch))
        cand &= ok
    if exh is not None:
        fv = F['ifr']
        ok = np.isfinite(fv) & ((fv <= -exh) if side == 'long' else (fv >= exh))
        cand &= ok

    # کدِ آرشیو حلقه را از `w + 2` آغاز می‌کند
    cand[:w + 2] = False

    if not require_second:
        return cand
    # «سیگنالِ دوم» — یک کاندیدا فقط وقتی شلیک می‌کند که کاندیدای قبلی حداکثر
    # `second_lookback` کندل عقب‌تر باشد. (در حلقهٔ آرشیو `recent` همهٔ کاندیداهای
    # درونِ پنجره را نگه می‌دارد، پس شرط دقیقاً «فاصله تا کاندیدای قبلی ≤ پنجره» است.)
    pos = np.flatnonzero(cand)
    out = np.zeros(n, dtype=bool)
    if pos.size >= 2:
        fire = pos[1:][np.diff(pos) <= second_lookback]
        out[fire] = True
    return out


def signals_loop_reference(F, frac, side, w, buf, regime, require_second, stretch,
                           exh, second_lookback=40):
    """حلقهٔ **آرشیو**، کلمه‌به‌کلمه — تنها برای اثباتِ برابری."""
    h, l, c, atr = F['h'], F['l'], F['c'], F['atr']
    ch, r2, er = F['ch'], F['r2'], F['er']
    edist, ifr = F['edist'], F['ifr']
    n = len(h)
    finite = np.isfinite(ch) & np.isfinite(r2) & np.isfinite(er)
    reg = (finite & (ch >= regime['chop_min']) & (r2 <= regime['r2_max'])
           & (np.abs(er) <= regime['er_max']))
    last_sh, last_sl = frac
    sig = np.zeros(n, dtype=bool)
    recent = []
    for i in range(w + 2, n):
        if not reg[i]:
            continue
        a = atr[i]
        if not (a > 0) or not np.isfinite(a):
            continue
        buf_abs = buf * a
        if side == 'short':
            lvl = last_sh[i]
            if not np.isfinite(lvl):
                continue
            trig = (h[i] > lvl + buf_abs) and (c[i] < lvl)
        else:
            lvl = last_sl[i]
            if not np.isfinite(lvl):
                continue
            trig = (l[i] < lvl - buf_abs) and (c[i] > lvl)
        if not trig:
            continue
        if stretch is not None:
            ed = edist[i]
            if not np.isfinite(ed):
                continue
            if side == 'long' and not (ed <= -stretch):
                continue
            if side == 'short' and not (ed >= stretch):
                continue
        if exh is not None:
            fv = ifr[i]
            if not np.isfinite(fv):
                continue
            if side == 'long' and not (fv <= -exh):
                continue
            if side == 'short' and not (fv >= exh):
                continue
        if require_second:
            recent = [k for k in recent if i - k <= second_lookback]
            recent.append(i)
            if len(recent) < 2:
                continue
        sig[i] = True
    return sig


# ══════════════════════════ ۲. جدولِ برآمدِ برداری ══════════════════════════
def outcome_table(df, asset, sl_pip, tp_pip, mh, side='long'):
    """برآمدِ یک ورود در **هر** کندل، با معناشناسیِ دقیقِ `se.simulate_trades`.

    خروجی: `res` (۱=برد، −۱=باخت، ۰=غیرقابلِ‌ورود) و `xbar` (کندلِ خروج).
    """
    o = df['open'].to_numpy(float)
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    n = len(df)
    cfg = se.ASSETS[asset]
    pip = cfg['pip']
    spread = float(cfg['spread_pip'])
    slip = float(cfg.get('slip_pip', 0.0))
    sl_d, tp_d = sl_pip * pip, tp_pip * pip

    eb = np.arange(n) + 1
    live = eb < n
    ebc = np.minimum(eb, n - 1)
    if side == 'long':
        fill = o[ebc] + slip * pip
        sl_price, tp_price = fill - sl_d, fill + tp_d
    else:
        fill = o[ebc] - slip * pip
        sl_price, tp_price = fill + sl_d, fill - tp_d
    fill = np.where(live, fill, np.nan)

    res = np.zeros(n, dtype=np.int8)
    xbar = np.full(n, -1, dtype=np.int64)
    for j in range(mh):
        k = eb + j
        openslot = live & (res == 0) & (k < n)
        if not openslot.any():
            break
        kk = np.minimum(k, n - 1)
        if side == 'long':
            hit_sl = l[kk] <= sl_price
            hit_tp = h[kk] >= tp_price
        else:
            hit_sl = h[kk] >= sl_price
            hit_tp = l[kk] <= tp_price
        # ابهامِ هم‌زمان ⇒ باخت (عیناً سیاستِ محافظه‌کارانهٔ موتور)
        loss = openslot & hit_sl
        win = openslot & hit_tp & ~hit_sl
        res[loss] = -1
        xbar[loss] = k[loss]
        res[win] = 1
        xbar[win] = k[win]

    kend = np.minimum(eb + mh, n)
    to = live & (res == 0) & (kend > eb)
    if to.any():
        last = c[np.maximum(kend - 1, 0)]
        if side == 'long':
            pnl = (last - slip * pip - fill) / pip - spread
        else:
            pnl = (fill - last - slip * pip) / pip - spread
        res[to] = np.where(pnl[to] > 0, 1, -1)
        xbar[to] = kend[to] - 1
    return res, xbar


def wr_of(picks, res, xbar):
    """WRِ یک مجموعهٔ ورود با قاعدهٔ ناهم‌پوشانیِ موتور (`entry_bar > busy_until`)."""
    wins = used = 0
    last_exit = -1
    for si in picks:
        if si + 1 <= last_exit or res[si] == 0:
            continue
        used += 1
        last_exit = xbar[si]
        if res[si] == 1:
            wins += 1
    return (100.0 * wins / used) if used else None


# ═════════════════════════ ۳. مدلِ صفر + p تجربی ═════════════════════════
def build_null(df, asset, k_sig, sl, tp, mh, k_perm, seed, side='long'):
    res, xbar = outcome_table(df, asset, sl, tp, mh, side=side)
    n = len(df)
    lo = min(300, max(0, n // 10))
    valid = np.arange(lo, max(lo + 1, n - mh - 2))
    valid = valid[res[valid] != 0]
    uncond = wr_of(valid, res, xbar)

    rng = np.random.default_rng(seed)
    draws = []
    k = min(k_sig, valid.size)
    for _ in range(k_perm):
        pick = np.sort(rng.choice(valid, size=k, replace=False))
        w = wr_of(pick, res, xbar)
        if w is not None:
            draws.append(w)
    draws = np.asarray(draws, dtype=float)
    side_null = dict(uncond_wr=uncond, perm_mean=float(draws.mean()),
                     perm_sd=float(draws.std(ddof=1)), perm_max=float(draws.max()),
                     perm_k=int(draws.size))
    zero = dict(uncond_wr=None, perm_mean=None, perm_sd=None, perm_max=None, perm_k=0)
    other = 'short' if side == 'long' else 'long'
    return {side: side_null, other: zero}, draws


def empirical_p(draws, wr_obs):
    """p یک‌طرفهٔ تجربی با برآوردگرِ محافظه‌کارانهٔ `(1+#{≥obs})/(1+K)`.

    عددِ `+1` استانداردِ مونت‌کارلو است (Davison & Hinkley 1997) و از گزارشِ
    `p = 0` که با نمونهٔ متناهی هرگز اثبات‌شدنی نیست جلوگیری می‌کند.
    """
    ge = int((draws >= wr_obs - 1e-12).sum())
    return (1.0 + ge) / (1.0 + len(draws)), ge


# ═════════════════════ ۴. اندازه‌گیریِ N_eff از خودِ گرید ═════════════════════
def measure_neff(F, fracs, verbose=True):
    """`N_eff` از ساختارِ همبستگیِ **۸۶۴ ستونِ سیگنالِ** گریدِ آرشیو.

    براکت‌ها (`sl×tp×mh`) سیگنال را عوض نمی‌کنند، پس ضربِ `× N_BRACKETS` **بدونِ
    تخفیف** اعمال می‌شود (محافظه‌کارانه: جریمه را بالا نگه می‌دارد).

    ⚠️ **چرا ماتریسِ داده ساخته نمی‌شود — و چرا `stride` علماً غلط بود.**
    نسخهٔ اولِ این تابع ۸۶۴ ستونِ کاملِ ۲۰۰٬۰۰۰-سطری را به `R2.effective_trials`
    می‌داد و در سندباکسِ ۹۸۵MB **کشته شد**. راهِ ظاهراً بی‌ضررِ «نمونه‌گیریِ سطری
    با stride» اینجا فقط ناکارآمد نیست، **جهت‌دارِ خطرناک** است: سیگنال‌ها به‌شدت
    تُنُک‌اند (۶۳ سیگنال در ۲۰۰٬۰۰۰ کندلِ M5 ⇒ چگالیِ ۳ در ۱۰٬۰۰۰). با
    `stride≈7` احتمالِ آنکه یک ستون **هیچ** سطرِ اطلاع‌داری را نگه دارد بالاست،
    آن ستون بی‌واریانس می‌شود، فیلترِ `nanvar > min_var` حذفش می‌کند، `M` سقوط
    می‌کند و `M_eff → 1` ⇒ **جریمهٔ چندگانگی مصنوعاً صفر**. یعنی آن باگِ حافظه در
    مسیرِ دوم به لایه پاسِ ناشایست می‌داد؛ دقیقاً همان «دور زدنِ معیار» که
    اشتباهِ رایجِ #۸ ممنوع کرده است.

    راهِ درست: همبستگیِ پیرسونِ دو بردارِ **دودویی** فرمِ بستهٔ دقیق دارد (ضریبِ
    `phi`)، پس ماتریسِ همبستگی **بدونِ ساختنِ ماتریسِ داده** و تنها از اندازهٔ
    تقاطعِ مجموعه‌های تُنُک، **دقیق** (نه تقریبی) محاسبه می‌شود:

        r_ij = (n·n_ij − n_i·n_j) / √( n_i(n−n_i) · n_j(n−n_j) )

    این عیناً همان همبستگیِ جامعه‌ای است که `effective_trials` با تقسیم بر
    `A.shape[0]` می‌سازد، سپس همان برآوردگرِ Nyholt(2004)/Cheverud(2001) روی
    مقادیرِ ویژه اعمال می‌شود: `M_eff = 1 + (M−1)(1 − Var(λ)/M)`.
    ⇒ هم بی‌نیاز از حافظه، هم **دقیق‌تر** از نسخهٔ نمونه‌گیری‌شده.
    """
    n = len(F['h'])
    combos = list(itertools.product(SIDE_GRID, W_GRID, BUF_GRID, REGIME_GRID,
                                    SECOND_GRID, STRETCH_GRID, EXH_GRID))
    sets, counts = [], []
    for side, w, buf, reg, sec, st, ex in combos:
        s = signals_vec(F, fracs[w], side, w, buf, reg, sec, st, ex)
        idx = np.flatnonzero(s)
        sets.append(frozenset(idx.tolist()))
        counts.append(int(idx.size))
        del s, idx
    # ستونِ بی‌واریانس (همیشه-خاموش یا همیشه-روشن) آزمونِ واقعی نیست — همان
    # سیاستِ `effective_trials`.
    keep = [i for i, k in enumerate(counts) if 0 < k < n]
    M = len(keep)
    if M < 2:
        m_eff_sig = float(max(1, M))
        n_eff = float(m_eff_sig * N_BRACKETS)
        if verbose:
            print(f"    N_eff: only {M}/{len(combos)} grid members carry variance "
                  f"→ M_eff_sig={m_eff_sig:.1f} × {N_BRACKETS} = {n_eff:.0f}",
                  flush=True)
        return n_eff, m_eff_sig, len(combos), M

    C = np.eye(M, dtype=np.float64)
    nn = float(n)
    for a in range(M):
        ia = keep[a]
        na = float(counts[ia])
        sa = sets[ia]
        da = na * (nn - na)
        for b in range(a + 1, M):
            ib = keep[b]
            nb = float(counts[ib])
            # تقاطع را از سمتِ مجموعهٔ کوچک‌تر می‌گیریم (هزینهٔ O(min))
            nij = float(len(sa & sets[ib]) if na <= nb else len(sets[ib] & sa))
            den = (da * nb * (nn - nb)) ** 0.5
            C[a, b] = C[b, a] = 0.0 if den <= 0 else (nn * nij - na * nb) / den
    lam = np.clip(np.linalg.eigvalsh(C), 0.0, None)
    var_lam = float(np.mean(lam ** 2) - np.mean(lam) ** 2)
    m_eff_sig = float(min(max(1.0 + (M - 1.0) * (1.0 - var_lam / float(M)), 1.0),
                          float(M)))
    n_eff = float(m_eff_sig * N_BRACKETS)
    if verbose:
        print(f"    N_eff: {M}/{len(combos)} grid members carry variance → exact "
              f"phi-correlation M_eff_sig={m_eff_sig:.1f} × {N_BRACKETS} brackets "
              f"= {n_eff:.0f}", flush=True)
    return n_eff, m_eff_sig, len(combos), M


# ═══════════════════════════ ۵. اجرا برای یک کارت ═══════════════════════════
def resolve_cfg(card, df, asset):
    """پیکربندیِ منجمدِ آرشیو، یا قاعدهٔ مشتقِ پیش‌ثبت‌شده برای کارتِ آزموده‌نشده."""
    if card in ARCHIVE_CFG:
        c = dict(ARCHIVE_CFG[card])
        return c, 'ARCHIVE', N_TRIALS_HONEST, N_TRIALS_STRESS
    c = dict(DERIVED)
    med_atr = float(np.nanmedian(ib.atr_s(df, p=14).to_numpy()) / se.ASSETS[asset]['pip'])
    c['sl'] = round(c.pop('sl_k') * med_atr, 1)
    c['tp'] = round(c.pop('rr') * c['sl'], 1)
    return c, 'DERIVED', 1, 1


def parity_check(F, fracs, cfg):
    """اثباتِ برابریِ بیت‌به‌بیتِ نسخهٔ برداری با حلقهٔ آرشیو (روی همین پیکربندی)."""
    reg = dict(chop_min=cfg['chop_min'], r2_max=cfg['r2_max'], er_max=cfg['er_max'])
    a = signals_vec(F, fracs[cfg['w']], cfg['side'], cfg['w'], cfg['buf'], reg,
                    cfg['require_second'], cfg['stretch'], cfg['exh'])
    b = signals_loop_reference(F, fracs[cfg['w']], cfg['side'], cfg['w'], cfg['buf'],
                               reg, cfg['require_second'], cfg['stretch'], cfg['exh'])
    return bool(np.array_equal(a, b)), int(a.sum()), int(b.sum())


def run_card(card, do_neff=True, verbose=True):
    asset, tf = card.split('-')
    path = os.path.join('data', f'{asset}_{tf}.csv')
    if not os.path.exists(path):
        return dict(card=card, status='NO_DATA',
                    note=f'{path} does not exist in the repository')
    df = se.load_data(path)
    cfg, source, nt_honest, nt_stress = resolve_cfg(card, df, asset)
    F = base_features(df, cfg)
    fracs = {w: _fractal_levels(F['h'], F['l'], w) for w in sorted(set(W_GRID + [cfg['w']]))}

    ok, na, nb = parity_check(F, fracs, cfg)
    if not ok:
        raise AssertionError(
            f"{card}: vectorised signal does not match the archive loop "
            f"({na} vs {nb} signals). Refusing to judge a layer whose logic is "
            f"not proven identical to the recorded one.")
    if verbose:
        print(f"\n=== {card} :: source={source} bars={len(df)} "
              f"SL={cfg['sl']} TP={cfg['tp']} mh={cfg['mh']} "
              f"| parity OK ({na} signals)", flush=True)

    reg = dict(chop_min=cfg['chop_min'], r2_max=cfg['r2_max'], er_max=cfg['er_max'])
    sig = signals_vec(F, fracs[cfg['w']], cfg['side'], cfg['w'], cfg['buf'], reg,
                      cfg['require_second'], cfg['stretch'], cfg['exh'])
    n_sig = int(sig.sum())
    rec = dict(card=card, asset=asset, tf=tf, cfg_source=source,
               cfg={k: v for k, v in cfg.items()}, bars=len(df),
               parity_vec_vs_loop=dict(equal=ok, n_vec=na, n_loop=nb),
               n_signals=n_sig, seeds={}, honest={})

    if n_sig < 5:
        rec['status'] = 'NO_SIGNAL'
        return rec

    zero = np.zeros(len(df), bool)
    long_sig = sig if cfg['side'] == 'long' else zero
    short_sig = sig if cfg['side'] == 'short' else zero
    tr = se.simulate_trades(df, long_sig, short_sig, sl_pip=cfg['sl'], tp_pip=cfg['tp'],
                            asset=asset, max_hold=cfg['mh'], allow_overlap=False)
    if tr is None or len(tr) < 5:
        rec['status'] = 'NO_TRADES'
        return rec
    n = len(tr)
    wr_obs = 100.0 * float((tr['pnl_pip'] > 0).sum()) / n
    rec.update(status='JUDGED', n_trades=n, wr_obs=round(wr_obs, 3))

    # اثباتِ اپل‌به‌اپل بودنِ جدولِ برآمد با موتور (پیش از استفاده در نول)
    res_chk, xb_chk = outcome_table(df, asset, cfg['sl'], cfg['tp'], cfg['mh'],
                                    side=cfg['side'])
    wr_tbl = wr_of(np.flatnonzero(sig), res_chk, xb_chk)
    rec['parity_table_vs_engine'] = dict(wr_engine=round(wr_obs, 3),
                                         wr_table=None if wr_tbl is None else round(wr_tbl, 3))
    if verbose:
        print(f"    n_trades={n} WR_engine={wr_obs:.2f}% WR_table={wr_tbl:.2f}%",
              flush=True)

    n_eff = float(nt_honest)
    if do_neff and source == 'ARCHIVE':
        n_eff, m_eff_sig, n_cols, m_used = measure_neff(F, fracs, verbose=verbose)
        rec['neff'] = dict(n_eff=round(n_eff, 1), m_eff_signal=round(m_eff_sig, 2),
                           n_signal_columns=n_cols, m_with_variance=m_used,
                           method='exact_phi_correlation',
                           bracket_multiplier=N_BRACKETS)
    else:
        rec['neff'] = dict(n_eff=n_eff, note='derived card: no selection ⇒ N=1')

    close = df['close'].to_numpy(float)
    bar_time = df['time'].to_numpy()
    split_bar = int(len(df) * SPLIT_FRAC)
    labels = (('neff', n_eff), ('honest', nt_honest), ('stress', nt_stress))

    for seed in SEEDS:
        null, draws = build_null(df, asset, n_sig, cfg['sl'], cfg['tp'], cfg['mh'],
                                 PERM_K, seed, side=cfg['side'])
        p_emp, n_ge = empirical_p(draws, wr_obs)
        out = {}
        for label, nt in labels:
            r = R2.compute_rqs2(tr, asset, sl_pip=cfg['sl'], tp_pip=cfg['tp'],
                                bar_time=bar_time, close=close, null=null,
                                n_trials=int(round(nt)), split_bar=split_bar)
            out[label] = dict(verdict=r.get('verdict'), score=r.get('rqs2_score'),
                              rank=r.get('rank'), gates=r.get('gates'),
                              metrics=r.get('metrics'), notes=r.get('notes'))
        m0 = out['neff']['metrics']
        out['null'] = {k: null[cfg['side']][k] for k in
                       ('uncond_wr', 'perm_mean', 'perm_sd', 'perm_max', 'perm_k')}
        out['p_empirical'] = round(p_emp, 6)
        out['n_draws_ge_obs'] = n_ge
        out['p_parametric_engine'] = m0.get('skill_p_perm')
        out['honest_accept'] = bool(out['neff']['verdict'] == 'ACCEPT'
                                    and out['honest']['verdict'] == 'ACCEPT'
                                    and p_emp <= P_BAR)
        rec['seeds'][str(seed)] = out
        if verbose:
            print(f"  seed={seed} K={out['null']['perm_k']} | uncond="
                  f"{out['null']['uncond_wr']:.2f}% perm_mean="
                  f"{out['null']['perm_mean']:.2f}% sd={out['null']['perm_sd']:.2f} "
                  f"| lift={m0.get('skill_lift_pp')}pp z={m0.get('skill_z')}", flush=True)
            for label, _ in labels:
                bad = [g for g, v in (out[label]['gates'] or {}).items() if v is not True]
                print(f"      {label:6s}: {out[label]['verdict']:11s} "
                      f"score={out[label]['score']} failing={bad or 'NONE'}", flush=True)
            print(f"      p_emp={p_emp:.6f} ({n_ge}/{out['null']['perm_k']} ≥ obs) "
                  f"p_param={out['p_parametric_engine']} "
                  f"HONEST_ACCEPT={out['honest_accept']}", flush=True)

    verds = {s: v['neff']['verdict'] for s, v in rec['seeds'].items()}
    rec['honest'] = dict(
        seed_stable=len(set(verds.values())) == 1,
        verdicts_neff=verds,
        verdicts_honest={s: v['honest']['verdict'] for s, v in rec['seeds'].items()},
        verdicts_stress={s: v['stress']['verdict'] for s, v in rec['seeds'].items()},
        all_seeds_honest_accept=all(v['honest_accept'] for v in rec['seeds'].values()),
        decision='ALIVE' if all(v['honest_accept'] for v in rec['seeds'].values())
                 else 'NOT_ALIVE_UNDER_FROZEN_CFG',
    )
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cards', default='site')
    ap.add_argument('--no-neff', action='store_true')
    args = ap.parse_args()
    if args.cards == 'site':
        cards = SITE_CARDS
    elif args.cards == 'all':
        cards = CARDS_ALL
    else:
        cards = args.cards.split(',')
    os.makedirs(OUT, exist_ok=True)
    for card in cards:
        try:
            rec = run_card(card, do_neff=not args.no_neff)
        except Exception as exc:                                   # noqa: BLE001
            rec = dict(card=card, status='ERROR', error=repr(exc))
            print(f"  [ERROR] {card}: {exc!r}", flush=True)
        # ⛳ قانونِ سومِ پروژه: هر کارت **فوراً** ذخیره می‌شود
        with open(os.path.join(OUT, f'{card}.json'), 'w', encoding='utf-8') as fh:
            json.dump(rec, fh, ensure_ascii=False, indent=1, default=float)
        print(f"  [saved] {OUT}/{card}.json status={rec.get('status')} "
              f"decision={(rec.get('honest') or {}).get('decision')}", flush=True)


if __name__ == '__main__':
    main()
