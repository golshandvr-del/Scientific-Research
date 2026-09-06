#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S764 — «کاراییِ مسیرِ رتبه‌بندی‌شدهٔ علّی در شوک» (Causal-Ranked Path Efficiency Shock) · XAUUSD

پیش‌ثبت: results/S764_PREREG_RANKED_PATH_EFFICIENCY.md (commit see git — پیش از هر آزمون)
مسیرِ چندگانگی: C (hold-out) · SPLIT_FRAC=0.60 · SEED=20260905 · K_PERM=2000

E[t] = |close−open| / Σ_j|c_j−c_{j−1}| روی زیرکندل‌های ریزِ کندلِ درشتِ t ∈ (0,1].
شوک: range ≥ 1.618×ATR21[t−1]. LONG: شوک ∧ close>open ∧ E≥E* (+درفت اختیاری)؛ SHORT آینه. follow.
Q[t] = رتبهٔ علّیِ E بین ۱۰۰ شوکِ قبلی ∈[0,1] (مقیاس‌ناوردا). q*=0 = کنترل. سیگنال روی t ⇒ ورود openِ t+1.

اجرا:
  python3 strategies/s764_ranked_efficiency.py search H8
  python3 strategies/s764_ranked_efficiency.py holdout H8   # فقط پس از انجمادِ کامیت‌شده
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

SEED = 20260905
K_PERM = 2000
SPLIT_FRAC = 0.60
ASSET = 'XAUUSD'
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_scan_S764')

# ---- خانوادهٔ منجمدِ پیش‌ثبت: 5 TF × 3 q* (0=کنترل) × 2 gate = 30 (+30 بدهیِ S763 = 60 سخت‌گیرانه) ----
TFS = ['H4', 'H6', 'H8', 'H12', 'D1']
ESTARS = [0.0, 0.5, 0.75]   # q* (رتبهٔ علّی)
RANK_W = 100
GATES = ['none', 'drift']
N_FAMILY = len(TFS) * len(ESTARS) * len(GATES)   # = 30
N_STRICT = 60   # با بدهیِ S763

ATR_P = 21
K_RANGE = 1.618    # شوک: range ≥ 1.618×ATR21[t−1]
K_SL = 1.272       # SL = 1.272×ATR21[t−1]
RR = 1.618         # TP = 1.618×SL  (TP≥SL ✅)
MAX_HOLD = 16
S965_RANGE, S965_RHO = 2.618, 0.618   # فقط برای گزارشِ Jaccard (P3)

SUB_SRC = {'H4': 'M5', 'H6': 'M5', 'H8': 'M5', 'H12': 'M5', 'D1': 'H1'}
EXP_SUB = {'H4': 48, 'H6': 72, 'H8': 96, 'H12': 144, 'D1': 24}
DRIFT_K = {'H4': 360, 'H6': 240, 'H8': 180, 'H12': 120, 'D1': 60}   # ≈ ۶۰ روز


