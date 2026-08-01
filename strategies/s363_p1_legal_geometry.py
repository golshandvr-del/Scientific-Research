# -*- coding: utf-8 -*-
"""
S363 · پروتکل **P1 — هندسهٔ قانونی** برای لایهٔ S327 (Brooks Sell-Climax Reversal)

پیش‌ثبت: `results/S363_ADDENDUM_P1_LEGAL_GEOMETRY_PREREG.md` (کامیت‌شده پیش از اجرا)
مبنا:    `results/_scan_S363/P0_*.json` (بازداوریِ پیکربندیِ منجمد)

مسئله
-----
P0 نشان داد لبهٔ S327 **واقعی** است (لیفت `+7.8…+20.9pp` بر نولِ هم‌هندسه) اما
هندسه‌اش **غیرقانونی** است (`RR = 0.35…0.42 < 0.5` ⇒ `H2` روی هر ۷ کارت رد).
و مهم‌تر: کلِ تاریخِ جست‌وجویِ این لایه (۸٬۷۸۴ پیکربندی) **هرگز** `RR ≥ 0.5` را
بازدید نکرده است. پس ناحیهٔ قانونی اندازه‌گیری‌نشده است، نه اندازه‌گیری‌شده‌ومنفی.

طرح
----
سیگنال 🔒 منجمد روی پیکربندیِ آرشیوِ همان کارت · هندسه 🔍 جست‌وجو روی گریدِ §۳
پیش‌ثبت · آمارهٔ آزمون = **میانگینِ لیفتِ خانواده** (مسیرِ B) با **جای‌گشتِ
مشترک** · هندسهٔ استقرار با **قانونِ کم‌ترین‌انحرافِ** ساختاری (صفر درجهٔ آزادی).

سه تصمیمِ مهندسی که صحتِ نتیجه به آن‌ها وابسته است
--------------------------------------------------
۱. **`wr_of` روی جدولِ برآمد** به‌جای `se.simulate_trades` برای هر ۱۲۰ هندسه.
   P0 برابریِ بیت‌به‌بیتِ این دو را روی هر ۷ کارت اثبات کرد (`parity_table_vs_engine`)،
   پس این جایگزینی **اثبات‌شده** است نه فرض‌شده — و ۱۲۰ برابر ارزان‌تر.
   هندسهٔ **مستقر** با خودِ موتور (`simulate_trades`) دوباره داوری می‌شود.

۲. **قرعه‌های مشترک**: `K` جای‌گشت **یک‌بار** تولید و در **همهٔ** هندسه‌ها
   استفاده می‌شوند. قرعهٔ مستقل به‌ازای هندسه، پراکندگیِ نولِ میانگین را
   `√G` برابر کوچک می‌کند و p را مصنوعاً معنادار می‌سازد (بندِ ۴.۲ پیش‌ثبت).

۳. **حافظه**: `res/xbar` هر هندسه پس از مصرف آزاد می‌شود؛ فقط ماتریسِ
   `K × G`ِ `WR`ها نگه داشته می‌شود (۲۰۰۰×۱۲۰ float32 ≈ ۱MB). سندباکس ۹۸۵MB
   دارد و اجرای اولِ نشست با `MemoryError` کشته شد.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                                    # noqa: E402
from engine import rqs2 as R2                                            # noqa: E402
from strategies.s363_s327_v24_rejudge import (                           # noqa: E402
    ARCHIVE_CFG, N_BRACKETS, SEEDS, PERM_K, P_BAR, SPLIT_FRAC,
    build_features, geometry, signal_of, outcome_table, wr_of,
    measure_neff, empirical_p)

OUT = "results/_scan_S363"

# ═══════ گریدِ منجمدِ §۳ پیش‌ثبت — هیچ عددی پس از دیدنِ نتیجه تغییر نمی‌کند ═══════
SL_MULT = [2.05, 2.45, 2.85, 3.25, 3.65]
RR_GRID = [0.52, 0.64, 0.79, 0.97, 1.19, 1.46]
HOLD_GRID = [18, 27, 41, 62]


def build_family():
    """خانوادهٔ هندسه‌های **قانونی و دسترسی‌پذیر**.

    فیلتر **ساختاری** است (پیش از دیدنِ هر عملکردی):
      · `RR ≥ 0.5`            ← دروازهٔ H2
      · `(sl_m × RR)² ≤ hold` ← قانونِ دسترسی‌پذیریِ سد
    """
    fam, dropped = [], []
    for sl in SL_MULT:
        for rr in RR_GRID:
            tp = sl * rr
            need = (sl * rr) ** 2
            for hold in HOLD_GRID:
                g = dict(sl_m=round(sl, 4), tp_m=round(tp, 4), rr=rr, hold=hold,
                         tp_bars_needed=round(need, 2))
                (fam if hold >= need else dropped).append(g)
    return fam, dropped


# ═══════════════════════════ نولِ سطحِ‌خانواده ═══════════════════════════
def family_test(df, asset, feat, cfg, family, k_perm, seed, verbose=True):
    """لیفتِ میانگینِ خانواده + نولِ جای‌گشتیِ **مشترک**.

    خروجی: (per_geom, lift_family_obs, draws_family, meta)
    """
    n = len(df)
    sig = signal_of(feat, cfg, asset)          # 🔒 سیگنالِ منجمد
    sig_bars = np.flatnonzero(sig)
    k_sig = int(sig_bars.size)

    hold_max = max(g['hold'] for g in family)
    lo = min(300, max(0, n // 10))
    hi = max(lo + 1, n - hold_max - 2)
    pool = np.arange(lo, hi)

    # ── قرعه‌های مشترک: یک‌بار تولید، در همهٔ هندسه‌ها یکسان ──
    rng = np.random.default_rng(seed)
    k = min(k_sig, pool.size)
    picks = np.empty((k_perm, k), dtype=np.int64)
    for i in range(k_perm):
        picks[i] = np.sort(rng.choice(pool, size=k, replace=False))

    per_geom = []
    lift_draws = np.zeros(k_perm, dtype=np.float64)
    n_used_geom = 0
    t0 = time.time()

    for gi, g in enumerate(family):
        sl_arr, tp_arr, _ = geometry(feat, asset, g['sl_m'], g['tp_m'])
        res, xbar = outcome_table(df, asset, sl_arr, tp_arr, g['hold'])

        wr_obs = wr_of(sig_bars, res, xbar)
        if wr_obs is None:
            del res, xbar
            continue

        d = np.empty(k_perm, dtype=np.float64)
        ok = True
        for i in range(k_perm):
            w = wr_of(picks[i], res, xbar)
            if w is None:
                ok = False
                break
            d[i] = w
        if not ok:
            del res, xbar
            continue

        perm_mean = float(d.mean())
        perm_sd = float(d.std(ddof=1))
        lift = wr_obs - perm_mean

        # سربه‌سرِ هزینه‌دارِ همین هندسه (میانهٔ همان کندل‌های سیگنال)
        cost = float(se.ASSETS[asset]['spread_pip']) + \
            2.0 * float(se.ASSETS[asset].get('slip_pip', 0.0))
        sl_med = float(np.median(sl_arr[sig_bars]))
        tp_med = float(np.median(tp_arr[sig_bars]))
        be = R2.breakeven_wr_cost(sl_med, tp_med, cost)

        per_geom.append(dict(
            sl_m=g['sl_m'], tp_m=g['tp_m'], rr=g['rr'], hold=g['hold'],
            wr=round(wr_obs, 3), perm_mean=round(perm_mean, 3),
            perm_sd=round(perm_sd, 3), lift=round(lift, 3),
            z=round(lift / perm_sd, 3) if perm_sd > 0 else None,
            be_cost=None if be is None else round(be, 3),
            excess=None if be is None else round(wr_obs - be, 3),
            sl_pip_med=round(sl_med, 2), tp_pip_med=round(tp_med, 2)))

        lift_draws += (d - perm_mean)      # لیفتِ همان قرعه در همین هندسه
        n_used_geom += 1
        del res, xbar, d

        if verbose and (gi + 1) % 20 == 0:
            print(f"      ...{gi+1}/{len(family)} geoms  "
                  f"({time.time()-t0:.0f}s)", flush=True)

    if n_used_geom == 0:
        return [], None, None, dict(k_sig=k_sig, n_geom=0)

    lift_draws /= float(n_used_geom)
    lift_obs = float(np.mean([g['lift'] for g in per_geom]))
    meta = dict(k_sig=k_sig, n_geom=n_used_geom, k_perm=k_perm,
                pool_size=int(pool.size), seconds=round(time.time() - t0, 1))
    return per_geom, lift_obs, lift_draws, meta


# ═══════════════ قانونِ کم‌ترین‌انحراف (بندِ ۵ پیش‌ثبت) ═══════════════
def pick_deployment(family, arch):
    """هندسهٔ مستقر — **بدونِ نگاه به هیچ عددِ عملکردی**.

    ① کمینهٔ `rr` · ② کمینهٔ `|sl_m − sl_arch|` · ③ کمینهٔ `|hold − hold_arch|`
    """
    return min(family, key=lambda g: (g['rr'],
                                      abs(g['sl_m'] - arch['sl_m']),
                                      abs(g['hold'] - arch['hold'])))


# ═════════════════ داوریِ کاملِ RQS2 روی هندسهٔ مستقر ═════════════════
def judge_deployment(df, asset, feat, cfg, geo, n_eff, verbose=True):
    sl_arr, tp_arr, _ = geometry(feat, asset, geo['sl_m'], geo['tp_m'])
    sig = signal_of(feat, cfg, asset)
    zero = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, sig, zero, sl_pip=sl_arr, tp_pip=tp_arr,
                            asset=asset, max_hold=geo['hold'], allow_overlap=False)
    if tr is None or len(tr) < 5:
        return dict(status='NO_TRADES')

    n = len(tr)
    wr_obs = 100.0 * float((tr['pnl_pip'] > 0).sum()) / n
    sb = tr['signal_bar'].to_numpy(int)
    sl_med = float(np.median(sl_arr[sb]))
    tp_med = float(np.median(tp_arr[sb]))

    close = df['close'].to_numpy(float)
    bar_time = df['time'].to_numpy()
    split_bar = int(len(df) * SPLIT_FRAC)

    out = dict(status='JUDGED', geometry=dict(geo), n_trades=n,
               wr=round(wr_obs, 3), sl_pip_median=round(sl_med, 3),
               tp_pip_median=round(tp_med, 3),
               rr_realised=round(tp_med / sl_med, 4), seeds={})

    from strategies.s363_s327_v24_rejudge import build_null
    for seed in SEEDS:
        null, draws = build_null(df, asset, int(sig.sum()), sl_arr, tp_arr,
                                 geo['hold'], PERM_K, seed)
        p_emp, n_ge = empirical_p(draws, wr_obs)
        r = R2.compute_rqs2(tr, asset, sl_pip=sl_med, tp_pip=tp_med,
                            bar_time=bar_time, close=close, null=null,
                            n_trials=int(round(n_eff)), split_bar=split_bar)
        bad = [g for g, v in (r.get('gates') or {}).items() if v is not True]
        out['seeds'][str(seed)] = dict(
            verdict=r.get('verdict'), score=r.get('rqs2_score'),
            failing=bad, gates=r.get('gates'), metrics=r.get('metrics'),
            notes=r.get('notes'), p_empirical=round(p_emp, 6),
            null={k: null['long'][k] for k in
                  ('uncond_wr', 'perm_mean', 'perm_sd', 'perm_k')},
            accept=bool(r.get('verdict') == 'ACCEPT' and p_emp <= P_BAR))
        if verbose:
            print(f"      seed={seed}: {r.get('verdict'):11s} "
                  f"score={r.get('rqs2_score')} failing={bad or 'NONE'} "
                  f"p_emp={p_emp:.6f}", flush=True)

    out['all_seeds_accept'] = all(v['accept'] for v in out['seeds'].values())
    return out


# ═══════════════════════════════ اجرا ═══════════════════════════════
def run_card(card, k_perm=PERM_K, verbose=True):
    asset, tf = card.split('-')
    path = os.path.join('data', f'{asset}_{tf}.csv')
    if not os.path.exists(path):
        return dict(card=card, status='NO_DATA')

    df = se.load_data(path)
    cfg = dict(ARCHIVE_CFG[card])
    feat = build_features(df, asset)
    family, dropped = build_family()

    rec = dict(card=card, asset=asset, tf=tf, protocol='P1_legal_geometry',
               frozen_signal={k: cfg[k] for k in
                              ('k_body', 'br_min', 'streak_n', 'rsi_lo', 'regime')},
               archive_geometry={k: cfg[k] for k in ('sl_m', 'tp_m', 'hold')},
               archive_rr=round(cfg['tp_m'] / cfg['sl_m'], 4),
               family=dict(raw=len(family) + len(dropped), kept=len(family),
                           dropped_unreachable=len(dropped),
                           grid=dict(sl=SL_MULT, rr=RR_GRID, hold=HOLD_GRID)))

    if verbose:
        print(f"\n=== {card} :: P1  family={len(family)} legal+reachable "
              f"(dropped {len(dropped)} unreachable)  archive RR="
              f"{rec['archive_rr']}", flush=True)

    n_eff, m_eff, n_cols, m_used = measure_neff(feat, asset, verbose=verbose)
    rec['neff'] = dict(n_eff=round(n_eff, 1), m_eff_signal=round(m_eff, 2),
                       n_signal_columns=n_cols, bracket_multiplier=N_BRACKETS,
                       note='path B: family averaging adds no multiplicity')

    fam_res = {}
    for seed in SEEDS:
        per_geom, lift_obs, draws, meta = family_test(
            df, asset, feat, cfg, family, k_perm, seed, verbose=verbose)
        if lift_obs is None:
            fam_res[str(seed)] = dict(status='NO_FAMILY')
            continue
        ge = int((draws >= lift_obs - 1e-12).sum())
        p_fam = (1.0 + ge) / (1.0 + len(draws))
        p_adj = min(1.0, p_fam * n_eff)
        z_fam = (lift_obs - float(draws.mean())) / float(draws.std(ddof=1)) \
            if draws.std(ddof=1) > 0 else None
        fam_res[str(seed)] = dict(
            lift_family=round(lift_obs, 4), draws_mean=round(float(draws.mean()), 4),
            draws_sd=round(float(draws.std(ddof=1)), 4),
            draws_max=round(float(draws.max()), 4), n_ge=ge,
            p_family=round(p_fam, 6), p_adj=round(p_adj, 6),
            z_family=None if z_fam is None else round(z_fam, 3),
            pass_family=bool(lift_obs >= 4.0 and p_fam <= P_BAR and p_adj < 0.05),
            meta=meta)
        if seed == SEEDS[0]:
            rec['per_geometry'] = per_geom
        if verbose:
            f = fam_res[str(seed)]
            print(f"    seed={seed} LIFT_FAMILY={f['lift_family']:+.3f}pp "
                  f"null={f['draws_mean']:+.3f}±{f['draws_sd']:.3f} "
                  f"z={f['z_family']} p={f['p_family']:.6f} "
                  f"p_adj={f['p_adj']:.4f} PASS={f['pass_family']}", flush=True)

    rec['family_test'] = fam_res
    rec['family_pass_all_seeds'] = all(
        v.get('pass_family') for v in fam_res.values())

    # هندسهٔ مستقر — ساختاری، حتی اگر آزمونِ خانوادگی رد شود (برای ثبت)
    dep = pick_deployment(family, cfg)
    rec['deployment_geometry_rule'] = dep
    if verbose:
        print(f"    deployment (min-perturbation rule): sl={dep['sl_m']} "
              f"tp={dep['tp_m']} rr={dep['rr']} hold={dep['hold']}", flush=True)

    if rec['family_pass_all_seeds']:
        rec['deployment_judgement'] = judge_deployment(
            df, asset, feat, cfg, dep, n_eff, verbose=verbose)
        rec['decision'] = ('ALIVE_AT_LEGAL_GEOMETRY'
                           if rec['deployment_judgement'].get('all_seeds_accept')
                           else 'FAMILY_PASS_BUT_DEPLOYMENT_REJECT')
    else:
        rec['deployment_judgement'] = dict(
            status='SKIPPED',
            reason='family-mean test failed; the pre-registration forbids '
                   'retreating to the best family member')
        rec['decision'] = 'P1_FAIL_FAMILY'
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cards', default='XAUUSD-M5')
    ap.add_argument('--perm', type=int, default=PERM_K)
    a = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    cards = [c.strip() for c in a.cards.split(',') if c.strip()]
    print('=' * 100)
    print('S363 · P1 — هندسهٔ قانونی (RR ≥ 0.5) برای S327')
    print(f'cards={cards}  SEEDS={SEEDS}  K={a.perm}')
    fam, dropped = build_family()
    print(f'family: {len(fam)} legal+reachable of {len(fam)+len(dropped)} raw')
    print('=' * 100)

    for card in cards:
        rec = run_card(card, k_perm=a.perm)
        fp = os.path.join(OUT, f'P1_{card}.json')
        with open(fp, 'w') as fh:
            json.dump(rec, fh, ensure_ascii=False, indent=1, default=str)
        print(f"  → saved {fp}  decision={rec.get('decision')}", flush=True)


if __name__ == '__main__':
    main()
