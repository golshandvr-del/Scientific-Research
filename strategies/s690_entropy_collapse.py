# -*- coding: utf-8 -*-
"""
S690 — Entropy Collapse (فروریزش آنتروپی) — XAUUSD فقط
=========================================================
پیش‌ثبت: results/S690_PREREG_ENTROPY_COLLAPSE.md (کامیت f79f6848 — قبل از این فایل)

مفهوم (منجمد):
  تریگر  : رتبهٔ صدکی غلتانِ entropy (پنجرهٔ ۲۳۳) در t−k بالای 0.786 و در t زیر 0.382
  جهت    : علامتِ corr_t(p=21) در کندل سیگنال؛ ورود در Open کندل بعد (forward-safe)
  هندسه  : SL = k_sl×ATR(13) ، TP = max(rr×SL, SL) — سپر ضدخطای #۸ (TP ≥ SL همیشه)
  نگه‌داری: ۱۶ ساعتِ ثابتِ زمانی (bars_per_hour — علاج BUG-TFM)

خانوادهٔ منجمد: ent_p∈{13,21,34} × k∈{3,5,8} × k_sl∈{0.618,1.0,1.618} × rr∈{1.0,1.272,1.618,2.058}
  ⇒ |Family| = 108 per side · مسیر C (hold-out): جست‌وجو فقط روی TRAIN=۶۰٪ اول،
  یک آزمون per side روی HOLDOUT؛ حکم فقط از compute_rqs2 با ورودی کامل.

⚡ آنتروپی و corr_t بانک حلقهٔ پایتونی‌اند (روی M1 غیرقابل‌اجرا)؛ این‌جا برداری‌شده‌اند
   و برابری‌شان با بانک در `parity_check()` اثبات می‌شود (خطای نسبی < 1e-9).
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

# ─── خانوادهٔ منجمد (عیناً از پیش‌ثبت — هیچ انحرافی مجاز نیست) ───
ENT_P_GRID = (13, 21, 34)
K_GRID     = (3, 5, 8)
SL_K_GRID  = (0.618, 1.0, 1.618)
RR_GRID    = (1.0, 1.272, 1.618, 2.058)
N_TRIALS   = len(ENT_P_GRID) * len(K_GRID) * len(SL_K_GRID) * len(RR_GRID)   # 108
RANK_W     = 233
HI_TH, LO_TH = 0.786, 0.382
CORR_P     = 21
ATR_P      = 13
HOLD_HOURS = 16.0
SPLIT_FRAC = 0.60
N_PERM     = 500            # K ≥ 500 (الزام H3)
N_UNCOND_CAP = 25000        # زیرنمونهٔ نال بی‌قید (SE_wr ≈ 0.3pp — کافی برای مبنا)
SEED       = 690
ENT_BINS   = 8
ASSET      = 'XAUUSD'
TF_ORDER   = ['M1','M3','M4','M5','M6','M10','M12','M15','M20','M30',
              'H1','H2','H3','H6','H8','H12','D1','W1','MN1']
OUT_DIR    = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'results', 's690_runs')


# ═══════════════ هستهٔ برداری‌شده (با اثبات برابری با بانک) ═══════════════

def returns_like_bank(xv):
    """عین ret بانک: ret[0]=0 و ret[i]=(x[i]-x[i-1])/x[i-1] اگر x[i-1]≠0."""
    ret = np.zeros(len(xv))
    ret[1:] = np.where(xv[:-1] != 0, (xv[1:] - xv[:-1]) / xv[:-1], 0.0)
    return ret


def fast_entropy(xv, p=20, bins=ENT_BINS, chunk=100_000):
    """آنتروپی شانون بانک — برداری‌شده با پنجرهٔ لغزان قطعه‌ای + ترفند bincount."""
    from numpy.lib.stride_tricks import sliding_window_view
    n = len(xv)
    ret = returns_like_bank(xv)
    out = np.full(n, np.nan)
    if n <= p:
        return out
    # پنجرهٔ بانک: ret[i-p+1 : i+1] برای i از p تا n-1
    for lo in range(p, n, chunk):
        hi = min(lo + chunk, n)
        w = sliding_window_view(ret[lo - p + 1:hi], p)       # (hi-lo, p)
        mn = w.min(1); mx = w.max(1)
        rng = mx - mn
        rng[rng == 0] = 1e-10
        idx = np.minimum(bins - 1,
                         ((w - mn[:, None]) / rng[:, None] * bins).astype(np.int64))
        rows = np.arange(idx.shape[0], dtype=np.int64)[:, None]
        flat = (rows * bins + idx).ravel()
        hist = np.bincount(flat, minlength=idx.shape[0] * bins)\
                 .reshape(idx.shape[0], bins)
        pr = hist / float(p)
        with np.errstate(divide='ignore', invalid='ignore'):
            lg = np.where(pr > 0, np.log2(np.where(pr > 0, pr, 1.0)), 0.0)
        out[lo:hi] = -(pr * lg).sum(1)
    return out


def fast_corr_t(xv, p=CORR_P, chunk=250_000):
    """corr_t بانک (پیرسونِ قیمت×زمان) — قطعه‌ای برای رژیم حافظه.

    درس OOM: نسخهٔ تمام-آرایه‌ای روی M1 حدود ۴۰۰MB پیک می‌ساخت و سندباکس را
    کشت. اینجا هر قطعه حداکثر ~۱۶MB موقت مصرف می‌کند. مرکز‌کردن با میانگین
    سراسری، همبستگی را تغییر نمی‌دهد ولی کنسلاسیون عددی روی قیمت ~۲۰۰۰$ را حذف می‌کند."""
    n = len(xv)
    out = np.full(n, np.nan)
    if n < p:
        return out
    mu = float(np.mean(xv))
    t = np.arange(p, dtype=np.float64)
    st, stt = t.sum(), (t * t).sum()
    kern = np.ones(p)
    for lo in range(0, n - p + 1, chunk):
        hi = min(lo + chunk, n - p + 1)
        seg = xv[lo:hi + p - 1].astype(np.float64) - mu       # طول = (hi-lo)+p-1
        sy  = np.convolve(seg, kern, 'valid')
        syy = np.convolve(seg * seg, kern, 'valid')
        sxy = np.correlate(seg, t, 'valid')
        num = p * sxy - st * sy
        den2 = (p * stt - st * st) * (p * syy - sy * sy)
        den = np.sqrt(np.maximum(den2, 0.0))
        out[lo + p - 1:hi + p - 1] = np.where(den > 0,
                                              num / np.where(den > 0, den, 1.0), 0.0)
        del seg, sy, syy, sxy, num, den2, den
    return out


def rolling_rank(x, w=RANK_W, chunk=100_000):
    """رتبهٔ صدکی غلتان: سهمِ مقادیر پنجرهٔ w-تایی (شامل خودِ کندل) که ≤ مقدار فعلی‌اند."""
    from numpy.lib.stride_tricks import sliding_window_view
    n = len(x)
    out = np.full(n, np.nan)
    if n < w:
        return out
    for lo in range(w - 1, n, chunk):
        hi = min(lo + chunk, n)
        win = sliding_window_view(x[lo - w + 1:hi], w)          # (hi-lo, w)
        cur = x[lo:hi][:, None]
        out[lo:hi] = (win <= cur).mean(1)
    return out


def parity_check(n_sample=3000, tol=1e-9):
    """اثبات برابری هسته‌های برداری با بانک (انضباط S670) روی نمونهٔ واقعی طلا."""
    from engine import indicator_bank as ib
    d = fd.load_fast(ASSET, 'H1')
    xv = d['close'][:n_sample].astype(np.float64)
    df = pd.DataFrame({'close': xv})
    ok = True
    for p in ENT_P_GRID:
        a = ib.entropy(df, p=p, bins=ENT_BINS).values
        b = fast_entropy(xv, p=p)
        m = np.isfinite(a) & np.isfinite(b)
        err = np.max(np.abs(a[m] - b[m])) if m.any() else np.inf
        print(f"  parity entropy p={p:>2}: max|Δ|={err:.2e}", flush=True)
        ok &= err < tol
    a = ib.corr_t(df, p=CORR_P).values
    b = fast_corr_t(xv, p=CORR_P)
    m = np.isfinite(a) & np.isfinite(b)
    err = np.max(np.abs(a[m] - b[m])) if m.any() else np.inf
    print(f"  parity corr_t p={CORR_P}: max|Δ|={err:.2e}", flush=True)
    ok &= err < 1e-7        # rolling.apply بانک float64؛ کنولوشن مرتبِ متفاوت
    if not ok:
        raise AssertionError("PARITY FAILED — هسته‌های برداری با بانک نمی‌خوانند؛ اجرا ممنوع")
    print("  ✅ parity OK — هسته‌ها هم‌ارز بانک‌اند", flush=True)


# ═══════════════ منطق استراتژی ═══════════════

def bars_per_hour(time_arr):
    d = np.median(np.diff(time_arr.astype(np.float64)))
    return 3600.0 / d if d > 0 else 1.0


def build_signals(xv, ct, ent_p, warmup):
    """سیگنال‌های فروریزش برای یک ent_p؛ ct از بیرون می‌آید (یک‌بار per TF).
    خروجی dict[k] = (sig_idx, is_long)."""
    ent = fast_entropy(xv, p=ent_p)
    rank = rolling_rank(ent, RANK_W)
    del ent
    gc.collect()
    out = {}
    n = len(xv)
    for k in K_GRID:
        lo_now = rank < LO_TH
        hi_then = np.zeros(n, dtype=bool)
        hi_then[k:] = rank[:-k] > HI_TH
        cond = lo_now & hi_then & np.isfinite(rank)
        cond[:warmup] = False
        idx = np.flatnonzero(cond)
        ctv = ct[idx]
        keep = np.isfinite(ctv) & (ctv != 0)
        idx = idx[keep]
        out[k] = (idx, ct[idx] > 0)
        del lo_now, hi_then, cond
    del rank
    gc.collect()
    return out


def uncond_wr_for_geo(df, valid, atr, k_sl, rr, hold, rng):
    """WR بی‌قید (نال) با هندسهٔ داده‌شده روی زیرنمونهٔ valid — per side."""
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
    """نال اندازه‌گیری‌شده per side با هندسهٔ منجمدِ برندهٔ همان سمت (K=N_PERM)."""
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
    print(f"\n{'='*88}\n=== S690 Entropy-Collapse :: XAUUSD-{tf} ===", flush=True)
    d = fd.load_fast(ASSET, tf)
    # ⚡ رژیم حافظه (درس OOM اجرای اول: rss=755MB → kill در سندباکس 985MB):
    #   فقط time/ohlc لازم است؛ volume/hour/minute/dow روی M1 یعنی 160MB مرده.
    for _k in ('volume', 'hour', 'minute', 'dow'):
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
    warmup = max(RANK_W + max(ENT_P_GRID) + max(K_GRID), 4 * ATR_P, 300)
    split = int(n * SPLIT_FRAC)
    c = cost_pip(ASSET)
    print(f"    hold={hold} bars (16h @ {bph:.3f} bph) · warmup={warmup} · "
          f"split_bar={split} · cost={c:.2f}pip", flush=True)

    out = dict(strategy='S690', concept='entropy_collapse', asset=ASSET, tf=tf,
               bars=n, src=src, hold_bars=hold, split_bar=split,
               n_trials=N_TRIALS, family='3x3x3x4=108/side', cost_pip=c)

    if n < warmup + 500:
        out['verdict'] = 'TOO_SHORT'
        _save(tf, out, do_git); return out

    rng = np.random.default_rng(SEED)

    # ── ۱) سیگنال‌ها برای ۹ پیکربندی (ent_p × k) — corr_t فقط یک‌بار ──
    xv = d['close'].astype(np.float64) if d['close'].dtype != np.float64 \
        else d['close']
    ct = fast_corr_t(xv, p=CORR_P)
    sig_map = {}
    for ep in ENT_P_GRID:
        sm = build_signals(xv, ct, ep, warmup)
        for k, v in sm.items():
            sig_map[(ep, k)] = v
        print(f"    signals ent_p={ep}: " +
              " ".join(f"k={k}:{len(sm[k][0])}" for k in K_GRID), flush=True)
    del ct
    gc.collect()

    # ── ۲) نال بی‌قید TRAIN per geometry (برای lift جست‌وجو) ──
    valid_all = np.arange(warmup, n - hold - 2)
    fin = np.isfinite(atr[valid_all]) & (atr[valid_all] > 0)
    valid_all = valid_all[fin]
    valid_tr = valid_all[valid_all < split]
    geo_null_tr = {}
    for k_sl in SL_K_GRID:
        for rr in RR_GRID:
            geo_null_tr[(k_sl, rr)] = uncond_wr_for_geo(
                df, valid_tr, atr, k_sl, rr, hold, rng)

    # ── ۳) جست‌وجوی ۱۰۸ سلول per side — فقط TRAIN ──
    best = {'long': None, 'short': None}
    scan = []
    for (ep, k), (sig, is_long) in sig_map.items():
        m_tr = sig < split - hold
        sig_tr, dir_tr = sig[m_tr], is_long[m_tr]
        for k_sl in SL_K_GRID:
            for rr in RR_GRID:
                for side, flag in (('long', True), ('short', False)):
                    ss = sig_tr[dir_tr == flag]
                    if len(ss) < 5:
                        continue
                    sl = k_sl * atr[ss]
                    ok = np.isfinite(sl) & (sl > 0)
                    st = queue_rr(df, ss[ok], np.full(ok.sum(), flag),
                                  sl[ok], ASSET, hold, rr)
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
                    scan.append(dict(ep=ep, k=k, k_sl=k_sl, rr=rr, side=side,
                                     n=st['n'], wr=round(st['wr'], 2),
                                     u=round(u_wr, 2), lift=round(lift, 2),
                                     exp=round(st['exp'], 2), feas=bool(feas)))
                    if feas and (best[side] is None or score > best[side][0]):
                        best[side] = (score, ep, k, k_sl, rr, st['n'], lift)
    out['train_scan_top'] = sorted(scan, key=lambda r: -(r['lift'] *
                                   np.sqrt(r['n']) if r['lift'] > 0 else -1e9))[:12]
    for side in ('long', 'short'):
        print(f"    TRAIN winner {side}: {best[side]}", flush=True)
    out['winner'] = {s: (None if best[s] is None else dict(
        zip(('score', 'ent_p', 'k', 'k_sl', 'rr', 'n_train', 'lift_train'),
            [round(float(x), 3) if isinstance(x, (int, float, np.floating))
             else x for x in best[s]]))) for s in ('long', 'short')}

    if best['long'] is None and best['short'] is None:
        out['verdict'] = 'REJECT (no feasible cell on TRAIN — glass ceiling)'
        _save(tf, out, do_git); return out

    # ── ۴) اجرای کامل سلول برنده (کل داده) + نال + حکم RQS2 ──
    frames, geo_by_side, n_by_side = [], {}, {'long': 0, 'short': 0}
    for side, flag in (('long', True), ('short', False)):
        if best[side] is None:
            geo_by_side[side] = (1.0, 1.0)
            continue
        _, ep, k, k_sl, rr, _, _ = best[side]
        geo_by_side[side] = (k_sl, rr)
        sig, is_long = sig_map[(ep, k)]
        ss = sig[is_long == flag]
        sl = k_sl * atr[ss]
        ok = np.isfinite(sl) & (sl > 0)
        st = queue_rr(df, ss[ok], np.full(ok.sum(), flag), sl[ok], ASSET, hold, rr)
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
          f"S={n_by_side['short']}) sl_med={sl_med:.1f} tp_med={tp_med:.1f}", flush=True)

    null = build_null(df, valid_all, atr, geo_by_side, n_by_side, hold, rng)

    bar_time = d['time']
    close = d['close'].astype(np.float64)
    r = rqs2.compute_rqs2(trades, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=bar_time, null=null, n_trials=N_TRIALS,
                          split_bar=split, close=close)
    print(rqs2.format_rqs2(f'S690 {tf} ', r), flush=True)

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
            subprocess.run(['git', 'add', 'results/s690_runs'], cwd=root, check=True)
            subprocess.run(['git', 'commit', '-m',
                            f"S690 incremental: XAUUSD-{tf} → {out.get('verdict','?')}"],
                           cwd=root, capture_output=True)
            subprocess.run(['git', 'push', 'origin', 'main'], cwd=root,
                           capture_output=True, timeout=60)
            print(f"    git ✓ pushed XAUUSD-{tf}", flush=True)
        except Exception as e:                                   # noqa: BLE001
            print(f"    git ✗ {e} (ادامه می‌دهیم — قانون افزایشی)", flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--tfs', nargs='*', default=TF_ORDER)
    ap.add_argument('--no-git', action='store_true')
    ap.add_argument('--skip-parity', action='store_true')
    a = ap.parse_args()
    if not a.skip_parity:
        print("— parity check (هسته‌های برداری vs بانک) —", flush=True)
        parity_check()
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
    print("\n=== S690 sweep complete ===", flush=True)
