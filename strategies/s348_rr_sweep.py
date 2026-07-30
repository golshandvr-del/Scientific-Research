# -*- coding: utf-8 -*-
"""
S348 — جاروبِ هندسهٔ براکت با قیدِ `RR > 1` ، روی هر ۱۱ کارت
================================================================================
سندِ پشتیبان: `docs/FINDING_COST_BURDEN_GEOMETRY_LAW.md`
معیارِ داوری : `engine/rqs2.py` نسخهٔ ۲.۳ (پذیرش = هر ۱۱ دروازه)

--------------------------------------------------------------------------------
پرسشِ علمیِ این ماژول — تنها یک پرسش
--------------------------------------------------------------------------------
    «آیا شکستِ تایم‌فریم‌های پایین یک خاصیتِ بازار بود، یا مصنوعِ قیدِ
      منجمدِ `RR = 1` که پروژه در `s347_ensemble.py:54` گذاشته بود؟»

یافتهٔ بارِ هزینه نشان داد این قید روی `EURUSD-M1/M5` سربه‌سرِ مقاوم را به
**بالای ۱۰۰٪** می‌بَرد ⇒ آن دو کارت *حسابی* ناممکن بودند، نه بی‌الگو. این
ماژول همان یک متغیر را آزاد می‌کند و هیچ چیزِ دیگری را.

--------------------------------------------------------------------------------
⛔ سه محافظِ صحتِ آماری که **پیش از اجرا** ثبت شده‌اند
--------------------------------------------------------------------------------

**۱) تفکیکِ تابعِ هدفِ اکتشاف از تابعِ هدفِ داوری**
   درسِ گران‌بهای S347: اگر اکتشاف همان چیزی را بیشینه کند که داوری می‌سنجد،
   داوری بی‌معنا می‌شود. پس:
     • تابعِ هدفِ **اکتشاف** = امیدِ ریاضی (pip) روی *پنجرهٔ اکتشاف*. RQS2 نیست.
     • تابعِ هدفِ **داوری**  = RQS2 v2.3 روی *کلِ نمونه* با `split_bar`.
   RQS2 هرگز در حلقهٔ انتخاب دیده نمی‌شود.

**۲) هندسه فقط از ۶۰٪ نخستِ داده انتخاب می‌شود ⇒ `H7` واقعاً خارج از نمونه است**
   S347 مجبور بود بنویسد «H7 روی این کارت آلوده است» چون فیلترهای C1 از کلِ
   سری بیرون آمده بودند. برای *هندسه* آن آلودگی لازم نیست و ما آن را نمی‌پذیریم:
   انتخابِ `(RR, SL_K, K)` **تنها** به `bars[:split]` نگاه می‌کند.
   ⚠️ آلودگیِ ارثیِ فیلترهای C1 سرِ جایش باقی است و در گزارش **افشا** می‌شود؛
   پنهان‌کردنش بدترین کارِ ممکن بود.

**۳) بهای چندگانگیِ جاروب صریحاً به `H5` پرداخت می‌شود**
   شبکه = `|RR| × |SL_K| × |K|` = ۶×۵×۵ = **۱۵۰** آزمونِ نو. حکمِ رسمی با
   `n_trials = 150 × N_eff(بانک) = 150 × 301 = 45,150` صادر می‌شود، چون
   فیلترهای C1 خودشان از جست‌وجوی ۴۰۱ اندیکاتوری بیرون آمده‌اند و آن بها
   هم باید پرداخت شود. کرانِ لازم ⇒ `E[max z] ≈ 4.63σ`.
   سناریوی خوش‌بینانه (`n_trials = 150`) فقط به‌عنوانِ تحلیلِ حساسیت.

--------------------------------------------------------------------------------
چه چیزی **منجمد** می‌ماند (تا فقط یک متغیر حرکت کند)
--------------------------------------------------------------------------------
رویدادِ کانالِ تطبیقی (`P_LIST`, `MULT_LIST`, `ER_LIST`, `MODE`)، دروازهٔ
دو-فیلترهٔ C1 (گونهٔ B)، و افقِ نگهداری `ENS_HOLD = 8` — همه عیناً از لایهٔ
منتشرشدهٔ S347. **تنها هندسهٔ براکت حرکت می‌کند.** این «یک متغیر در یک زمان»
است، یعنی طراحیِ آزمایشیِ استاندارد.

--------------------------------------------------------------------------------
قاعدهٔ انتخاب — **پیش‌ثبت‌شده** (pre-registered)
--------------------------------------------------------------------------------
از میانِ ۱۵۰ ترکیب، تنها ترکیبی نامزدِ داوری می‌شود که:
   (الف) `n ≥ 30` در پنجرهٔ اکتشاف            [کفِ H0]
   (ب) `RR ≥ 1.0`                              [سپرِ اشتباهِ #۸]
   (ج) `TP > 2c` یعنی سربه‌سرِ مقاوم < ۱۰۰٪    [قانونِ بارِ هزینه]
   (د) **تکرارپذیریِ درونِ اکتشاف**: امیدِ ریاضی در *هر دو نیمهٔ*
       پنجرهٔ اکتشاف مثبت باشد — تا ترکیبی که فقط در یک رژیم کار می‌کند
       نامزد نشود. (holdout دست‌نخورده می‌ماند.)
سپس `argmax` امیدِ ریاضیِ پنجرهٔ اکتشاف. **این قاعده قبل از دیدنِ نتایج نوشته
شده و در همین فایل ثبت است**؛ تغییرش بعد از دیدنِ خروجی، تقلب است.

--------------------------------------------------------------------------------
قانونِ «اندک اندک» — چک‌پوینتِ هر کارت
--------------------------------------------------------------------------------
هر کارت که تمام شود، فوراً JSONِ خودش نوشته می‌شود
(`results/_scan_S348/<card>.json`) تا ریستِ سندباکس کلِ پروسه را نبرد.
"""
import sys
import os
import json
import argparse

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                              # noqa: E402
from engine import rqs2                                            # noqa: E402
from strategies.s346_geom import CARDS                              # noqa: E402
from strategies.s346_fast import barrier_outcomes, select_non_overlap  # noqa: E402
from strategies.s347_ensemble import (                              # noqa: E402
    SEED, P_LIST, ENS_HOLD, K_GRID, WARMUP_REF,
    build_votes, entries_for_K, _ind, _ref_quantiles, C1_FILTERS,
)
from strategies.s347_verdict import build_filter_gate, side_null, BANK_NEFF  # noqa: E402

