# -*- coding: utf-8 -*-
"""
S691 — CLV Streak (پایداری مکان بسته‌شدن) — XAUUSD فقط
========================================================
پیش‌ثبت: results/S691_PREREG_CLV_STREAK.md (کامیت 0557e55f — قبل از این فایل)

سیگنال (منجمد):
  clv[t] = (close−low)/(high−low) ∈ [0,1]
  Long : clv > q برای k کندل متوالی منتهی به t و کندل t−k چنین نباشد (لبهٔ رشته)
  Short: قرینهٔ کامل (clv < 1−q)
  ورود: Open کندل t+1 · SL=k_sl×ATR(13) · TP=max(rr×SL,SL) · hold=16h زمانی

خانوادهٔ منجمد: k∈{3,5,8} × q∈{0.786,0.854} × k_sl∈{0.618,1.0,1.618} × rr∈{1.0,1.272,1.618,2.058}
  ⇒ 72 سلول per side · مسیر C: جست‌وجو فقط TRAIN=۶۰٪، حکم از compute_rqs2 (n_trials=72).

درس‌های ارثی S690: رژیم حافظهٔ سخت (سندباکس 985MB)، کامیت افزایشی per-TF،
bars_per_hour (BUG-TFM)، نال K=500، حکم هرگز دستی.
"""
import sys, os, json, gc, subprocess, argparse, time as _time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

from engine import scalp_engine as se                      # noqa: E402
from engine import rqs2                                    # noqa: E402
from strategies.s348_rr_sweep import queue_rr, trades_df, cost_pip  # noqa: E402
from strategies.s351_lpsb import atr_series                # noqa: E402
from tools import s434_fast_data as fd                     # noqa: E402

# ─── خانوادهٔ منجمد (عیناً از پیش‌ثبت) ───
K_GRID     = (3, 5, 8)
Q_GRID     = (0.786, 0.854)
SL_K_GRID  = (0.618, 1.0, 1.618)
RR_GRID    = (1.0, 1.272, 1.618, 2.058)
N_TRIALS   = len(K_GRID) * len(Q_GRID) * len(SL_K_GRID) * len(RR_GRID)   # 72
ATR_P      = 13
HOLD_HOURS = 16.0
SPLIT_FRAC = 0.60
N_PERM     = 500
N_UNCOND_CAP = 25000
SEED       = 691
ASSET      = 'XAUUSD'
TF_ORDER   = ['M1','M3','M4','M5','M6','M10','M12','M15','M20','M30',
              'H1','H2','H3','H6','H8','H12','D1','W1','MN1']
OUT_DIR    = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'results', 's691_runs')


def bars_per_hour(time_arr):
    d = np.median(np.diff(time_arr.astype(np.float64)))
    return 3600.0 / d if d > 0 else 1.0


def clv_series(d):
    h = d['high'].astype(np.float64); l = d['low'].astype(np.float64)
    c = d['close'].astype(np.float64)
    rng = h - l
    ok = rng > 0
    clv = np.full(len(c), np.nan)
    clv[ok] = (c[ok] - l[ok]) / rng[ok]
    return clv


def streak_signals(clv, k, q, warmup):
    """لبهٔ رشتهٔ k-تایی: k کندل متوالی شرط را دارند و کندل k+1-ام قبلی ندارد.

    برداری: cnt[t] = طول دنبالهٔ متوالی منتهی به t (کندل نامعتبر رشته را می‌شکند).
    """
    n = len(clv)
    out = {}
    for side, cond in (('long', clv > q), ('short', clv < 1.0 - q)):
        cond = cond & np.isfinite(clv)
        # طول رشتهٔ متوالی با ترفند cumsum-reset
        idx = np.arange(n)
        last_false = np.maximum.accumulate(np.where(~cond, idx, -1))
        cnt = idx - last_false                     # 0 جایی که cond=False
        sig = (cnt == k)                            # دقیقاً لبهٔ رسیدن به k
        sig[:warmup] = False
        out[side] = np.flatnonzero(sig)
    return out


def uncond_wr_for_geo(df, valid, atr, k_sl, rr, hold, rng):
    pick = valid if len(valid) <= N_UNCOND_CAP else \
        np.sort(rng.choice(valid, size=N_UNCOND_CAP, replace=False))
    sl = k_sl * atr[pick]
    ok = np.isfinite(sl) & (sl > 0)
    pick, sl = pick[ok], sl[ok]
    res = {}
    for side, flag in (('long', True), ('short', False)):
        s = queue_rr(df, pick, np.full(len(pick), flag), sl, ASSET, hold, rr)
        res[side] = (float(s['wr']) if s else None, int(s['n']) if s else 0)
    return res


