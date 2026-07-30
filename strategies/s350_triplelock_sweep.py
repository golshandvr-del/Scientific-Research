# -*- coding: utf-8 -*-
"""
S350 — جاروبِ هندسه با **قانونِ قفلِ سه‌گانه**: `hold` مشتق می‌شود، نه منجمد

================================================================================
این ماژول یک **آزمایشِ کنترل‌شده** در برابرِ S348 است، نه یک جست‌وجوی بزرگ‌تر.
هرچیزی عیناً از S348 وارد (import) می‌شود — رویداد، دروازهٔ منجمدِ C1، پنجرهٔ
اکتشافِ ۶۰٪، قاعدهٔ انتخابِ پیش‌ثبت‌شده، شبکهٔ ۱۵۰ سلولی و بهایِ چندگانگیِ
۴۵٬۱۵۰. **تنها یک قاعده** عوض می‌شود:

    S348:  hold = ENS_HOLD = 8      (برای هر ۱۵۰ سلول، یکسان و منجمد)
    S350:  hold = ceil((sl_k · rr)²)  (برای هر سلول، مشتق‌شده)

چرا این کار مجاز است و درجهٔ آزادیِ نو اضافه نمی‌کند
--------------------------------------------------------------------------------
`hold` **جست‌وجو نمی‌شود**؛ از دو پارامترِ موجود با یک فرمولِ بسته و *قبل از
دیدنِ هر سیگنالی* محاسبه می‌شود. پس شبکه همان ۱۵۰ سلول می‌ماند (نه ۱۵۰×تعدادِ
افق‌های کاندیدا) و `n_trials` تغییر نمی‌کند. همین ثابت‌ماندنِ `n_trials` است که
مقایسه با S348 را از یک «تلاشِ دیگر» به یک **آزمایشِ کنترل‌شده** تبدیل می‌کند.
همین استدلال قبلاً برای `RR`ِ حداقلیِ هر کارت در `tools/rr_feasibility.py`
پذیرفته شد: کمیتی که با فرمولِ بسته از پارامترهای دیگر می‌آید، بهای آزمونِ
چندگانه ندارد.

مبنای علمی — قانونِ قفلِ سه‌گانه
--------------------------------------------------------------------------------
زمانِ نخستین-گذر تا سدی در فاصلهٔ d با پراکندگیِ σ در هر کندل، متناسبِ (d/σ)²
است. با سدهای مقیاس‌شده به ATR:

    زمانِ لازم برای لمسِ SL ≈ k_sl²          کندل
    زمانِ لازم برای لمسِ TP ≈ (k_sl · rr)²   کندل
    ⇒ شرطِ دست‌یافتنی‌بودنِ TP:  hold ≥ (k_sl · rr)²

اندازه‌گیریِ مستقل‌از-استراتژی روی هر ۱۵ کارت
(`tools/reachability_map.py`، ورودی‌های تصادفیِ بذردار) نشان داد زیرِ هندسهٔ
S348 احتمالِ لمس در ۸ کندل:

    SL:  ۶۱.۶٪ – ۷۴.۱٪        TP:  ۲.۱٪ – ۹.۴٪      (روی هر ۱۵ کارت)

یعنی TP **تزئینی** بود و `rr` عملاً یک no-op؛ معامله در لباسِ براکت، در واقع
یک «نگه‌داری تا انقضا» بود. تأییدِ متقاطع: XAUUSD-W1 تنها کارتی است که هندسهٔ
S348ش قانون را **رعایت** می‌کرد (۴.۲ ≤ ۸) و تنها کارتی است که بهینه‌اش روی
لبهٔ شبکه نیفتاد (rr=1.618 درونی). سه کارتِ دیگر قانون را ۱.۳۱× تا ۵.۵۴× نقض
می‌کردند و همه به لبه (rr=3.236) چسبیدند — دقیقاً آن‌چه قانون پیش‌بینی می‌کند:
وقتی TP دست‌نیافتنی است، هیچ‌چیز جلوی افزایشِ `rr` را نمی‌گیرد.

فرضیهٔ اصلی — و فرضیهٔ رقیب، با وزنِ برابر
--------------------------------------------------------------------------------
تحلیلِ توان نشان می‌دهد H5 در این سطحِ چندگانگی چه لیفتی از نرخِ برد می‌خواهد:

    n = 121  ⇒  لازم ≈ ۱۹.۲ pp     (طلا-D1 داد ۱۱.۰۹ ⇒ رد)
    n = 4413 ⇒  لازم ≈  ۳.۲ pp     (طلا-H1  داد  ۰.۵۰ ⇒ رد)

پس نقطهٔ اهرم XAUUSD-H1 است: هم بزرگ‌ترین نمونه را دارد، هم بدترین نقضِ
دست‌یافتنی‌بودن (۵.۵۴× — افقِ ۴۴.۴ لازم داشت، ۸ داشت).

⚖️ **فرضیهٔ رقیب، که با همان وزن ثبت می‌شود**: لیفتِ ۱۱.۰۹ppِ طلا-D1
بیشینهٔ *انتخاب‌شده* از ۱۵۰ سلول روی ۱۲۱ معامله است، پس رو به بالا اریب است.
اگر لبهٔ حقیقی کوچک باشد، اصلاحِ افق H1 را هم نجات نمی‌دهد. آن نتیجه هم
**به همان اندازه ارزشمند** است، چون باورِ فعلیِ پروژه («لبه روی TF بالا هست و
فقط نمونه کم است») را ابطال می‌کند.

قیدِ نویی که این کار می‌سازد و صریح اعلام می‌شود
--------------------------------------------------------------------------------
`select_non_overlap` فعال است ⇒ افقِ بلندتر = معاملاتِ کمتر. اندازه‌گیریِ
پیش‌آزمون روی طلا-D1: با hold=28 امیدِ ریاضی از +۷۲.۱۷ به +۱۲۸.۰ رفت (۷۷٪+)
ولی n از ۷۳ به ۴۴ افتاد. پس این یک **بده‌بستان** است، نه بردِ رایگان: چیزی که
به H1/H2 داده می‌شود، از H3/H5 گرفته می‌شود.

سپرهایی که دست‌نخورده می‌مانند
--------------------------------------------------------------------------------
۱. سپرِ اشتباهِ #۸: `tp = max(rr·sl, sl)` و کفِ شبکه `rr = 1.0` ⇒ TP < SL محال.
   و افزایشِ افق نرخِ برد را **پایین** می‌آورد (۵۶.۱۶٪ → ۴۷.۷۳٪) در حالی که
   امید بالا می‌رود ⇒ عکسِ آن‌چه تقلبِ #۸ تولید می‌کند.
۲. جدا بودنِ تابعِ هدفِ اکتشاف (امیدِ ریاضی) از خط‌کشِ داوری (RQS2).
۳. holdout (۴۰٪ آخر) هرگز در انتخابِ هندسه دیده نمی‌شود ⇒ H7 صادقانه.
۴. هندسه از خروجیِ pipِ خودِ موتور خوانده می‌شود، بازمحاسبه نمی‌شود.
۵. چک‌پوینتِ هر کارت به‌صورت جدا ⇒ ریستِ سندباکس یک کارت هزینه دارد.

پوشش: ۱۵ کارت — شاملِ چهار کارتِ EURUSD (D1/H4/H1/W1) که S349 کشف کرد در هیچ
فهرستِ کارتی نبودند (نقضِ قانونِ MTF).
"""