OUT = 'results/_scan_S348'
SPLIT_FRAC = 0.60          # عیناً `s346_geom.split_idx` — دست نمی‌خورد

# ---------------- شبکهٔ جاروب: اعدادِ غیر-رند، طبقِ اشتباهِ رایجِ #۷ ----------------
# RR: از ۱.۰ (نقطهٔ منجمدِ قدیم، به‌عنوانِ شاهد) تا ۳.۲۳۶. نسبت‌های فیبوناچی.
RR_GRID = (1.0, 1.272, 1.618, 2.058, 2.618, 3.236)
# SL_K: ضریبِ ATR. عمداً شاملِ ۰.۶۱۸ و ۱.۲۷۲ و ۱.۶۱۸ و ۲.۰۵۸ — نه ۰.۵/۱/۲.
SL_K_GRID = (0.618, 1.0, 1.272, 1.618, 2.058)
# K: عیناً شبکهٔ فیبوناچیِ منتشرشدهٔ پروژه
K_SWEEP = K_GRID

N_GRID = len(RR_GRID) * len(SL_K_GRID) * len(K_SWEEP)      # = 150
N_TRIALS_CONS = N_GRID * BANK_NEFF                          # = 45,150
N_TRIALS_OPT = N_GRID                                       # تحلیلِ حساسیت

MIN_N_DISC = 30            # کفِ H0 — کمتر از این، ترکیب حتی نامزد نمی‌شود


def cost_pip(asset):
    cfg = se.ASSETS[asset]
    return float(cfg['spread_pip']) + 2.0 * float(cfg.get('slip_pip', 0.0))


def queue_rr(df, sig, is_long, sl_dist, asset, hold, rr):
    """
    عیناً `s347_ensemble._queue` ولی `rr` **پارامتر** است نه ثابتِ ماژول.

    ⛔ سپرِ اشتباهِ #۸ سرِ جایش: `tp = max(rr*sl, sl)` ⇒ TP هرگز < SL نمی‌شود.
    """
    cfg = se.ASSETS[asset]
    tp_dist = np.maximum(rr * sl_dist, sl_dist)
    fo = barrier_outcomes(df, sig, is_long, sl_dist, tp_dist, hold,
                          float(cfg['pip']), float(cfg['spread_pip']),
                          float(cfg.get('slip_pip', 0.0)))
    if len(fo['entry_bar']) == 0:
        return None
    keep = select_non_overlap(fo['entry_bar'], fo['exit_off'])
    pnl = fo['pnl_pip'][keep]
    if len(pnl) == 0:
        return None
    win = pnl > 0
    gw = float(pnl[win].sum())
    gl = float(-pnl[~win].sum())
    return dict(n=int(len(pnl)), wr=float(win.mean() * 100.0),
                exp=float(pnl.mean()),
                pf=float(gw / gl) if gl > 0 else 999.0,
                pnl=pnl, win=win,
                entry_bar=fo['entry_bar'][keep],
                exit_bar=fo['entry_bar'][keep] + fo['exit_off'][keep],
                is_long=fo['is_long'][keep],
                sl_pip=fo['sl_pip'][keep], tp_pip=fo['tp_pip'][keep])


