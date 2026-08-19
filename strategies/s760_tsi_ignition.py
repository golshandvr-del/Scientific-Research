#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S760 — «اشتعالِ TSI» · XAUUSD · لایهٔ نو (نه احیا)

پیش‌ثبت: results/S760_PREREG_TSI_IGNITION.md (commit 69368b85 — پیش از هر آزمون)
مسیرِ چندگانگی: C (hold-out) · SPLIT_FRAC=0.60 · SEED=20260812 · K_PERM=2000

فاز ۱ (این اسکریپت، حالتِ search):
  جستجوی خانوادهٔ منجمدِ ۹۶-پیکربندی فقط روی ۶۰٪ نخستِ کارت.
  خروجی: results/_scan_S760/<TF>_search.json + بهترین پیکربندی per-side.

فاز ۲ (حالتِ holdout — فقط پس از commitِ الحاقیهٔ انجماد):
  یک آزمونِ یگانه روی ۴۰٪ دوم با rqs2.compute_rqs2 و همهٔ ورودی‌های الزامی.

اجرا:
  python3 strategies/s760_tsi_ignition.py search M1
  python3 strategies/s760_tsi_ignition.py holdout M1   # فقط پس از انجماد
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se           # noqa: E402
from engine import rqs2                          # noqa: E402
from tools import s434_fast_data as fd           # noqa: E402

SEED = 20260812
K_PERM = 2000
SPLIT_FRAC = 0.60
ASSET = 'XAUUSD'
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_scan_S760')

# ---- خانوادهٔ منجمدِ پیش‌ثبت (۹۶ پیکربندی) — خارج از این‌ها هیچ چیز ----
TSI_PERIODS = [(25, 13), (34, 13), (55, 21)]
THETAS = [1.0, 1.272, 1.618, 2.0]
SIDES = ['long', 'short']
GEOMS = [(1.0, 1.0), (1.0, 1.5), (1.5, 1.0), (1.5, 1.5)]   # (k_sl, rr) — TP>=SL همیشه
ATR_P = 100

# max_hold منجمدِ per-TF: ≈۴ ساعتِ بازار روی TFهای دقیقه‌ای؛ ۶۴ کندل روی H1+
MAX_HOLD = {
    'M1': 240, 'M2': 120, 'M3': 80, 'M4': 60, 'M5': 48, 'M6': 40, 'M10': 24,
    'H4': 64,
    'M12': 20, 'M15': 16, 'M20': 12, 'M30': 8,
    'H1': 64, 'H2': 64, 'H3': 64, 'H6': 64, 'H8': 64, 'H12': 64,
    'D1': 64, 'W1': 32, 'MN1': 12,
}


def ema(x: pd.Series, p: int) -> pd.Series:
    return x.ewm(span=p, adjust=False).mean()


def tsi_series(close: pd.Series, long_p: int, short_p: int) -> np.ndarray:
    m = close.diff()
    r = ema(ema(m, long_p), short_p)
    a = ema(ema(m.abs(), long_p), short_p)
    return (100.0 * r / a.replace(0, np.nan)).values


