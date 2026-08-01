# -*- coding: utf-8 -*-
"""
S358 — لایهٔ **رأیِ خانوادگیِ** S341 (vote ensemble) — گامِ ۳ پیش‌ثبت‌شده
==============================================================================

پیش‌ثبت: `results/S358_PREREGISTRATION_S341_VOTE_ENSEMBLE.md` (commitِ جداگانه،
**پیش از** اجرای این اسکریپت؛ هیچ عددِ ensemble در آن لحظه محاسبه نشده بود).

زنجیرهٔ استدلالی که به اینجا رسید
---------------------------------
* `S357` (پیکربندیِ منجمد): لیفتِ **+۱۵…+۲۱pp** واقعی، اما `z = ۱.۸۹…۲.۹۳` در
  برابرِ کرانِ `E[max_z(10368)] = ۳.۸۵۵` ⇒ رد. یعنی لبه **هست**، **توان** نیست
  (۴۸ معامله در ۲۰۰٬۰۰۰ کندلِ M5 = ۳ ورود در هر ۱۰٬۰۰۰ کندل).
* `S357B` (سطحِ خانواده، مسیرِ `B`): زیرِ مدلِ صفرِ حاکمِ `SHIFT`، خانوادهٔ ۷۲ عضوی
  روی `M5` لیفتِ **+۲.۹۸pp** روی ۲۶٬۶۵۶ ورود دارد (z=۱.۹۱، هر سه بذر) ⇒ سازه
  زنده است؛ روی `H1` لیفتِ **−۳.۵۹pp** ⇒ سازه مرده است.

مسئلهٔ باقی‌مانده: **یک خانواده روی سایت قابلِ نمایش نیست.** کاربر یک تصمیم
می‌خواهد، و بازگشت به «بهترین عضو» بدهیِ `N=10368` را زنده می‌کند.

راهِ حلِ این فایل: از خودِ خانواده **یک** تصمیم بساز، بدونِ انتخابِ هیچ عضوی.

    v_long(i)  = تعدادِ ۳۶ عضوِ long  که در کندلِ i شلیک می‌کنند
    v_short(i) = تعدادِ ۳۶ عضوِ short که در کندلِ i شلیک می‌کنند

    LONG   اگر  v_long  ≥ θ  و  v_long  > v_short
    SHORT  اگر  v_short ≥ θ  و  v_short > v_long

چهار نکتهٔ مهندسیِ این اسکریپت (و دلیلِ هرکدام)
-----------------------------------------------
**۱) قاعده ذاتاً بی‌تساوی است.** نامساویِ **اکید** یعنی هیچ کندلی نمی‌تواند هر دو
   سمت را شلیک کند، پس تقدمِ دلبخواهیِ `long` در `se.simulate_trades`
   (خطِ «اگر هر دو، long مقدم») **هرگز فعال نمی‌شود**. لایه از یک قراردادِ
   پیاده‌سازیِ موتور سود نمی‌برد. این با `assert` تحقیق‌پذیر است، نه ادعا.

**۲) قدم‌زنِ ناهم‌پوشانیِ پرشی.** مدلِ صفر به ۲۰۰۰ قرعه × ۴ آستانه × ۳ بذر × ۱۶
   کارت نیاز دارد. قدم‌زنِ سادهٔ `O(k)` روی هر قرعه غیرعملی است. `walk_fast` با
   `searchsorted` روی ورودهای رد‌شده **می‌پرد**، پس هزینهٔ هر قرعه
   `O(n_trades · log k)` می‌شود نه `O(k)`. معناشناسی **بیت‌به‌بیت** همان
   `busy_until` موتور است و `parity` آن روی هر کارت اثبات می‌شود.

**۳) مدلِ صفرِ حاکم = شیفتِ دوّارِ مشترک.** همان مدلی که در `S357B` حاکم اعلام شد.
   یک شیفتِ **مشترک** به `long_sig` و `short_sig` **هم‌زمان** اعمال می‌شود، پس هم
   خوشه‌بندیِ درون‌سمتی و هم کلِ ساختارِ هم‌پوشانیِ بین دو سمت دست‌نخورده می‌ماند و
   تنها هم‌ترازیِ «زمانِ سیگنال ↔ قیمت» از بین می‌رود. مدلِ خوش‌بینانهٔ `INDEP`
   (قرعهٔ زمانیِ مستقل، کنوانسیونِ `s346/s354_family.py`) هم گزارش می‌شود، اما
   **مبنای هیچ حکمی نیست** — روی M5 آن مدل `sd` را ۲.۴۴ برابر کم‌برآورد می‌کرد.

**۴) دو خط‌کش، و پاس نیازِ *هر دو*.** `blend_null` کلیدِ `p_perm` را حمل نمی‌کند،
   پس موتور به `p`ِ پارامتریک می‌افتد. اینجا `p`ِ **تجربی** از شمارشِ واقعیِ
   قرعه‌ها هم سنجیده می‌شود و سدِ `≤ 0.001` پیش‌ثبتِ `S357` **بی‌هیچ شلی** بر آن
   اعمال می‌شود.

اجرا:
    python3 strategies/s358_s341_vote_ensemble.py --cards site
    python3 strategies/s358_s341_vote_ensemble.py --cards all
    python3 strategies/s358_s341_vote_ensemble.py --cards XAUUSD-M5 --k 300
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                                    # noqa: E402
from engine import rqs2 as R2                                            # noqa: E402
from strategies.s341_brooks_swing_levels import _fractal_levels          # noqa: E402
from strategies import s357_s341_v24_rejudge as S357                     # noqa: E402

OUT = "results/_scan_S358"

# ───────── پارامترهای آماری: عیناً از پیش‌ثبتِ S357/S358، بی‌هیچ تغییر ─────────
SEEDS = S357.SEEDS                  # (23, 101, 777)
PERM_K = S357.PERM_K                # 2000
P_BAR = S357.P_BAR                  # 0.001  ← هیچ شلی داده نمی‌شود
SPLIT_FRAC = S357.SPLIT_FRAC        # 0.60

# آستانه‌های **قفل‌شده** در بندِ «درجهٔ آزادیِ جدید» پیش‌ثبتِ S358.
# فاصله‌گذاری نامنظم و غیررند (پادزهرِ اشتباهِ رایجِ #۷). افزودنِ θِ پنجم
# بعد از دیدنِ نتایج ممنوع است.
THETA_GRID = (4, 7, 11, 16)         # ≈ ۱۱٪ · ۱۹٪ · ۳۱٪ · ۴۴٪ از ۳۶ عضوِ هر سمت

# بدهیِ چندگانگی — صریح، از بندِ «بدهیِ چندگانگی» پیش‌ثبت:
#   هیچ عضوی انتخاب نمی‌شود ⇒ بدهیِ ۱۰۳۶۸ **دیگر بدهکار نیست** (RQS2_SPEC §۲.۵)
N_TRIALS_HONEST = 12 * len(THETA_GRID)      # 48   = براکتِ آرشیو × θ
N_TRIALS_STRESS = 864 * len(THETA_GRID)     # 3456 = کلِ گریدِ ساختار×براکت × θ

MEMBERS_PER_SIDE = (len(S357.W_GRID) * len(S357.BUF_GRID)
                    * len(S357.REGIME_GRID) * len(S357.SECOND_GRID))    # 36


# ═══════════════════ ۱. شمارشِ رأی‌ها (۳۶ عضو در هر سمت) ═══════════════════
def vote_counts(F, fracs):
    """`v_long` و `v_short`: تعدادِ اعضای شلیک‌کننده در هر کندل.

    اعضا = `w × buf × regime × second` با `stretch = exh = None`. دو فیلترِ
    `stretch/exh` **عمداً** حذف شده‌اند: آن‌ها درجاتِ آزادیِ *گزینشیِ* مرحلهٔ احیا
    بودند و عضوِ خانوادهٔ ساختاریِ فصلِ ۱۷ نیستند (همان تفکیکی که در `S357B`
    نشان داد لبهٔ کارتِ H1 از آن دو فیلتر می‌آید نه از الگوی Brooks).
    """
    n = len(F['h'])
    v = {'long': np.zeros(n, dtype=np.int16), 'short': np.zeros(n, dtype=np.int16)}
    members = {'long': [], 'short': []}
    for side in ('long', 'short'):
        for w, buf, reg, sec in itertools.product(
                S357.W_GRID, S357.BUF_GRID, S357.REGIME_GRID, S357.SECOND_GRID):
            s = S357.signals_vec(F, fracs[w], side, w, buf, reg, sec, None, None)
            v[side] += s.astype(np.int16)
            members[side].append(dict(w=w, buf=buf, chop_min=reg['chop_min'],
                                      second=sec, n_sig=int(s.sum())))
            del s
    return v, members


def rule_signals(v_long, v_short, theta):
    """قاعدهٔ ورودِ متقارن. نامساویِ **اکید** ⇒ دو سمت هرگز هم‌زمان شلیک نمی‌کنند."""
    long_sig = (v_long >= theta) & (v_long > v_short)
    short_sig = (v_short >= theta) & (v_short > v_long)
    # این `assert` ادعای «بی‌تساوی بودن» را به یک واقعیتِ تحقیق‌شده تبدیل می‌کند.
    assert not np.any(long_sig & short_sig), \
        'rule is not tie-free — the simulator long-precedence would leak in'
    return long_sig, short_sig


# ═════════════ ۲. قدم‌زنِ ناهم‌پوشانیِ پرشی (معناشناسیِ `busy_until`) ═════════════
def walk_fast(sb, is_long, res_l, xb_l, res_s, xb_s):
    """گزینشِ حریصانهٔ ناهم‌پوشان، **بیت‌به‌بیت** مطابقِ `se.simulate_trades`.

    قاعدهٔ موتور: `entry_bar = si + 1`؛ اگر `entry_bar <= busy_until` رد شود.
    پس شرطِ پذیرش `si >= last_exit` است و می‌توان با `searchsorted` روی همهٔ
    ورودهای رد‌شده **پرید** — هزینه `O(n_trades · log k)` به‌جای `O(k)`.

    خروجی: `(n_long, wins_long, n_short, wins_short)`.
    """
    nl = wl = ns = ws = 0
    last_exit = -1
    i, m = 0, sb.size
    while i < m:
        si = int(sb[i])
        if si + 1 <= last_exit:
            # `sb[i] < last_exit` ⇒ اندیسِ بازگشتی اکیداً بزرگ‌تر است ⇒ بی‌حلقهٔ بی‌پایان
            i = int(np.searchsorted(sb, last_exit, side='left'))
            continue
        if is_long[i]:
            r, x = int(res_l[si]), int(xb_l[si])
        else:
            r, x = int(res_s[si]), int(xb_s[si])
        if r == 0:                      # ورودِ ناممکن (لبهٔ داده) — موتور هم رد می‌کند
            i += 1
            continue
        last_exit = x
        if is_long[i]:
            nl += 1
            wl += (r == 1)
        else:
            ns += 1
            ws += (r == 1)
        i += 1
    return nl, wl, ns, ws


def merged(long_sig, short_sig):
    """ورودهای مرتب‌شده + برچسبِ سمت (ورودی `walk_fast`)."""
    sb = np.flatnonzero(long_sig | short_sig)
    return sb, long_sig[sb]


# ═══════════════════ ۳. مدل‌های صفر (SHIFT حاکم، INDEP فقط گزارشی) ═══════════════════
def null_shift(long_sig, short_sig, tables, k_perm, seed, lo, hi):
    """مدلِ صفرِ **حاکم**: یک شیفتِ دوّارِ *مشترک* روی هر دو سمت هم‌زمان.

    ساختارِ هم‌پوشانیِ بین دو سمت و خوشه‌بندیِ درون‌سمتی کاملاً حفظ می‌شود؛ تنها
    هم‌ترازیِ «زمانِ سیگنال ↔ قیمت» شکسته می‌شود.
    """
    res_l, xb_l, res_s, xb_s = tables
    rng = np.random.default_rng(seed)
    n = long_sig.size
    d_l, d_s, d_all = [], [], []
    for _ in range(k_perm):
        sh = int(rng.integers(lo, hi))
        sb, isl = merged(np.roll(long_sig, sh), np.roll(short_sig, sh))
        if sb.size == 0:
            continue
        nl, wl, ns, wsn = walk_fast(sb, isl, res_l, xb_l, res_s, xb_s)
        tot = nl + ns
        if tot == 0:
            continue
        d_all.append(100.0 * (wl + wsn) / tot)
        if nl:
            d_l.append(100.0 * wl / nl)
        if ns:
            d_s.append(100.0 * wsn / ns)
    return (np.asarray(d_all, float), np.asarray(d_l, float), np.asarray(d_s, float))


def null_indep(long_sig, short_sig, tables, k_perm, seed):
    """مدلِ خوش‌بینانه (کنوانسیونِ `s346/s354_family.py`) — **فقط گزارشی**.

    زمان‌های ورود مستقلاً و تصادفی قرعه‌کشی می‌شوند؛ خوشه‌بندی و هم‌پوشانیِ واقعیِ
    دو سمت از بین می‌رود و `sd`ِ صفر کم‌برآورد می‌شود. هیچ حکمی بر آن بنا نیست.
    """
    res_l, xb_l, res_s, xb_s = tables
    n = long_sig.size
    k_l, k_s = int(long_sig.sum()), int(short_sig.sum())
    lo = min(300, max(0, n // 10))
    pool = np.arange(lo, max(lo + 1, n - 2))
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(k_perm):
        pl = rng.choice(pool, size=min(k_l, pool.size), replace=False) if k_l else np.array([], int)
        ps = rng.choice(pool, size=min(k_s, pool.size), replace=False) if k_s else np.array([], int)
        ls = np.zeros(n, bool); ls[pl] = True
        ss = np.zeros(n, bool); ss[ps] = True
        ss &= ~ls                                   # بی‌تساوی نگه داشته می‌شود
        sb, isl = merged(ls, ss)
        if sb.size == 0:
            continue
        nl, wl, ns, wsn = walk_fast(sb, isl, res_l, xb_l, res_s, xb_s)
        tot = nl + ns
        if tot:
            out.append(100.0 * (wl + wsn) / tot)
    return np.asarray(out, float)


def uncond_side(res, xb, n, lo):
    """WRِ «ورود در هر کندلِ ممکن» برای یک سمت — خطِ مبنایِ بی‌شرط."""
    valid = np.arange(lo, max(lo + 1, n - 2))
    valid = valid[res[valid] != 0]
    if valid.size == 0:
        return None
    isl = np.ones(valid.size, bool)
    nl, wl, _, _ = walk_fast(valid, isl, res, xb, res, xb)
    return (100.0 * wl / nl) if nl else None


# ═══════════════════════════ ۴. اجرا برای یک کارت ═══════════════════════════
def run_card(card, k_perm=PERM_K, verbose=True):
    asset, tf = card.split('-')
    path = os.path.join('data', f'{asset}_{tf}.csv')
    if not os.path.exists(path):
        return dict(card=card, status='NO_DATA',
                    note=f'{path} does not exist in the repository')

    df = se.load_data(path)
    cfg, source, _, _ = S357.resolve_cfg(card, df, asset)
    sl, tp, mh = cfg['sl'], cfg['tp'], cfg['mh']
    F = S357.base_features(df, cfg)
    fracs = {w: _fractal_levels(F['h'], F['l'], w) for w in S357.W_GRID}

    v, members = vote_counts(F, fracs)
    n = len(df)
    rec = dict(card=card, asset=asset, tf=tf, bars=n, bracket_source=source,
               bracket=dict(sl=sl, tp=tp, mh=mh, rr=round(tp / sl, 3)),
               members_per_side=MEMBERS_PER_SIDE,
               vote_hist={str(t): dict(long=int((v['long'] >= t).sum()),
                                       short=int((v['short'] >= t).sum()))
                          for t in THETA_GRID},
               n_trials=dict(honest=N_TRIALS_HONEST, stress=N_TRIALS_STRESS),
               thetas={})
    if verbose:
        print(f"\n=== {card} :: bars={n} bracket={source} SL={sl} TP={tp} "
              f"mh={mh} RR={tp/sl:.2f} | max votes L/S = "
              f"{int(v['long'].max())}/{int(v['short'].max())}", flush=True)

    tables = (*S357.outcome_table(df, asset, sl, tp, mh, side='long'),
              *S357.outcome_table(df, asset, sl, tp, mh, side='short'))
    res_l, xb_l, res_s, xb_s = tables
    lo = min(300, max(0, n // 10))
    unc = {'long': uncond_side(res_l, xb_l, n, lo),
           'short': uncond_side(res_s, xb_s, n, lo)}
    rec['uncond_wr'] = {k: (None if x is None else round(x, 3)) for k, x in unc.items()}

    close = df['close'].to_numpy(float)
    bar_time = df['time'].to_numpy()
    split_bar = int(n * SPLIT_FRAC)

    for theta in THETA_GRID:
        long_sig, short_sig = rule_signals(v['long'], v['short'], theta)
        nsig = int(long_sig.sum() + short_sig.sum())
        th = dict(theta=theta, n_signals=nsig,
                  n_sig_long=int(long_sig.sum()), n_sig_short=int(short_sig.sum()),
                  seeds={})
        if nsig < 5:
            th['status'] = 'NO_SIGNAL'
            rec['thetas'][str(theta)] = th
            if verbose:
                print(f"  θ={theta:2d} : NO_SIGNAL ({nsig} signals)", flush=True)
            continue

        tr = se.simulate_trades(df, long_sig, short_sig, sl_pip=sl, tp_pip=tp,
                                asset=asset, max_hold=mh, allow_overlap=False)
        if tr is None or len(tr) < 5:
            th['status'] = 'NO_TRADES'
            rec['thetas'][str(theta)] = th
            if verbose:
                print(f"  θ={theta:2d} : NO_TRADES", flush=True)
            continue

        nt = len(tr)
        wr_obs = 100.0 * float((tr['pnl_pip'] > 0).sum()) / nt

        # parityِ قدم‌زنِ پرشی با موتور — پیش از هر استفاده در مدلِ صفر
        sb, isl = merged(long_sig, short_sig)
        nl, wl, ns_, ws_ = walk_fast(sb, isl, res_l, xb_l, res_s, xb_s)
        wr_walk = 100.0 * (wl + ws_) / (nl + ns_) if (nl + ns_) else None
        th.update(status='JUDGED', n_trades=nt, wr_obs=round(wr_obs, 3),
                  parity_walk_vs_engine=dict(
                      n_engine=nt, n_walk=nl + ns_,
                      wr_engine=round(wr_obs, 3),
                      wr_walk=None if wr_walk is None else round(wr_walk, 3)),
                  n_long_used=nl, n_short_used=ns_)
        if verbose:
            print(f"  θ={theta:2d} : sig={nsig} (L{int(long_sig.sum())}/"
                  f"S{int(short_sig.sum())}) n_trades={nt} WR={wr_obs:.2f}% "
                  f"| walk n={nl+ns_} WR={wr_walk:.2f}% (L{nl}/S{ns_})", flush=True)

        for seed in SEEDS:
            d_all, d_l, d_s = null_shift(long_sig, short_sig, tables, k_perm,
                                         seed, lo, max(lo + 1, n - 2))
            d_ind = null_indep(long_sig, short_sig, tables, max(200, k_perm // 4), seed)

            def side_block(draws, unc_side):
                if draws.size == 0:
                    return dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                                perm_max=None, perm_k=0)
                return dict(uncond_wr=unc_side, perm_mean=float(draws.mean()),
                            perm_sd=float(draws.std(ddof=1)),
                            perm_max=float(draws.max()), perm_k=int(draws.size))

            null = {'long': side_block(d_l, unc['long']),
                    'short': side_block(d_s, unc['short'])}
            p_emp, n_ge = S357.empirical_p(d_all, wr_obs)

            out = {}
            for label, ntr in (('honest', N_TRIALS_HONEST), ('stress', N_TRIALS_STRESS)):
                r = R2.compute_rqs2(tr, asset, sl_pip=sl, tp_pip=tp,
                                    bar_time=bar_time, close=close, null=null,
                                    n_trials=ntr, split_bar=split_bar)
                out[label] = dict(verdict=r.get('verdict'), score=r.get('rqs2_score'),
                                  rank=r.get('rank'), gates=r.get('gates'),
                                  metrics=r.get('metrics'), notes=r.get('notes'))
            m0 = out['honest']['metrics']
            sd_sh = float(d_all.std(ddof=1)) if d_all.size > 1 else None
            sd_in = float(d_ind.std(ddof=1)) if d_ind.size > 1 else None
            out['null_shift_combined'] = dict(
                mean=round(float(d_all.mean()), 3) if d_all.size else None,
                sd=None if sd_sh is None else round(sd_sh, 3),
                k=int(d_all.size),
                lift_pp=round(wr_obs - float(d_all.mean()), 3) if d_all.size else None,
                z=(round((wr_obs - float(d_all.mean())) / sd_sh, 3)
                   if sd_sh and sd_sh > 0 else None))
            out['null_indep_combined'] = dict(
                mean=round(float(d_ind.mean()), 3) if d_ind.size else None,
                sd=None if sd_in is None else round(sd_in, 3), k=int(d_ind.size),
                z=(round((wr_obs - float(d_ind.mean())) / sd_in, 3)
                   if sd_in and sd_in > 0 else None),
                note='OPTIMISTIC — reported only, governs nothing')
            out['sd_understatement_factor'] = (round(sd_sh / sd_in, 3)
                                               if (sd_sh and sd_in) else None)
            out['p_empirical'] = round(p_emp, 6)
            out['n_draws_ge_obs'] = n_ge
            out['p_parametric_engine'] = m0.get('skill_p_perm')
            out['honest_accept'] = bool(out['honest']['verdict'] == 'ACCEPT'
                                        and p_emp <= P_BAR)
            th['seeds'][str(seed)] = out
            if verbose:
                ns_b = out['null_shift_combined']
                bad_h = [g for g, x in (out['honest']['gates'] or {}).items() if x is not True]
                bad_s = [g for g, x in (out['stress']['gates'] or {}).items() if x is not True]
                print(f"     seed={seed} SHIFT null={ns_b['mean']}% sd={ns_b['sd']} "
                      f"lift={ns_b['lift_pp']}pp z={ns_b['z']} | INDEP z="
                      f"{out['null_indep_combined']['z']} (sd×"
                      f"{out['sd_understatement_factor']}) | p_emp={p_emp:.5f}",
                      flush=True)
                print(f"        honest: {out['honest']['verdict']:11s} "
                      f"score={out['honest']['score']} fail={bad_h or 'NONE'} || "
                      f"stress: {out['stress']['verdict']:11s} fail={bad_s or 'NONE'}",
                      flush=True)

        th['all_seeds_honest_accept'] = bool(
            th['seeds'] and all(s['honest_accept'] for s in th['seeds'].values()))
        rec['thetas'][str(theta)] = th

    # ── انتخابِ θِ گزارشی: بدهیِ ۴ از قبل در N_honest=48 پرداخت شده است ──
    judged = [t for t in rec['thetas'].values() if t.get('status') == 'JUDGED']
    if judged:
        def zkey(t):
            zs = [s['null_shift_combined']['z'] for s in t['seeds'].values()
                  if s['null_shift_combined']['z'] is not None]
            return min(zs) if zs else -99.0
        best = max(judged, key=zkey)
        rec['reported_theta'] = best['theta']
        rec['decision'] = ('ALIVE' if best.get('all_seeds_honest_accept')
                           else 'NOT_ALIVE_UNDER_ENSEMBLE')
        rec['status'] = 'JUDGED'
        rec['min_z_shift_at_reported_theta'] = zkey(best)
    else:
        rec['status'] = 'NO_SIGNAL'
        rec['decision'] = None
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cards', default='site')
    ap.add_argument('--k', type=int, default=PERM_K)
    a = ap.parse_args()
    if a.cards == 'site':
        cards = S357.SITE_CARDS
    elif a.cards == 'all':
        cards = S357.CARDS_ALL
    else:
        cards = [c.strip() for c in a.cards.split(',') if c.strip()]

    os.makedirs(OUT, exist_ok=True)
    for card in cards:
        rec = run_card(card, k_perm=a.k)
        with open(os.path.join(OUT, f'{card}.json'), 'w', encoding='utf-8') as f:
            json.dump(rec, f, ensure_ascii=False, indent=1, default=str)
        print(f"  [saved] {OUT}/{card}.json status={rec.get('status')} "
              f"decision={rec.get('decision')} θ={rec.get('reported_theta')}",
              flush=True)


if __name__ == '__main__':
    main()