def trades_df(st):
    return pd.DataFrame(dict(
        pnl_pip=st['pnl'],
        outcome=np.where(st['win'], 'win', 'loss'),
        sl_pip=st['sl_pip'], tp_pip=st['tp_pip'],
        entry_bar=st['entry_bar'].astype(int),
        exit_bar=st['exit_bar'].astype(int),
        direction=np.where(st['is_long'], 'long', 'short'),
    ))


# ==============================================================================
#  مرحلهٔ ۱ — اکتشاف: تنها روی ۶۰٪ نخست، تابعِ هدف = امیدِ ریاضی (نه RQS2)
# ==============================================================================
def discover(df, asset, split, warmup, gate, votes, verbose=True):
    """
    جاروبِ ۱۵۰ ترکیب روی پنجرهٔ اکتشاف. holdout **هرگز** دیده نمی‌شود.
    برمی‌گرداند: فهرستِ کاملِ شبکه + نامزدِ برنده طبقِ قاعدهٔ پیش‌ثبت‌شده.
    """
    vl, vs, wl, ws, atr = votes
    c = cost_pip(asset)
    half = warmup + (split - warmup) // 2          # مرزِ دو نیمهٔ پنجرهٔ اکتشاف
    rows = []

    for K in K_SWEEP:
        sig0, isl0, sl0 = entries_for_K(vl, vs, wl, ws, atr, K)
        if len(sig0) == 0:
            continue
        keep = gate[sig0]                          # گونهٔ B — دروازهٔ منجمدِ C1
        sig0, isl0, sl0 = sig0[keep], isl0[keep], sl0[keep]
        in_disc = sig0 < split
        sig_d, isl_d, sl_d = sig0[in_disc], isl0[in_disc], sl0[in_disc]
        if len(sig_d) < MIN_N_DISC:
            continue

        for sk in SL_K_GRID:
            sl_scaled = sl_d * sk                  # entries_for_K با SL_K=1.0
            for rr in RR_GRID:
                st = queue_rr(df.iloc[:split], sig_d, isl_d, sl_scaled,
                              asset, ENS_HOLD, rr)
                if st is None or st['n'] < MIN_N_DISC:
                    continue
                # ⚠️ رفعِ خطای بُعدیِ این نشست — **همان‌جنسِ خطایی که v2.1 در H1
                #   افشا کرد**، و این‌بار در خودِ همین ماژول تکرار شده بود.
                #   `entries_for_K` فاصلهٔ SL را بر حسبِ **واحدِ قیمت** برمی‌گرداند
                #   (چون از `atr_a`ِ خامِ کانال می‌آید)، اما `cost_pip` بر حسبِ
                #   **pip** است. نسخهٔ نخست این دو را بی‌تبدیل در یک نامعادله جمع
                #   می‌کرد ⇒ روی EURUSD (که pip=0.0001 است) سربه‌سرِ مقاوم عددِ
                #   بی‌معنای **۱۶۹٬۷۵۳٪** می‌داد و دروازهٔ امکان‌سنجی هر ۱۵۰ ترکیب
                #   را «ناممکن» علامت می‌زد؛ روی طلا هم انتخاب را مصنوعاً به سمتِ
                #   بزرگ‌ترین `slk×rr` می‌راند.
                #   ⛔ درسِ روش‌شناختی: هندسه را **بازمحاسبه نکن**. موتور خودش
                #   `sl_pip`/`tp_pip` را بر حسبِ pip بیرون می‌دهد؛ همان را بخوان.
                #   این‌طور امکانِ ناسازگاریِ واحد از بین می‌رود، نه آن‌که رفع شود.
                sl_med = float(np.median(st['sl_pip']))
                tp_med = float(np.median(st['tp_pip']))
                # (ج) قانونِ بارِ هزینه — سربه‌سرِ مقاوم باید < ۱۰۰٪ باشد
                feasible = tp_med > 2.0 * c
                # (د) تکرارپذیریِ درونِ اکتشاف — هر دو نیمه مثبت
                e1 = st['pnl'][st['entry_bar'] < half]
                e2 = st['pnl'][st['entry_bar'] >= half]
                repl = (len(e1) >= 5 and len(e2) >= 5
                        and float(e1.mean()) > 0 and float(e2.mean()) > 0)
                rbe = rqs2.breakeven_wr_cost(sl_med, tp_med, 2.0 * c)
                rows.append(dict(
                    K=int(K), sl_k=float(sk), rr=float(rr),
                    n=st['n'], wr=st['wr'], exp=st['exp'], pf=st['pf'],
                    sl_pip=sl_med, tp_pip=tp_med,
                    rr_eff=float(tp_med / sl_med) if sl_med > 0 else None,
                    robust_be=float(rbe), feasible=bool(feasible),
                    repl=bool(repl),
                    eligible=bool(feasible and repl and st['n'] >= MIN_N_DISC),
                ))
                if verbose:
                    flag = 'OK ' if rows[-1]['eligible'] else '   '
                    why = '' if rows[-1]['eligible'] else \
                          ('!infeasible' if not feasible else '!no-repl')
                    print(f"    {flag}K={K:<3}slk={sk:<6}rr={rr:<6} "
                          f"n={st['n']:<5}WR={st['wr']:6.2f}% "
                          f"exp={st['exp']:+7.3f}pip PF={st['pf']:5.2f} "
                          f"RBE={rbe:5.1f}% {why}", flush=True)

    elig = [r for r in rows if r['eligible']]
    best = max(elig, key=lambda r: r['exp']) if elig else None
    return rows, best