import os
import sys
import json
import math
import argparse

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                              # noqa: E402
from engine import rqs2                                            # noqa: E402
from strategies.s346_geom import CARDS as BASE_CARDS               # noqa: E402
from strategies.s347_ensemble import (                             # noqa: E402
    SEED, P_LIST, WARMUP_REF, build_votes, entries_for_K,
)
from strategies.s347_verdict import build_filter_gate              # noqa: E402
from strategies.s348_rr_sweep import (                             # noqa: E402
    SPLIT_FRAC, RR_GRID, SL_K_GRID, K_SWEEP, N_GRID,
    N_TRIALS_CONS, N_TRIALS_OPT, MIN_N_DISC,
    cost_pip, queue_rr, trades_df,
)

OUT = 'results/_scan_S350'

# --- کارت‌های EURUSD که S349 کشف کرد هرگز در فهرست نبودند (نقضِ قانونِ MTF) ---
CARDS = dict(BASE_CARDS)
for _c, _p in (('EURUSD-H1', 'data/EURUSD_H1.csv'),
               ('EURUSD-H4', 'data/EURUSD_H4.csv'),
               ('EURUSD-D1', 'data/EURUSD_D1.csv'),
               ('EURUSD-W1', 'data/EURUSD_W1.csv')):
    if _c not in CARDS and os.path.exists(_p):
        CARDS[_c] = ('EURUSD', _p)

