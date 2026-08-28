#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S761 — «ترکیبِ علامت‌دارِ واریانسِ درون‌باری» · XAUUSD · لایهٔ نو (نه احیا)

پیش‌ثبت: results/S761_PREREG_SIGNED_SEMIVARIANCE.md (commit d8fd585d — پیش از هر آزمون)
مسیرِ چندگانگی: C (hold-out) · SPLIT_FRAC=0.60 · SEED=20260826 · K_PERM=2000

RSV±[t] = مجموعِ مربعِ زیربازده‌های مثبت/منفیِ داخلِ کندلِ درشتِ t (از M5؛ D1 از H1).
SJ_W[t] = Σ_W(RSV+−RSV−)/Σ_W(RSV++RSV−) ∈ [−1,+1]  (پنجرهٔ غلتان W شاملِ خودِ t)
رویداد = حالت‌گذرِ SJ از ±θ · سیگنال روی t ⇒ ورود openِ t+1 (قراردادِ موتور، forward-safe).

اجرا:
  python3 strategies/s761_signed_semivariance.py search H1
  python3 strategies/s761_signed_semivariance.py holdout H1   # فقط پس از انجمادِ کامیت‌شده
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

SEED = 20260826
K_PERM = 2000
SPLIT_FRAC = 0.60
ASSET = 'XAUUSD'
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_scan_S761')

# ---- خانوادهٔ منجمدِ پیش‌ثبت (۱۲ پیکربندی/TF × ۸ TF = ۹۶) ----
TFS = ['H1', 'H2', 'H3', 'H4', 'H6', 'H8', 'H12', 'D1']
WINDOWS = [8, 21, 55]
THETAS = [0.333, 0.555]
MODES = ['cont', 'rev']
N_FAMILY = len(TFS) * len(WINDOWS) * len(THETAS) * len(MODES)   # = 96

ATR_P = 89
K_SL = 1.618      # SL = 1.618×ATR(89)
RR = 1.5          # TP = 1.5×SL  (TP≥SL ✅)
MAX_HOLD = 34     # کندلِ درشت

SUB_SRC = {'H1': 'M5', 'H2': 'M5', 'H3': 'M5', 'H4': 'M5',
           'H6': 'M5', 'H8': 'M5', 'H12': 'M5', 'D1': 'H1'}