def build_null(df, valid, atr, geo_by_side, n_by_side, hold, rng):
    null = {}
    for side, flag in (('long', True), ('short', False)):
        dnull = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                     perm_max=None, perm_k=None)
        k_sl, rr = geo_by_side[side]
        n_side = n_by_side[side]
        if n_side >= 1 and len(valid) > n_side:
            u = uncond_wr_for_geo(df, valid, atr, k_sl, rr, hold, rng)
            dnull['uncond_wr'] = u[side][0]
            slv_all = k_sl * atr[valid]
            ok = np.isfinite(slv_all) & (slv_all > 0)
            vi, slv_all = valid[ok], slv_all[ok]
            wrs = []
            for _ in range(N_PERM):
                pick = np.sort(rng.choice(len(vi), size=n_side, replace=False))
                s = queue_rr(df, vi[pick], np.full(n_side, flag),
                             slv_all[pick], ASSET, hold, rr)
                if s:
                    wrs.append(s['wr'])
            if wrs:
                a = np.asarray(wrs)
                dnull.update(perm_mean=float(a.mean()), perm_sd=float(a.std(ddof=1)),
                             perm_max=float(a.max()), perm_k=int(len(a)))
        null[side] = dnull
        print(f"    null {side:<5} uncond={dnull['uncond_wr']} "
              f"μ={dnull['perm_mean']} σ={dnull['perm_sd']} K={dnull['perm_k']}",
              flush=True)
    return null


def run_tf(tf, do_git=True):
    t0 = _time.time()
    print(f"\n{'='*88}\n=== S691 CLV-Streak :: XAUUSD-{tf} ===", flush=True)
    d = fd.load_fast(ASSET, tf)
    for _k in ('volume', 'hour', 'minute', 'dow'):     # رژیم حافظه (درس OOM)
        d.pop(_k, None)
    gc.collect()
    df = pd.DataFrame({'time': d['time'], 'open': d['open'], 'high': d['high'],
                       'low': d['low'], 'close': d['close']}, copy=False)
    n = len(df)
    src = d.get('src', '?')
    print(f"    bars={n:,}  src={src}  span={d.get('span_years','?')}y", flush=True)

    bph = bars_per_hour(d['time'])
    hold = max(1, int(round(HOLD_HOURS * bph)))
    atr = atr_series(df, p=ATR_P)
    warmup = max(4 * ATR_P, max(K_GRID) + 2, 60)
    split = int(n * SPLIT_FRAC)
    c = cost_pip(ASSET)
    print(f"    hold={hold} bars (16h @ {bph:.3f} bph) · warmup={warmup} · "
          f"split_bar={split} · cost={c:.2f}pip", flush=True)

    out = dict(strategy='S691', concept='clv_streak', asset=ASSET, tf=tf,
               bars=n, src=src, hold_bars=hold, split_bar=split,
               n_trials=N_TRIALS, family='3x2x3x4=72/side', cost_pip=c)

    if n < warmup + 500:
        out['verdict'] = 'TOO_SHORT'
        _save(tf, out, do_git); return out

    rng = np.random.default_rng(SEED)
    clv = clv_series(d)

    # ── ۱) سیگنال‌ها برای ۶ پیکربندی (k × q) ──
    sig_map = {}
    for k in K_GRID:
        for q in Q_GRID:
            sm = streak_signals(clv, k, q, warmup)
            sig_map[(k, q)] = sm
            print(f"    signals k={k} q={q}: L={len(sm['long'])} "
                  f"S={len(sm['short'])}", flush=True)
    del clv
    gc.collect()

    # ── ۲) نال بی‌قید TRAIN per geometry ──
    valid_all = np.arange(warmup, n - hold - 2)
    fin = np.isfinite(atr[valid_all]) & (atr[valid_all] > 0)
    valid_all = valid_all[fin]
    valid_tr = valid_all[valid_all < split]
    geo_null_tr = {}
    for k_sl in SL_K_GRID:
        for rr in RR_GRID:
            geo_null_tr[(k_sl, rr)] = uncond_wr_for_geo(
                df, valid_tr, atr, k_sl, rr, hold, rng)

    # ── ۳) جست‌وجوی ۷۲ سلول per side — فقط TRAIN ──
    best = {'long': None, 'short': None}
    scan = []
    for (k, q), sm in sig_map.items():
        for side, flag in (('long', True), ('short', False)):
            sig = sm[side]
            sig_tr = sig[sig < split - hold]
            if len(sig_tr) < 5:
                continue
            for k_sl in SL_K_GRID:
                sl = k_sl * atr[sig_tr]
                okm = np.isfinite(sl) & (sl > 0)
                for rr in RR_GRID:
                    st = queue_rr(df, sig_tr[okm], np.full(okm.sum(), flag),
                                  sl[okm], ASSET, hold, rr)
                    if not st:
                        continue
                    u_wr = geo_null_tr[(k_sl, rr)][side][0]
                    if u_wr is None:
                        continue
                    lift = st['wr'] - u_wr
                    n_req = rqs2.n_required_for_h3(lift, u_wr / 100.0) \
                        if lift > 0 else float('inf')
                    score = lift * np.sqrt(st['n']) if lift > 0 else -1e9
                    feas = st['n'] >= n_req
                    scan.append(dict(k=k, q=q, k_sl=k_sl, rr=rr, side=side,
                                     n=st['n'], wr=round(st['wr'], 2),
                                     u=round(u_wr, 2), lift=round(lift, 2),
                                     exp=round(st['exp'], 2), feas=bool(feas)))
                    if feas and (best[side] is None or score > best[side][0]):
                        best[side] = (score, k, q, k_sl, rr, st['n'], lift)
    out['train_scan_top'] = sorted(
        scan, key=lambda r: -(r['lift'] * np.sqrt(r['n'])
                              if r['lift'] > 0 else -1e9))[:12]
    for side in ('long', 'short'):
        print(f"    TRAIN winner {side}: {best[side]}", flush=True)
    out['winner'] = {s: (None if best[s] is None else dict(
        zip(('score', 'k', 'q', 'k_sl', 'rr', 'n_train', 'lift_train'),
            [round(float(x), 3) if isinstance(x, (int, float, np.floating))
             else x for x in best[s]]))) for s in ('long', 'short')}

    if best['long'] is None and best['short'] is None:
        out['verdict'] = 'REJECT (no feasible cell on TRAIN — glass ceiling)'
        _save(tf, out, do_git); return out

    # ── ۴) اجرای کامل سلول برنده + نال + حکم ──
    frames, geo_by_side, n_by_side = [], {}, {'long': 0, 'short': 0}
    for side, flag in (('long', True), ('short', False)):
        if best[side] is None:
            geo_by_side[side] = (1.0, 1.0)
            continue
        _, k, q, k_sl, rr, _, _ = best[side]
        geo_by_side[side] = (k_sl, rr)
        sig = sig_map[(k, q)][side]
        sl = k_sl * atr[sig]
        okm = np.isfinite(sl) & (sl > 0)
        st = queue_rr(df, sig[okm], np.full(okm.sum(), flag), sl[okm],
                      ASSET, hold, rr)
        if st:
            frames.append(trades_df(st))
            n_by_side[side] = st['n']

    if not frames:
        out['verdict'] = 'REJECT (no trades on full run)'
        _save(tf, out, do_git); return out

    trades = pd.concat(frames, ignore_index=True)
    sl_med = float(trades['sl_pip'].median())
    tp_med = float(trades['tp_pip'].median())
    print(f"    full-run trades={len(trades)} (L={n_by_side['long']} "
          f"S={n_by_side['short']}) sl_med={sl_med:.1f} tp_med={tp_med:.1f}",
          flush=True)

    null = build_null(df, valid_all, atr, geo_by_side, n_by_side, hold, rng)

    r = rqs2.compute_rqs2(trades, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=d['time'], null=null, n_trials=N_TRIALS,
                          split_bar=split, close=d['close'].astype(np.float64))
    print(rqs2.format_rqs2(f'S691 {tf} ', r), flush=True)

    out.update(verdict=r['verdict'], rqs2_score=r['rqs2_score'],
               gates={k2: (None if v is None else bool(v))
                      for k2, v in r['gates'].items()},
               metrics={k2: (float(v) if isinstance(v, (int, float, np.floating))
                             and np.isfinite(float(v)) else str(v))
                        for k2, v in r['metrics'].items()},
               notes=r['notes'], null=null,
               n_trades=int(len(trades)), sl_med=sl_med, tp_med=tp_med,
               elapsed_s=round(_time.time() - t0, 1))
    _save(tf, out, do_git)
    return out