HOLD_FLOOR = 3      # سلولِ (0.618, 1.0) افقِ ۱ کندل می‌دهد که بی‌معناست.
HOLD_CAP = 400      # سقفِ ایمنی — جلوگیری از افقِ نجومی در سلول‌های حاشیه‌ای


def derived_hold(sl_k, rr):
    """افقِ **مشتق‌شده** = کوچک‌ترین افقی که TP در آن دست‌یافتنی است.

    فرمولِ بسته، بدونِ جست‌وجو ⇒ بهای چندگانگی ندارد. کفِ ۳ کندل گذاشته شده
    چون بالا بردنِ یک کرانِ پایین، نقضِ قانونی که خودش کرانِ پایین است نیست.
    """
    return int(min(HOLD_CAP, max(HOLD_FLOOR, math.ceil((sl_k * rr) ** 2))))


# ==============================================================================
#  مرحلهٔ ۱ — اکتشاف: عیناً S348، تنها `hold` مشتق می‌شود
# ==============================================================================
def discover(df, asset, split, warmup, gate, votes, verbose=True):
    vl, vs, wl, ws, atr = votes
    c = cost_pip(asset)
    half = warmup + (split - warmup) // 2
    rows = []

    for K in K_SWEEP:
        sig0, isl0, sl0 = entries_for_K(vl, vs, wl, ws, atr, K)
        if len(sig0) == 0:
            continue
        keep = gate[sig0]
        sig0, isl0, sl0 = sig0[keep], isl0[keep], sl0[keep]
        in_disc = sig0 < split
        sig_d, isl_d, sl_d = sig0[in_disc], isl0[in_disc], sl0[in_disc]
        if len(sig_d) < MIN_N_DISC:
            continue

        for sk in SL_K_GRID:
            sl_scaled = sl_d * sk
            for rr in RR_GRID:
                hold = derived_hold(sk, rr)          # ⭐ تنها تفاوت با S348
                st = queue_rr(df.iloc[:split], sig_d, isl_d, sl_scaled,
                              asset, hold, rr)
                if st is None or st['n'] < MIN_N_DISC:
                    continue
                sl_med = float(np.median(st['sl_pip']))
                tp_med = float(np.median(st['tp_pip']))
                feasible = tp_med > 2.0 * c          # قانونِ بارِ هزینه
                e1 = st['pnl'][st['entry_bar'] < half]
                e2 = st['pnl'][st['entry_bar'] >= half]
                repl = (len(e1) >= 5 and len(e2) >= 5
                        and float(e1.mean()) > 0 and float(e2.mean()) > 0)
                rbe = rqs2.breakeven_wr_cost(sl_med, tp_med, 2.0 * c)
                tp_hit = float((st['pnl'] >= st['tp_pip'] * 0.95).mean() * 100)
                rows.append(dict(
                    K=int(K), sl_k=float(sk), rr=float(rr), hold=int(hold),
                    n=st['n'], wr=st['wr'], exp=st['exp'], pf=st['pf'],
                    sl_pip=sl_med, tp_pip=tp_med,
                    rr_eff=float(tp_med / sl_med) if sl_med > 0 else None,
                    tp_hit_pct=tp_hit,
                    robust_be=float(rbe), feasible=bool(feasible),
                    repl=bool(repl),
                    eligible=bool(feasible and repl and st['n'] >= MIN_N_DISC),
                ))
                if verbose:
                    r = rows[-1]
                    flag = 'OK ' if r['eligible'] else '   '
                    why = '' if r['eligible'] else \
                          ('!infeasible' if not feasible else '!no-repl')
                    print(f"    {flag}K={K:<3}slk={sk:<6}rr={rr:<6}h={hold:<4}"
                          f"n={st['n']:<5}WR={st['wr']:6.2f}% "
                          f"exp={st['exp']:+8.3f}pip PF={st['pf']:5.2f} "
                          f"TPhit={tp_hit:5.1f}% RBE={rbe:5.1f}% {why}",
                          flush=True)

    elig = [r for r in rows if r['eligible']]
    best = max(elig, key=lambda r: r['exp']) if elig else None
    return rows, best