def atr_pip(df: pd.DataFrame, asset: str, p: int = ATR_P) -> np.ndarray:
    """ATR وایلدر بر حسبِ pip — علّی (فقط دادهٔ ≤ t)."""
    pip = se.ASSETS[asset]['pip']
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.r_[np.nan, c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    atr = pd.Series(tr).ewm(alpha=1.0 / p, adjust=False).mean().values
    return atr / pip


def rsv_per_bar(coarse_t: np.ndarray, sub_t: np.ndarray,
                sub_c: np.ndarray) -> tuple:
    """RSV+ و RSV− هر کندلِ درشت از زیربازده‌های لگاریتمیِ TF ریز.

    زیرکندلِ j به کندلِ درشتِ i تعلق دارد اگر sub_t[j] ∈ [coarse_t[i], coarse_t[i+1}).
    زیربازده‌ای که مرزِ کندلِ درشت را قطع می‌کند (اولین زیرکندلِ هر درشت) به همان
    کندلِ درشتِ جدید نسبت داده می‌شود — کاملاً درونِ [شروعِ i، پایانِ i] بسته می‌شود
    پیش از openِ i+1 ⇒ علّی.
    """
    r = np.diff(np.log(sub_c))                 # r_j = log(c_j/c_{j-1})؛ زمانِ r_j = sub_t[1:]
    rt = sub_t[1:]
    pos2 = np.where(r > 0, r * r, 0.0)
    neg2 = np.where(r < 0, r * r, 0.0)
    idx = np.searchsorted(coarse_t, rt, side='right') - 1   # اندیسِ کندلِ درشتِ میزبان
    ok = idx >= 0
    n = len(coarse_t)
    rsvp = np.zeros(n)
    rsvn = np.zeros(n)
    np.add.at(rsvp, idx[ok], pos2[ok])
    np.add.at(rsvn, idx[ok], neg2[ok])
    cnt = np.zeros(n)
    np.add.at(cnt, idx[ok], 1.0)
    return rsvp, rsvn, cnt


def sj_series(rsvp: np.ndarray, rsvn: np.ndarray, w: int) -> np.ndarray:
    """SJ_W[t] = Σ_W(RSV+−RSV−)/Σ_W(RSV++RSV−) — پنجرهٔ غلتانِ شاملِ خودِ t."""
    num = pd.Series(rsvp - rsvn).rolling(w, min_periods=w).sum().values
    den = pd.Series(rsvp + rsvn).rolling(w, min_periods=w).sum().values
    with np.errstate(divide='ignore', invalid='ignore'):
        sj = np.where(den > 0, num / den, np.nan)
    return sj


def cross_signals(sj: np.ndarray, theta: float, mode: str):
    """حالت‌گذرِ SJ از ±θ. سیگنال روی t (SJ تا پایانِ t) ⇒ موتور در openِ t+1 وارد می‌شود."""
    prev = np.r_[np.nan, sj[:-1]]
    up = (prev < theta) & (sj >= theta)
    dn = (prev > -theta) & (sj <= -theta)
    up = np.nan_to_num(up).astype(bool)
    dn = np.nan_to_num(dn).astype(bool)
    if mode == 'cont':
        return up, dn          # UP⇒LONG · DOWN⇒SHORT
    return dn, up              # rev: آینه


def load_card(tf: str):
    d = fd.load_fast(ASSET, tf)
    df = pd.DataFrame({'open': d['open'], 'high': d['high'],
                       'low': d['low'], 'close': d['close']})
    t = d['time'].astype(np.int64)
    sub = fd.load_fast(ASSET, SUB_SRC[tf])
    sub_t = sub['time'].astype(np.int64)
    sub_c = sub['close'].astype(np.float64)
    return df, t, sub_t, sub_c, d['src'], sub['src']


def prepare(tf: str):
    df, t, sub_t, sub_c, src, sub_src = load_card(tf)
    rsvp, rsvn, cnt = rsv_per_bar(t, sub_t, sub_c)
    atr = atr_pip(df, ASSET)
    sl_arr = np.round(K_SL * atr, 3)
    tp_arr = np.round(RR * sl_arr, 3)
    # کندلِ معتبر: ATR آماده + پوششِ زیرکندلیِ کافی (حداقل نیمی از انتظار)
    exp_sub = {'H1': 12, 'H2': 24, 'H3': 36, 'H4': 48,
               'H6': 72, 'H8': 96, 'H12': 144, 'D1': 24}[tf]
    valid_mask = (~np.isnan(atr)) & (np.arange(len(df)) >= ATR_P) & \
                 (cnt >= exp_sub * 0.5)
    return df, t, rsvp, rsvn, sl_arr, tp_arr, valid_mask, src, sub_src


def scan_search(tf: str):
    """فاز ۱ — جستجو فقط روی ۶۰٪ نخست."""
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()
    df, t, rsvp, rsvn, sl_arr, tp_arr, valid_mask, src, sub_src = prepare(tf)
    n_all = len(df)
    split = int(SPLIT_FRAC * n_all)
    # فقط نیمهٔ جستجو — هولدآوت هرگز شبیه‌سازی نمی‌شود
    dfs = df.iloc[:split].reset_index(drop=True)
    sl_s, tp_s = sl_arr[:split], tp_arr[:split]
    vm_s = valid_mask[:split]
    rng = np.random.default_rng(SEED)

    # مبنای بی‌قیدِ نیمهٔ جستجو (یک بار — هندسه آرایه‌ای است و per-bar تفاوتی ندارد)
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

    rows = []
    best = {'long': None, 'short': None}
    for w in WINDOWS:
        sj = sj_series(rsvp[:split], rsvn[:split], w)
        for theta in THETAS:
            for mode in MODES:
                ls, ss = cross_signals(sj, theta, mode)
                ls &= vm_s
                ss &= vm_s
                tr = se.simulate_trades(dfs, ls, ss, sl_pip=sl_s, tp_pip=tp_s,
                                        asset=ASSET, max_hold=MAX_HOLD,
                                        allow_overlap=False)
                if tr is None or not len(tr) or 'pnl_pip' not in tr:
                    continue
                for side in ('long', 'short'):
                    sub = tr[tr['direction'] == side] if 'direction' in tr else tr
                    n = len(sub)
                    if n < 30 or base[side] is None:
                        continue
                    wr = float((sub['pnl_pip'] > 0).mean() * 100)
                    expp = float(sub['pnl_pip'].mean())
                    lift = wr - base[side]
                    score = lift * np.sqrt(n)
                    row = dict(w=w, theta=theta, mode=mode, side=side, n=int(n),
                               wr=round(float(wr), 2), exp_pip=round(float(expp), 3),
                               lift=round(float(lift), 2), score=round(float(score), 2))
                    rows.append(row)
                    if expp > 0 and lift > 0 and (
                            best[side] is None or score > best[side]['score']):
                        best[side] = row

    out = dict(tf=tf, src=src, sub_src=sub_src, n_bars=n_all, split=split,
               base_wr=base, n_family=N_FAMILY, rows=rows, best=best,
               barrier='lift*sqrt(n)>=78',
               best_pass={s: bool(best[s] is not None and best[s]['score'] >= 78)
                          for s in ('long', 'short')},
               elapsed_s=round(time.time() - t0, 1))
    path = os.path.join(OUT_DIR, f"{tf}_search.json")
    with open(path, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"[S761 search {tf}] src={os.path.basename(str(src))} bars={n_all} "
          f"split={split} best={best} pass={out['best_pass']} "
          f"({out['elapsed_s']}s)")


# ---- فاز ۲: هولدآوت (فقط پس از کامیتِ الحاقیهٔ انجماد پر می‌شود) ----
FROZEN = {
    'H1': dict(side='short', mode='cont', w=21, theta=0.555),
    'D1': dict(side='short', mode='cont', w=8, theta=0.333),
}


def build_null_side(dfa, valid, sl_arr, tp_arr, side, n_side, rng,
                    n_perm=K_PERM):
    """مبنای اندازه‌گیری‌شده به الگوی s351/s760 با هندسهٔ منجمد."""
    is_long = (side == 'long')
    d = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
             perm_max=None, perm_k=None)
    other = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                 perm_max=None, perm_k=None)
    if n_side < 1 or len(valid) < 2:
        return {side: d, ('short' if is_long else 'long'): other}
    samp = valid if len(valid) <= 20000 else np.sort(
        rng.choice(valid, size=20000, replace=False))
    sig = np.zeros(len(dfa), bool)
    sig[samp] = True
    tr = se.simulate_trades(
        dfa, sig if is_long else np.zeros(len(dfa), bool),
        sig if not is_long else np.zeros(len(dfa), bool),
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
            trp = se.simulate_trades(
                dfa, sig if is_long else np.zeros(len(dfa), bool),
                sig if not is_long else np.zeros(len(dfa), bool),
                sl_pip=sl_arr, tp_pip=tp_arr, asset=ASSET,
                max_hold=MAX_HOLD, allow_overlap=False)
            if trp is not None and len(trp) and 'pnl_pip' in trp:
                wrs.append(float((trp['pnl_pip'] > 0).mean() * 100))
        if wrs:
            a = np.asarray(wrs)
            d.update(perm_mean=float(a.mean()), perm_sd=float(a.std(ddof=1)),
                     perm_max=float(a.max()), perm_k=int(len(a)))
    return {side: d, ('short' if is_long else 'long'): other}


def judge_holdout(tf: str):
    """آزمونِ یگانهٔ hold-out — هر کارت فقط یک بار (مرگِ ابدی در صورتِ تکرار)."""
    import gc
    cfg = FROZEN.get(tf)
    if not cfg:
        raise SystemExit(f"{tf} در FROZEN نیست — انجماد نشده یا NO_CANDIDATE.")
    guard = os.path.join(OUT_DIR, f"{tf}_JUDGED")
    if os.path.exists(guard):
        raise SystemExit(f"{tf} قبلاً داوری شده — آزمونِ دوم ممنوع (مرگِ ابدی).")
    os.makedirs(OUT_DIR, exist_ok=True)
    df, t, rsvp, rsvn, sl_arr, tp_arr, valid_mask, src, sub_src = prepare(tf)
    n_all = len(df)
    split = int(SPLIT_FRAC * n_all)
    rng = np.random.default_rng(SEED + 761)

    sj = sj_series(rsvp, rsvn, cfg['w'])
    ls, ss = cross_signals(sj, cfg['theta'], cfg['mode'])
    ls &= valid_mask
    ss &= valid_mask
    if cfg['side'] == 'long':
        ss = np.zeros(n_all, bool)
    else:
        ls = np.zeros(n_all, bool)

    trades = se.simulate_trades(df, ls, ss, sl_pip=sl_arr, tp_pip=tp_arr,
                                asset=ASSET, max_hold=MAX_HOLD,
                                allow_overlap=False)
    if trades is None or not len(trades):
        raise SystemExit(f"{tf}: هیچ معامله‌ای — INCOMPLETE.")
    ent = trades['entry_bar'].values
    n_hold = int((ent >= split).sum())

    # نولِ اندازه‌گیری‌شده روی هولدآوت با n_holdout
    valid_hold = np.where(valid_mask & (np.arange(n_all) >= split))[0]
    null = build_null_side(df, valid_hold, sl_arr, tp_arr,
                           cfg['side'], n_hold, rng)
    gc.collect()

    sl_med = float(np.median(sl_arr[ent[ent < n_all]])) if len(ent) else None
    tp_med = sl_med * RR if sl_med else None

    res = {}
    for label, ntr in (('N1_pathC', 1), ('N96_strict', N_FAMILY)):
        v = rqs2.compute_rqs2(
            trades, ASSET, sl_pip=sl_med, tp_pip=tp_med,
            bar_time=t, null=null, n_trials=ntr,
            split_bar=split, close=df['close'].values)
        res[label] = v
        print(f"[{label}] verdict={v.get('verdict')} rqs2={v.get('rqs2')} "
              f"| n={v.get('n')} lift={v.get('lift')} z={v.get('z')} "
              f"p_perm={v.get('p_perm')}")

    def _clean(o):
        if isinstance(o, dict):
            return {k: _clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [_clean(x) for x in o]
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        return o

    out = dict(tf=tf, cfg=cfg, src=str(src), sub_src=str(sub_src),
               n_bars=n_all, split=split, n_total_trades=int(len(trades)),
               n_holdout=n_hold, sl_med=sl_med, tp_med=tp_med,
               null=_clean(null), verdicts=_clean(res))
    with open(os.path.join(OUT_DIR, f"{tf}_holdout.json"), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    with open(guard, 'w') as f:
        f.write(f"judged at {time.strftime('%F %T')}\n")


if __name__ == '__main__':
    phase = sys.argv[1] if len(sys.argv) > 1 else 'search'
    tf = sys.argv[2] if len(sys.argv) > 2 else 'H1'
    if phase == 'search':
        scan_search(tf)
    else:
        judge_holdout(tf)
