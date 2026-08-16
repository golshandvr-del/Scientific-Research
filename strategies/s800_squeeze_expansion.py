# -*- coding: utf-8 -*-
"""
S800 — لایهٔ نو: «فشردگی → گشایش» (Squeeze-Expansion Breakout) روی طلا
================================================================================
پیش‌ثبت: `results/S800_PREREG_SQUEEZE_EXPANSION_XAUUSD.md` (کامیت 6081dceb —
قفل‌شده پیش از دیدن هر عدد). مسیر چندگانگی: **C (hold-out)**.

معماری دوفازی (مطابق پیش‌ثبت):
  • فاز `explore`: جست‌وجوی خانوادهٔ ۹۷۲تایی **فقط روی نیمهٔ اول** داده.
    برندهٔ نیمهٔ اول در JSON قفل و کامیت می‌شود.
  • سنجش توان: `lift·√n ≥ 78` روی نیمهٔ اول با نول اندازه‌گیری‌شده (K=500).
    اگر برآورده نشود، فاز judge اجرا نمی‌شود (POWER-LIMITED همان‌جا).
  • فاز `judge`: همان پیکربندی قفل‌شده روی کل داده شبیه‌سازی و با
    `compute_rqs2` استاندارد (split_bar=نیمه، n_trials=1) داوری می‌شود.

مدل صفر (صادق نسبت به هندسهٔ RR≠1):
  به‌جای «علامتِ حرکتِ رو به جلو» (که برای RR=1 درست است)، خروجی واقعی سدِ
  SL/TP را برای هر سیگنال در *هر دو جهت* با شبیه‌ساز می‌سنجیم (۲ اجرا)،
  سپس K=500 جای‌گشتِ جهتِ تصادفی روی همین خروجی‌های اندازه‌گیری‌شده.
  ⇒ نول، احتمال بردِ واقعیِ ورودِ بی‌شرط با همین هندسه را بازتاب می‌دهد.

اجرا:
  python3 strategies/s800_squeeze_expansion.py --tf M1 --phase explore
  python3 strategies/s800_squeeze_expansion.py --tf M1 --phase judge
خروجی: results/_scan_S800/<TF>_explore.json / <TF>_locked.json / <TF>_judge.json
"""
import sys
import os
import gc
import json
import argparse
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se            # noqa: E402
from engine import rqs2                          # noqa: E402
from engine import indicator_bank as ib          # noqa: E402
from tools import s434_fast_data as fd           # noqa: E402

OUT = 'results/_scan_S800'
ASSET = 'XAUUSD'
SEED = 20260813                                   # بذرِ پیش‌ثبت‌شده
K_PERM = 500                                      # کفِ همگرایی v2.4
POWER_MIN = 78.0                                  # lift·√n روی نیمهٔ اول
N_TRIALS_JUDGE = 1                                # قرارداد مسیر C

# ---------------- خانوادهٔ جست‌وجو (قفل‌شده در پیش‌ثبت — ۹۷۲ ترکیب) ----------
DONCH_P   = [21, 34, 55]                          # دورهٔ کانال (فیبوناچی)
SQZ_Q     = [20.0, 30.0, 40.0]                    # آستانهٔ چندکِ atr_pct
SL_K      = [1.272, 1.618, 2.058]                 # SL = k·ATR(21)
RR        = [1.0, 1.272, 1.618]                   # TP = RR·SL (هرگز RR<1)
HOLD      = [21, 34, 55, 89]                      # کندل (فیبوناچی)
FILTERS   = ['none', 'r2', 'hurst']               # تأیید رژیم روندی
N_FAMILY  = (len(DONCH_P) * len(SQZ_Q) * len(SL_K)
             * len(RR) * len(HOLD) * len(FILTERS))  # = 972


def load(tf):
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    # صرفه‌جویی حافظه (سندباکس ~1GB): فقط ستون‌های لازم، float32
    keep = ['time', 'open', 'high', 'low', 'close']
    df = df[[c for c in keep if c in df.columns]].copy()
    for c in ('open', 'high', 'low', 'close'):
        df[c] = df[c].astype(np.float32)
    gc.collect()
    return d, df


def ind_path(tf, name):
    return f'{OUT}/{tf}_ind_{name}.npy'


