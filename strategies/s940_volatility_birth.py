# -*- coding: utf-8 -*-
"""
S940 — «تولدِ نوسان» (Volatility Birth) · XAUUSD only · RQS2 v2.6 · مسیر C
============================================================================

فرضیه (پیش‌ثبت: results/S940_PREREG_VOLATILITY_BIRTH.md · commit 8af5124c):
NATR وقتی از دهکِ پایینِ توزیعِ تاریخیِ *خودش* رو به بالا می‌شکند، بازار از
فشردگی واردِ انبساط می‌شود — «تولدِ نوسان = تولدِ روند». منبع: یادداشتِ
خلاقانهٔ هرگزآزموده‌نشدهٔ docs/indicators/volatility.md + قرینهٔ یافتهٔ S434
(نوسانِ بالا هنگام ورود = پیش‌بینِ منفی).

پروتکل C (رویهٔ اثبات‌شدهٔ S346):
  --phase discover --tf M1 : جاروبِ گریدِ منجمد فقط روی ۶۰٪ اول. چک‌پوینتِ
                             هر ترکیب (قانونِ ذره‌ذره). قفلِ برنده در JSON.
  --phase final --tf M1    : پس از commitِ قفل — سیگنال‌ها فقط در ۴۰٪ آخر،
                             یک آزمونِ RQS2 با n_trials=1، H7 با تقسیمِ
                             تودرتوی ۶۰/۴۰ درونِ holdout. رد شد = مرده.

گریدِ منجمد (هیچ عددی بیرونِ پیش‌ثبت آزموده نمی‌شود):
  NATR p∈{13,21,34,55} × پنجرهٔ چارک W∈{377,610,987} × آستانه thr∈{0.10,0.20}
  × جهت{mom13,mom21,mom34,long,short} × k_sl∈{1.3,1.7,2.1} × RR∈{1.0,1.5,2.0}
  × hold∈{48,96}   ⇒  N_eff اسمی = 3888 (اعلام‌شده در پیش‌ثبت)

نول: شبیه‌سازیِ سدِ واقعی (همان هندسه) روی *همهٔ* کندل‌های معتبرِ ناحیهٔ آزمون
(numba) → uncond_wr؛ سپس K=1000 زیرنمونهٔ هم‌اندازه با seed=940 → perm_*.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd
from numba import njit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import scalp_engine as se          # noqa: E402
from engine import rqs2                        # noqa: E402
from tools import s434_fast_data as fd         # noqa: E402

ASSET = 'XAUUSD'
OUT = os.path.join(ROOT, 'results', '_scan_S940')

# ---- گریدِ منجمدِ پیش‌ثبت‌شده ----
GRID_P    = (13, 21, 34, 55)          # دورهٔ NATR (فیبوناچی)
GRID_W    = (377, 610, 987)           # پنجرهٔ چارکِ تاریخی (فیبوناچی)
GRID_THR  = (0.10, 0.20)              # دهک/پنجکِ پایین
GRID_DIR  = ('mom13', 'mom21', 'mom34', 'long', 'short')
GRID_KSL  = (1.3, 1.7, 2.1)           # غیرِ رُند (ضدِ اشتباهِ ۷)
GRID_RR   = (1.0, 1.5, 2.0)           # هرگز TP < SL (ضدِ اشتباهِ ۸)
GRID_HOLD = (48, 96)
# اسمی طبق پیش‌ثبت: 4*3*2*9*3*3*2 = 3888 (سه mode بدونِ m را ۹ شمردیم — محافظه‌کارانه)
N_EFF_DECLARED = 3888

ATR_GEOM_P = 100                      # ATR هندسهٔ SL (همان سنتِ S382)
SPLIT_FRAC = 0.60
MIN_TRADES_DISC = 150                 # کفِ فنیِ کشف (آزادیِ درون‌نمونه، در قفل اعلام می‌شود)
K_PERM = 1000
SEED = 940
SL_FLOOR_PIP = 5.0                    # کفِ فنی: SL هرگز صفر/NaN


# ---------------------------------------------------------------- ویژگی‌ها
def true_range(d):
    h, l, c = d['high'], d['low'], d['close']
    prev_c = np.concatenate(([c[0]], c[:-1]))
    return np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))


def natr_pct(d, p):
    """NATR = 100 · RMA(TR,p) / close  (تعریفِ volatility.md، RMA وایلدر)."""
    tr = true_range(d)
    rma = pd.Series(tr).ewm(alpha=1.0 / p, adjust=False).mean().values
    return 100.0 * rma / d['close']


def atr_geom_pip(d):
    """ATR(100) سادهٔ pip برای هندسهٔ SL."""
    tr = true_range(d)
    atr = pd.Series(tr).rolling(ATR_GEOM_P).mean().values
    return atr / se.ASSETS[ASSET]['pip']


def birth_events(natr, W, thr):
    """رویدادِ تولد: NATR دیروز ≤ چارکِ thr پنجرهٔ W، امروز > همان چارک."""
    s = pd.Series(natr)
    q = s.rolling(W, min_periods=W).quantile(thr).values
    below_prev = np.roll(natr <= q, 1)
    below_prev[0] = False
    ev = below_prev & (natr > q) & np.isfinite(q)
    return np.nan_to_num(ev, nan=False).astype(bool)


def directed_signals(d, ev, mode):
    """جهت‌دهی طبقِ گرید: مومنتومِ همزمان یا جهتِ خام."""
    if mode == 'long':
        return ev.copy(), np.zeros_like(ev)
    if mode == 'short':
        return np.zeros_like(ev), ev.copy()
    m = int(mode[3:])                          # mom13/mom21/mom34
    c = d['close']
    mom = c - np.concatenate((np.full(m, np.nan), c[:-m]))
    ls = ev & (mom > 0)
    ss = ev & (mom < 0)
    return (np.nan_to_num(ls, nan=False).astype(bool),
            np.nan_to_num(ss, nan=False).astype(bool))


# ---------------------------------------------------------- نولِ سدِ واقعی
@njit(cache=True)
def _barrier_all_bars(o, h, l, sl_d, tp_d, hold, slip_d, spread_pip, pip,
                      long_side):
    """نتیجهٔ win/loss هندسهٔ واقعی برای ورود در *هر* کندل (نولِ بی‌قید).
    آینه‌ی دقیقِ simulate_trades: ورود openِ کندلِ بعد + اسلیپیج، ابهام → SL،
    برچسبِ win بر اساسِ pnl خالص (نه سطحِ خورده)."""
    n = len(o)
    out = np.full(n, -1, dtype=np.int8)        # -1 نامعتبر، 0 باخت، 1 برد
    for si in range(n - 1):
        if not np.isfinite(sl_d[si]) or sl_d[si] <= 0.0:
            continue
        eb = si + 1
        if long_side:
            fill = o[eb] + slip_d
            slp = fill - sl_d[si]
            tpp = fill + tp_d[si]
        else:
            fill = o[eb] - slip_d
            slp = fill + sl_d[si]
            tpp = fill - tp_d[si]
        end = eb + hold
        if end > n:
            end = n
        exit_price = np.nan
        for j in range(eb, end):
            if long_side:
                hit_sl = l[j] <= slp
                hit_tp = h[j] >= tpp
            else:
                hit_sl = h[j] >= slp
                hit_tp = l[j] <= tpp
            if hit_sl:                          # ابهام → بدترین (مثلِ موتور)
                exit_price = slp
                break
            if hit_tp:
                exit_price = tpp
                break
        if np.isnan(exit_price):
            exit_price = -1e18                  # علامتِ timeout
        if exit_price == -1e18:
            # بسته‌شدن با close آخرِ پنجره — تقریبِ closeِ کندلِ end-1 با o بعدی
            # برای سادگی از h/l میانگین نمی‌گیریم؛ close در آرایهٔ جدا لازم است.
            out[si] = -2                        # جای‌گذاری؛ در پایتون تکمیل می‌شود
            continue
        if long_side:
            pnl = (exit_price - slip_d) - fill
        else:
            pnl = fill - (exit_price + slip_d)
        pnl_pip = pnl / pip - spread_pip
        out[si] = 1 if pnl_pip > 0.0 else 0
    return out


@njit(cache=True)
def _fill_timeouts(out, o, c, sl_d, hold, slip_d, spread_pip, pip, long_side):
    n = len(o)
    for si in range(n - 1):
        if out[si] != -2:
            continue
        eb = si + 1
        end = eb + hold
        if end > n:
            end = n
        xb = end - 1
        if long_side:
            fill = o[eb] + slip_d
            pnl = (c[xb] - slip_d) - fill
        else:
            fill = o[eb] - slip_d
            pnl = fill - (c[xb] + slip_d)
        pnl_pip = pnl / pip - spread_pip
        out[si] = 1 if pnl_pip > 0.0 else 0
    return out


def barrier_outcomes(d, sl_pip_arr, rr, hold):
    cfg = se.ASSETS[ASSET]
    pip, spread, slip = cfg['pip'], cfg['spread_pip'], cfg['slip_pip']
    sl_d = sl_pip_arr * pip
    tp_d = rr * sl_d
    o, h, l, c = d['open'], d['high'], d['low'], d['close']
    res = {}
    for side, is_long in (('long', True), ('short', False)):
        out = _barrier_all_bars(o, h, l, sl_d, tp_d, hold, slip * pip,
                                spread, pip, is_long)
        out = _fill_timeouts(out, o, c, sl_d, hold, slip * pip, spread, pip,
                             is_long)
        res[side] = out
    return res


def build_null(d, ls, ss, sl_pip_arr, rr, hold, lo, hi, K=K_PERM, seed=SEED):
    """نولِ اندازه‌گیری‌شده روی ناحیهٔ [lo,hi): uncond + K زیرنمونهٔ هم‌اندازه."""
    outs = barrier_outcomes(d, sl_pip_arr, rr, hold)
    rng = np.random.default_rng(seed)
    null = {}
    for side, sig in (('long', ls), ('short', ss)):
        n_side = int(sig[lo:hi].sum())
        valid = np.where(outs[side][lo:hi] >= 0)[0]
        if n_side < 5 or len(valid) < 100:
            null[side] = dict(uncond_wr=float('nan'), perm_mean=float('nan'),
                              perm_sd=float('nan'), perm_max=float('nan'),
                              perm_k=0)
            continue
        pool = outs[side][lo:hi][valid].astype(np.float64)
        uncond = float(pool.mean() * 100.0)
        m = min(n_side, len(valid))
        wrs = np.empty(K)
        for t in range(K):
            pick = rng.choice(len(pool), size=m, replace=False)
            wrs[t] = pool[pick].mean() * 100.0
        null[side] = dict(uncond_wr=uncond, perm_mean=float(wrs.mean()),
                          perm_sd=float(wrs.std(ddof=1)),
                          perm_max=float(wrs.max()), perm_k=int(K))
    return null


# ------------------------------------------------------------------ فازها
def run_combo(df, d, atr_g, ls, ss, k_sl, rr, hold):
    sl = np.nan_to_num(np.clip(k_sl * atr_g, SL_FLOOR_PIP, None),
                       nan=SL_FLOOR_PIP)
    tp = rr * sl
    tr = se.simulate_trades(df, ls, ss, sl, tp, ASSET,
                            max_hold=hold, allow_overlap=False)
    if tr is None or len(tr) == 0:
        return None
    n = len(tr)
    wr = float((tr['pnl_pip'] > 0).mean() * 100.0)
    net = float(tr['pnl_pip'].sum())
    sl_med = float(np.median(tr['sl_pip'].values))
    tp_med = rr * sl_med
    cost = se.ASSETS[ASSET]['spread_pip']
    be = 100.0 * (sl_med + cost) / (sl_med + tp_med)
    lift = wr - be
    zscore = lift * np.sqrt(n)                 # نمایندهٔ بودجهٔ lift·√n
    return dict(n=n, wr=round(wr, 3), net=round(net, 1),
                sl_med=round(sl_med, 1), be=round(be, 3),
                lift=round(lift, 3), score=round(zscore, 2))


def phase_discover(tf):
    os.makedirs(OUT, exist_ok=True)
    ckpt_fp = os.path.join(OUT, f'discover_{tf}.json')
    done = {}
    if os.path.exists(ckpt_fp):
        with open(ckpt_fp) as f:
            done = json.load(f).get('combos', {})
        print(f'[resume] {len(done)} combos already checkpointed', flush=True)

    d = fd.load_fast(ASSET, tf)
    print(f"DATA src={d['src']}  n_bars={d['n_bars']:,}  "
          f"span={d['span_years']}y", flush=True)
    n_all = int(d['n_bars'])
    split = int(n_all * SPLIT_FRAC)

    # فقط ۶۰٪ اول — نیمهٔ دوم در فازِ کشف وجود ندارد
    d1 = {k: (v[:split] if isinstance(v, np.ndarray) else v)
          for k, v in d.items()}
    df1 = fd.as_dataframe(d1)
    atr_g = atr_geom_pip(d1)
    print(f'discovery bars={split:,} (first {SPLIT_FRAC:.0%})', flush=True)

    t0 = time.time()
    results = dict(done)
    i = 0
    n_total = (len(GRID_P) * len(GRID_W) * len(GRID_THR) * len(GRID_DIR)
               * len(GRID_KSL) * len(GRID_RR) * len(GRID_HOLD))
    save_every = 10 if tf in ('M1', 'M3', 'M4', 'M5') else 1
    dirty = 0
    for p in GRID_P:
        natr = natr_pct(d1, p)
        for W in GRID_W:
            for thr in GRID_THR:
                ev = birth_events(natr, W, thr)
                for mode in GRID_DIR:
                    ls, ss = directed_signals(d1, ev, mode)
                    n_sig = int(ls.sum() + ss.sum())
                    for k_sl in GRID_KSL:
                        for rr in GRID_RR:
                            for hold in GRID_HOLD:
                                i += 1
                                key = (f'p{p}_W{W}_t{thr}_{mode}'
                                       f'_k{k_sl}_rr{rr}_h{hold}')
                                if key in results:
                                    continue
                                if n_sig < 10:
                                    results[key] = dict(n=0)
                                else:
                                    r = run_combo(df1, d1, atr_g, ls, ss,
                                                  k_sl, rr, hold)
                                    results[key] = r if r else dict(n=0)
                                dirty += 1
                                if dirty >= save_every:
                                    with open(ckpt_fp, 'w') as f:
                                        json.dump(dict(tf=tf, split=split,
                                                       n_bars=n_all,
                                                       src=d['src'],
                                                       combos=results),
                                                  f, indent=1)
                                    dirty = 0
                                rr_ = results[key]
                                print(f'[{i:4d}/{n_total}] {key:<42} '
                                      f'n={rr_.get("n", 0):>6} '
                                      f'wr={rr_.get("wr", "-")} '
                                      f'lift={rr_.get("lift", "-")} '
                                      f'score={rr_.get("score", "-")} '
                                      f'({time.time() - t0:.0f}s)', flush=True)
    with open(ckpt_fp, 'w') as f:
        json.dump(dict(tf=tf, split=split, n_bars=n_all, src=d['src'],
                       combos=results), f, indent=1)

    # ---- انتخاب: بیشینهٔ lift·√n (هم‌راستا با بودجهٔ H3) با کفِ معامله ----
    best_key, best_score = None, -1e18
    for key, r in results.items():
        if r.get('n', 0) < MIN_TRADES_DISC:
            continue
        if r.get('net', -1) <= 0:              # لبهٔ اقتصادی الزامی
            continue
        if r['score'] > best_score:
            best_key, best_score = key, r['score']
    locked = dict(layer='S940', tf=tf, split_bar=split, n_bars=n_all,
                  src=d['src'], n_eff_declared=N_EFF_DECLARED,
                  criterion='max lift*sqrt(n) s.t. n>=150 & net>0',
                  min_trades=MIN_TRADES_DISC, best_key=best_key,
                  best=results.get(best_key) if best_key else None,
                  score=round(best_score, 3) if best_key else None)
    lock_fp = os.path.join(OUT, f'lock_XAUUSD-{tf}.json')
    with open(lock_fp, 'w') as f:
        json.dump(locked, f, indent=2)
    print(f'\nLOCKED -> {lock_fp}')
    print(json.dumps(locked, indent=2))
    print('\nNEXT: commit the lock, THEN --phase final '
          '(touches the 40% holdout exactly once).', flush=True)


def parse_key(key):
    toks = key.split('_')
    return dict(p=int(toks[0][1:]), W=int(toks[1][1:]), thr=float(toks[2][1:]),
                mode=toks[3], k_sl=float(toks[4][1:]),
                rr=float(toks[5][2:]), hold=int(toks[6][1:]))


def phase_final(tf):
    lock_fp = os.path.join(OUT, f'lock_XAUUSD-{tf}.json')
    with open(lock_fp) as f:
        locked = json.load(f)
    if not locked.get('best_key'):
        print(f'NO LOCKED CONFIG for {tf} (discovery floor unmet) — '
              'nothing to test; TF verdict = NO-CANDIDATE.', flush=True)
        return
    p = parse_key(locked['best_key'])
    d = fd.load_fast(ASSET, tf)
    assert d['src'] == locked['src'], 'data source changed since lock!'
    assert int(d['n_bars']) == int(locked['n_bars']), 'n_bars changed!'
    split = int(locked['split_bar'])
    n_all = int(d['n_bars'])
    print(f"FINAL ONE-SHOT S940 {tf} · locked={locked['best_key']} · "
          f'holdout=[{split:,},{n_all:,}) · n_trials=1', flush=True)

    df = fd.as_dataframe(d)
    atr_g = atr_geom_pip(d)                    # علّی — محاسبه روی کلِ سری
    natr = natr_pct(d, p['p'])
    ev = birth_events(natr, p['W'], p['thr'])
    ls, ss = directed_signals(d, ev, p['mode'])
    # سیگنال فقط در ناحیهٔ holdout (ماسکِ سختِ ضدِ نشت)
    ls[:split] = False
    ss[:split] = False

    sl = np.nan_to_num(np.clip(p['k_sl'] * atr_g, SL_FLOOR_PIP, None),
                       nan=SL_FLOOR_PIP)
    tp = p['rr'] * sl
    tr = se.simulate_trades(df, ls, ss, sl, tp, ASSET,
                            max_hold=p['hold'], allow_overlap=False)
    print(f'holdout trades = {len(tr)}', flush=True)
    if len(tr) == 0:
        print('ZERO trades on holdout — dead layer for this TF.', flush=True)
        return

    # نول روی همان ناحیهٔ holdout با همان هندسه (K=1000, seed=940)
    null = build_null(d, ls, ss, sl, p['rr'], p['hold'], split, n_all)
    null_fp = os.path.join(OUT, f'null_XAUUSD-{tf}.json')
    with open(null_fp, 'w') as f:
        json.dump(null, f, indent=2)

    # H7: تقسیمِ تودرتوی ۶۰/۴۰ درونِ holdout (سخت‌گیرانه‌تر — رویهٔ S346)
    nested_split = split + int(0.60 * (n_all - split))
    sl_med = float(np.median(tr['sl_pip'].values))
    tp_med = p['rr'] * sl_med
    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=df['time'].values, null=null,
                          n_trials=1, split_bar=nested_split,
                          close=df['close'].values)
    out = dict(layer='S940', tf=tf, locked_key=locked['best_key'],
               src=d['src'], n_bars=n_all, span_years=d['span_years'],
               holdout_from=split, nested_split=nested_split,
               n_trades=int(len(tr)), sl_med=round(sl_med, 1),
               tp_med=round(tp_med, 1), n_trials=1,
               verdict=r['verdict'], score=r.get('rqs2_score'),
               gates=r.get('gates'), metrics=r.get('metrics'),
               notes=r.get('notes'))
    fp = os.path.join(OUT, f'final_XAUUSD-{tf}.json')
    with open(fp, 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nVERDICT={r['verdict']}  score={r.get('rqs2_score')}")
    print(f"skill_p_perm={r.get('metrics', {}).get('skill_p_perm')}")
    print(f'SAVED -> {fp}', flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', choices=['discover', 'final'], required=True)
    ap.add_argument('--tf', required=True)
    a = ap.parse_args()
    if a.phase == 'discover':
        phase_discover(a.tf)
    else:
        phase_final(a.tf)