def atr_pip(df: pd.DataFrame, asset: str, p: int = ATR_P) -> np.ndarray:
    pip = se.ASSETS[asset]['pip']
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.r_[np.nan, c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    atr = pd.Series(tr).ewm(alpha=1.0 / p, adjust=False).mean().values
    return atr / pip


def cross_signals(tsi: np.ndarray, thr_hi: float, thr_lo: float):
    """گذرِ رویدادی با shift(1) ضدِ نشتی: سیگنال روی کندلِ t از دادهٔ t-1/t-2."""
    v1 = np.r_[np.nan, tsi[:-1]]     # مقدارِ t-1
    v2 = np.r_[np.nan, v1[:-1]]      # مقدارِ t-2
    long_sig = (v2 <= thr_hi) & (v1 > thr_hi)
    short_sig = (v2 >= thr_lo) & (v1 < thr_lo)
    return np.nan_to_num(long_sig).astype(bool), np.nan_to_num(short_sig).astype(bool)


RESAMPLE_SRC = {'M2': ('M1', 2), 'H4': ('H1', 4)}   # طبقِ راهنما: بازنمونه‌گیری


def load_card(tf: str):
    """کارت را می‌خواند؛ M2/H4 از منبعِ ریزتر بازنمونه‌گیری می‌شوند."""
    if tf not in RESAMPLE_SRC:
        d = fd.load_fast(ASSET, tf)
        return d, fd.as_dataframe(d)
    src_tf, k = RESAMPLE_SRC[tf]
    d = fd.load_fast(ASSET, src_tf)
    sec = 120 if tf == 'M2' else 14400
    t = d['time'].astype(np.int64)
    bucket = (t // sec) * sec
    # کندل‌ها مرتب‌اند ⇒ مرزِ سطل‌ها با np.unique (سبک، بدونِ pandas resample)
    uniq, first_idx = np.unique(bucket, return_index=True)
    nb = len(uniq)
    o = d['open']; h = d['high']; l = d['low']; c = d['close']; v = d['volume']
    O = o[first_idx]
    C = np.empty(nb); H = np.empty(nb); L = np.empty(nb); V = np.empty(nb)
    ends = np.r_[first_idx[1:], len(t)]
    H = np.maximum.reduceat(h, first_idx)
    L = np.minimum.reduceat(l, first_idx)
    V = np.add.reduceat(v.astype(np.float64), first_idx)
    C = c[ends - 1]
    out = pd.DataFrame(dict(time=uniq, open=O, high=H, low=L, close=C, volume=V))
    d2 = {'src': d['src'] + f'  (resampled {src_tf}->{tf})'}
    return d2, out


def scan_search(tf: str):
    import gc
    t_all = time.time()
    d, df = load_card(tf)
    n = len(df)
    split = int(n * SPLIT_FRAC)
    dfs = df.iloc[:split].reset_index(drop=True)
    del df
    for k_ in ('open', 'high', 'low', 'volume', 'close', 'time',
               'hour', 'minute', 'dow'):
        d.pop(k_, None)
    gc.collect()   # M1: آزادسازیِ نیمهٔ hold-out از RAM — دیوارِ ۱GB سندباکس
    mh = MAX_HOLD[tf]
    atr = atr_pip(dfs, ASSET)
    close_s = pd.Series(dfs['close'].values)
    warm = 4 * (55 + 21) + ATR_P    # گرم‌شدنِ کافی برای بلندترین دوره

    print(f"=== S760 SEARCH {ASSET}-{tf} | src={d['src']} | bars={n:,} "
          f"| search={split:,} | mh={mh} ===", flush=True)

    rows = []
    for (lp, sp) in TSI_PERIODS:
        tsi = tsi_series(close_s, lp, sp)
        tv = tsi[warm:split]
        tv = tv[np.isfinite(tv)]
        mu, sd = float(np.mean(tv)), float(np.std(tv))
        for th in THETAS:
            thr_hi = mu + th * sd
            thr_lo = mu - th * sd
            ls, ss = cross_signals(tsi, thr_hi, thr_lo)
            ls[:warm] = False
            ss[:warm] = False
            for (k, rr) in GEOMS:
                sl = k * atr
                tp = rr * sl
                ok = np.isfinite(sl) & (sl > 0)
                for side in SIDES:
                    sig = ls if side == 'long' else ss
                    sig = sig & ok
                    if sig.sum() < 5:
                        rows.append(dict(lp=lp, sp=sp, th=th, k=k, rr=rr,
                                         side=side, n=int(sig.sum()), skip=True))
                        continue
                    tr = se.simulate_trades(
                        dfs,
                        sig if side == 'long' else np.zeros(len(dfs), bool),
                        sig if side == 'short' else np.zeros(len(dfs), bool),
                        sl_pip=sl, tp_pip=tp, asset=ASSET,
                        max_hold=mh, allow_overlap=False)
                    if tr is None or len(tr) == 0:
                        rows.append(dict(lp=lp, sp=sp, th=th, k=k, rr=rr,
                                         side=side, n=0, skip=True))
                        continue
                    ntr = len(tr)
                    wr = float((tr['pnl_pip'] > 0).mean() * 100)
                    exp = float(tr['pnl_pip'].mean())
                    # مبنای بی‌قیدِ سریعِ فاز جستجو (فاز ۲ null کامل می‌سازد)
                    rows.append(dict(lp=lp, sp=sp, th=th, k=k, rr=rr, side=side,
                                     n=ntr, wr=round(wr, 3), exp_pip=round(exp, 3),
                                     thr_hi=round(thr_hi, 3), thr_lo=round(thr_lo, 3)))
            print(f"  tsi({lp},{sp}) th={th} done "
                  f"({time.time()-t_all:.0f}s)", flush=True)

    # مبنای WR بی‌قید برای هر هندسه (روی نمونهٔ تصادفیِ کندل‌های واجد)
    rng = np.random.default_rng(SEED)
    uncond = {}
    valid = np.where(np.isfinite(atr) & (atr > 0))[0]
    valid = valid[valid >= warm]
    samp = np.sort(rng.choice(valid, size=min(20000, len(valid)), replace=False))
    for (k, rr) in GEOMS:
        sl = k * atr
        tp = rr * sl
        for side in SIDES:
            sig = np.zeros(len(dfs), bool)
            sig[samp] = True
            tr = se.simulate_trades(
                dfs,
                sig if side == 'long' else np.zeros(len(dfs), bool),
                sig if side == 'short' else np.zeros(len(dfs), bool),
                sl_pip=sl, tp_pip=tp, asset=ASSET,
                max_hold=mh, allow_overlap=False)
            key = f"{k}x{rr}_{side}"
            if tr is None or len(tr) == 0 or 'pnl_pip' not in tr:
                uncond[key] = dict(wr=None, n=0)
            else:
                uncond[key] = dict(wr=float((tr['pnl_pip'] > 0).mean() * 100),
                                   n=int(len(tr)))

    # رتبه‌بندی به معیارِ پیش‌ثبت: lift×sqrt(n) در برابرِ مبنای بی‌قیدِ هم‌هندسه
    best = {'long': None, 'short': None}
    for r in rows:
        if r.get('skip') or r['n'] < 30:
            continue
        base = uncond[f"{r['k']}x{r['rr']}_{r['side']}"]['wr']
        if base is None:
            continue
        lift = r['wr'] - base
        score = lift * np.sqrt(r['n'])
        r['lift_pp'] = round(lift, 3)
        r['score'] = round(float(score), 2)
        b = best[r['side']]
        if b is None or r['score'] > b['score']:
            best[r['side']] = r

    os.makedirs(OUT_DIR, exist_ok=True)
    out = dict(tf=tf, src=d['src'], n_full=n, n_search=split,
               split_bar=split, seed=SEED, n_configs=len(TSI_PERIODS) * len(THETAS)
               * len(SIDES) * len(GEOMS), max_hold=mh,
               elapsed_s=round(time.time() - t_all, 1),
               uncond=uncond, best=best, rows=rows)
    fp = os.path.join(OUT_DIR, f"{tf}_search.json")
    with open(fp, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"SAVED {fp} | best_long={best['long']} | best_short={best['short']}",
          flush=True)




# ================= فاز ۲: آزمونِ یگانهٔ hold-out (پس از الحاقیهٔ انجماد) =====
# پیکربندی‌های منجمد — عیناً از results/S760_PREREG_ADDENDUM_FREEZE.md
FROZEN = {
    'H8':  dict(side='short', lp=25, sp=13, thr=-21.729, k=1.0, rr=1.0),
    'H12': dict(side='short', lp=34, sp=13, thr=-19.536, k=1.0, rr=1.0),
    'H6':  dict(side='long',  lp=55, sp=21, thr=17.282,  k=1.0, rr=1.0),
    'H4':  dict(side='short', lp=55, sp=21, thr=-15.838, k=1.5, rr=1.5),
    'H3':  dict(side='long',  lp=34, sp=13, thr=22.389,  k=1.5, rr=1.0),
    'H2':  dict(side='long',  lp=55, sp=21, thr=17.939,  k=1.0, rr=1.0),
    'H1':  dict(side='long',  lp=55, sp=21, thr=27.938,  k=1.5, rr=1.0),
}
N_FAMILY_SEARCH = 96   # سدِ سخت‌گیرانه per تعهدِ پیش‌ثبت


def build_null_side_s760(dfa, valid, sl_arr, tp_arr, side, n_side, mh, rng,
                         n_perm=K_PERM):
    """مبنای اندازه‌گیری‌شده به الگوی s351.build_null_side با هندسهٔ منجمد."""
    is_long = (side == 'long')
    d = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
             perm_max=None, perm_k=None)
    if n_side < 1 or len(valid) < 2:
        return {side: d,
                ('short' if is_long else 'long'): dict(
                    uncond_wr=None, perm_mean=None, perm_sd=None,
                    perm_max=None, perm_k=None)}
    # مبنای بی‌قید: نمونهٔ بزرگ از کندل‌های واجد با همان هندسه
    samp = valid if len(valid) <= 20000 else np.sort(
        rng.choice(valid, size=20000, replace=False))
    sig = np.zeros(len(dfa), bool)
    sig[samp] = True
    tr = se.simulate_trades(
        dfa, sig if is_long else np.zeros(len(dfa), bool),
        sig if not is_long else np.zeros(len(dfa), bool),
        sl_pip=sl_arr, tp_pip=tp_arr, asset=ASSET,
        max_hold=mh, allow_overlap=False)
    if tr is not None and len(tr) and 'pnl_pip' in tr:
        d['uncond_wr'] = float((tr['pnl_pip'] > 0).mean() * 100)
    # جای‌گشت: K زیرمجموعهٔ هم‌اندازه (n_side) از کندل‌های واجد
    if len(valid) > n_side:
        wrs = []
        for _ in range(n_perm):
            pick = np.sort(rng.choice(len(valid), size=n_side, replace=False))
            sig = np.zeros(len(dfa), bool)
            sig[valid[pick]] = True
            trp = se.simulate_trades(
                dfa, sig if is_long else np.zeros(len(dfa), bool),
                sig if not is_long else np.zeros(len(dfa), bool),
                sl_pip=sl_arr, tp_pip=tp_arr, asset=ASSET,
                max_hold=mh, allow_overlap=False)
            if trp is not None and len(trp) and 'pnl_pip' in trp:
                wrs.append(float((trp['pnl_pip'] > 0).mean() * 100))
        if wrs:
            a = np.asarray(wrs)
            d.update(perm_mean=float(a.mean()), perm_sd=float(a.std(ddof=1)),
                     perm_max=float(a.max()), perm_k=int(len(a)))
    other = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                 perm_max=None, perm_k=None)
    return {side: d, ('short' if is_long else 'long'): other}


