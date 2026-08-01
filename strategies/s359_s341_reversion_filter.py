# -*- coding: utf-8 -*-
"""
S359 — گامِ ۳ب: فیلترِ رژیمِ **بازگشتی** روی لایهٔ رأیِ خانوادگیِ S341.

سندِ حاکم: `results/S359_PREREGISTRATION_S341_REVERSION_FILTER.md`
(پیش از نوشتنِ این فایل commit شده؛ هیچ چیزی در این اسکریپت خارج از آن نیست).

═══════════════════════════════════════════════════════════════════════════════
چرا این اسکریپت وجود دارد
═══════════════════════════════════════════════════════════════════════════════
سه دروازهٔ رژیمِ لایهٔ اصلی (`chop ≥ x` AND `r2 ≤ y` AND `|ER| ≤ z`) هر سه **نبودِ
روند** را می‌سنجند، نه **حضورِ بازگشت**. یک بازارِ بی‌روند می‌تواند گشتِ تصادفیِ
بی‌حافظه باشد (`H≈0.5`) که در آن fade هیچ لبه‌ای ندارد. این اسکریپت محورِ گم‌شده را
اضافه می‌کند: ضدپایایی (`hurst`)، دندانه‌داریِ فراکتالی (`fdi`)، و پیش‌بینی‌پذیریِ
اطلاعاتی (`entropy`).

═══════════════════════════════════════════════════════════════════════════════
سه فاز، با مرزِ داده‌ایِ سخت
═══════════════════════════════════════════════════════════════════════════════
* **فازِ A (جست‌وجو)** — فقط `bar < 0.60·n`. چندک‌ها نیز فقط از همین بازه.
  خروجی: **یک** زوجِ `(filter, θ)` برای هر کارت.
* **فازِ B (تأییدِ یگانه)** — فقط `bar ≥ 0.60·n`. همان زوجِ منجمد، یک بار.
* **فازِ C (تعمیمِ ساختاری)** — همان ۴۰٪ آخر: فیلتر باید ≥۴۴ از ۷۲ عضوِ فردی را
  هم بالا ببرد (`RQS2_SPEC` §۲.۵).

═══════════════════════════════════════════════════════════════════════════════
دو مدلِ صفر، **هر دو** الزامی
═══════════════════════════════════════════════════════════════════════════════
1. **زیرمجموعهٔ هم‌انتخاب‌گر (SUBSET)** — الزامِ صریحِ `RQS2_SPEC` §۲.۵ برای فیلترها:
   «هر فیلتری با کوچک‌کردنِ `n` واریانسِ WR را بالا می‌برد و به‌شانس لیفتِ مثبت
   نشان می‌دهد». پس زیرمجموعهٔ تصادفیِ **هم‌اندازه** از رویدادهای فیلترنشده کشیده
   می‌شود. این می‌سنجد: «آیا خودِ فیلتر مهارت دارد؟»
2. **شیفتِ دوّارِ مشترک (SHIFT)** — همان صفرِ حاکمِ S357B/S358. این می‌سنجد:
   «آیا کلِ لایه (ensemble+filter) از زمان‌بندیِ تصادفی بهتر است؟»

⚠️ **هیچ‌یک جای دیگری را نمی‌گیرد.** یک فیلتر می‌تواند مهارتِ افزایشی داشته باشد
درحالی‌که پایهٔ آن هیچ لبه‌ای ندارد (SUBSET پاس، SHIFT رد)، و برعکس. پس موتور
**دو بار** صدا زده می‌شود — یک‌بار با هر صفر — و پذیرش نیازمندِ `ACCEPT` زیرِ
**هر دو** است. این سخت‌گیری عمدی است.

═══════════════════════════════════════════════════════════════════════════════
کفِ نمونهٔ فازِ A — **مشتق‌شده**، نه اختراع‌شده
═══════════════════════════════════════════════════════════════════════════════
`H7` موتور در holdout نیاز به `n ≥ 15` دارد. فازِ B درونِ ۴۰٪ آخر خودش ۶۰/۴۰
تقسیم می‌شود (تا `H7` مبنایی داشته باشد) ⇒ بخشِ holdoutِ آن `0.40 × n_oos` است ⇒
`n_oos ≥ 15/0.40 = 37.5 ⇒ 38`. و `n_oos ≈ (40/60) · n_is = 0.667 · n_is` ⇒
`n_is ≥ 38/0.667 = 57`. پس **کفِ ۵۷** معامله در فازِ A، مستقیماً از خودِ معیار.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import indicator_bank as ib          # noqa: E402
from engine import rqs2 as R2                    # noqa: E402
from engine import scalp_engine as se            # noqa: E402
from strategies import s357_s341_v24_rejudge as S357     # noqa: E402
from strategies import s358_s341_vote_ensemble as S358   # noqa: E402

OUT = "results/_scan_S359"

SEEDS = S357.SEEDS                # (23, 101, 777)
PERM_K = S357.PERM_K              # 2000
P_BAR = S358.P_BAR                # 0.001 — از S357/S358، شل نمی‌شود
SPLIT_FRAC = 0.60                 # مرزِ فازِ A/B
THETA_GRID = S358.THETA_GRID      # (4, 7, 11, 16) — پیش‌ثبتِ S358
N_IS_FLOOR = 57                   # مشتق‌شده در docstring
GEN_MIN_MEMBERS = 44              # ۴۴ از ۷۲ — پیش‌ثبتِ فازِ C

# ── خانوادهٔ فیلترِ پیش‌ثبت‌شده و **بسته** (بندِ ۳ سندِ S359) ──────────────────
#   `dirn = -1` ⇒ کندل نگه داشته می‌شود اگر مقدار ≤ چندکِ `q`
#   `dirn = +1` ⇒ کندل نگه داشته می‌شود اگر مقدار ≥ چندکِ `1-q`
FILTER_SPECS = [
    ('hurst', 47, -1), ('hurst', 64, -1), ('hurst', 89, -1),
    ('fdi', 29, +1), ('fdi', 55, +1),
    ('entropy', 47, -1), ('entropy', 89, -1),
]
Q_GRID = (0.15, 0.28, 0.42)

# قبضِ چندگانگی (بندِ ۶ سندِ S359)
N_TRIALS_HONEST = 1
N_TRIALS_CONSERV = len(FILTER_SPECS) * len(Q_GRID) * len(THETA_GRID)   # ۸۴
N_TRIALS_STRESS = N_TRIALS_CONSERV * 2                                  # ۱۶۸


# ═══════════════════════ ۱. اندیکاتورهای فیلتر ═══════════════════════
def filter_series(df, name, p):
    if name == 'hurst':
        return ib.hurst(df, p=p).to_numpy(float)
    if name == 'fdi':
        return ib.fdi(df, p=p).to_numpy(float)
    if name == 'entropy':
        return ib.entropy(df, p=p).to_numpy(float)
    raise KeyError(name)


def filter_mask(vals, thr, dirn):
    """ماسکِ نگه‌داشتن. `NaN` هرگز نگه داشته نمی‌شود (محافظه‌کارانه)."""
    ok = np.isfinite(vals)
    if dirn < 0:
        return ok & (vals <= thr)
    return ok & (vals >= thr)


def in_sample_threshold(vals, cut, q, dirn):
    """چندکِ **منجمد** از ۶۰٪ اول. هیچ اطلاعی از ۴۰٪ آخر استفاده نمی‌شود."""
    v = vals[:cut]
    v = v[np.isfinite(v)]
    if v.size < 100:
        return None
    return float(np.quantile(v, q if dirn < 0 else 1.0 - q))


# ═══════════════════ ۲. ارزیابیِ یک ماسک روی یک بازه ═══════════════════
def wr_on(long_sig, short_sig, tables, lo=None, hi=None):
    """WR و شمارشِ معاملات با قدم‌زنِ ناهم‌پوشانِ `S358.walk_fast`.

    `lo/hi` بازهٔ کندل را محدود می‌کند. صف **از نو** ساخته می‌شود، چون فیلتر
    خودِ صفِ ناهم‌پوشانی را تغییر می‌دهد و اعمالِ آن روی معاملاتِ نهایی، اثرِ صف
    را نادیده می‌گیرد (بندِ ۵ سندِ پیش‌ثبت).
    """
    res_l, xb_l, res_s, xb_s = tables
    sb, isl = S358.merged(long_sig, short_sig)
    if lo is not None:
        keep = sb >= lo
        sb, isl = sb[keep], isl[keep]
    if hi is not None:
        keep = sb < hi
        sb, isl = sb[keep], isl[keep]
    if sb.size == 0:
        return None, 0, 0, 0
    nl, wl, ns, ws = S358.walk_fast(sb, isl, res_l, xb_l, res_s, xb_s)
    tot = nl + ns
    return ((100.0 * (wl + ws) / tot) if tot else None), tot, nl, ns


# ═══════════════════ ۳. مدلِ صفرِ زیرمجموعهٔ هم‌انتخاب‌گر ═══════════════════
def null_subset(long_sig, short_sig, tables, k_keep, k_perm, seed, lo, hi):
    """از رویدادهای **فیلترنشدهٔ** بازه، زیرمجموعهٔ تصادفیِ `k_keep`-تایی.

    این صفرِ حاکمِ فیلتر است (`RQS2_SPEC` §۲.۵): کسرِ انتخاب یکسان است، پس
    تورّمِ واریانسِ ناشی از کوچک‌شدنِ `n` در **هر دو** طرفِ مقایسه حاضر است و
    نمی‌تواند به‌شانس لیفتِ مثبت بسازد.

    زیرمجموعه روی **رویدادها** (سیگنال‌ها) اعمال می‌شود، نه معاملات، و صفِ
    ناهم‌پوشانی برای هر قرعه از نو ساخته می‌شود.
    """
    res_l, xb_l, res_s, xb_s = tables
    sb_all, isl_all = S358.merged(long_sig, short_sig)
    keep = (sb_all >= lo) & (sb_all < hi)
    sb_all, isl_all = sb_all[keep], isl_all[keep]
    m = sb_all.size
    if m == 0 or k_keep <= 0 or k_keep > m:
        return np.asarray([], float), np.asarray([], float), np.asarray([], float)
    rng = np.random.default_rng(seed)
    d_all, d_l, d_s = [], [], []
    for _ in range(k_perm):
        pick = np.sort(rng.choice(m, size=k_keep, replace=False))
        nl, wl, ns, ws = S358.walk_fast(sb_all[pick], isl_all[pick],
                                        res_l, xb_l, res_s, xb_s)
        tot = nl + ns
        if tot == 0:
            continue
        d_all.append(100.0 * (wl + ws) / tot)
        if nl:
            d_l.append(100.0 * wl / nl)
        if ns:
            d_s.append(100.0 * ws / ns)
    return (np.asarray(d_all, float), np.asarray(d_l, float),
            np.asarray(d_s, float))


def null_shift_masked(long_sig, short_sig, fmask, tables, k_perm, seed, lo, hi):
    """صفرِ شیفتِ دوّارِ مشترک، با ماسکِ فیلتر **همراهِ** سیگنال جابه‌جا می‌شود.

    اگر ماسک ثابت بماند و فقط سیگنال بچرخد، تعدادِ رویدادهای بازمانده تغییر
    می‌کند و مقایسه بی‌اعتبار می‌شود. چرخاندنِ هر دو با هم، «شکلِ» لایه را حفظ
    و تنها هم‌ترازیِ آن با قیمت را نابود می‌کند.
    """
    res_l, xb_l, res_s, xb_s = tables
    rng = np.random.default_rng(seed)
    d_all, d_l, d_s = [], [], []
    for _ in range(k_perm):
        sh = int(rng.integers(lo, hi))
        ls = np.roll(long_sig & fmask, sh)
        ss = np.roll(short_sig & fmask, sh)
        wr, tot, nl, ns = None, 0, 0, 0
        sb, isl = S358.merged(ls, ss)
        keep = (sb >= lo) & (sb < hi)
        sb, isl = sb[keep], isl[keep]
        if sb.size == 0:
            continue
        nl, wl, ns, ws = S358.walk_fast(sb, isl, res_l, xb_l, res_s, xb_s)
        tot = nl + ns
        if tot == 0:
            continue
        d_all.append(100.0 * (wl + ws) / tot)
        if nl:
            d_l.append(100.0 * wl / nl)
        if ns:
            d_s.append(100.0 * ws / ns)
    return (np.asarray(d_all, float), np.asarray(d_l, float),
            np.asarray(d_s, float))


# ═══════════════════════════ ۴. فازِ A — جست‌وجو ═══════════════════════════
def phase_a(df, F, v, tables, cut, verbose=True):
    """جست‌وجوی درون‌نمونه‌ای. رتبه‌بندی با `z`ِ دوجمله‌ایِ تقریبی.

    چرا `z`ِ دوجمله‌ای و نه لیفتِ خام: لیفتِ خام همیشه فیلترِ سخت‌گیرانه‌تر را
    برنده می‌کند، چون `n` کوچک‌تر واریانسِ بیشتری دارد. `z` دوجمله‌ای این تورّم
    را با تقسیم بر `sqrt(p(1-p)/n)` **درست** جریمه می‌کند. این فقط یک ابزارِ
    رتبه‌بندیِ ارزان در فازِ A است؛ حکمِ نهایی با جای‌گشتِ فازِ B صادر می‌شود.
    """
    lo = min(300, max(0, len(df) // 10))
    cands = []
    base = {}
    for theta in THETA_GRID:
        ls, ss = S358.rule_signals(v['long'], v['short'], theta)
        wr0, n0, _, _ = wr_on(ls, ss, tables, lo=lo, hi=cut)
        base[theta] = dict(wr=wr0, n=n0, sig=(ls, ss))
        if verbose:
            print(f"  [A] θ={theta:2d} baseline IS: n={n0} WR="
                  f"{'--' if wr0 is None else f'{wr0:.2f}%'}", flush=True)

    series_cache = {}
    for name, p, dirn in FILTER_SPECS:
        key = (name, p)
        if key not in series_cache:
            series_cache[key] = filter_series(df, name, p)
        vals = series_cache[key]
        for q in Q_GRID:
            thr = in_sample_threshold(vals, cut, q, dirn)
            if thr is None:
                continue
            fm = filter_mask(vals, thr, dirn)
            for theta in THETA_GRID:
                b = base[theta]
                if b['wr'] is None or b['n'] < N_IS_FLOOR:
                    continue
                ls, ss = b['sig']
                wr1, n1, _, _ = wr_on(ls & fm, ss & fm, tables, lo=lo, hi=cut)
                if wr1 is None or n1 < N_IS_FLOOR:
                    continue
                p0 = b['wr'] / 100.0
                sd = 100.0 * (p0 * (1.0 - p0) / n1) ** 0.5
                lift = wr1 - b['wr']
                cands.append(dict(name=name, p=p, dirn=dirn, q=q, thr=thr,
                                  theta=theta, n_is=n1, wr_is=round(wr1, 3),
                                  wr_base_is=round(b['wr'], 3),
                                  n_base_is=b['n'],
                                  keep_frac=round(n1 / b['n'], 4),
                                  lift_is=round(lift, 3),
                                  z_binom=round(lift / sd, 3) if sd > 0 else None))
    cands.sort(key=lambda d: (-(d['z_binom'] if d['z_binom'] is not None else -99)))
    if verbose:
        print(f"  [A] {len(cands)} admissible candidates "
              f"(floor n_is ≥ {N_IS_FLOOR}); top 6 by binomial z:", flush=True)
        for c in cands[:6]:
            print(f"      {c['name']}_{c['p']}(q={c['q']}) θ={c['theta']:2d} "
                  f"n={c['n_is']:4d} keep={c['keep_frac']:.3f} "
                  f"WR {c['wr_base_is']:.2f}→{c['wr_is']:.2f} "
                  f"lift={c['lift_is']:+.2f}pp z={c['z_binom']}", flush=True)
    return cands, series_cache


# ═══════════════════ ۵. فازِ C — تعمیمِ ساختاری روی ۷۲ عضو ═══════════════════
def phase_c(F, fracs, fm, tables, lo, hi, verbose=True):
    """آیا فیلتر اعضای **فردی** را هم بالا می‌برد، یا فقط `ensemble` را؟"""
    res_l, xb_l, res_s, xb_s = tables
    rows, better, worse, same = [], 0, 0, 0
    for side in ('long', 'short'):
        for w, buf, reg, sec in itertools.product(
                S357.W_GRID, S357.BUF_GRID, S357.REGIME_GRID, S357.SECOND_GRID):
            s = S357.signals_vec(F, fracs[w], side, w, buf, reg, sec, None, None)
            zero = np.zeros_like(s)
            if side == 'long':
                wr0, n0, _, _ = wr_on(s, zero, tables, lo=lo, hi=hi)
                wr1, n1, _, _ = wr_on(s & fm, zero, tables, lo=lo, hi=hi)
            else:
                wr0, n0, _, _ = wr_on(zero, s, tables, lo=lo, hi=hi)
                wr1, n1, _, _ = wr_on(zero, s & fm, tables, lo=lo, hi=hi)
            d = None if (wr0 is None or wr1 is None) else round(wr1 - wr0, 3)
            if d is None:
                same += 1
            elif d > 0:
                better += 1
            elif d < 0:
                worse += 1
            else:
                same += 1
            rows.append(dict(side=side, w=w, buf=buf,
                             chop_min=reg['chop_min'], second=sec,
                             n_base=n0, n_filt=n1,
                             wr_base=None if wr0 is None else round(wr0, 3),
                             wr_filt=None if wr1 is None else round(wr1, 3),
                             delta=d))
            del s
    ok = better >= GEN_MIN_MEMBERS
    if verbose:
        print(f"  [C] generalisation: better={better} worse={worse} "
              f"undetermined={same} of {len(rows)} | need ≥{GEN_MIN_MEMBERS} "
              f"⇒ {'PASS' if ok else 'FAIL'}", flush=True)
    return dict(n_members=len(rows), better=better, worse=worse,
                undetermined=same, threshold=GEN_MIN_MEMBERS, passed=bool(ok),
                members=rows)


# ═══════════════════════ ۶. فازِ B — آزمونِ تأییدیِ یگانه ═══════════════════════
def phase_b(card, df, asset, F, fracs, v, tables, cut, chosen, series_cache,
            k_perm=PERM_K, verbose=True, run_gen=True):
    n = len(df)
    lo = min(300, max(0, n // 10))
    sl, tp, mh = chosen['sl'], chosen['tp'], chosen['mh']
    vals = series_cache.get((chosen['name'], chosen['p']))
    if vals is None:
        vals = filter_series(df, chosen['name'], chosen['p'])
    fm = filter_mask(vals, chosen['thr'], chosen['dirn'])

    ls_raw, ss_raw = S358.rule_signals(v['long'], v['short'], chosen['theta'])
    # فیلتر + محدودسازی به ۴۰٪ آخر (سیگنالِ پیش از `cut` صفر می‌شود)
    oos = np.zeros(n, bool)
    oos[max(cut, lo):] = True
    ls = ls_raw & fm & oos
    ss = ss_raw & fm & oos
    ls_nf = ls_raw & oos              # فیلترنشده، همان بازه — پایهٔ SUBSET
    ss_nf = ss_raw & oos

    out = dict(card=card, phase='B', chosen=chosen,
               oos_bars=[int(max(cut, lo)), int(n)],
               n_trials=dict(honest=N_TRIALS_HONEST,
                             conservative=N_TRIALS_CONSERV,
                             stress=N_TRIALS_STRESS))

    wr_f, n_f, nl_f, ns_f = wr_on(ls, ss, tables, lo=max(cut, lo), hi=n)
    wr_b, n_b, _, _ = wr_on(ls_nf, ss_nf, tables, lo=max(cut, lo), hi=n)
    out['oos_walk'] = dict(wr_filtered=None if wr_f is None else round(wr_f, 3),
                           n_filtered=n_f,
                           wr_unfiltered=None if wr_b is None else round(wr_b, 3),
                           n_unfiltered=n_b,
                           keep_frac=round(n_f / n_b, 4) if n_b else None,
                           n_long=nl_f, n_short=ns_f)
    if verbose:
        print(f"  [B] OOS bars {max(cut, lo)}..{n} | unfiltered n={n_b} WR="
              f"{'--' if wr_b is None else f'{wr_b:.2f}%'} → filtered n={n_f} "
              f"WR={'--' if wr_f is None else f'{wr_f:.2f}%'}", flush=True)

    tr = se.simulate_trades(df, ls, ss, sl_pip=sl, tp_pip=tp, asset=asset,
                            max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) < 5:
        out['status'] = 'NO_TRADES_OOS'
        out['decision'] = 'DEAD_UNDER_FILTER'
        return out
    nt = len(tr)
    wr_obs = 100.0 * float((tr['pnl_pip'] > 0).sum()) / nt
    out['n_trades_engine'] = nt
    out['wr_engine'] = round(wr_obs, 3)
    out['parity_walk_vs_engine'] = dict(n_engine=nt, n_walk=n_f,
                                        wr_engine=round(wr_obs, 3),
                                        wr_walk=None if wr_f is None else round(wr_f, 3))

    # H7 نیاز به holdout دارد؛ ۶۰/۴۰ **درونِ** همان ۴۰٪ آخر
    split_bar = int(max(cut, lo) + 0.60 * (n - max(cut, lo)))
    out['split_bar_within_oos'] = split_bar
    close = df['close'].to_numpy(float)
    bar_time = df['time'].to_numpy()

    unc = {'long': S358.uncond_side(tables[0], tables[1], n, max(cut, lo)),
           'short': S358.uncond_side(tables[2], tables[3], n, max(cut, lo))}
    out['uncond_wr_oos'] = {k: (None if x is None else round(x, 3))
                            for k, x in unc.items()}

    def side_block(draws, unc_side):
        if draws.size == 0:
            return dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                        perm_max=None, perm_k=0)
        return dict(uncond_wr=unc_side, perm_mean=float(draws.mean()),
                    perm_sd=float(draws.std(ddof=1)),
                    perm_max=float(draws.max()), perm_k=int(draws.size))

    out['seeds'] = {}
    for seed in SEEDS:
        s_all, s_l, s_s = null_subset(ls_nf, ss_nf, tables, n_f, k_perm, seed,
                                      max(cut, lo), n)
        h_all, h_l, h_s = null_shift_masked(ls_raw, ss_raw, fm, tables, k_perm,
                                            seed, max(cut, lo), n)
        blk = {}
        for tag, (d_all, d_l, d_s) in (('subset', (s_all, s_l, s_s)),
                                       ('shift', (h_all, h_l, h_s))):
            null = {'long': side_block(d_l, unc['long']),
                    'short': side_block(d_s, unc['short'])}
            p_emp, n_ge = S357.empirical_p(d_all, wr_obs)
            sd = float(d_all.std(ddof=1)) if d_all.size > 1 else None
            lab = {}
            for name_, ntr in (('honest', N_TRIALS_HONEST),
                               ('conservative', N_TRIALS_CONSERV),
                               ('stress', N_TRIALS_STRESS)):
                r = R2.compute_rqs2(tr, asset, sl_pip=sl, tp_pip=tp,
                                    bar_time=bar_time, close=close, null=null,
                                    n_trials=ntr, split_bar=split_bar)
                lab[name_] = dict(verdict=r.get('verdict'),
                                  score=r.get('rqs2_score'), rank=r.get('rank'),
                                  gates=r.get('gates'), metrics=r.get('metrics'),
                                  notes=r.get('notes'))
            blk[tag] = dict(
                null_mean=round(float(d_all.mean()), 3) if d_all.size else None,
                null_sd=None if sd is None else round(sd, 3), k=int(d_all.size),
                lift_pp=(round(wr_obs - float(d_all.mean()), 3)
                         if d_all.size else None),
                z=(round((wr_obs - float(d_all.mean())) / sd, 3)
                   if sd and sd > 0 else None),
                p_empirical=round(p_emp, 6), n_draws_ge_obs=n_ge,
                labels=lab)
        accept = bool(
            blk['subset']['labels']['conservative']['verdict'] == 'ACCEPT'
            and blk['shift']['labels']['conservative']['verdict'] == 'ACCEPT'
            and blk['subset']['p_empirical'] <= P_BAR
            and blk['shift']['p_empirical'] <= P_BAR)
        blk['accept_both_nulls_conservative'] = accept
        out['seeds'][str(seed)] = blk
        if verbose:
            for tag in ('subset', 'shift'):
                b = blk[tag]
                bad = [g for g, x in
                       (b['labels']['conservative']['gates'] or {}).items()
                       if x is not True]
                print(f"     seed={seed} {tag.upper():6s} null={b['null_mean']}% "
                      f"sd={b['null_sd']} lift={b['lift_pp']}pp z={b['z']} "
                      f"p={b['p_empirical']:.5f} | conserv: "
                      f"{b['labels']['conservative']['verdict']} "
                      f"score={b['labels']['conservative']['score']} "
                      f"fail={bad or 'NONE'}", flush=True)

    out['all_seeds_accept'] = bool(
        out['seeds'] and all(s['accept_both_nulls_conservative']
                             for s in out['seeds'].values()))

    if run_gen:
        out['phase_c'] = phase_c(F, fracs, fm, tables, max(cut, lo), n,
                                 verbose=verbose)
    else:
        out['phase_c'] = dict(skipped=True,
                              reason='transfer card — phase C is only required '
                                     'for the two search cards')
    out['status'] = 'JUDGED'
    gen_ok = bool(out['phase_c'].get('passed')) if run_gen else True
    out['decision'] = ('ALIVE_UNDER_FILTER'
                       if (out['all_seeds_accept'] and gen_ok)
                       else 'DEAD_UNDER_FILTER')
    return out


# ═══════════════════════════ ۷. اجرا برای یک کارت ═══════════════════════════
def prepare(card):
    asset, tf = card.split('-')
    path = os.path.join('data', f'{asset}_{tf}.csv')
    if not os.path.exists(path):
        return None
    df = se.load_data(path)
    cfg, source, _, _ = S357.resolve_cfg(card, df, asset)
    F = S357.base_features(df, cfg)
    fracs = {w: S358._fractal_levels(F['h'], F['l'], w) for w in S357.W_GRID}
    v, _ = S358.vote_counts(F, fracs)
    tables = (*S357.outcome_table(df, asset, cfg['sl'], cfg['tp'], cfg['mh'],
                                  side='long'),
              *S357.outcome_table(df, asset, cfg['sl'], cfg['tp'], cfg['mh'],
                                  side='short'))
    return dict(asset=asset, tf=tf, df=df, cfg=cfg, source=source, F=F,
                fracs=fracs, v=v, tables=tables, cut=int(len(df) * SPLIT_FRAC))


def run_search_card(card, k_perm=PERM_K, verbose=True):
    P = prepare(card)
    if P is None:
        return dict(card=card, status='NO_DATA',
                    note=f'data/{card.replace("-", "_")}.csv does not exist')
    if verbose:
        print(f"\n=== {card} :: bars={len(P['df'])} cut60={P['cut']} "
              f"bracket={P['source']} SL={P['cfg']['sl']} TP={P['cfg']['tp']} "
              f"mh={P['cfg']['mh']}", flush=True)
    cands, cache = phase_a(P['df'], P['F'], P['v'], P['tables'], P['cut'],
                           verbose=verbose)
    if not cands:
        return dict(card=card, status='NO_CANDIDATE', phase_a_candidates=0,
                    note=f'no filter reached the derived in-sample floor of '
                         f'{N_IS_FLOOR} trades')
    top = dict(cands[0])
    top.update(sl=P['cfg']['sl'], tp=P['cfg']['tp'], mh=P['cfg']['mh'])
    rec = phase_b(card, P['df'], P['asset'], P['F'], P['fracs'], P['v'],
                  P['tables'], P['cut'], top, cache, k_perm=k_perm,
                  verbose=verbose, run_gen=True)
    rec['phase_a_candidates'] = len(cands)
    rec['phase_a_top10'] = cands[:10]
    rec['role'] = 'SEARCH_CARD'
    return rec


def run_transfer_card(card, frozen, k_perm=PERM_K, verbose=True):
    """کارتِ خارج از دامنهٔ جست‌وجو — همان زوجِ منجمد، فقط انتقال‌پذیری."""
    P = prepare(card)
    if P is None:
        return dict(card=card, status='NO_DATA', role='TRANSFER_CARD',
                    note=f'data/{card.replace("-", "_")}.csv does not exist')
    vals = filter_series(P['df'], frozen['name'], frozen['p'])
    thr = in_sample_threshold(vals, P['cut'], frozen['q'], frozen['dirn'])
    if thr is None:
        return dict(card=card, status='NO_THRESHOLD', role='TRANSFER_CARD')
    ch = dict(frozen)
    ch.update(thr=thr, sl=P['cfg']['sl'], tp=P['cfg']['tp'], mh=P['cfg']['mh'])
    if verbose:
        print(f"\n=== {card} [TRANSFER] :: bars={len(P['df'])} "
              f"{frozen['name']}_{frozen['p']}(q={frozen['q']}) thr={thr:.4f} "
              f"θ={frozen['theta']}", flush=True)
    rec = phase_b(card, P['df'], P['asset'], P['F'], P['fracs'], P['v'],
                  P['tables'], P['cut'], ch, {(frozen['name'], frozen['p']): vals},
                  k_perm=k_perm, verbose=verbose, run_gen=False)
    rec['role'] = 'TRANSFER_CARD'
    rec['note'] = ('outside the pre-registered search domain — reported for '
                   'transferability only, cannot by itself admit the layer')
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cards', default='search')
    ap.add_argument('--k', type=int, default=PERM_K)
    ap.add_argument('--frozen', default=None,
                    help='JSON of the frozen pair for transfer cards')
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    if a.cards == 'search':
        cards = ['XAUUSD-M30', 'XAUUSD-M5']          # بندِ ۴ سندِ پیش‌ثبت
        for card in cards:
            rec = run_search_card(card, k_perm=a.k)
            with open(os.path.join(OUT, f'{card}.json'), 'w',
                      encoding='utf-8') as f:
                json.dump(rec, f, ensure_ascii=False, indent=1, default=str)
            print(f"  [saved] {OUT}/{card}.json status={rec.get('status')} "
                  f"decision={rec.get('decision')}", flush=True)
        return

    frozen = json.loads(a.frozen) if a.frozen else None
    for card in [c.strip() for c in a.cards.split(',') if c.strip()]:
        rec = run_transfer_card(card, frozen, k_perm=a.k)
        with open(os.path.join(OUT, f'{card}.json'), 'w', encoding='utf-8') as f:
            json.dump(rec, f, ensure_ascii=False, indent=1, default=str)
        print(f"  [saved] {OUT}/{card}.json status={rec.get('status')} "
              f"decision={rec.get('decision')}", flush=True)


if __name__ == '__main__':
    main()
