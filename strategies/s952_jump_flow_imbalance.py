# =============================================================================
# S952 — «عدم‌توازن جریان جهش» (Jump Flow Imbalance)
# پیش‌ثبت: results/S952_PREREG_jump_flow_imbalance.md (قبل از هر آزمون)
# دانشمند: Robert Merton (باند S950–S959)
#
# خانواده: k∈{2.0,2.6} × L∈{34,89} × m∈{2,3} × mode∈{continuation,fade} = 16 عضو
# قاعده: J(t)=Σ جهش‌های مثبت−منفی در پنجرهٔ L؛ سیگنال = گذرِ تازهٔ |J| از m.
# هندسه قفل از S950: SL=TP=2.058×ATR(89) (SMA-ATR شیفت ۱) · mh=34 · tek-trade
# داوری: بهترین عضو هر TF با z-پروکسی، سپس compute_rqs2 (gates-only verbatim).
# حافظه: چانک permutation (CH=50)، del+gc تهاجمی — درس OOMهای S951 روی M1.
# =============================================================================
import sys, os, json, gc
sys.path.insert(0, '/home/user/webapp')
os.chdir('/home/user/webapp')
import numpy as np

from engine import scalp_engine as se, rqs2
from tools import s434_fast_data as fd
# توابع اثبات‌شده از S951 (همان قالب null که موتور rqs2 پذیرفت) — بازنویسی نمی‌کنیم
from strategies.s951_compression_breakout import zproxy, build_null_perm

BV_WIN = 89
MAX_HOLD = 34
SL_K = 2.058
RR = 1.0
K_LIST = [2.0, 2.6]
L_LIST = [34, 89]
M_LIST = [2, 3]
MODES = ['continuation', 'fade']
N_TRIALS = 16                            # پیش‌ثبت
SEED = 20260904
K_PERM = 2000
SPLIT_FRAC = 0.7

OUT_DIR = 'results/_scan_S952'
os.makedirs(OUT_DIR, exist_ok=True)

TFS = ['D1', 'H12', 'H8', 'H6', 'H4', 'H3', 'H2', 'H1', 'M30', 'M20', 'M15',
       'M12', 'M10', 'M6', 'M5', 'M4', 'M3', 'M2', 'M1']


def sma_causal(x, p):
    """np.convolve(x, ones(p)/p, 'full')[:len(x)] — عین S950 (جمع جزئی ÷ p)."""
    kern = np.ones(p) / p
    return np.convolve(x, kern, mode='full')[:len(x)]


