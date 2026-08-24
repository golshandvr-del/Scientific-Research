#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S893 — داوریِ مجددِ S892 زیرِ نالِ کانونیِ هندسه-همتا (صفر درجهٔ آزادی).

قرارداد: results/S893_PREREG_CanonicalNullReaudit_Xauusd_MTF.md (کامیت 532099e5)
  - معاملات: بازتولیدِ بیت-به-بیتِ S892 (پیکربندیِ قفل‌شده از JSONهای _s892).
  - نالِ ①: ورودِ غیرشرطیِ هندسه-همتا، ۳ قرعهٔ یکنواختِ بذردار {893,1893,2893}؛
    مرجع = max (محافظه‌کاری _side_null_ref).
  - نالِ ②: جای‌گشتِ زمانیِ K=500 seed=893 فقط اگر دروازه‌های مستقل-از-نال سبز
    باشند + استثنای لنگرِ H2 (همیشه).
  - n_trials=912 (بدون افزایش — صفر آزمایشِ جدید). split همان 70٪ S892.

اجرا:  python3 strategies/s893_canonical_null.py H2
"""
import sys, os, json, gc
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from tools import s434_fast_data as fd
from engine import rqs2
from engine import scalp_engine as se

ASSET = 'XAUUSD'
N_TRIALS = 912           # شمارشِ صادقانهٔ S892؛ S893 هیچ آزمایشِ جدیدی ندارد
PERM_K = 500
PERM_SEED = 893
UNC_SEEDS = (893, 1893, 2893)
IN = 'results/_s892'
OUT = 'results/_s893'
PREREG = '532099e5'
ANCHOR_TF = 'H2'         # استثنای لنگر: perm در هر صورت اجرا می‌شود

# دروازه‌های مستقل از نال (فقط از خودِ معاملات)
NULL_INDEP = ('H0', 'H1', 'H2', 'H6', 'H8', 'H9', 'H10')


def hour_first_mask(times, H):
    hrs = pd.to_datetime(times, unit='s').hour.values
    is_h = hrs == H
    prev = np.roll(is_h, 1); prev[0] = False
    return is_h & ~prev


def simulate(df, ls, ss, sl_pip, tp_pip, hold):
    return se.simulate_trades(df, ls, ss, sl_pip=sl_pip, tp_pip=tp_pip,
                              asset=ASSET, max_hold=hold, allow_overlap=False)


def uncond_geo_baseline(df, direction, sl_pip, tp_pip, hold, N):
    """نالِ ①: ورودِ غیرشرطی با همان هندسه — ۳ قرعهٔ یکنواختِ بذردار."""
    lo, hi = 200, N - hold - 2
    size = min(20000, N // max(hold, 1))
    rows = []
    for seed in UNC_SEEDS:
        rng = np.random.default_rng(seed)
        pos = rng.choice(np.arange(lo, hi), size=min(size, hi - lo), replace=False)
        sig = np.zeros(N, dtype=bool); sig[np.sort(pos)] = True
        z = np.zeros(N, dtype=bool)
        ls = sig if direction == 'long' else z
        ss = sig if direction == 'short' else z
        tr = simulate(df, ls, ss, sl_pip, tp_pip, hold)
        wr = 100.0 * float((tr['outcome'] == 'win').mean()) if len(tr) else None
        rows.append((seed, wr, len(tr)))
        print(f"  uncond seed={seed}: n={len(tr)} wr={wr:.2f}%", flush=True)
        del tr; gc.collect()
    uncond_wr = max(r[1] for r in rows if r[1] is not None)
    return uncond_wr, rows


def perm_geo_baseline(df, direction, sl_pip, tp_pip, hold, n_sig, N,
                      k=PERM_K, seed=PERM_SEED):
    """نالِ ②: جای‌گشتِ زمانیِ همان تعدادِ سیگنالِ خام با همان هندسه."""
    rng = np.random.default_rng(seed)
    lo, hi = 200, N - hold - 2
    z = np.zeros(N, dtype=bool)
    wrs = []
    for i in range(k):
        pos = rng.choice(np.arange(lo, hi), size=n_sig, replace=False)
        sig = np.zeros(N, dtype=bool); sig[np.sort(pos)] = True
        ls = sig if direction == 'long' else z
        ss = sig if direction == 'short' else z
        tr = simulate(df, ls, ss, sl_pip, tp_pip, hold)
        if tr is not None and len(tr) >= 30:
            wrs.append(100.0 * float((tr['outcome'] == 'win').mean()))
        del tr
        if (i + 1) % 100 == 0:
            gc.collect()
            print(f"  perm {i+1}/{k} …", flush=True)
    a = np.asarray(wrs, float)
    return dict(mean=float(a.mean()), sd=float(a.std(ddof=1)),
                max=float(a.max()), min=float(a.min()),
                p95=float(np.percentile(a, 95)), k=int(len(a)))


def run_tf(tf):
    print('=' * 72)
    print(f"S893 Canonical-Null Re-audit · XAUUSD-{tf} (prereg {PREREG})")
    print('=' * 72, flush=True)
    src_json = f'{IN}/rqs2_XAUUSD-{tf}.json'
    with open(src_json) as f:
        prev = json.load(f)
    if prev.get('verdict') == 'INCOMPLETE' or 'locked' not in prev or not prev.get('locked', {}).get('dir'):
        _save(tf, dict(card=f'XAUUSD-{tf}', prereg=PREREG, verdict='INCOMPLETE',
                       reason='S892 card was INCOMPLETE — nothing to re-audit'))
        print("S892 INCOMPLETE → S893 INCOMPLETE"); return

    lk = prev['locked']; H, direction = int(lk['H']), lk['dir']
    sl_pip, tp_pip = float(prev['sl_pip']), float(prev['tp_pip'])
    hold, split = int(prev['hold']), int(prev['split'])

    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    if 'volume' in df.columns:
        df = df.drop(columns=['volume'])
    src = d.get('src', '?'); del d; gc.collect()
    N = len(df)
    assert N == int(prev['bars']), f"bar count changed! {N} != {prev['bars']}"
    times = df['time'].values
    c = df['close'].values

    # ---------- بازتولیدِ قطعیِ معاملاتِ S892 ----------
    ev = hour_first_mask(times, H)
    z = np.zeros(N, dtype=bool)
    ls = ev if direction == 'long' else z
    ss = ev if direction == 'short' else z
    n_sig = int(ev.sum())
    tr = simulate(df, ls, ss, sl_pip, tp_pip, hold)
    n_all = len(tr); wr_all = 100.0 * float((tr['outcome'] == 'win').mean())
    repro_ok = (n_all == int(prev['n']) and abs(wr_all - float(prev['wr'])) < 0.05)
    print(f"repro: n={n_all} (S892 {prev['n']})  wr={wr_all:.2f} (S892 {prev['wr']})"
          f"  → {'OK' if repro_ok else 'MISMATCH!'}", flush=True)
    assert repro_ok, "trade reproduction mismatch — loud fail per policy"

    # ---------- نالِ ①: غیرشرطیِ هندسه-همتا ----------
    print(f"\n[null-1] unconditional geometry-matched ({direction}, "
          f"SL={sl_pip:.2f} TP={tp_pip:.2f} hold={hold}):", flush=True)
    uncond_wr, unc_rows = uncond_geo_baseline(df, direction, sl_pip, tp_pip, hold, N)
    print(f"  => hardest unconditional = {uncond_wr:.2f}%  "
          f"(layer {wr_all:.2f} ⇒ geo-lift {wr_all-uncond_wr:+.2f}pp)", flush=True)

    # ---------- تصمیمِ perm طبق قانونِ پیش‌ثبتی ----------
    g892 = (prev.get('rqs2') or {}).get('gates') or {}
    indep_green = all(g892.get(k, False) for k in NULL_INDEP)
    do_perm = indep_green or tf == ANCHOR_TF
    perm = None
    if do_perm:
        why = 'anchor card' if tf == ANCHOR_TF and not indep_green else 'gates green'
        print(f"\n[null-2] timing permutation K={PERM_K} seed={PERM_SEED} ({why}):",
              flush=True)
        perm = perm_geo_baseline(df, direction, sl_pip, tp_pip, hold, n_sig, N)
        print(f"  mean={perm['mean']:.2f} sd={perm['sd']:.2f} max={perm['max']:.2f}"
              f" k={perm['k']}", flush=True)
    else:
        print(f"\n[null-2] skipped per prereg rule (null-independent gate fails: "
              f"{[k for k in NULL_INDEP if not g892.get(k, False)]})", flush=True)

    side = dict(uncond_wr=uncond_wr,
                perm_mean=perm['mean'] if perm else None,
                perm_sd=perm['sd'] if perm else None,
                perm_max=perm['max'] if perm else None,
                perm_k=perm['k'] if perm else None)
    null = {'long': dict(side), 'short': dict(side)}

    # ---------- داوریِ یک‌باره ----------
    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_pip, tp_pip=tp_pip,
                          bar_time=times, null=null,
                          n_trials=N_TRIALS, split_bar=split, close=c)
    ref = max(v for v in (uncond_wr, side['perm_mean']) if v is not None)
    print(f"\nVERDICT: {r.get('verdict')}  score={r.get('rqs2_score')}")
    print(f"geo-matched lift = {wr_all - ref:+.2f}pp  (S892 prereg-null lift was "
          f"{float(prev['wr']) - float(prev['null']['long']['uncond_wr']):+.2f}pp)")
    print(f"gates: {r.get('gates')}", flush=True)

    _save(tf, dict(card=f'XAUUSD-{tf}', prereg=PREREG, s892_prereg='b0f8770a',
                   src=src, bars=N, split=split, hold=hold,
                   sl_pip=sl_pip, tp_pip=tp_pip, locked=lk,
                   n=n_all, wr=round(wr_all, 2), n_sig=n_sig,
                   uncond_draws=unc_rows, uncond_wr=round(uncond_wr, 4),
                   perm=perm, null=null,
                   lift_geo_pp=round(wr_all - ref, 2),
                   lift_s892_pp=round(float(prev['wr'])
                                      - float(prev['null']['long']['uncond_wr']), 2),
                   s892_gates=g892, rqs2=r))


def _save(tf, res):
    os.makedirs(OUT, exist_ok=True)
    with open(f'{OUT}/rqs2_XAUUSD-{tf}.json', 'w') as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print(f"saved → {OUT}/rqs2_XAUUSD-{tf}.json", flush=True)


if __name__ == '__main__':
    run_tf(sys.argv[1] if len(sys.argv) > 1 else 'H2')