def phase_prep(tf, name):
    """یک اندیکاتور در فرآیند جداگانه — ضد OOM روی M1 (سندباکس 1GB)."""
    os.makedirs(OUT, exist_ok=True)
    p = ind_path(tf, name)
    if os.path.exists(p):
        print(f'[prep] {tf}/{name} موجود است — رد می‌شوم', flush=True)
        return
    d, df = load(tf)
    v = np.asarray(ib.compute(name, df), dtype=np.float32)
    np.save(p, v)
    print(f'[prep] {tf}/{name} → {p}  ({len(v)})', flush=True)


def base_arrays(df, need_filters=True, tf=None):
    """اندیکاتورهای مشترک — یک بار، تک‌به‌تک با آزادسازی حافظه (سندباکس 1GB)."""
    pip = se.ASSETS[ASSET]['pip']

    def get(name):
        if tf is not None and os.path.exists(ind_path(tf, name)):
            return np.load(ind_path(tf, name), mmap_mode='r')
        return np.asarray(ib.compute(name, df), dtype=np.float32)

    atr21 = np.asarray(get('atr_fib_21'), dtype=np.float32)
    gc.collect()
    atr_pct = np.asarray(get('atr_pct'), dtype=np.float32)
    gc.collect()
    # فشردگی با تأخیر ۱ کندل (وضعیت در بازشدنِ کندلِ سیگنال معلوم است)
    sqz_raw = np.empty_like(atr_pct)
    sqz_raw[0] = np.nan
    sqz_raw[1:] = atr_pct[:-1]
    del atr_pct
    gc.collect()
    if need_filters:
        r2 = np.asarray(get('r2_fib_34'), dtype=np.float32)
        gc.collect()
        hu = np.asarray(get('hurst'), dtype=np.float32)
        gc.collect()
    else:
        r2 = np.full(len(df), np.nan, dtype=np.float32)
        hu = r2
    sl_pip_arr = (atr21 / pip).astype(np.float32)        # واحد pip
    del atr21
    gc.collect()
    return dict(pip=pip, sl_pip=sl_pip_arr, sqz=sqz_raw, r2=r2, hurst=hu)


def donch_signals(df, p):
    """شکست کانال دانچیان دورهٔ p (forward-safe: سقف/کفِ p کندلِ قبل)."""
    h = pd.Series(df['high'].values)
    l = pd.Series(df['low'].values)
    hh = h.rolling(p).max().shift(1).values
    ll = l.rolling(p).min().shift(1).values
    c = df['close'].values
    long_b = c > hh
    short_b = c < ll
    long_b[np.isnan(hh)] = False
    short_b[np.isnan(ll)] = False
    return long_b, short_b


def apply_filter(base, name):
    if name == 'none':
        return np.ones(len(base['r2']), dtype=bool)
    if name == 'r2':
        f = base['r2'] >= 0.30
    else:
        f = base['hurst'] >= 0.55
    f = np.asarray(f, dtype=bool)
    f[~np.isfinite(base['r2'])] = False
    return f


def run_cfg(df, base, cfg, lo=0, hi=None, donch_cache=None):
    """شبیه‌سازی یک پیکربندی؛ سیگنال‌ها به بازهٔ [lo,hi) محدود می‌شوند."""
    n = len(df)
    hi = n if hi is None else hi
    if donch_cache is not None and cfg['p'] in donch_cache:
        long_b, short_b = donch_cache[cfg['p']]
    else:
        long_b, short_b = donch_signals(df, cfg['p'])
    sqz_ok = base['sqz'] < cfg['q']
    filt = apply_filter(base, cfg['filter'])
    valid_sl = np.isfinite(base['sl_pip']) & (base['sl_pip'] > 0)
    ls = long_b & sqz_ok & filt & valid_sl
    ss = short_b & sqz_ok & filt & valid_sl
    mask = np.zeros(n, dtype=bool)
    mask[lo:hi] = True
    ls &= mask
    ss &= mask
    sl = np.where(valid_sl, base['sl_pip'] * cfg['k'], 1.0)
    tp = sl * cfg['rr']
    tr = se.simulate_trades(df, ls, ss, sl, tp, ASSET,
                            max_hold=cfg['hold'], allow_overlap=False)
    return tr, ls, ss, sl, tp


def summarize(tr, cost_pip):
    if tr is None or len(tr) == 0:
        return None
    n = len(tr)
    wins = int((tr['outcome'] == 'win').sum())
    wr = wins / n * 100.0
    pnl = tr['pnl_pip'].values.astype(np.float64)
    exp_pip = float(np.mean(pnl))
    gp = float(pnl[pnl > 0].sum())
    gl = float(-pnl[pnl < 0].sum())
    pf = gp / gl if gl > 0 else float('inf')
    sl_m = float(np.mean(tr['sl_pip'].values))
    # tp از هندسه بازسازی می‌شود (simulate_trades ستون tp نمی‌سازد)
    return dict(n=n, wr=wr, exp_pip=exp_pip, pf=pf, sl_med=sl_m)