def features(df):
    """r، σ_BV علّی (ایندکس عین S950: bv[t]=bv_full[t−2]) و ATR(89) علّی."""
    c = df['close'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    n = len(c)
    r = np.zeros(n)
    r[1:] = np.log(c[1:] / c[:-1])
    absr = np.abs(r)
    prod = absr[1:] * absr[:-1]
    bv_full = sma_causal(prod, BV_WIN)
    bv = np.zeros(n)
    bv[2:] = bv_full[:n - 2]                     # علّی: فقط تا t−1
    sigma = np.sqrt(np.maximum(bv * (np.pi / 2.0), 0.0))
    del absr, prod, bv_full, bv
    tr_arr = np.zeros(n)
    tr_arr[1:] = np.maximum.reduce([h[1:] - l[1:],
                                    np.abs(h[1:] - c[:-1]),
                                    np.abs(l[1:] - c[:-1])])
    atr_full = sma_causal(tr_arr, BV_WIN)
    atr = np.zeros(n)
    atr[1:] = atr_full[:-1]                      # شیفت ۱
    del tr_arr, atr_full
    gc.collect()
    return r, sigma, atr


def jump_counter(r, sigma, k, L):
    """J(t) = تعداد جهش‌های + منهای − در پنجرهٔ [t−L+1..t] (شامل t) — int16."""
    s = np.where(sigma > 0,
                 (r > k * sigma).astype(np.int16) - (r < -k * sigma).astype(np.int16),
                 0).astype(np.int16)
    cs = np.cumsum(s, dtype=np.int32)
    J = cs.copy()
    J[L:] = cs[L:] - cs[:-L]
    del s, cs
    return J.astype(np.int16)


def member_signals(J, m, mode, warm):
    """گذر تازه: J از m عبور کند (این کندل ≥m، قبلی <m). شیفت ۱ روی J قبلی."""
    n = len(J)
    idx_ok = np.arange(n) >= warm
    prev = np.empty(n, dtype=np.int16)
    prev[0] = 0
    prev[1:] = J[:-1]
    cross_up = idx_ok & (J >= m) & (prev < m)
    cross_dn = idx_ok & (J <= -m) & (prev > -m)
    del prev
    if mode == 'continuation':
        return cross_up, cross_dn
    return cross_dn, cross_up


def judge_tf(tf):
    out_path = f'{OUT_DIR}/{tf}.json'
    if os.path.exists(out_path):
        print(f'[{tf}] checkpoint موجود — رد می‌شوم', flush=True)
        return
    try:
        d = fd.load_fast('XAUUSD', tf)
    except Exception as ex:
        json.dump(dict(tf=tf, error=str(ex)), open(out_path, 'w'), ensure_ascii=False)
        print(f'[{tf}] ERROR: {ex}', flush=True)
        return
    for kx in ('hour', 'minute', 'dow'):
        if kx in d:
            del d[kx]
    gc.collect()
    df = fd.as_dataframe(d)
    pip = se.ASSETS['XAUUSD']['pip']
    r, sigma, atr = features(df)
    sl64 = np.maximum(SL_K * atr / pip, 1e-9)
    tp64 = sl64 if RR == 1.0 else sl64 * RR   # RR=1 ⇒ ارجاع، نه کپی (۴۰MB صرفه در M1)
    del atr; gc.collect()
    n = len(r)

    # ── گذر ۱: کشف — فقط پارامترهای برنده نگه داشته می‌شود ──
    best = None; members = []
    for k in K_LIST:
        for L in L_LIST:
            J = jump_counter(r, sigma, k, L)
            warm = BV_WIN + 2 + L
            for m in M_LIST:
                for mode in MODES:
                    ls, ss = member_signals(J, m, mode, warm)
                    n_sig = int(ls.sum() + ss.sum())
                    if n_sig < 30:
                        members.append(dict(k=k, L=L, m=m, mode=mode, n_sig=n_sig, z=-99))
                        del ls, ss; continue
                    tr = se.simulate_trades(df, ls, ss, sl64, tp64, 'XAUUSD',
                                            max_hold=MAX_HOLD, allow_overlap=False)
                    del ls, ss
                    sl_med = float(np.median(tr['sl_pip'].values)) if len(tr) else 0.0
                    z, info = zproxy(tr, sl_med, sl_med * RR)
                    members.append(dict(k=k, L=L, m=m, mode=mode, n_sig=n_sig,
                                        z=round(z, 2), **(info or {})))
                    if best is None or z > best['z']:
                        best = dict(k=k, L=L, m=m, mode=mode, z=z, sl_med=sl_med)
                    del tr; gc.collect()
            del J; gc.collect()

    res = dict(tf=tf, src=d['src'], n_bars=n, members=members)
    if best is None or best['z'] < 1.0:
        res['verdict'] = 'NO-CANDIDATE'
        res['best'] = None if best is None else {x: best[x] for x in ('k', 'L', 'm', 'mode', 'z')}
    else:
        # ── گذر ۲: بازاجرای فقط برنده + rqs2 ──
        J = jump_counter(r, sigma, best['k'], best['L'])
        warm = BV_WIN + 2 + best['L']
        ls, ss = member_signals(J, best['m'], best['mode'], warm)
        del J, r, sigma; gc.collect()
        tr = se.simulate_trades(df, ls, ss, sl64, tp64, 'XAUUSD',
                                max_hold=MAX_HOLD, allow_overlap=False)
        del sl64, tp64; gc.collect()
        null = build_null_perm(df, ls, ss, MAX_HOLD, K=K_PERM, seed=SEED)
        del ls, ss; gc.collect()
        split = int(n * SPLIT_FRAC)
        rq = rqs2.compute_rqs2(tr, 'XAUUSD', sl_pip=best['sl_med'],
                               tp_pip=best['sl_med'] * RR,
                               bar_time=df['time'].values, null=null,
                               n_trials=N_TRIALS, split_bar=split,
                               close=df['close'].values)
        mtr = rq['metrics']
        res['verdict'] = rq['verdict']; res['rqs2_score'] = rq['rqs2_score']
        res['gates'] = {g: (None if v is None else bool(v)) for g, v in rq['gates'].items()}
        res['best'] = dict(k=best['k'], L=best['L'], m=best['m'], mode=best['mode'],
                           z_proxy=round(best['z'], 2), n=len(tr),
                           wr=round(100 * float((tr['pnl_pip'] > 0).mean()), 2),
                           sl_med=round(best['sl_med'], 1),
                           skill_z=mtr.get('skill_z'),
                           lift_pp=mtr.get('skill_lift_pp'),
                           p_perm=mtr.get('skill_p_perm'))
    json.dump(res, open(out_path, 'w'), ensure_ascii=False, indent=1, default=str)
    print(f"[{tf}] {res['verdict']} best={res.get('best')}", flush=True)


if __name__ == '__main__':
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for tf in TFS:
        if only and tf != only:
            continue
        judge_tf(tf)
        gc.collect()
    print('S952 scan تمام شد.', flush=True)