def judge_holdout(tf: str):
    """آزمونِ یگانهٔ hold-out — هر کارت فقط یک بار."""
    import gc
    cfg = FROZEN[tf]
    guard = os.path.join(OUT_DIR, f"{tf}_JUDGED")
    if os.path.exists(guard):
        raise SystemExit(f"{tf} قبلاً داوری شده — آزمونِ دوم ممنوع (مرگِ ابدی).")
    t0 = time.time()
    d, df = load_card(tf)
    n = len(df)
    split = int(n * SPLIT_FRAC)
    mh = MAX_HOLD[tf]
    atr = atr_pip(df, ASSET)
    close_s = pd.Series(df['close'].values)
    warm = 4 * (55 + 21) + ATR_P
    tsi = tsi_series(close_s, cfg['lp'], cfg['sp'])
    v1 = np.r_[np.nan, tsi[:-1]]
    v2 = np.r_[np.nan, v1[:-1]]
    if cfg['side'] == 'long':
        sig = np.nan_to_num((v2 <= cfg['thr']) & (v1 > cfg['thr'])).astype(bool)
    else:
        sig = np.nan_to_num((v2 >= cfg['thr']) & (v1 < cfg['thr'])).astype(bool)
    sig[:warm] = False
    ok = np.isfinite(atr) & (atr > 0)
    sig &= ok
    sl = cfg['k'] * atr
    tp = cfg['rr'] * sl
    is_long = cfg['side'] == 'long'
    trades = se.simulate_trades(
        df, sig if is_long else np.zeros(n, bool),
        sig if not is_long else np.zeros(n, bool),
        sl_pip=sl, tp_pip=tp, asset=ASSET, max_hold=mh, allow_overlap=False)
    print(f"=== S760 HOLDOUT {ASSET}-{tf} {cfg['side'].upper()} | src={d['src']}"
          f" | bars={n:,} split={split:,} | trades(all)={len(trades)}", flush=True)
    # * نمونهٔ hold-out برای null: شمارِ معاملاتِ پس از مرز
    ent = trades['entry_bar'].values
    n_hold = int((ent >= split).sum())
    n_search_tr = int((ent < split).sum())
    print(f"    n_search_trades={n_search_tr} n_holdout_trades={n_hold}", flush=True)
    rng = np.random.default_rng(SEED)
    valid = np.where(ok)[0]
    valid = valid[valid >= warm]
    null = build_null_side_s760(df, valid, sl, tp, cfg['side'],
                                max(n_hold, 1), mh, rng)
    med_sl = float(np.median(sl[sig])) if sig.any() else float(np.nanmedian(sl))
    med_tp = float(np.median(tp[sig])) if sig.any() else float(np.nanmedian(tp))
    results = {}
    for n_trials, tag in ((1, 'N1_pathC'), (N_FAMILY_SEARCH, 'N96_strict')):
        r = rqs2.compute_rqs2(
            trades, ASSET, sl_pip=med_sl, tp_pip=med_tp,
            bar_time=df['time'].values, null=null, n_trials=n_trials,
            split_bar=split, close=df['close'].values)
        results[tag] = dict(verdict=r['verdict'], rqs2=r.get('rqs2_score'),
                            gates={k2: v2g for k2, v2g in r['gates'].items()},
                            skill_p=r['metrics'].get('skill_p_perm'),
                            metrics={k2: r['metrics'].get(k2) for k2 in
                                     ('skill_lift_pp', 'skill_z', 'pf', 'wr',
                                      'n_trades', 'max_dd_pct', 'exp_pip')})
        print(f"  [{tag}] verdict={r['verdict']} rqs2={r.get('rqs2_score')}"
              f" p_perm={r['metrics'].get('skill_p_perm')}", flush=True)
    out = dict(tf=tf, cfg=cfg, src=d['src'], n_full=n, split_bar=split,
               med_sl_pip=med_sl, med_tp_pip=med_tp, mh=mh,
               n_search_trades=n_search_tr, n_holdout_trades=n_hold,
               null=null, results=results, seed=SEED, k_perm=K_PERM,
               elapsed_s=round(time.time() - t0, 1))
    with open(os.path.join(OUT_DIR, f"{tf}_holdout.json"), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    open(guard, 'w').write('judged once — second test forbidden\n')
    print(f"SAVED {tf}_holdout.json", flush=True)


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'search'
    tf = sys.argv[2] if len(sys.argv) > 2 else 'M1'
    if mode == 'search':
        scan_search(tf)
    else:
        judge_holdout(tf)