def build_null_barrier(df, ls, ss, sl, tp, hold, K=K_PERM, seed=SEED):
    """نولِ سدمحور: خروجی واقعی SL/TP در هر دو جهت در همان کندل‌های سیگنال،
    سپس K جای‌گشتِ جهتِ تصادفی. قالب خروجی: کانونیِ null_from_s346."""
    sig = ls | ss
    if int(sig.sum()) < 30:
        return None
    # هر دو جهت با allow_overlap=True تا هر سیگنال یک خروجی داشته باشد
    trL = se.simulate_trades(df, sig, np.zeros_like(sig), sl, tp, ASSET,
                             max_hold=hold, allow_overlap=True)
    trS = se.simulate_trades(df, np.zeros_like(sig), sig, sl, tp, ASSET,
                             max_hold=hold, allow_overlap=True)
    mL = {int(b): (o == 'win') for b, o in zip(trL['entry_bar'], trL['outcome'])}
    mS = {int(b): (o == 'win') for b, o in zip(trS['entry_bar'], trS['outcome'])}
    bars = sorted(set(mL) & set(mS))
    m = len(bars)
    if m < 30:
        return None
    wl = np.array([mL[b] for b in bars], dtype=bool)
    ws = np.array([mS[b] for b in bars], dtype=bool)
    rng = np.random.default_rng(seed)
    wrs = np.empty(K)
    for i in range(K):
        pick = rng.integers(0, 2, size=m).astype(bool)
        w = np.where(pick, wl, ws)
        wrs[i] = w.mean() * 100.0
    ref = float(np.mean(wrs))
    side = dict(uncond_wr=ref, perm_mean=ref, perm_sd=float(np.std(wrs)),
                perm_max=float(np.max(wrs)), perm_k=K)
    return {'long': dict(side), 'short': dict(side)}


def phase_explore(tf):
    os.makedirs(OUT, exist_ok=True)
    d, df = load(tf)
    n = len(df)
    split = n // 2
    cost = se.ASSETS[ASSET]['spread_pip']
    print(f"[S800/{tf}] explore  src={d['src']}  bars={n}  split={split}",
          flush=True)
    base = base_arrays(df, tf=tf)
    # کشِ سیگنال‌های دانچیان (bool — ارزان)
    donch_cache = {p: donch_signals(df, p) for p in DONCH_P}
    gc.collect()
    rows = []
    t0 = time.time()
    done = 0
    for p in DONCH_P:
        for q in SQZ_Q:
            for filt in FILTERS:
                for k in SL_K:
                    for rr in RR:
                        for hold in HOLD:
                            cfg = dict(p=p, q=q, filter=filt, k=k, rr=rr,
                                       hold=hold)
                            tr, *_ = run_cfg(df, base, cfg, lo=0, hi=split,
                                             donch_cache=donch_cache)
                            s = summarize(tr, cost)
                            done += 1
                            if s is None or s['n'] < 30:
                                continue
                            be = ((s['sl_med'] + cost)
                                  / (s['sl_med'] * (1 + rr)) * 100.0)
                            lift_be = s['wr'] - be
                            score = lift_be * np.sqrt(s['n'])
                            rows.append(dict(cfg=cfg, **s, be_wr=be,
                                             lift_be=lift_be, score=score))
                            if done % 108 == 0:
                                el = time.time() - t0
                                print(f"  … {done}/{N_FAMILY}  ({el:.0f}s)  "
                                      f"valid={len(rows)}", flush=True)
                                # checkpoint اندک‌اندک
                                with open(f'{OUT}/{tf}_explore.json', 'w') as f:
                                    json.dump(dict(tf=tf, done=done,
                                                   rows=rows), f)
    rows.sort(key=lambda r: -r['score'])
    with open(f'{OUT}/{tf}_explore.json', 'w') as f:
        json.dump(dict(tf=tf, done=done, split=split, bars=n,
                       src=d['src'], rows=rows[:50]), f, indent=1)
    if not rows:
        print(f"[S800/{tf}] هیچ ترکیب معتبری (n≥30, exp>0) روی نیمهٔ اول "
              f"یافت نشد ⇒ UNPROVEN در این TF", flush=True)
        return
    best = rows[0]
    print(f"[S800/{tf}] برندهٔ نیمهٔ اول: {best['cfg']}  n={best['n']}  "
          f"wr={best['wr']:.1f}  lift_be={best['lift_be']:.2f}pp  "
          f"score={best['score']:.1f}", flush=True)

    # --- سنجش توان با نول اندازه‌گیری‌شده (فقط نیمهٔ اول) ---
    cfg = best['cfg']
    tr, ls, ss, sl, tp = run_cfg(df, base, cfg, lo=0, hi=split,
                                 donch_cache=donch_cache)
    null = build_null_barrier(df, ls, ss, sl, tp, cfg['hold'])
    if null is None:
        print(f"[S800/{tf}] نول ساخته نشد (سیگنال<30) ⇒ POWER-LIMITED",
              flush=True)
        return
    s = summarize(tr, cost)
    lift = s['wr'] - null['long']['perm_mean']
    power = lift * np.sqrt(s['n'])
    ok = bool(power >= POWER_MIN)
    locked = dict(tf=tf, cfg=cfg, explore=dict(**s), null_explore=null,
                  lift_vs_null=lift, power=power, power_ok=ok,
                  split=split, bars=n, src=d['src'], seed=SEED)
    with open(f'{OUT}/{tf}_locked.json', 'w') as f:
        json.dump(locked, f, indent=1)
    print(f"[S800/{tf}] lift(null)={lift:.2f}pp  n={s['n']}  "
          f"lift·√n={power:.1f}  (آستانه {POWER_MIN})  "
          f"{'✓ مجوز آزمون نهایی' if ok else '✗ توان ناکافی — judge اجرا نمی‌شود'}",
          flush=True)


