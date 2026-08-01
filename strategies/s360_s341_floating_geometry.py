# -*- coding: utf-8 -*-
"""
S360 — گامِ ۳پ: هندسهٔ **شناورِ** `SL/TP` بر حسبِ `ATR`ِ کندلِ سیگنال.

سندِ پیش‌ثبت: `results/S360_PREREGISTRATION_S341_FLOATING_GEOMETRY.md`
(این اسکریپت **پس از** آن سند نوشته شده و هیچ پارامتری بیرون از گریدِ آن ندارد.)

    SL_pip[i] = k_sl · ATR_p[i]        TP_pip[i] = rr · SL_pip[i]

`ATR` روی کندلِ **سیگنال** خوانده می‌شود و سفارش در بستنِ همان کندل برای
`open`ِ کندلِ بعد گذاشته می‌شود ⇒ هیچ اطلاعِ آینده‌ای وارد نمی‌شود.

────────────────────────────────────────────────────────────────────────────
⚠️ **تلهٔ آماریِ مرکزیِ این گام — و چرا نمی‌شود `WR`ها را مستقیم مقایسه کرد.**

این گام `RR` را عوض می‌کند، و `RR`ِ کوچک‌تر `WR` را **مکانیکی** بالا می‌برد،
بی‌آنکه یک ذره مهارت اضافه شود: با `rr = 0.85` هدف نزدیک‌تر از استاپ است، پس
حتی ورودِ کاملاً تصادفی هم بیشتر «برنده» می‌شود. بنابراین:

* رتبه‌بندیِ فازِ A **نمی‌تواند** روی `WR`ِ خام باشد؛ وگرنه گرید همیشه
  `rr = 0.85` را برنده اعلام می‌کند و ما فقط ریاضیاتِ براکت را کشف کرده‌ایم،
  نه لبه‌ای در بازار.
* فازِ C هم **نمی‌تواند** `WR`ِ عضو با هندسهٔ شناور را با `WR`ِ همان عضو با
  هندسهٔ آرشیو مقایسه کند؛ اگر `rr`ِ برنده کوچک‌تر از `rr`ِ آرشیو باشد، **همهٔ**
  ۷۲ عضو مکانیکی «بهتر» می‌شوند و آزمونِ تعمیم به یک `72/72`ِ توخالی بدل می‌شود.

راهِ درست در هر دو جا یکی است: هر هندسه با **خطِ مبنایِ بی‌شرطِ خودش** سنجیده
می‌شود — یعنی `WR`ِ «ورود در هر کندلِ ممکن با همان براکت» (`S358.uncond_side`).
آماره همیشه **لیفت** است: `WR_layer − WR_uncond(same geometry)`. اثرِ مکانیکیِ
`RR` در هر دو جملهٔ تفریق حاضر است و حذف می‌شود. این عیناً همان کاری است که
`H3`ِ موتور با مدلِ صفر می‌کند، و §۴ سندِ پیش‌ثبت (سپرِ اشتباهِ #۸) روی آن
تکیه دارد.
────────────────────────────────────────────────────────────────────────────

فازها (مرزِ داده در کد اجرا می‌شود، نه با انضباط):
  A — جست‌وجو **فقط** روی `bar < 0.60·n`، هر ۴ کارتِ سایت، ۱۲۸ آزمون در هر کارت.
  B — **یک** آزمونِ تأییدی روی `bar ≥ 0.60·n` با زوجِ منجمدِ فازِ A. بی‌بازگشت.
  C — تعمیمِ ساختاری روی ۷۲ عضوِ فردی، همان ۴۰٪ آخر، آستانهٔ ≥۴۴ از ۷۲.

اجرا:
    python3 strategies/s360_s341_floating_geometry.py --cards search
    python3 strategies/s360_s341_floating_geometry.py --cards all
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

OUT = "results/_scan_S360"

SEEDS = S357.SEEDS                # (23, 101, 777)
PERM_K = S357.PERM_K              # 2000
P_BAR = S358.P_BAR                # 0.001 — شل نمی‌شود
SPLIT_FRAC = 0.60                 # مرزِ فازِ A/B
THETA_GRID = S358.THETA_GRID      # (4, 7, 11, 16) — پیش‌ثبتِ S358، تغییر نمی‌کند
GEN_MIN_MEMBERS = 44              # ≥۴۴ از ۷۲ — پیش‌ثبتِ فازِ C

# ─────────────── گریدِ **بستهٔ** پیش‌ثبت‌شدهٔ §۳.۲ سندِ S360 ───────────────
K_SL_GRID = (2.1, 4.7, 8.3, 13.4)     # تنگ … معادلِ آرشیو (۸.۳۳× و ۱۴.۳×)
RR_GRID = (0.85, 1.21, 1.68, 2.34)    # دو طرفِ `RR`های آرشیو (۱.۴۴ … ۲.۹۸)
ATR_P_GRID = (14, 34)                 # کوتاه/بلند، غیررند در سطحِ ۳۴

# کفِ نمونهٔ درون‌نمونه‌ای — عیناً همان زنجیرِ مشتقِ S359 (نه عددِ دلبخواه):
#   موتور `H7` دستِ‌کم ۱۵ معاملهٔ holdout می‌خواهد؛ holdout = ۴۰٪ِ **درونِ** بازهٔ
#   خارج‌نمونه ⇒ خارج‌نمونه ≥ ۳۸؛ نسبتِ ۶۰/۴۰ دو بازه ⇒ درون‌نمونه ≥ ۵۷.
N_IS_FLOOR = 57

N_TRIALS_HONEST = 1
N_TRIALS_CONSERV = len(K_SL_GRID) * len(RR_GRID) * len(ATR_P_GRID) * len(THETA_GRID)  # ۱۲۸
N_TRIALS_STRESS = N_TRIALS_CONSERV * 4                                                 # ۵۱۲

SEARCH_CARDS = ["XAUUSD-M5", "XAUUSD-M15", "XAUUSD-M30", "XAUUSD-H1"]
CARDS_ALL = S357.CARDS_ALL


# ═════════════════════ ۱. هندسهٔ شناور و جدولِ برآمد ═════════════════════
def atr_series(df, p):
    return ib.atr_s(df, p=p).to_numpy(float)


def float_brackets(atr_pip, k_sl, rr):
    """آرایهٔ `SL/TP` بر حسبِ pip، و ماسکِ کندل‌های **قابلِ ورود**.

    کندلی که `ATR` آن `NaN` است (گرم‌شدنِ اندیکاتور) قابلِ ورود **نیست** و با
    عددِ جانشین معامله نمی‌شود — بندِ ۳.۱ سندِ پیش‌ثبت.
    """
    ok = np.isfinite(atr_pip) & (atr_pip > 0)
    sl = np.where(ok, k_sl * atr_pip, np.nan)
    return sl, rr * sl, ok


def tables_for(df, asset, sl_arr, tp_arr, ok, mh):
    """`(res, xbar)` دو سمت با براکتِ **هر-کندلی**.

    `S357.outcome_table` از ابتدا برداری نوشته شده و آرایهٔ هم‌طول را می‌پذیرد؛
    فقط باید کندل‌های `NaN` را صریحاً غیرقابلِ‌ورود کرد، چون شاخهٔ `timeout`
    آن تابع در نبودِ `SL/TP` هم یک نتیجه اسناد می‌دهد.
    """
    out = []
    for side in ('long', 'short'):
        res, xb = S357.outcome_table(df, asset, sl_arr, tp_arr, mh, side=side)
        res = res.copy()
        res[~ok] = 0
        out.extend([res, xb.astype(np.int64)])
    return tuple(out)


# ═════════════════════ ۲. آمارهٔ لیفت با خطِ مبنایِ خودِ هندسه ═════════════════════
def lift_stat(long_sig, short_sig, tables, n, lo, hi):
    """لیفتِ لایه نسبت به خطِ مبنایِ بی‌شرطِ **همان هندسه**.

    این تابع قلبِ ضدِ-تلهٔ این گام است (بندِ سرصفحه): مقایسهٔ `WR`ِ خام بینِ
    هندسه‌ها بی‌معناست، چون `RR`ِ کوچک‌تر `WR` را مکانیکی بالا می‌برد. خطِ مبنا
    «ورود در هر کندلِ ممکن با همان براکت» است، پس اثرِ مکانیکی در هر دو جمله
    حاضر و حذف می‌شود.

    خطِ مبنا با **تعدادِ معاملهٔ هر سمت** وزن می‌گیرد، عیناً منطقِ
    `rqs2.blend_null`، تا ترکیبِ long/shortِ خودِ لایه بازتاب یابد.
    """
    res_l, xb_l, res_s, xb_s = tables
    sb, isl = S358.merged(long_sig, short_sig)
    keep = (sb >= lo) & (sb < hi)
    sb, isl = sb[keep], isl[keep]
    if sb.size == 0:
        return None
    nl, wl, ns, ws = S358.walk_fast(sb, isl, res_l, xb_l, res_s, xb_s)
    tot = nl + ns
    if tot == 0:
        return None
    wr = 100.0 * (wl + ws) / tot
    u_l = S358.uncond_side(res_l, xb_l, hi, lo)
    u_s = S358.uncond_side(res_s, xb_s, hi, lo)
    parts, wts = [], []
    if nl and u_l is not None:
        parts.append(u_l); wts.append(nl)
    if ns and u_s is not None:
        parts.append(u_s); wts.append(ns)
    if not parts:
        return None
    base = float(np.average(parts, weights=wts))
    lift = wr - base
    se_b = float(np.sqrt(max(base * (100.0 - base), 1e-9) / tot))
    return dict(wr=round(wr, 3), base=round(base, 3), lift_pp=round(lift, 3),
                z_binom=round(lift / se_b, 3), n=int(tot),
                n_long=int(nl), n_short=int(ns))


# ═══════════════════════ ۳. صفرِ حاکم — شیفتِ دوّارِ مشترک ═══════════════════════
def null_shift_geom(long_sig, short_sig, tables, k_perm, seed, lo, hi):
    """صفرِ شیفتِ دوّار، با جدولِ برآمدِ **همان هندسهٔ کاندیدا**.

    صف دقیقاً همان هندسه را می‌بیند، پس صفر نمی‌تواند از تفاوتِ براکت زیان یا
    سود ببرد؛ تنها هم‌ترازیِ سیگنال با قیمت نابود می‌شود (بندِ ۵ سندِ پیش‌ثبت).

    مدلِ «زیرمجموعهٔ هم‌انتخاب‌گر» این‌جا **عمداً محاسبه نمی‌شود**: این گام چیزی
    را انتخاب نمی‌کند و `n` را عوض نمی‌کند، پس آن سنجه بی‌ربط است.
    """
    res_l, xb_l, res_s, xb_s = tables
    rng = np.random.default_rng(seed)
    d_all, d_l, d_s = [], [], []
    for _ in range(k_perm):
        sh = int(rng.integers(lo, hi))
        sb, isl = S358.merged(np.roll(long_sig, sh), np.roll(short_sig, sh))
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
def phase_a(df, asset, F, v, cut, mh, verbose=True):
    """جست‌وجوی درون‌نمونه‌ای روی ۱۲۸ آزمون؛ رتبه‌بندی با `z`ِ دوجمله‌ایِ لیفت.

    این رتبه‌بندی یک ابزارِ **ارزان** است و اقتدارِ حکم ندارد؛ حکم را فقط
    ماشینِ جای‌گشتِ فازِ B صادر می‌کند. اما برخلافِ `WR`ِ خام، سوگیریِ مکانیکیِ
    `RR` را ندارد (بندِ سرصفحه).
    """
    n = len(df)
    lo = min(300, max(0, n // 10))
    pip = se.ASSETS[asset]['pip']
    atr_cache = {p: atr_series(df, p) / pip for p in ATR_P_GRID}
    rows = []
    for atr_p, k_sl, rr in itertools.product(ATR_P_GRID, K_SL_GRID, RR_GRID):
        sl_arr, tp_arr, ok = float_brackets(atr_cache[atr_p], k_sl, rr)
        tabs = tables_for(df, asset, sl_arr, tp_arr, ok, mh)
        for th in THETA_GRID:
            ls, ss = S358.rule_signals(v['long'], v['short'], th)
            ls = ls & ok
            ss = ss & ok
            st = lift_stat(ls, ss, tabs, n, lo, cut)
            if st is None or st['n'] < N_IS_FLOOR:
                rows.append(dict(atr_p=atr_p, k_sl=k_sl, rr=rr, theta=th,
                                 skipped=True,
                                 reason=('no trades' if st is None
                                         else f"n={st['n']} < {N_IS_FLOOR}"),
                                 **({} if st is None else st)))
                continue
            rows.append(dict(atr_p=atr_p, k_sl=k_sl, rr=rr, theta=th,
                             skipped=False, **st))
        del tabs
    live = [r for r in rows if not r['skipped']]
    live.sort(key=lambda r: -r['z_binom'])
    if verbose:
        print(f"  [A] in-sample bars {lo}..{cut} | {len(live)}/{len(rows)} of the "
              f"128 candidates cleared the n≥{N_IS_FLOOR} floor", flush=True)
        for r in live[:6]:
            print(f"      atr_p={r['atr_p']:<3d} k_sl={r['k_sl']:<5} "
                  f"rr={r['rr']:<5} θ={r['theta']:<3d} n={r['n']:5d} "
                  f"WR={r['wr']:6.2f}% base={r['base']:6.2f}% "
                  f"lift={r['lift_pp']:+6.2f}pp z≈{r['z_binom']:+.2f}", flush=True)
    chosen = None
    if live:
        b = live[0]
        chosen = dict(atr_p=b['atr_p'], k_sl=b['k_sl'], rr=b['rr'],
                      theta=b['theta'], mh=mh,
                      is_lift_pp=b['lift_pp'], is_wr=b['wr'], is_base=b['base'],
                      is_n=b['n'], is_z_binom=b['z_binom'])
    return dict(candidates=rows, chosen=chosen,
                n_cleared=len(live), n_total=len(rows))


def spearman_rr_lift(rows):
    """آزمونِ مستقیمِ `P11`: همبستگیِ اسپیرمنِ `(rr, لیفت)` روی گریدِ فازِ A."""
    live = [r for r in rows if not r['skipped']]
    if len(live) < 4:
        return None
    x = np.asarray([r['rr'] for r in live], float)
    y = np.asarray([r['lift_pp'] for r in live], float)

    def rank(a):
        o = np.argsort(a, kind='mergesort')
        rk = np.empty(a.size, float)
        rk[o] = np.arange(1, a.size + 1, dtype=float)
        # میانگینِ رتبه برای گره‌ها
        for val in np.unique(a):
            m = a == val
            rk[m] = rk[m].mean()
        return rk

    rx, ry = rank(x), rank(y)
    rho = float(np.corrcoef(rx, ry)[0, 1])
    return dict(rho=round(rho, 4), n=len(live),
                falsifies_P11=bool(rho >= 0.0))


# ═══════════════════ ۵. فازِ C — تعمیمِ ساختاری روی ۷۲ عضو ═══════════════════
def phase_c(F, fracs, asset, df, arch, chosen, ok, tabs_new, lo, hi,
            verbose=True):
    """آیا هندسهٔ شناور، اعضای **فردی** را هم بالا می‌برد یا فقط `ensemble` را؟

    ⚠️ مقایسه روی **لیفت** است نه `WR`ِ خام. اگر `rr`ِ برنده کوچک‌تر از `rr`ِ
    آرشیو باشد، `WR`ِ خامِ همهٔ ۷۲ عضو مکانیکی بالا می‌رود و آزمون به یک
    `72/72`ِ توخالی بدل می‌شود. هر عضو با خطِ مبنایِ بی‌شرطِ **هندسهٔ خودش**
    سنجیده می‌شود، پس اثرِ مکانیکی حذف می‌گردد.
    """
    tabs_old = tables_for(
        df, asset,
        np.full(len(df), float(arch['sl'])), np.full(len(df), float(arch['tp'])),
        np.ones(len(df), bool), arch['mh'])
    rows, better, worse, same = [], 0, 0, 0
    for side in ('long', 'short'):
        for w, buf, reg, sec in itertools.product(
                S357.W_GRID, S357.BUF_GRID, S357.REGIME_GRID, S357.SECOND_GRID):
            s = S357.signals_vec(F, fracs[w], side, w, buf, reg, sec, None, None)
            zero = np.zeros_like(s)
            a = (s, zero) if side == 'long' else (zero, s)
            b = ((s & ok), zero) if side == 'long' else (zero, (s & ok))
            st_old = lift_stat(a[0], a[1], tabs_old, len(df), lo, hi)
            st_new = lift_stat(b[0], b[1], tabs_new, len(df), lo, hi)
            d = (None if (st_old is None or st_new is None)
                 else round(st_new['lift_pp'] - st_old['lift_pp'], 3))
            if d is None:
                same += 1
            elif d > 0:
                better += 1
            elif d < 0:
                worse += 1
            else:
                same += 1
            rows.append(dict(
                side=side, w=w, buf=buf, chop_min=reg['chop_min'], second=sec,
                lift_archive=None if st_old is None else st_old['lift_pp'],
                lift_floating=None if st_new is None else st_new['lift_pp'],
                n_archive=None if st_old is None else st_old['n'],
                n_floating=None if st_new is None else st_new['n'],
                delta_lift=d))
            del s
    del tabs_old
    ok_gen = better >= GEN_MIN_MEMBERS
    if verbose:
        print(f"  [C] generalisation on LIFT: better={better} worse={worse} "
              f"undetermined={same} of {len(rows)} | need ≥{GEN_MIN_MEMBERS} "
              f"⇒ {'PASS' if ok_gen else 'FAIL'}", flush=True)
    return dict(n_members=len(rows), better=better, worse=worse,
                undetermined=same, threshold=GEN_MIN_MEMBERS,
                statistic='delta_of_lift_vs_own_uncond_baseline',
                passed=bool(ok_gen), members=rows)


# ═══════════════════════ ۶. فازِ B — آزمونِ تأییدیِ یگانه ═══════════════════════
def phase_b(card, df, asset, F, fracs, v, cut, chosen, arch,
            k_perm=PERM_K, verbose=True, run_gen=True):
    n = len(df)
    lo = min(300, max(0, n // 10))
    start = max(cut, lo)
    pip = se.ASSETS[asset]['pip']
    atr_pip = atr_series(df, chosen['atr_p']) / pip
    sl_arr, tp_arr, ok = float_brackets(atr_pip, chosen['k_sl'], chosen['rr'])
    tabs = tables_for(df, asset, sl_arr, tp_arr, ok, chosen['mh'])

    ls_raw, ss_raw = S358.rule_signals(v['long'], v['short'], chosen['theta'])
    oos = np.zeros(n, bool)
    oos[start:] = True
    ls = ls_raw & ok & oos
    ss = ss_raw & ok & oos

    out = dict(card=card, phase='B', chosen=chosen, archive_bracket=arch,
               oos_bars=[int(start), int(n)],
               n_trials=dict(honest=N_TRIALS_HONEST,
                             conservative=N_TRIALS_CONSERV,
                             stress=N_TRIALS_STRESS))
    st = lift_stat(ls, ss, tabs, n, start, n)
    out['oos_walk'] = st
    if verbose:
        print(f"  [B] OOS bars {start}..{n} | "
              + ('no trades' if st is None else
                 f"n={st['n']} WR={st['wr']:.2f}% base={st['base']:.2f}% "
                 f"lift={st['lift_pp']:+.2f}pp"), flush=True)

    tr = se.simulate_trades(df, ls, ss, sl_pip=sl_arr, tp_pip=tp_arr,
                            asset=asset, max_hold=chosen['mh'],
                            allow_overlap=False)
    if tr is None or len(tr) < 5:
        out['status'] = 'NO_TRADES_OOS'
        out['decision'] = 'DEAD_UNDER_FLOATING_GEOMETRY'
        return out
    nt = len(tr)
    wr_obs = 100.0 * float((tr['pnl_pip'] > 0).sum()) / nt
    sl_med = float(np.median(tr['sl_pip'].to_numpy(float)))
    # `RR` تحتِ این پارامترسازی **دقیقاً** ثابت است ⇒ سربه‌سرِ `H2` دقیق می‌ماند.
    out['n_trades_engine'] = nt
    out['wr_engine'] = round(wr_obs, 3)
    out['sl_pip_median'] = round(sl_med, 2)
    out['rr_exact'] = chosen['rr']
    out['parity_walk_vs_engine'] = dict(
        n_engine=nt, n_walk=None if st is None else st['n'],
        wr_engine=round(wr_obs, 3), wr_walk=None if st is None else st['wr'])

    split_bar = int(start + 0.60 * (n - start))
    out['split_bar_within_oos'] = split_bar
    close = df['close'].to_numpy(float)
    bar_time = df['time'].to_numpy()
    unc = {'long': S358.uncond_side(tabs[0], tabs[1], n, start),
           'short': S358.uncond_side(tabs[2], tabs[3], n, start)}
    out['uncond_wr_oos'] = {k: (None if x is None else round(x, 3))
                            for k, x in unc.items()}

    def side_block(draws, u):
        if draws.size == 0:
            return dict(uncond_wr=u, perm_mean=None, perm_sd=None,
                        perm_max=None, perm_k=0)
        return dict(uncond_wr=u, perm_mean=float(draws.mean()),
                    perm_sd=float(draws.std(ddof=1)),
                    perm_max=float(draws.max()), perm_k=int(draws.size))

    out['seeds'] = {}
    for seed in SEEDS:
        d_all, d_l, d_s = null_shift_geom(ls_raw & ok, ss_raw & ok, tabs,
                                          k_perm, seed, start, n)
        null = {'long': side_block(d_l, unc['long']),
                'short': side_block(d_s, unc['short'])}
        p_emp, n_ge = S357.empirical_p(d_all, wr_obs)
        sd = float(d_all.std(ddof=1)) if d_all.size > 1 else None
        lab = {}
        for name_, ntr in (('honest', N_TRIALS_HONEST),
                           ('conservative', N_TRIALS_CONSERV),
                           ('stress', N_TRIALS_STRESS)):
            r = R2.compute_rqs2(tr, asset, sl_pip=sl_med,
                                tp_pip=sl_med * chosen['rr'],
                                bar_time=bar_time, close=close, null=null,
                                n_trials=ntr, split_bar=split_bar)
            lab[name_] = dict(verdict=r.get('verdict'), score=r.get('rqs2_score'),
                              rank=r.get('rank'), gates=r.get('gates'),
                              metrics=r.get('metrics'), notes=r.get('notes'))
        blk = dict(
            null_mean=round(float(d_all.mean()), 3) if d_all.size else None,
            null_sd=None if sd is None else round(sd, 3), k=int(d_all.size),
            lift_pp=(round(wr_obs - float(d_all.mean()), 3)
                     if d_all.size else None),
            z=(round((wr_obs - float(d_all.mean())) / sd, 3)
               if sd and sd > 0 else None),
            p_empirical=round(p_emp, 6), n_draws_ge_obs=n_ge, labels=lab)
        blk['accept_conservative'] = bool(
            lab['conservative']['verdict'] == 'ACCEPT'
            and blk['p_empirical'] <= P_BAR)
        out['seeds'][str(seed)] = blk
        if verbose:
            bad = [g for g, x in (lab['conservative']['gates'] or {}).items()
                   if x is not True]
            print(f"     seed={seed} SHIFT null={blk['null_mean']}% "
                  f"sd={blk['null_sd']} lift={blk['lift_pp']}pp z={blk['z']} "
                  f"p={blk['p_empirical']:.5f} | conserv: "
                  f"{lab['conservative']['verdict']} "
                  f"score={lab['conservative']['score']} fail={bad or 'NONE'}",
                  flush=True)

    out['all_seeds_accept'] = bool(
        out['seeds'] and all(s['accept_conservative']
                             for s in out['seeds'].values()))
    if run_gen:
        out['phase_c'] = phase_c(F, fracs, asset, df, arch, chosen, ok, tabs,
                                 start, n, verbose=verbose)
    else:
        out['phase_c'] = dict(skipped=True,
                              reason='transfer card — phase C is required only '
                                     'for the four search cards')
    del tabs
    out['status'] = 'JUDGED'
    gen_ok = bool(out['phase_c'].get('passed')) if run_gen else True
    out['decision'] = ('ALIVE_UNDER_FLOATING_GEOMETRY'
                       if (out['all_seeds_accept'] and gen_ok)
                       else 'DEAD_UNDER_FLOATING_GEOMETRY')
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
    fracs = {w: S357._fractal_levels(F['h'], F['l'], w) for w in S357.W_GRID}
    v, _members = S358.vote_counts(F, fracs)   # v = {'long': counts, 'short': counts}
    arch = dict(sl=cfg['sl'], tp=cfg['tp'], mh=cfg['mh'],
                rr=round(cfg['tp'] / cfg['sl'], 3), source=source)
    return df, asset, cfg, F, fracs, v, arch


def save(rec, card):
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, f'{card}.json')
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(rec, f, ensure_ascii=False, indent=1, default=str)
    print(f"  [saved] {p} status={rec.get('status')} "
          f"decision={rec.get('decision')}", flush=True)


def run_search_card(card, k_perm=PERM_K, verbose=True):
    pre = prepare(card)
    if pre is None:
        rec = dict(card=card, status='NO_DATA',
                   note=f'data/{card.replace("-", "_")}.csv is absent')
        save(rec, card)
        return rec
    df, asset, cfg, F, fracs, v, arch = pre
    n = len(df)
    cut = int(n * SPLIT_FRAC)
    if verbose:
        print(f"\n=== {card} :: bars={n} cut60={cut} archive SL={arch['sl']} "
              f"TP={arch['tp']} RR={arch['rr']} mh={arch['mh']}", flush=True)
    a = phase_a(df, asset, F, v, cut, arch['mh'], verbose=verbose)
    rho = spearman_rr_lift(a['candidates'])
    if verbose and rho:
        print(f"      [P11] spearman(rr, lift) = {rho['rho']:+.4f} over "
              f"{rho['n']} candidates ⇒ "
              f"{'FALSIFIES P11' if rho['falsifies_P11'] else 'consistent with P11'}",
              flush=True)
    rec = dict(card=card, asset=asset, tf=card.split('-')[1], bars=n,
               split_bar=cut, archive_bracket=arch, phase_a=a,
               p11_spearman_rr_lift=rho)
    if a['chosen'] is None:
        rec['status'] = 'NO_CANDIDATE'
        rec['decision'] = 'DEAD_UNDER_FLOATING_GEOMETRY'
        save(rec, card)
        return rec
    b = phase_b(card, df, asset, F, fracs, v, cut, a['chosen'], arch,
                k_perm=k_perm, verbose=verbose, run_gen=True)
    rec['phase_b'] = b
    rec['status'] = b['status']
    rec['decision'] = b['decision']
    save(rec, card)
    return rec


TF_ORDER = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1', 'W1']


def pick_frozen(card, asset, frozen_by_asset, frozen_by_tf):
    """زوجِ منجمد برای یک کارتِ انتقال، با فالبکِ **بین‌دارایی**.

    ⚠️ نکتهٔ علمیِ این فالبک: `k_sl` بر حسبِ **واحدِ ATR** است، یعنی
    **بی‌بعد** (dimensionless). براکتِ ثابتِ آرشیو بر حسبِ pip بود و انتقالِ آن
    از طلا به یورو بی‌معنا بود — همان چیزی که `WR`های ۳۵٪ِ یوروی گامِ ۳الف را
    توضیح می‌داد. اما هندسهٔ **شناور** با نوسانِ خودِ دارایی مقیاس می‌گیرد، پس
    انتقالِ آن بین دارایی‌ها **مشروع** است و آزمونِ انتقال‌پذیری معنا پیدا می‌کند.
    بدونِ این فالبک، ۸ کارتِ یورو بی‌حکم می‌ماندند و تعهدِ چندتایم‌فریمیِ بندِ ۸
    سندِ پیش‌ثبت **ناتمام** می‌ماند.

    ترتیبِ اولویت: همان دارایی ← همان تایم‌فریم از داراییِ دیگر ← نزدیک‌ترین
    تایم‌فریمِ موجود. منبع در رکورد ثبت می‌شود تا هیچ انتقالی «بومی» جا نزند.
    """
    tf = card.split('-')[1]
    if frozen_by_asset.get(asset):
        return dict(frozen_by_asset[asset]), f'same-asset pair ({asset})'
    if frozen_by_tf.get(tf):
        return dict(frozen_by_tf[tf]), f'cross-asset pair, same timeframe ({tf})'
    if not frozen_by_tf:
        return None, None
    i = TF_ORDER.index(tf) if tf in TF_ORDER else 0
    best = min(frozen_by_tf,
               key=lambda t: abs((TF_ORDER.index(t) if t in TF_ORDER else 0) - i))
    return dict(frozen_by_tf[best]), f'cross-asset pair, nearest timeframe ({best})'


def run_transfer_card(card, frozen, frozen_by_tf=None, k_perm=PERM_K,
                      verbose=True):
    pre = prepare(card)
    if pre is None:
        rec = dict(card=card, status='NO_DATA',
                   note=f'data/{card.replace("-", "_")}.csv is absent')
        save(rec, card)
        return rec
    df, asset, cfg, F, fracs, v, arch = pre
    ch, src = pick_frozen(card, asset, frozen, frozen_by_tf or {})
    if not ch:
        rec = dict(card=card, status='NO_FROZEN_PAIR',
                   note='no search card produced any pair to transfer')
        save(rec, card)
        return rec
    ch['mh'] = arch['mh']          # `max_hold` همان عددِ منجمدِ خودِ کارت
    n = len(df)
    cut = int(n * SPLIT_FRAC)
    if verbose:
        print(f"\n=== {card} :: TRANSFER (outside search domain) bars={n} "
              f"frozen k_sl={ch['k_sl']} rr={ch['rr']} atr_p={ch['atr_p']} "
              f"θ={ch['theta']} mh={ch['mh']} | pair from: {src}", flush=True)
    b = phase_b(card, df, asset, F, fracs, v, cut, ch, arch,
                k_perm=k_perm, verbose=verbose, run_gen=False)
    rec = dict(card=card, asset=asset, tf=card.split('-')[1], bars=n,
               split_bar=cut, archive_bracket=arch, transfer=True,
               frozen_pair_source=src,
               phase_b=b, status=b['status'],
               decision=b['decision'] + '_TRANSFER',
               note='outside the search domain — a transfer card cannot admit '
                    'the layer on its own')
    save(rec, card)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cards', default='search')
    ap.add_argument('--k', type=int, default=PERM_K)
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()
    if args.cards == 'search':
        cards, transfers = SEARCH_CARDS, []
    elif args.cards == 'all':
        cards = SEARCH_CARDS
        transfers = [c for c in CARDS_ALL if c not in SEARCH_CARDS]
    else:
        cards = [c.strip() for c in args.cards.split(',') if c.strip()]
        transfers = []
    verbose = not args.quiet
    frozen, frozen_by_tf = {}, {}
    for card in cards:
        rec = run_search_card(card, k_perm=args.k, verbose=verbose)
        ch = (rec.get('phase_a') or {}).get('chosen')
        if not ch:
            continue
        pair = dict(k_sl=ch['k_sl'], rr=ch['rr'], atr_p=ch['atr_p'],
                    theta=ch['theta'])
        if rec.get('asset') and rec['asset'] not in frozen:
            frozen[rec['asset']] = pair
        if rec.get('tf'):
            frozen_by_tf.setdefault(rec['tf'], pair)
    for card in transfers:
        run_transfer_card(card, frozen, frozen_by_tf=frozen_by_tf,
                          k_perm=args.k, verbose=verbose)


if __name__ == '__main__':
    main()