def atr_pip(df: pd.DataFrame, asset: str, p: int = ATR_P) -> np.ndarray:
    pip = se.ASSETS[asset]['pip']
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.r_[np.nan, c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    atr = pd.Series(tr).ewm(alpha=1.0 / p, adjust=False).mean().values
    return atr / pip


def path_per_bar(coarse_t, sub_t, sub_c):
    """Σ|Δc| زیرکندلی و شمارِ زیرکندل برای هر کندلِ درشت (اولین زیرکندلِ هر گروه Δ ندارد)."""
    n = len(coarse_t)
    idx = np.searchsorted(coarse_t, sub_t, side='right') - 1
    ok = idx >= 0
    idx, c = idx[ok], sub_c[ok]
    dc = np.abs(np.diff(c))
    same = idx[1:] == idx[:-1]
    path = np.zeros(n)
    np.add.at(path, idx[1:][same], dc[same])
    cnt = np.bincount(idx, minlength=n).astype(float)
    return path, cnt


def load_card(tf: str):
    d = fd.load_fast(ASSET, tf)
    df = pd.DataFrame({'open': d['open'], 'high': d['high'],
                       'low': d['low'], 'close': d['close']})
    t = d['time'].astype(np.int64)
    sub = fd.load_fast(ASSET, SUB_SRC[tf])
    path, cnt = path_per_bar(t, sub['time'].astype(np.int64),
                             sub['close'].astype(np.float64))
    return df, t, path, cnt, d['src'], sub['src']


def prepare(tf: str):
    df, t, path, cnt, src, sub_src = load_card(tf)
    atr = atr_pip(df, ASSET)
    atr_prev = np.r_[np.nan, atr[:-1]]
    pip = se.ASSETS[ASSET]['pip']
    c, o = df['close'].values, df['open'].values
    rng_pip = (df['high'].values - df['low'].values) / pip
    sl_arr = np.round(K_SL * np.nan_to_num(atr_prev, nan=np.nan), 3)
    tp_arr = np.round(RR * sl_arr, 3)
    n = len(df)
    valid_mask = (~np.isnan(atr_prev)) & (np.arange(n) >= ATR_P + 1) & \
                 (cnt >= EXP_SUB[tf] * 0.5) & (path > 0)
    # (پس از محاسبهٔ Q، warm-up به valid اضافه می‌شود — پایین)
    quality = rng_pip >= K_RANGE * np.nan_to_num(atr_prev, nan=np.inf)   # شوک
    with np.errstate(divide='ignore', invalid='ignore'):
        eff = np.where(path > 0, np.abs(c - o) / path, 0.0)
        rho = np.where(rng_pip > 0, np.abs(c - o) / pip / rng_pip, 0.0)
    s965 = (rng_pip >= S965_RANGE * np.nan_to_num(atr_prev, nan=np.inf)) & (rho >= S965_RHO)
    # رتبهٔ علّی: Q[t] = سهمِ RANK_W شوکِ قبلی (بدونِ t) با E < E[t]؛ فقط برای شوک‌ها تعریف می‌شود
    q = np.full(n, np.nan)
    sh_idx = np.where(quality & (cnt >= EXP_SUB[tf] * 0.5) & (path > 0))[0]
    e_sh = eff[sh_idx]
    for j in range(RANK_W, len(sh_idx)):
        prev = e_sh[j - RANK_W:j]
        q[sh_idx[j]] = float((prev < e_sh[j]).mean())
    has_q = ~np.isnan(q)
    k = DRIFT_K[tf]
    c_lag = np.r_[np.full(k, np.nan), c[:-k]]
    drift_up = c > c_lag
    drift_dn = c < c_lag
    # warm-up منصفانه برای کنترل و بازوها: فقط از اولین کندلِ دارای Q
    if has_q.any():
        valid_mask &= np.arange(n) >= int(np.argmax(has_q))
    feats = dict(eff=eff, q=np.nan_to_num(q, nan=-1.0), quality=quality, s965=s965,
                 bull=c > o, bear=c < o,
                 drift_up=np.nan_to_num(drift_up).astype(bool),
                 drift_dn=np.nan_to_num(drift_dn).astype(bool))
    return df, t, feats, sl_arr, tp_arr, valid_mask, src, sub_src


def signals(feats, e_star, gate, n):
    ok = feats['quality'] & (feats['q'] >= e_star) if e_star > 0 else feats['quality']
    up = ok & feats['bull']
    dn = ok & feats['bear']
    if gate == 'drift':
        up &= feats['drift_up']
        dn &= feats['drift_dn']
    return up, dn


def _slice(feats, split):
    return {k: v[:split] for k, v in feats.items()}


def scan_search(tf: str):
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()
    df, t, feats, sl_arr, tp_arr, valid_mask, src, sub_src = prepare(tf)
    n_all = len(df)
    split = int(SPLIT_FRAC * n_all)
    dfs = df.iloc[:split].reset_index(drop=True)
    sl_s, tp_s = sl_arr[:split], tp_arr[:split]
    vm_s = valid_mask[:split]
    fs = _slice(feats, split)
    rng = np.random.default_rng(SEED)

    valid_idx = np.where(vm_s)[0]
    base = {}
    for side in ('long', 'short'):
        samp = valid_idx if len(valid_idx) <= 20000 else np.sort(
            rng.choice(valid_idx, size=20000, replace=False))
        sig = np.zeros(split, bool)
        sig[samp] = True
        tr = se.simulate_trades(
            dfs, sig if side == 'long' else np.zeros(split, bool),
            sig if side == 'short' else np.zeros(split, bool),
            sl_pip=sl_s, tp_pip=tp_s, asset=ASSET,
            max_hold=MAX_HOLD, allow_overlap=False)
        base[side] = (float((tr['pnl_pip'] > 0).mean() * 100)
                      if tr is not None and len(tr) and 'pnl_pip' in tr else None)

    rows, best = [], {'long': None, 'short': None}
    ctrl = {}   # lift بازویِ کنترل (E*=0) به‌تفکیکِ gate/side — برای P1
    jacc = {}
    for e_star in ESTARS:
        for gate in GATES:
            ls, ss = signals(fs, e_star, gate, split)
            ls &= vm_s
            ss &= vm_s
            ev = ls | ss
            s9 = fs['s965'] & vm_s
            inter, uni = int((ev & s9).sum()), int((ev | s9).sum())
            jacc[f"{e_star}|{gate}"] = round(inter / uni, 3) if uni else None
            tr = se.simulate_trades(dfs, ls, ss, sl_pip=sl_s, tp_pip=tp_s,
                                    asset=ASSET, max_hold=MAX_HOLD,
                                    allow_overlap=False)
            if tr is None or not len(tr) or 'pnl_pip' not in tr:
                continue
            for side in ('long', 'short'):
                sub = tr[tr['direction'] == side]
                n = len(sub)
                if n < 30 or base[side] is None:
                    continue
                wr = float((sub['pnl_pip'] > 0).mean() * 100)
                expp = float(sub['pnl_pip'].mean())
                lift = wr - base[side]
                score = lift * np.sqrt(n)
                row = dict(e_star=e_star, gate=gate, side=side, n=int(n),
                           wr=round(wr, 2), exp_pip=round(expp, 3),
                           lift=round(float(lift), 2), score=round(float(score), 2))
                if e_star == 0.0:
                    ctrl[f"{gate}|{side}"] = row['lift']
                else:
                    row['ctrl_lift'] = ctrl.get(f"{gate}|{side}")
                    row['p1_beats_ctrl'] = bool(row['ctrl_lift'] is not None
                                                and lift > row['ctrl_lift'])
                rows.append(row)
                # کنترل نامزدِ انجماد نمی‌شود؛ P1 باید برقرار باشد
                if e_star > 0 and expp > 0 and lift > 0 and row.get('p1_beats_ctrl') and (
                        best[side] is None or score > best[side]['score']):
                    best[side] = row

    out = dict(tf=tf, src=str(src), sub_src=str(sub_src), n_bars=n_all, split=split,
               base_wr=base, n_family=N_FAMILY, rows=rows, best=best,
               jaccard_vs_s965=jacc,
               barrier='lift*sqrt(n)>=78 & exp>0 & n>=30 & q*>0 & P1(beats control)',
               best_pass={s: bool(best[s] is not None and best[s]['score'] >= 78)
                          for s in ('long', 'short')},
               elapsed_s=round(time.time() - t0, 1))
    with open(os.path.join(OUT_DIR, f"{tf}_search.json"), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"[S764 search {tf}] src={os.path.basename(str(src))} bars={n_all} "
          f"split={split} best={best} pass={out['best_pass']} ({out['elapsed_s']}s)")


# ---- فاز ۲: هولدآوت (فقط پس از کامیتِ الحاقیهٔ انجماد پر می‌شود) ----
FROZEN = {
    'H6': dict(side='short', e_star=0.75, gate='drift'),
    'H8': dict(side='short', e_star=0.75, gate='drift'),
}


def build_null_side(dfa, valid, sl_arr, tp_arr, side, n_side, rng, n_perm=K_PERM):
    is_long = (side == 'long')
    d = dict(uncond_wr=None, perm_mean=None, perm_sd=None, perm_max=None, perm_k=None)
    other = dict(d)
    if n_side < 1 or len(valid) < 2:
        return {side: d, ('short' if is_long else 'long'): other}
    samp = valid if len(valid) <= 20000 else np.sort(
        rng.choice(valid, size=20000, replace=False))
    sig = np.zeros(len(dfa), bool)
    sig[samp] = True
    z = np.zeros(len(dfa), bool)
    tr = se.simulate_trades(dfa, sig if is_long else z, sig if not is_long else z,
                            sl_pip=sl_arr, tp_pip=tp_arr, asset=ASSET,
                            max_hold=MAX_HOLD, allow_overlap=False)
    if tr is not None and len(tr) and 'pnl_pip' in tr:
        d['uncond_wr'] = float((tr['pnl_pip'] > 0).mean() * 100)
    if len(valid) > n_side:
        wrs = []
        for _ in range(n_perm):
            pick = np.sort(rng.choice(len(valid), size=n_side, replace=False))
            sig = np.zeros(len(dfa), bool)
            sig[valid[pick]] = True
            trp = se.simulate_trades(dfa, sig if is_long else z, sig if not is_long else z,
                                     sl_pip=sl_arr, tp_pip=tp_arr, asset=ASSET,
                                     max_hold=MAX_HOLD, allow_overlap=False)
            if trp is not None and len(trp) and 'pnl_pip' in trp:
                wrs.append(float((trp['pnl_pip'] > 0).mean() * 100))
        if wrs:
            a = np.asarray(wrs)
            d.update(perm_mean=float(a.mean()), perm_sd=float(a.std(ddof=1)),
                     perm_max=float(a.max()), perm_k=int(len(a)))
    return {side: d, ('short' if is_long else 'long'): other}


def _clean(o):
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(x) for x in o]
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def judge_holdout(tf: str):
    import gc
    cfg = FROZEN.get(tf)
    if not cfg:
        raise SystemExit(f"{tf} در FROZEN نیست — انجماد نشده یا NO_CANDIDATE.")
    guard = os.path.join(OUT_DIR, f"{tf}_JUDGED")
    if os.path.exists(guard):
        raise SystemExit(f"{tf} قبلاً داوری شده — آزمونِ دوم ممنوع (مرگِ ابدی).")
    os.makedirs(OUT_DIR, exist_ok=True)
    df, t, feats, sl_arr, tp_arr, valid_mask, src, sub_src = prepare(tf)
    n_all = len(df)
    split = int(SPLIT_FRAC * n_all)
    rng = np.random.default_rng(SEED + 764)

    ls, ss = signals(feats, cfg['e_star'], cfg['gate'], n_all)
    ls &= valid_mask
    ss &= valid_mask
    if cfg['side'] == 'long':
        ss = np.zeros(n_all, bool)
    else:
        ls = np.zeros(n_all, bool)
    trades = se.simulate_trades(df, ls, ss, sl_pip=sl_arr, tp_pip=tp_arr,
                                asset=ASSET, max_hold=MAX_HOLD, allow_overlap=False)
    if trades is None or not len(trades):
        raise SystemExit(f"{tf}: هیچ معامله‌ای — INCOMPLETE.")
    ent = trades['entry_bar'].values
    n_hold = int((ent >= split).sum())
    valid_hold = np.where(valid_mask & (np.arange(n_all) >= split))[0]
    null = build_null_side(df, valid_hold, sl_arr, tp_arr, cfg['side'], n_hold, rng)
    gc.collect()
    sl_med = float(np.median(sl_arr[ent[ent < n_all]]))
    tp_med = sl_med * RR

    res = {}
    for label, ntr in (('N1_pathC', 1), ('N60_strict', N_STRICT)):
        v = rqs2.compute_rqs2(trades, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                              bar_time=t, null=null, n_trials=ntr,
                              split_bar=split, close=df['close'].values)
        res[label] = v
        m = v.get('metrics', {})
        print(f"[{label}] verdict={v.get('verdict')} rqs2={v.get('rqs2_score')} "
              f"| n={m.get('n_trades')} PF={m.get('profit_factor')} "
              f"lift={m.get('side_lift_pp')} p={m.get('p_emp')} "
              f"gates={''.join('Y' if x else 'N' for x in v.get('gates', {}).values())}")

    out = dict(tf=tf, cfg=cfg, src=str(src), sub_src=str(sub_src), n_bars=n_all,
               split=split, n_total_trades=int(len(trades)), n_holdout=n_hold,
               sl_med=sl_med, tp_med=tp_med, null=_clean(null), verdicts=_clean(res))
    with open(os.path.join(OUT_DIR, f"{tf}_holdout.json"), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    with open(guard, 'w') as f:
        f.write(f"judged at {time.strftime('%F %T')}\n")


if __name__ == '__main__':
    phase, tf = sys.argv[1], sys.argv[2]
    if phase == 'search':
        scan_search(tf)
    else:
        judge_holdout(tf)
