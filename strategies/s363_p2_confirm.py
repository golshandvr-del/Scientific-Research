# -*- coding: utf-8 -*-
"""
S363 · پروتکل **P2 — مرحلهٔ ۲: تأییدِ تک‌شات** روی لایهٔ S327

    python3 strategies/s363_p2_confirm.py [--cards XAUUSD-M5,...]

این اسکریپت **حقِ جست‌وجو ندارد.** ورودی‌اش یک فایلِ قفلِ از-پیش-کامیت‌شده
(`results/_scan_S363/P2_LOCK.json`) است که در آن *یک* اندیکاتور، *یک* جهت،
*یک* چندک و — مهم‌تر از همه — **آستانهٔ عددیِ مطلقِ هر کارت** ثبت شده است.
اینجا هیچ گریدی، هیچ حلقه‌ای روی کاندیداها، و هیچ انتخابی وجود ندارد.

چرا این تفکیکِ دو-مرحله‌ای، *ساختاری* است و نه تشریفاتی
--------------------------------------------------------
مسیرِ C در `docs/GUIDE_FOR_STRATEGY_BUILDER_AI.md` می‌گوید: اگر کشف را به ۶۰٪
اولِ داده محدود کنی و **پیش از دیدنِ ۴۰٪ باقی‌مانده** پیکربندی را در یک کامیتِ
جداگانه قفل کنی، آنگاه آزمونِ تأییدی **یک آزمون** است، نه ۴۰۱۰ آزمون. تمامِ
اعتبارِ این ادعا به یک چیز بند است: اینکه بینِ «قفل» و «تأیید» هیچ اطلاعاتی از
۴۰٪ آخر به پیکربندی برنگردد. دو نشتِ ظریف اینجا کمین کرده‌اند و هر دو با
تصمیمِ صریحِ کد بسته شده‌اند:

  ۱. **نشتِ آستانه.** وسوسه‌انگیز است که در مرحلهٔ ۲ چندکِ ۰.۳۰ را دوباره روی
     *کلِ* نمونه حساب کنیم (طبیعی به‌نظر می‌رسد!). این نشت است: آنگاه ۴۰٪ آخر
     در تعیینِ آستانهٔ خودش شرکت کرده. کد **عددِ مطلقِ** ذخیره‌شده در فایلِ قفل
     را می‌خواند و `np.quantile` را هرگز صدا نمی‌زند.

  ۲. **نشتِ انتخاب.** اگر مرحلهٔ ۲ اجازه داشته باشد «اگر برندهٔ اول رد شد، دومی
     را امتحان کن»، صورت‌حسابِ چندگانگی دوباره ۴۰۱۰ می‌شود. کد فقط `rank=1` را
     می‌خواند و هیچ آرگومانی برای انتخابِ رتبهٔ دیگر ندارد.

صورت‌حسابِ چندگانگی — و چرا آن را **نرم نمی‌کنم**
--------------------------------------------------
مسیرِ C آزمونِ تأییدی را تک-آزمون می‌کند، پس *هزینهٔ خودِ فیلتر* `N=1` است.
اما پیکربندیِ **سیگنال** (k_body/br_min/streak/rsi/regime) از همان جست‌وجویِ
تاریخیِ ۸۷۸۴-تایی آمده و افزودنِ یک فیلتر آن بدهیِ تاریخی را پاک نمی‌کند. پس
مثل P0/P1 هر سه حسابداری گزارش می‌شود و `neff` (≈۵۰۷۷) مبنای حکم است. در
الحاقیهٔ P2 نوشتم که این کار را می‌کنم و دروازهٔ `H5` احتمالاً سخت‌ترین می‌ماند؛
اینجا به آن پایبندم.

هندسه
-----
هندسهٔ **مستقرِ P1** (`RR=0.52`، قاعدهٔ کم‌ترین-انحراف) — نه هندسهٔ آرشیو. این
هندسه پیش از دیدنِ هر نتیجه‌ای در §۵ الحاقیهٔ P1 منجمد شده بود.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import indicator_bank as ib                                  # noqa: E402
from engine import rqs2 as R2                                            # noqa: E402
from engine import scalp_engine as se                                    # noqa: E402
from strategies.s363_s327_v24_rejudge import (                           # noqa: E402
    ARCHIVE_CFG, N_BRACKETS, SEEDS, PERM_K, P_BAR, SPLIT_FRAC,
    build_features, geometry, signal_of, outcome_table, wr_of,
    build_null, empirical_p, measure_neff)
from strategies.s363_p1_legal_geometry import build_family, pick_deployment  # noqa: E402

OUT = "results/_scan_S363"
LOCK = os.path.join(OUT, 'P2_LOCK.json')


def apply_filter(df, lock_card, direction):
    """ماسکِ فیلتر روی **میلهٔ سیگنال**، با آستانهٔ **مطلقِ** قفل‌شده.

    ⚠️ `np.quantile` عمداً اینجا وجود ندارد. عدد از فایلِ قفل می‌آید تا ۴۰٪
    خارج‌ازنمونه نتواند در تعیینِ آستانهٔ خودش شرکت کند.
    """
    thr = float(lock_card['thr'])
    v = ib.compute(lock_card['indicator'], df).to_numpy(float)
    if direction == 'KEEP_HIGH':
        keep = v >= thr
    elif direction == 'KEEP_LOW':
        keep = v <= thr
    else:
        raise ValueError(f"unknown direction {direction!r}")
    return keep & np.isfinite(v)


def run_card(card, lock, verbose=True):
    asset, tf = card.split('-')
    path = os.path.join('data', f'{asset}_{tf}.csv')
    if not os.path.exists(path):
        return dict(card=card, status='NO_DATA')

    lc = lock['per_card'].get(card)
    if lc is None:
        return dict(card=card, status='NOT_IN_LOCK')

    df = se.load_data(path)
    cfg = ARCHIVE_CFG[card]
    fam, _ = build_family()
    geom = pick_deployment(fam, cfg)                  # هندسهٔ منجمدِ P1

    feat = build_features(df, asset)
    sl_arr, tp_arr, _ = geometry(feat, asset, geom['sl_m'], geom['tp_m'])
    sig_raw = signal_of(feat, cfg, asset)
    keep = apply_filter(df, lc, lock['direction'])
    sig = sig_raw & keep

    n_raw, n_flt = int(sig_raw.sum()), int(sig.sum())
    rr = geom['tp_m'] / geom['sl_m']

    rec = dict(card=card, asset=asset, tf=tf, protocol='P2_CONFIRM',
               lock=dict(indicator=lock['indicator'], direction=lock['direction'],
                         quantile=lock['quantile'], thr=lc['thr'],
                         lock_commit=lock.get('lock_commit')),
               geometry=dict(sl_m=geom['sl_m'], tp_m=geom['tp_m'],
                             rr=round(rr, 4), hold=geom['hold']),
               signals=dict(raw=n_raw, filtered=n_flt,
                            retention=round(n_flt / n_raw, 4) if n_raw else None),
               bars=len(df), seeds={})

    if verbose:
        print(f"\n=== {card} :: P2-CONFIRM  filter={lock['indicator']} "
              f"{lock['direction']} thr={lc['thr']:.6g}\n"
              f"    geometry sl={geom['sl_m']} tp={geom['tp_m']} "
              f"RR={rr:.3f} hold={geom['hold']} | "
              f"signals {n_raw} -> {n_flt} "
              f"({100.0*n_flt/max(n_raw,1):.1f}% retained)", flush=True)

    if n_flt < 5:
        rec['status'] = 'NO_SIGNAL'
        return rec

    zero = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, sig, zero, sl_pip=sl_arr, tp_pip=tp_arr,
                            asset=asset, max_hold=geom['hold'], allow_overlap=False)
    if tr is None or len(tr) < 5:
        rec['status'] = 'NO_TRADES'
        return rec

    n = len(tr)
    wr_obs = 100.0 * float((tr['pnl_pip'] > 0).sum()) / n
    sb = tr['signal_bar'].to_numpy(int)
    sl_med = float(np.median(sl_arr[sb]))
    tp_med = float(np.median(tp_arr[sb]))

    cost = (float(se.ASSETS[asset]['spread_pip'])
            + 2.0 * float(se.ASSETS[asset].get('slip_pip', 0.0)))
    be_true = R2.breakeven_wr_cost(sl_med, tp_med, cost)

    rec.update(status='JUDGED', n_trades=n, wr_obs=round(wr_obs, 3),
               sl_pip_median=round(sl_med, 3), tp_pip_median=round(tp_med, 3),
               rr_realised=round(tp_med / sl_med, 4),
               breakeven=dict(cost_pip=cost,
                              be_true_pct=None if be_true is None else round(be_true, 3),
                              excess_true_pp=None if be_true is None
                              else round(wr_obs - be_true, 3)))

    # اثباتِ اپل‌به‌اپل بودنِ جدولِ برآمد پیش از ساختِ نول
    res_chk, xb_chk = outcome_table(df, asset, sl_arr, tp_arr, geom['hold'])
    wr_tbl = wr_of(np.flatnonzero(sig), res_chk, xb_chk)
    rec['parity_table_vs_engine'] = dict(
        wr_engine=round(wr_obs, 3),
        wr_table=None if wr_tbl is None else round(wr_tbl, 3))
    if wr_tbl is None or abs(wr_tbl - wr_obs) > 0.51:
        raise AssertionError(
            f"{card}: outcome table disagrees with engine "
            f"(WR {wr_tbl} vs {wr_obs}); refusing to build a null on it.")

    # ── تفکیکِ کشف/خارج‌ازنمونه، فقط برای گزارش (دروازهٔ H7 خودش می‌سنجد) ──
    split_bar = int(len(df) * SPLIT_FRAC)
    in_hold = sb >= split_bar
    if in_hold.any():
        w = (tr['pnl_pip'].to_numpy() > 0)
        rec['segments'] = dict(
            discovery=dict(n=int((~in_hold).sum()),
                           wr=round(100.0 * w[~in_hold].mean(), 3) if (~in_hold).any() else None),
            holdout=dict(n=int(in_hold.sum()),
                         wr=round(100.0 * w[in_hold].mean(), 3)))

    # صورت‌حسابِ چندگانگی: همان بدهیِ تاریخیِ سیگنال (نرم نمی‌شود)
    n_eff, m_eff, n_cols, m_used = measure_neff(feat, asset, verbose=verbose)
    rec['neff'] = dict(n_eff=round(n_eff, 1), m_eff_signal=round(m_eff, 2),
                       n_signal_columns=n_cols, m_with_variance=m_used,
                       method='exact_phi_correlation',
                       bracket_multiplier=N_BRACKETS,
                       note='historical signal-selection debt; path C makes the '
                            'FILTER a single test but does not erase it')

    close = df['close'].to_numpy(float)
    bar_time = df['time'].to_numpy()
    labels = (('neff', n_eff), ('pathC', 1.0))

    if verbose:
        print(f"    n_trades={n} WR={wr_obs:.2f}% (table {wr_tbl:.2f}%) "
              f"be_true={be_true:.2f}% excess={wr_obs-be_true:+.2f}pp", flush=True)

    for seed in SEEDS:
        null, draws = build_null(df, asset, n_flt, sl_arr, tp_arr, geom['hold'],
                                 PERM_K, seed)
        p_emp, n_ge = empirical_p(draws, wr_obs)
        out = {}
        for label, nt in labels:
            r = R2.compute_rqs2(tr, asset, sl_pip=sl_med, tp_pip=tp_med,
                                bar_time=bar_time, close=close, null=null,
                                n_trials=int(round(nt)), split_bar=split_bar)
            out[label] = dict(verdict=r.get('verdict'), score=r.get('rqs2_score'),
                              rank=r.get('rank'), gates=r.get('gates'),
                              metrics=r.get('metrics'), notes=r.get('notes'))
        m0 = out['neff']['metrics']
        out['null'] = {k: null['long'][k] for k in
                       ('uncond_wr', 'perm_mean', 'perm_sd', 'perm_max', 'perm_k')}
        out['p_empirical'] = round(p_emp, 6)
        out['n_draws_ge_obs'] = n_ge
        out['accept_neff'] = bool(out['neff']['verdict'] == 'ACCEPT' and p_emp <= P_BAR)
        out['accept_pathC'] = bool(out['pathC']['verdict'] == 'ACCEPT' and p_emp <= P_BAR)
        rec['seeds'][str(seed)] = out
        if verbose:
            print(f"  seed={seed} | perm_mean={out['null']['perm_mean']:.2f}% "
                  f"sd={out['null']['perm_sd']:.2f} lift={m0.get('skill_lift_pp')}pp "
                  f"z={m0.get('skill_z')} p_emp={p_emp:.6f}", flush=True)
            for label, _ in labels:
                bad = [g for g, v in (out[label]['gates'] or {}).items() if v is not True]
                print(f"      {label:6s}: {out[label]['verdict']:11s} "
                      f"score={out[label]['score']} failing={bad or 'NONE'}", flush=True)

    rec['honest'] = dict(
        verdicts_neff={s: v['neff']['verdict'] for s, v in rec['seeds'].items()},
        verdicts_pathC={s: v['pathC']['verdict'] for s, v in rec['seeds'].items()},
        all_seeds_accept_neff=all(v['accept_neff'] for v in rec['seeds'].values()),
        all_seeds_accept_pathC=all(v['accept_pathC'] for v in rec['seeds'].values()))
    rec['honest']['decision'] = (
        'ALIVE' if rec['honest']['all_seeds_accept_neff']
        else 'ALIVE_PATHC_ONLY' if rec['honest']['all_seeds_accept_pathC']
        else 'P2_FAIL')
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cards', default=None)
    a = ap.parse_args()

    if not os.path.exists(LOCK):
        sys.exit(f"lock file {LOCK} does not exist. Stage 2 refuses to run "
                 f"without a pre-committed lock — that file IS the "
                 f"pre-registration of this test.")
    lock = json.load(open(LOCK))
    cards = a.cards.split(',') if a.cards else list(lock['per_card'].keys())

    print(f"\n{'='*92}")
    print("S363 · P2 STAGE-2 CONFIRMATION — single-shot, zero search")
    print(f"  locked filter : {lock['indicator']} {lock['direction']} "
          f"q={lock['quantile']}")
    print(f"  lock commit   : {lock.get('lock_commit')}")
    print(f"  cards         : {len(cards)}")
    print(f"{'='*92}", flush=True)

    for card in cards:
        rec = run_card(card, lock)
        path = os.path.join(OUT, f'P2C_{card}.json')
        with open(path, 'w') as f:
            json.dump(rec, f, indent=1, ensure_ascii=False)
        print(f"  → saved {path}  status={rec.get('status')} "
              f"decision={rec.get('honest', {}).get('decision')}", flush=True)


if __name__ == '__main__':
    main()