# ==============================================================================
#  مرحلهٔ ۲ — داوریِ رسمی: RQS2 v2.3 روی کلِ نمونه، با بهای چندگانگی
# ==============================================================================
def judge(df, asset, card, best, warmup, gate, votes, n_perm, close, bar_time):
    vl, vs, wl, ws, atr = votes
    K, sk, rr = best['K'], best['sl_k'], best['rr']
    split = int(len(df) * SPLIT_FRAC)

    sig, isl, sl = entries_for_K(vl, vs, wl, ws, atr, K)
    keep = gate[sig]
    sig, isl, sl = sig[keep], isl[keep], sl[keep] * sk

    st = queue_rr(df, sig, isl, sl, asset, ENS_HOLD, rr)
    if st is None or st['n'] < 5:
        return None, None
    tr = trades_df(st)
    n_long = int((tr['direction'] == 'long').sum())
    n_short = int(len(tr) - n_long)
    print(f"    FULL-SAMPLE trades n={st['n']} (L={n_long} S={n_short}) "
          f"WR={st['wr']:.2f}% exp={st['exp']:+.3f}pip PF={st['pf']:.3f}",
          flush=True)

    # ---- خطِ مبنای اندازه‌گیری‌شده، به‌تفکیکِ سمت، با **همان** هندسه ----
    atr_plain = np.nanmedian(atr, axis=0) * sk
    valid = np.where(np.isfinite(atr_plain) & (atr_plain > 0))[0]
    valid = valid[(valid >= warmup) & gate[valid]]
    print(f"    null pool = {len(valid):,} bars · {n_perm} perms/side "
          f"(same geometry rr={rr})", flush=True)

    # `side_null` از `_queue`ِ ماژولِ S347 استفاده می‌کند که RR=1 منجمد دارد؛
    # پس این‌جا نسخهٔ RR-آگاهِ خودمان را می‌سازیم تا خطِ مبنا **همان هندسه**
    # را داشته باشد. مقایسهٔ لبه با مبنایی که هندسهٔ دیگری دارد بی‌معناست.
    rng = np.random.default_rng(SEED)
    null = {}
    for side, is_long_flag, n_side in (('long', True, n_long),
                                       ('short', False, n_short)):
        d = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                 perm_max=None, perm_k=None)
        if n_side >= 1 and len(valid) >= 2:
            slv = atr_plain[valid]
            ok = np.isfinite(slv) & (slv > 0)
            vi, slv = valid[ok], slv[ok]
            s_all = queue_rr(df, vi, np.full(len(vi), is_long_flag), slv,
                             asset, ENS_HOLD, rr)
            if s_all:
                d['uncond_wr'] = s_all['wr']
            if len(vi) > n_side:
                wrs = []
                for _ in range(n_perm):
                    pick = np.sort(rng.choice(len(vi), size=n_side,
                                              replace=False))
                    s_p = queue_rr(df, vi[pick],
                                   np.full(n_side, is_long_flag), slv[pick],
                                   asset, ENS_HOLD, rr)
                    if s_p:
                        wrs.append(s_p['wr'])
                if wrs:
                    a = np.asarray(wrs, dtype='float64')
                    d.update(perm_mean=float(a.mean()),
                             perm_sd=float(a.std(ddof=1)),
                             perm_max=float(a.max()), perm_k=int(len(a)))
        null[side] = d
        print(f"      {side:<5} uncond={d['uncond_wr']} "
              f"perm_mean={d['perm_mean']} sd={d['perm_sd']}", flush=True)

    common = dict(sl_pip=float(np.median(st['sl_pip'])),
                  tp_pip=float(np.median(st['tp_pip'])),
                  bar_time=bar_time, null=null, split_bar=split, close=close)
    res_cons = rqs2.compute_rqs2(tr, asset, n_trials=N_TRIALS_CONS, **common)
    res_opt = rqs2.compute_rqs2(tr, asset, n_trials=N_TRIALS_OPT, **common)
    return res_cons, res_opt