# ==============================================================================
#  مرحلهٔ ۲ — داوریِ رسمی: RQS2 روی کلِ نمونه، با همان بهای چندگانگیِ S348
# ==============================================================================
def judge(df, asset, best, warmup, gate, votes, n_perm, close, bar_time):
    vl, vs, wl, ws, atr = votes
    K, sk, rr, hold = best['K'], best['sl_k'], best['rr'], best['hold']
    split = int(len(df) * SPLIT_FRAC)

    sig, isl, sl = entries_for_K(vl, vs, wl, ws, atr, K)
    keep = gate[sig]
    sig, isl, sl = sig[keep], isl[keep], sl[keep] * sk

    st = queue_rr(df, sig, isl, sl, asset, hold, rr)
    if st is None or st['n'] < 5:
        return None, None
    tr = trades_df(st)
    n_long = int((tr['direction'] == 'long').sum())
    n_short = int(len(tr) - n_long)
    tp_hit = float((st['pnl'] >= st['tp_pip'] * 0.95).mean() * 100)
    print(f"    FULL-SAMPLE n={st['n']} (L={n_long} S={n_short}) "
          f"WR={st['wr']:.2f}% exp={st['exp']:+.3f}pip PF={st['pf']:.3f} "
          f"TPhit={tp_hit:.1f}%", flush=True)

    # خطِ مبنای اندازه‌گیری‌شده، به‌تفکیکِ سمت، با **همان** هندسه و همان افق
    atr_plain = np.nanmedian(atr, axis=0) * sk
    valid = np.where(np.isfinite(atr_plain) & (atr_plain > 0))[0]
    valid = valid[(valid >= warmup) & gate[valid]]
    print(f"    null pool = {len(valid):,} bars · {n_perm} perms/side "
          f"(same geometry rr={rr}, hold={hold})", flush=True)

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
                             asset, hold, rr)
            if s_all:
                d['uncond_wr'] = s_all['wr']
            if len(vi) > n_side:
                wrs = []
                for _ in range(n_perm):
                    pick = np.sort(rng.choice(len(vi), size=n_side,
                                              replace=False))
                    s_p = queue_rr(df, vi[pick],
                                   np.full(n_side, is_long_flag), slv[pick],
                                   asset, hold, rr)
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

    print(f"\n{'='*92}\n=== S350 TRIPLE-LOCK :: {card} (bars={len(df):,}) ===",
          flush=True)
    print(f"    cost={c:.2f}pip · split@{split:,} ({SPLIT_FRAC:.0%}) · "
          f"grid={N_GRID} · n_trials_cons={N_TRIALS_CONS:,} · hold=DERIVED",
          flush=True)

    votes = build_votes(df, warmup)
    gate, _thr = build_filter_gate(df, warmup)
    print(f"    C1 gate keeps {gate.mean()*100:.2f}% of bars", flush=True)

    print("  -- PHASE 1 : DISCOVERY (first 60% only, objective = expectancy) --",
          flush=True)
    rows, best = discover(df, asset, split, warmup, gate, votes, verbose)

    out = dict(card=card, asset=asset, bars=len(df), cost_pip=c,
               split_bar=split, grid_size=N_GRID, hold_rule='ceil((sl_k*rr)^2)',
               n_trials_cons=N_TRIALS_CONS, n_trials_opt=N_TRIALS_OPT,
               n_evaluated=len(rows),
               n_eligible=sum(r['eligible'] for r in rows),
               grid=rows, best=best, verdict=None)

    if best is None:
        print("    !!! no eligible geometry in the discovery window", flush=True)
        out['verdict'] = 'NO_ELIGIBLE_GEOMETRY'
    else:
        print(f"    >>> WINNER (pre-registered rule): K={best['K']} "
              f"sl_k={best['sl_k']} rr={best['rr']} hold={best['hold']} | "
              f"disc n={best['n']} WR={best['wr']:.2f}% "
              f"exp={best['exp']:+.3f}pip TPhit={best['tp_hit_pct']:.1f}% "
              f"RBE={best['robust_be']:.1f}%", flush=True)
        print("  -- PHASE 2 : OFFICIAL RQS2 VERDICT (full sample) --", flush=True)
        rc, ro = judge(df, asset, best, warmup, gate, votes,
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
    # قانونِ MTF — ترتیبِ پیش‌فرض از ریزترین کارتِ طلا
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