def _save(tf, out, do_git):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f'XAUUSD_{tf}.json')
    with open(path, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"    saved → {path}", flush=True)
    if do_git:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try:
            subprocess.run(['git', 'add', 'results/s691_runs'], cwd=root, check=True)
            subprocess.run(['git', 'commit', '-m',
                            f"S691 incremental: XAUUSD-{tf} → {out.get('verdict','?')}"],
                           cwd=root, capture_output=True)
            subprocess.run(['git', 'push', 'origin', 'main'], cwd=root,
                           capture_output=True, timeout=60)
            print(f"    git ✓ pushed XAUUSD-{tf}", flush=True)
        except Exception as e:                                   # noqa: BLE001
            print(f"    git ✗ {e} (ادامه — قانون افزایشی)", flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--tfs', nargs='*', default=TF_ORDER)
    ap.add_argument('--no-git', action='store_true')
    a = ap.parse_args()
    for tf in a.tfs:
        jp = os.path.join(OUT_DIR, f'XAUUSD_{tf}.json')
        if os.path.exists(jp):
            print(f"skip {tf} (result exists)", flush=True)
            continue
        try:
            run_tf(tf, do_git=not a.no_git)
        except Exception as e:                                   # noqa: BLE001
            import traceback; traceback.print_exc()
            print(f"!! {tf} failed: {e} — ادامه به TF بعدی", flush=True)
        gc.collect()
    print("\n=== S691 sweep complete ===", flush=True)