def run_card(card, n_perm=200, verbose=True):
    asset, path = CARDS[card]
    df = se.load_data(path)
    close = df['close'].values.astype('float64')
    bar_time = df['dt'].values if 'dt' in df.columns else None
    warmup = max(5 * max(P_LIST), WARMUP_REF)
    split = int(len(df) * SPLIT_FRAC)
    c = cost_pip(asset)

    print(f"\n{'='*88}\n=== S348 RR-SWEEP :: {card} (bars={len(df):,}) ===",
          flush=True)
    print(f"    cost={c:.2f}pip · split@{split:,} ({SPLIT_FRAC:.0%}) · "
          f"grid={N_GRID} · n_trials_cons={N_TRIALS_CONS:,}", flush=True)

    votes = build_votes(df, warmup)
    gate, thr = build_filter_gate(df, warmup)
    print(f"    C1 gate keeps {gate.mean()*100:.2f}% of bars", flush=True)

    print("  -- PHASE 1 : DISCOVERY (first 60% only, objective = expectancy) --",
          flush=True)
    rows, best = discover(df, asset, split, warmup, gate, votes, verbose)

    out = dict(card=card, asset=asset, bars=len(df), cost_pip=c,
               split_bar=split, grid_size=N_GRID,
               n_trials_cons=N_TRIALS_CONS, n_trials_opt=N_TRIALS_OPT,
               n_evaluated=len(rows), n_eligible=sum(r['eligible'] for r in rows),
               grid=rows, best=best, verdict=None)

    if best is None:
        print("    !!! no eligible geometry in the discovery window", flush=True)
        out['verdict'] = 'NO_ELIGIBLE_GEOMETRY'
    else:
        print(f"    >>> WINNER (pre-registered rule): K={best['K']} "
              f"sl_k={best['sl_k']} rr={best['rr']} | disc n={best['n']} "
              f"WR={best['wr']:.2f}% exp={best['exp']:+.3f}pip "
              f"RBE={best['robust_be']:.1f}%", flush=True)
        print("  -- PHASE 2 : OFFICIAL RQS2 v2.3 VERDICT (full sample) --",
              flush=True)
        rc, ro = judge(df, asset, card, best, warmup, gate, votes,
                       n_perm, close, bar_time)
        if rc is None:
            out['verdict'] = 'NO_TRADES_FULL'
        else:
            print(rqs2.format_rqs2(f'{card} CONS', rc), flush=True)
            print(rqs2.format_rqs2(f'{card} OPT ', ro), flush=True)
            out['verdict'] = rc['verdict']
            out['rqs2_cons'] = {k: rc[k] for k in
                                ('verdict', 'rqs2_score', 'gates', 'metrics',
                                 'notes') if k in rc}
            out['rqs2_opt'] = {k: ro[k] for k in
                               ('verdict', 'rqs2_score', 'gates') if k in ro}

    os.makedirs(OUT, exist_ok=True)
    p = f'{OUT}/{card}.json'
    with open(p, 'w') as f:
        json.dump(out, f, indent=1, default=float)
    print(f"    [checkpoint] {p}", flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cards', nargs='*', default=None)
    ap.add_argument('--n-perm', type=int, default=200)
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()
    # ترتیبِ پیش‌فرض = قانونِ MTF: از ریزترین کارتِ طلا شروع کن
    order = a.cards if a.cards else list(CARDS.keys())
    for card in order:
        if card not in CARDS:
            print(f"!! unknown card {card}", flush=True)
            continue
        try:
            run_card(card, n_perm=a.n_perm, verbose=not a.quiet)
        except Exception as e:
            import traceback
            print(f"!!! {card} FAILED: {type(e).__name__}: {e}", flush=True)
            traceback.print_exc()


if __name__ == '__main__':
    main()
