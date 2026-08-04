# -*- coding: utf-8 -*-
"""کالیبراسیونِ توان با **لبهٔ کاشته‌شده** — پیاده‌سازیِ `Q10` پاسخِ مشاور

## چرا این ابزار

مشاور در `Q10` به پرسشِ ناراحت‌کنندهٔ پروژه («نرخِ پذیرشِ ۱.۱٪ یعنی بازار کاراست
یا معیارِ ما بیش‌تصحیح دارد؟») این‌گونه پاسخ داد:

> «از ۱.۱٪ *به‌تنهایی* هیچ نتیجه‌ای نمی‌توان گرفت، چون
> **نرخِ پذیرش = (نرخِ پایهٔ لبه‌های واقعی) × (توانِ خطِ لوله)**
> و شما هیچ‌کدام از دو عامل را جدا اندازه نگرفته‌اید.»

و این را **اقدامِ شمارهٔ ۲** گذاشت با استدلالِ: «تا این نباشد، معنیِ هیچ `REJECT`ی
معلوم نیست؛ ۲۲۷ حکمِ گذشته را هم بازتفسیر می‌کند.»

`results/AUDIT_CONSULTANT_UPTAKE_GAP.md` ثبت کرد که این انجام **نشده** بود.

## پروتکلِ مشاور (عیناً، بندِ به بند)

1. از دادهٔ **واقعیِ** `XAUUSD` سیگنال‌های یک لایهٔ **خنثی** بساز — «ورودِ تصادفی
   با همان توزیعِ فایرِ `S333`».
2. لبه بکار: با احتمالِ `p_edge` نتیجهٔ برد تزریق کن تا `WR`ِ **حقیقی** روی شبکهٔ
   `{58, 60, 62, 65, 68, 72}%` قرار گیرد؛ `n` روی `{40, 80, 160, 320, 640}`.
3. خطِ لولهٔ `RQS2` را روی هر سلول **۵۰۰ بار** اجرا کن ⇒ `Power(WR, n)`.
4. سلولِ `WR=58٪` (بی‌لبه) ⇒ **خطای نوعِ ۱ی تجربی**؛ باید `≤۵٪` باشد.
5. **معیارِ قضاوت:**
   - `Power(65%, 356) ≥ 80%` ⇒ معیار سالم، مشکل فقط `n`ِ کم.
   - توان زیرِ `~۵۰٪` حتی با `n`ِ کافی ⇒ **بیش‌تصحیحِ ساختاری**؛ دروازه‌های
     همبسته (`H5`+`H6`+`H7`) باید ادغام شوند.

## 🔴 انحرافِ صریح از پروتکل — و دلیلش

مشاور گفت «**هر ۱۱ دروازه**». من دروازه‌های **آماری** را اجرا می‌کنم و
دروازه‌های **اقتصادی/ساختاری** را نه. دلیل، و نه بهانه:

| دروازه | اجرا؟ | چرا |
|---|---|---|
| `H0` کفایتِ نمونه | ✅ | مستقیماً تابعِ `n` است — قلبِ همین آزمون |
| `H1` `WR≥60` و `PF≥1.3` | ✅ | مستقیماً تابعِ `WR`ِ کاشته‌شده |
| `H3` مهارت (`lift≥4pp` و `p_perm≤0.001`) | ✅ | دروازهٔ ⭐ و اصلی‌ترین مصرف‌کنندهٔ توان |
| `H5` چندگانگی (`p×n_trials<0.05`) | ✅ | دومین مصرف‌کنندهٔ بزرگِ توان |
| `H6` پایداریِ تقویمی | ✅ | مشاور صریح گفت `H5+H6+H7` هم‌منبع‌اند |
| `H7` خارج از نمونه | ✅ | همان |
| `H2` لبهٔ هندسی | ⚠️ جزئی | `WR − BE ≥ 3pp` قابلِ محاسبه است؛ `RR` از هندسهٔ ثابت می‌آید |
| `H4` مهارتِ هر سمت | ❌ | لایهٔ کاشته یک‌سویه است ⇒ بی‌معنا |
| `H8` ریسکِ دنباله | ❌ | نیازمندِ سریِ `P&L`ِ واقعیِ چیده‌شده؛ کاشتِ نتیجه آن را مصنوعی می‌کند |
| `H9` مقاومتِ هزینه | ❌ | همان — تابعِ هندسه است نه `WR`، و هندسه ثابت است |
| `H10` مقاومتِ رژیمی | ❌ | نیازمندِ سیگنالِ خلافِ جریان؛ لایهٔ خنثیِ تصادفی ندارد |

**اثرِ این انحراف بر نتیجه:** توانِ گزارش‌شده یک **کرانِ بالا** است. دروازه‌های
حذف‌شده فقط می‌توانند توان را **کمتر** کنند. پس اگر همین کرانِ بالا هم پایین
باشد، حکمِ «کم‌توان» **قوی‌تر** می‌شود، نه ضعیف‌تر. این انحراف در جهتِ
**علیهِ** نتیجهٔ دلخواه است، نه به نفعش.

## نردهٔ صداقت

- ❌ این ابزار **هیچ لایه‌ای را پاس نمی‌کند**. فقط توانِ *معیار* را می‌سنجد.
- ❌ توانِ کم **مجوزِ شل کردنِ هیچ دروازه‌ای نیست**. مشاور فقط در یک شرط
  ادغامِ دروازه را مجاز دانست: توان `<۵۰٪` **با `n`ِ کافی**.
- ❌ لبهٔ کاشته‌شده یک لبهٔ **واقعیِ بازار نیست**؛ یک برچسبِ تزریق‌شده است.
  پس این ابزار می‌گوید «معیار چقدر بیناست»، نه «بازار چقدر لبه دارد».
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as SE
import strategies.s333_s79_pullback_revival as S333

OUT = 'results/_calib_power'
os.makedirs(OUT, exist_ok=True)

# ── شبکهٔ مشاور، عیناً
WR_GRID = [58, 60, 62, 65, 68, 72]
N_GRID = [40, 80, 160, 320, 640]

# مشاور گفت `Power(65%, 356)` ⇒ ۳۵۶ به شبکه افزوده می‌شود
N_GRID_EXT = sorted(set(N_GRID + [356]))

N_REP = 500            # ۵۰۰ تکرار طبقِ بندِ ۳ پروتکل

# `n_trials` برای `H5` — از دفترِ چندگانگیِ پروژه در زمانِ نشستِ S376
N_TRIALS_H5 = 153


# ═══════════════════════════════════════════════════════════════════════
#  🐞 اصلاحِ باگِ **تفکیک‌پذیریِ جای‌گشت** — نقصِ ابزارِ من، نه نقصِ معیار
#
#  اجرای اول جدولی از **۳۶ صفر** داد و من نزدیک بود آن را «کوریِ معیار»
#  گزارش کنم. باگ حسابی بود:
#
#      N_PERM = 500  ⇒  p_min = 1/(500+1) = 0.001996
#
#  و دو دروازه این را می‌خواهند:
#      H3 : p ≤ 0.001                  ⇒ ناممکن (0.001996 > 0.001)
#      H5 : p × 153 < 0.05 ⇒ p < 0.000327 ⇒ ناممکن
#
#  یعنی `H3` و `H5` در شبیه‌سازِ من **به‌طور ریاضی غیرقابلِ ارضا** بودند؛
#  حتی لبه‌ای با `WR=100٪` هم رد می‌شد. آن ۱۰۰٪ شکست، «مطلق بودنِ پدیده»
#  نبود — **صفر تفکیک‌پذیریِ خط‌کش** بود.
#
#  کفِ لازم برای اینکه هر دو دروازه *دستِ‌کم امکانِ* پاس داشته باشند:
#      H3 ⇒ N_PERM ≥ 999
#      H5 ⇒ N_PERM ≥ 3059      (تنگ‌ترین قید ⇒ حاکم)
#
#  مقدارِ انتخابی با حاشیهٔ اطمینان بالای قیدِ تنگ‌تر گذاشته می‌شود تا
#  `p_min` یک مرتبه زیرِ آستانهٔ `H5` بنشیند و پاس شدن به «تکِ دنباله»
#  وابسته نباشد. عدد **رند نیست** (ضدِ اشتباهِ رایجِ #۷) و از ضربِ
#  قیدِ حاکم در یک عاملِ لوکاس (۴) می‌آید: 3059 × 4 ≈ 12236 → 12239.
N_PERM = 12239

# ── بازرسیِ اجباریِ پیش‌از‌اجرا: هیچ دروازه‌ای نباید *ساختاراً* ناممکن باشد.
#    اگر این `assert` بشکند یعنی خط‌کش دوباره درجه‌بندیِ کافی ندارد و هر
#    عددِ توانی که تولید شود بی‌معناست. این بازرسی عمداً `assert` است تا
#    اجرا **متوقف** شود، نه یک هشدارِ قابلِ نادیده‌گرفتن.
_P_MIN = 1.0 / (N_PERM + 1.0)
assert _P_MIN <= 0.001, f'H3 unsatisfiable: p_min={_P_MIN:.6f} > 0.001'
assert _P_MIN * N_TRIALS_H5 < 0.05, (
    f'H5 unsatisfiable: p_min*n_trials={_P_MIN * N_TRIALS_H5:.6f} >= 0.05')

SEED = 20260804


# ═══════════════════════════════════════════════════════════════════════
#  ۱) بندِ ۱ پروتکل — لایهٔ خنثی روی دادهٔ **واقعی**
# ═══════════════════════════════════════════════════════════════════════
def neutral_trades(card, rng, n_want):
    """معاملاتِ یک لایهٔ **خنثی** روی دادهٔ واقعی، با هندسهٔ قفلِ `S333`.

    «ورودِ تصادفی با همان توزیعِ فایرِ `S333`» (بندِ ۱ مشاور). هندسه از
    `BEST_CFG` می‌آید ⇒ `SL/TP/max_hold` **واقعی**، اسپردِ **واقعی**، پس
    توزیعِ برد/باختِ مبنا مصنوعی نیست.
    """
    cfg = S333.BEST_CFG[card]
    df = SE.load_data(f'data/{card}.csv')
    n = len(df)
    sl, tp, mh = cfg['sl'], cfg['tp'], cfg['mh']

    warm = 200
    pool = np.arange(warm, n - mh - 1)
    take = min(pool.size, n_want * 4)
    idx = rng.choice(pool, size=take, replace=False)
    m = np.zeros(n, bool); m[idx] = True

    tr = SE.simulate_trades(df, m, np.zeros(n, bool), sl, tp, card,
                            max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) < n_want:
        return None, None, None
    return df, tr, cfg


# ═══════════════════════════════════════════════════════════════════════
#  ۲) بندِ ۲ پروتکل — کاشتِ لبه
# ═══════════════════════════════════════════════════════════════════════
def seed_edge(base_win, target_wr, rng):
    """برچسبِ برد را طوری تزریق کن که `WR`ِ حقیقی = `target_wr`.

    `base_win` نتایجِ واقعیِ لایهٔ خنثی است. لبه به‌صورتِ **تبدیلِ برچسب** کاشته
    می‌شود: هر معامله با احتمالِ `p_flip` به برد تبدیل می‌شود.

        WR_target = WR_base + p_flip · (1 − WR_base)
        ⇒ p_flip  = (WR_target − WR_base) / (1 − WR_base)

    اگر `WR_target < WR_base` جهت برعکس می‌شود (تبدیلِ برد به باخت).
    """
    wr0 = float(base_win.mean())
    t = target_wr / 100.0
    out = base_win.copy()
    if t >= wr0:
        if wr0 >= 1.0:
            return out
        p = (t - wr0) / (1.0 - wr0)
        losers = np.flatnonzero(~base_win)
        k = int(round(p * losers.size))
        if k > 0:
            out[rng.choice(losers, size=min(k, losers.size), replace=False)] = True
    else:
        if wr0 <= 0.0:
            return out
        p = (wr0 - t) / wr0
        winners = np.flatnonzero(base_win)
        k = int(round(p * winners.size))
        if k > 0:
            out[rng.choice(winners, size=min(k, winners.size), replace=False)] = False
    return out


# ═══════════════════════════════════════════════════════════════════════
#  ۳) بندِ ۳ — خطِ لولهٔ دروازه‌های آماری
# ═══════════════════════════════════════════════════════════════════════
def run_gates(win, ref_wr, perm_dist, cfg, spread_pip, times=None):
    """دروازه‌های آماریِ `RQS2` روی یک نمونهٔ کاشته‌شده. `dict` پاس/رد برمی‌گرداند."""
    n = win.size
    wr = float(win.mean() * 100.0)
    sl, tp = cfg['sl'], cfg['tp']

    g = {}

    # H0 — کفایتِ نمونه
    g['H0'] = bool(n >= 30)

    # H1 — کیفیتِ خام: WR≥60 و PF≥1.3
    nw, nl = int(win.sum()), int((~win).sum())
    pf = (nw * tp) / (nl * sl) if nl > 0 else np.inf
    g['H1'] = bool(wr >= 60.0 and pf >= 1.3)

    # H2 (جزئی) — WR − breakeven ≥ 3pp
    be = 100.0 * (sl + spread_pip) / (sl + tp)
    g['H2'] = bool((wr - be) >= 3.0 and (tp / sl) >= 0.5)

    # H3 — lift≥4pp و p_perm≤0.001
    lift = wr - ref_wr
    p_perm = float((np.sum(perm_dist >= wr) + 1.0) / (perm_dist.size + 1.0))
    g['H3'] = bool(lift >= 4.0 and p_perm <= 0.001)

    # H5 — p_adj = p × n_trials < 0.05
    g['H5'] = bool(min(1.0, p_perm * N_TRIALS_H5) < 0.05)

    # H6 — پایداریِ تقویمی: ≥۳ از ۴ بازه مثبت، هر دو نیمه مثبت
    q = np.array_split(win, 4)
    pos_q = sum(1 for s in q if s.size and s.mean() * 100.0 > be)
    h1_, h2_ = np.array_split(win, 2)
    g['H6'] = bool(pos_q >= 3 and h1_.mean() * 100.0 > be and h2_.mean() * 100.0 > be)

    # H7 — خارج از نمونه: آخرین ۲۵٪
    k_ho = max(15, n // 4)
    ho = win[-k_ho:] if n >= k_ho else win
    pf_ho_num = int(ho.sum()) * tp
    pf_ho_den = int((~ho).sum()) * sl
    pf_ho = pf_ho_num / pf_ho_den if pf_ho_den > 0 else np.inf
    g['H7'] = bool(ho.size >= 15 and ho.mean() * 100.0 >= 57.0 and pf_ho >= 1.2)

    g['_wr'] = round(wr, 3)
    g['_p_perm'] = p_perm
    g['_lift'] = round(lift, 3)
    g['ALL'] = bool(all(v for k, v in g.items() if not k.startswith('_') and k != 'ALL'))
    return g


def _flush(card, wr_base, cfg, spread_pip, results, partial):
    """نوشتنِ اتمیکِ نتایج روی دیسک — پس از **هر سلول**، نه در پایانِ اجرا.

    `partial=True` یعنی اجرا هنوز تمام نشده؛ پرچمِ `complete` در فایل ثبت
    می‌شود تا هیچ تحلیلی به‌اشتباه یک اجرای نیمه‌کاره را کامل نپندارد.
    `n_cells_done` شمارشِ صریحِ سلول‌های تمام‌شده است (از ۳۶).

    نوشتن ابتدا در فایلِ موقت و سپس `os.replace` انجام می‌شود؛ اگر ریست
    دقیقاً در میانهٔ نوشتن رخ دهد، فایلِ قبلی سالم می‌ماند و JSONِ نیمه‌نوشته
    (که غیرقابلِ خواندن است) جای دادهٔ درست را نمی‌گیرد.
    """
    payload = dict(
        spec='consultant_Q10_seeded_edge_power_calibration',
        card=card, geometry=cfg, spread_pip=spread_pip,
        base_wr=round(wr_base, 3), ref_wr=round(wr_base, 3),
        n_rep=N_REP, n_perm=N_PERM, n_trials_h5=N_TRIALS_H5, seed=SEED,
        gates_run=['H0', 'H1', 'H2(partial)', 'H3', 'H5', 'H6', 'H7'],
        gates_omitted=['H4', 'H8', 'H9', 'H10'],
        note='reported power is an UPPER BOUND (omitted gates can only lower it)',
        complete=(not partial),
        n_cells_done=len(results),
        n_cells_total=len(WR_GRID) * len(N_GRID_EXT),
        cells=results,
    )
    dst = os.path.join(OUT, f'power_{card}.json')
    tmp = dst + '.tmp'
    with open(tmp, 'w') as fh:
        json.dump(payload, fh, indent=1, ensure_ascii=False)
    os.replace(tmp, dst)


def main():
    card = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD_M30'
    rng = np.random.default_rng(SEED)

    print('=' * 100)
    print(f'POWER CALIBRATION WITH SEEDED EDGE (consultant Q10) — card {card}')
    print(f'grid: WR {WR_GRID}  x  n {N_GRID_EXT}   reps={N_REP}')
    print('=' * 100)

    cfg = S333.BEST_CFG[card]
    spread_pip = SE.ASSETS[card]['spread_pip'] if card in SE.ASSETS else 33.0

    # ── لایهٔ خنثیِ بزرگ روی دادهٔ واقعی (یک بار؛ استخرِ برداشت)
    n_max = max(N_GRID_EXT)
    df, tr_pool, cfg = neutral_trades(card, rng, n_max)
    if tr_pool is None:
        print('could not build neutral pool'); return
    base_win_pool = (tr_pool['outcome'].values == 'win')
    wr_base = float(base_win_pool.mean() * 100.0)
    print(f'neutral pool: {base_win_pool.size} trades, base WR = {wr_base:.3f}%')
    print(f'geometry (locked): sl={cfg["sl"]} tp={cfg["tp"]} mh={cfg["mh"]} spread={spread_pip}')

    # ── مبنای مرجع = همان WRِ لایهٔ خنثی (مدلِ صفرِ کانونی)
    ref_wr = wr_base

    results = {}
    for n_t in N_GRID_EXT:
        # ── توزیعِ جای‌گشتی **یک بار برای هر `n`**، نه یک بار برای هر تکرار.
        #
        #  چرا این بازآرایی مجاز است (و نه یک میان‌بُرِ آماری):
        #  قیدِ قرعه‌کشیِ جای‌گشت فقط `base_win_pool` و `n_t` است — به `wr_t`
        #  و به نمونهٔ کاشته‌شده **هیچ وابستگی‌ای ندارد** (خطوطِ بالا را ببینید).
        #  پس نسخهٔ قبلی همان توزیع را ۶ × ۵۰۰ = ۳۰۰۰ بار برای هر `n` از نو
        #  می‌ساخت و هر ۳۰۰۰ نسخه هم‌توزیع بودند. مدلِ صفر عوض نمی‌شود.
        #
        #  ⚠️ چیزی که این کار **تغییر** می‌دهد و باید صریح گفته شود: تکرارهای
        #  یک سلول اکنون یک توزیعِ صفرِ مشترک دارند، پس خطای مونت‌کارلوی
        #  `p` بینِ تکرارها همبسته می‌شود. با `N_PERM=12239` نوسانِ آن توزیع
        #  ناچیز است، ولی این یعنی عددِ توان یک تخمینِ کم‌واریانس‌تر و نه یک
        #  تخمینِ متفاوت. هزینهٔ آن پذیرفتنی است چون بدون آن کلِ شبکه
        #  ۱.۸ ساعت طول می‌کشد و در سندباکسِ ناپایدار عملاً غیرقابلِ اتمام است.
        #
        #  قرعه‌کشی هم برداری شد: به‌جای ۱۲٬۲۳۹ فراخوانیِ `rng.choice`، یک
        #  ماتریسِ `argsort` روی نویزِ تصادفی ⇒ همان نمونه‌گیریِ بی‌جایگذاری.
        _pool = base_win_pool.astype(np.float64)
        _draw = rng.random((N_PERM, _pool.size)).argsort(axis=1)[:, :n_t]
        perm_shared = _pool[_draw].mean(axis=1) * 100.0

        for wr_t in WR_GRID:
            passes = 0
            gate_fail = {k: 0 for k in ['H0', 'H1', 'H2', 'H3', 'H5', 'H6', 'H7']}
            for _ in range(N_REP):
                idx = rng.choice(base_win_pool.size, size=n_t, replace=False)
                base = base_win_pool[idx]
                win = seed_edge(base, wr_t, rng)

                g = run_gates(win, ref_wr, perm_shared, cfg, spread_pip)
                if g['ALL']:
                    passes += 1
                for k in gate_fail:
                    if not g[k]:
                        gate_fail[k] += 1

            pw = passes / N_REP
            results[f'{wr_t}_{n_t}'] = dict(
                wr_target=wr_t, n=n_t, power=round(pw, 4),
                gate_fail_rate={k: round(v / N_REP, 4) for k, v in gate_fail.items()},
            )
            print(f'  WR={wr_t:3d}%  n={n_t:4d}  power={pw:6.1%}   '
                  f'binding: ' + ', '.join(
                      f'{k}={v/N_REP:.0%}' for k, v in sorted(
                          gate_fail.items(), key=lambda x: -x[1])[:3] if v > 0),
                  flush=True)

            # ── قانونِ «اندک اندک»: ذخیرهٔ **هر سلول** به‌محضِ اتمام.
            #
            #  نسخهٔ اول فقط در پایانِ هر ۳۶ سلول می‌نوشت. سندباکس در میانهٔ
            #  اجرا ریست شد و کلِ نتایجِ کاملِ ۱۴ سلول از دست رفت — دقیقاً همان
            #  حالتی که قانونِ سومِ پروژه («اندک اندک») برای جلوگیری از آن
            #  نوشته شده است. اکنون هر سلول بی‌درنگ روی دیسک می‌نشیند.
            _flush(card, wr_base, cfg, spread_pip, results, partial=True)

    _flush(card, wr_base, cfg, spread_pip, results, partial=False)
    print(f'\nsaved → {OUT}/power_{card}.json')


if __name__ == '__main__':
    main()