def phase_judge(tf):
    path = f'{OUT}/{tf}_locked.json'
    if not os.path.exists(path):
        print(f"[S800/{tf}] فایل قفل یافت نشد — ابتدا explore.", flush=True)
        return
    locked = json.load(open(path))
    if not locked.get('power_ok'):
        print(f"[S800/{tf}] پیش‌شرط توان برآورده نشده — طبق پیش‌ثبت judge "
              f"اجرا نمی‌شود.", flush=True)
        return
    d, df = load(tf)
    base = base_arrays(df, tf=tf)
    cfg = locked['cfg']
    split = locked['split']
    cost = se.ASSETS[ASSET]['spread_pip']
    # شبیه‌سازی روی کل داده (H7 با split_bar نیمهٔ دوم را جدا داوری می‌کند)
    tr, ls, ss, sl, tp = run_cfg(df, base, cfg, lo=0, hi=None)
    null = build_null_barrier(df, ls, ss, sl, tp, cfg['hold'])
    s = summarize(tr, cost)
    sl_med = float(np.median(tr['sl_pip'].values))
    tp_med = sl_med * cfg['rr']
    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=df['time'].values, null=null,
                          n_trials=N_TRIALS_JUDGE, split_bar=split,
                          close=df['close'].values)
    out = dict(tf=tf, cfg=cfg, src=d['src'], bars=len(df), split=split,
               n=s['n'], wr=s['wr'], exp_pip=s['exp_pip'], pf=s['pf'],
               sl_med=sl_med, tp_med=tp_med,
               verdict=r['verdict'], score=r['rqs2_score'],
               gates={k: (None if v is None else bool(v))
                      for k, v in r['gates'].items()},
               skill_p_perm=r['metrics'].get('skill_p_perm'),
               metrics={k: (float(v) if isinstance(v, (int, float, np.floating))
                            else str(v)) for k, v in r['metrics'].items()})
    with open(f'{OUT}/{tf}_judge.json', 'w') as f:
        json.dump(out, f, indent=1, default=str)
    print(rqs2.format_rqs2(f'S800 {tf} ', r), flush=True)
    print(f"[S800/{tf}] verdict={r['verdict']}  score={r['rqs2_score']:.1f}  "
          f"skill_p_perm={r['metrics'].get('skill_p_perm')}", flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--tf', required=True)
    ap.add_argument('--phase', choices=['prep', 'explore', 'judge', 'both'],
                    default='both')
    ap.add_argument('--ind', default=None)
    a = ap.parse_args()
    if a.phase == 'prep':
        phase_prep(a.tf, a.ind)
        sys.exit(0)
    if a.phase in ('explore', 'both'):
        phase_explore(a.tf)
    if a.phase in ('judge', 'both'):
        phase_judge(a.tf)
