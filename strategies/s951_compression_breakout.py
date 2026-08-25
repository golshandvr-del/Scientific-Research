# =============================================================================
# S951 — «آرامش پیش از طوفان»: فشردگیِ σ_BV → شکستِ جهت‌دار
# پیش‌ثبت: results/S951_PREREG_compression_breakout.md (قبل از هر آزمون)
# دانشمند: Robert Merton (باند S950–S959)
#
# خانواده: q∈{0.5,0.618,0.786} × W∈{21,34} × mode∈{continuation,fade} = 12 عضو
# هندسه قفل از S950: SL=TP=2.058×ATR(89) (SMA-ATR شیفتِ ۱) · mh=34 · tek-trade
# داوری: بهترین عضوِ هر TF با z-پروکسی، سپس compute_rqs2 (gates-only verbatim).
# حافظه: چانکِ permutation (CH=50) + آزادسازیِ صریح — درسِ OOMهای S950 روی M1.
# =============================================================================
import sys, os, json, gc
sys.path.insert(0, '/home/user/webapp')
os.chdir('/home/user/webapp')
import numpy as np

from engine import scalp_engine as se, rqs2
from tools import s434_fast_data as fd

BV_SHORT = 21
BV_LONG = 89
MAX_HOLD = 34
SL_K = 2.058
RR = 1.0
WARM = BV_LONG + 2                       # 91 — عینِ S950
Q_LIST = [0.5, 0.618, 0.786]
W_LIST = [21, 34]
MODES = ['continuation', 'fade']
N_TRIALS = 12                            # پیش‌ثبت
SEED = 20260825
K_PERM = 2000
SPLIT_FRAC = 0.7

OUT_DIR = 'results/_scan_S951'
os.makedirs(OUT_DIR, exist_ok=True)

TFS = ['M1', 'M2', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20', 'M30',
       'H1', 'H2', 'H3', 'H4', 'H6', 'H8', 'H12', 'D1']


def sma_causal(x, p):
    """np.convolve(x, ones(p)/p, 'full')[:len(x)] — عینِ S950 (جمعِ جزئی ÷ p)."""
    kern = np.ones(p) / p
    return np.convolve(x, kern, mode='full')[:len(x)]


def features(df):
    """σ_short/σ_long (Bipower علّی، ایندکسِ عینِ S950) + ATR(89) علّی بر pip."""
    c = df['close'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    n = len(c)
    r = np.zeros(n)
    r[1:] = np.log(c[1:] / c[:-1])
    absr = np.abs(r)
    prod = absr[1:] * absr[:-1]
    sig = {}
    for p, tag in ((BV_SHORT, 'short'), (BV_LONG, 'long')):
        bv_full = sma_causal(prod, p)
        bv = np.zeros(n)
        bv[2:] = bv_full[:n - 2]                 # علّی: فقط تا t−1
        sig[tag] = np.sqrt(np.maximum(bv * (np.pi / 2.0), 0.0))
        del bv_full, bv
    del absr, prod
    tr_arr = np.zeros(n)
    tr_arr[1:] = np.maximum.reduce([h[1:] - l[1:],
                                    np.abs(h[1:] - c[:-1]),
                                    np.abs(l[1:] - c[:-1])])
    atr_full = sma_causal(tr_arr, BV_LONG)
    atr = np.zeros(n)
    atr[1:] = atr_full[:-1]                      # شیفتِ ۱
    del tr_arr, atr_full
    gc.collect()
    return c, sig['short'], sig['long'], atr


def rolling_extrema(c, W):
    """hi/lo پنجرهٔ [t−W, t−1] (شیفتِ ۱) — برداری با sliding_window_view."""
    n = len(c)
    hi = np.full(n, np.inf)
    lo = np.full(n, -np.inf)
    if n <= W:
        return hi, lo
    sw = np.lib.stride_tricks.sliding_window_view(c, W)   # sw[j] = c[j..j+W-1]
    # پنجرهٔ [t−W..t−1] = sw[t−W] ⇒ برای t از W تا n−1
    hi[W:] = sw[:n - W].max(axis=1)
    lo[W:] = sw[:n - W].min(axis=1)
    return hi, lo


def member_signals(c, s_short, s_long, hi, lo, q, mode):
    n = len(c)
    valid = (np.arange(n) >= WARM) & (s_long > 0)
    compressed = valid & (s_short < q * s_long)
    brk_up = compressed & (c > hi)
    brk_dn = compressed & (c < lo)
    if mode == 'continuation':
        return brk_up, brk_dn
    return brk_dn, brk_up


def zproxy(tr, sl_med, tp_med, cost=3.3):
    if tr is None or len(tr) < 30:
        return -99.0, None
    n = len(tr)
    wr = float((tr['pnl_pip'] > 0).mean())
    be = (sl_med + cost) / (sl_med + tp_med)
    z = (wr - be) * np.sqrt(n) / max(np.sqrt(be * (1 - be)), 1e-9)
    return float(z), dict(n=n, wr=round(wr * 100, 2), be=round(be * 100, 2))


def build_null_perm(df, ls, ss, hold, K=K_PERM, seed=SEED, CH=50):
    """مدلِ صفرِ جایگشتی — چانکی (درسِ حافظهٔ S950 روی M1)."""
    c = df['close'].values.astype(np.float64)
    n = len(c)
    idx_l = np.where(ls)[0]
    idx_s = np.where(ss)[0]
    rng = np.random.default_rng(seed)
    fwd = np.zeros(n)
    e = np.minimum(np.arange(n) + hold, n - 1)
    fwd = c[e] - c
    pool = np.arange(WARM, n - hold - 1)
    stats = []
    for side, idx, sgn in (('L', idx_l, 1.0), ('S', idx_s, -1.0)):
        m = len(idx)
        if m == 0:
            continue
        real = float(np.mean(sgn * fwd[idx]))
        null_means = np.empty(K)
        done = 0
        while done < K:
            b = min(CH, K - done)
            samp = rng.choice(pool, size=(b, m), replace=True)
            null_means[done:done + b] = (sgn * fwd[samp]).mean(axis=1)
            del samp
            done += b
        p = float((null_means >= real).mean())
        stats.append(dict(side=side, m=m, real=real, p=p,
                          null_mu=float(null_means.mean()),
                          null_sd=float(null_means.std())))
        del null_means
    gc.collect()
    return dict(kind='perm', K=K, seed=seed, stats=stats)


def judge_tf(tf):
    out_path = f'{OUT_DIR}/{tf}.json'
    if os.path.exists(out_path):
        print(f'[{tf}] چک‌پوینت موجود — رد', flush=True)
        return
    try:
        d = fd.load_fast('XAUUSD', tf)
    except Exception as ex:
        json.dump(dict(tf=tf, error=str(ex)), open(out_path, 'w'))
        return
    df = fd.as_dataframe(d)
    pip = se.ASSETS['XAUUSD']['pip']
    c, s_short, s_long, atr = features(df)
    sl_arr = np.maximum(SL_K * atr / pip, 1e-9)
    ext = {W: rolling_extrema(c, W) for W in W_LIST}

    best = None
    members = []
    for q in Q_LIST:
        for W in W_LIST:
            hi, lo = ext[W]
            for mode in MODES:
                ls, ss = member_signals(c, s_short, s_long, hi, lo, q, mode)
                n_sig = int(ls.sum() + ss.sum())
                if n_sig < 30:
                    members.append(dict(q=q, W=W, mode=mode, n_sig=n_sig, z=-99))
                    continue
                tr = se.simulate_trades(df, ls, ss, sl_arr, sl_arr * RR,
                                        'XAUUSD', max_hold=MAX_HOLD,
                                        allow_overlap=False)
                sl_med = float(np.median(tr['sl_pip'].values)) if len(tr) else 0
                z, info = zproxy(tr, sl_med, sl_med * RR)
                members.append(dict(q=q, W=W, mode=mode, n_sig=n_sig,
                                    z=round(z, 2), **(info or {})))
                if best is None or z > best['z']:
                    best = dict(q=q, W=W, mode=mode, z=z, tr=tr,
                                ls=ls.copy(), ss=ss.copy(), sl_med=sl_med)
                del tr
    res = dict(tf=tf, src=d['src'], n_bars=len(df), members=members)
    if best is None or best['z'] < 1.0:
        res['verdict'] = 'NO-CANDIDATE'
        res['best'] = None if best is None else {k: best[k] for k in
                                                 ('q', 'W', 'mode', 'z')}
    else:
        tr = best['tr']
        null = build_null_perm(df, best['ls'], best['ss'], MAX_HOLD)
        split = int(len(df) * SPLIT_FRAC)
        rq = rqs2.compute_rqs2(tr, 'XAUUSD', sl_pip=best['sl_med'],
                               tp_pip=best['sl_med'] * RR,
                               bar_time=df['time'].values, null=null,
                               n_trials=N_TRIALS, split_bar=split,
                               close=df['close'].values)
        m = rq['metrics']
        res['verdict'] = rq['verdict']
        res['rqs2_score'] = rq['rqs2_score']
        res['gates'] = {g: (None if v is None else bool(v))
                        for g, v in rq['gates'].items()}
        res['best'] = dict(q=best['q'], W=best['W'], mode=best['mode'],
                           z_proxy=round(best['z'], 2), n=len(tr),
                           wr=round(100 * float((tr['pnl_pip'] > 0).mean()), 2),
                           sl_med=round(best['sl_med'], 1),
                           skill_z=m.get('skill_z'),
                           lift_pp=m.get('skill_lift_pp'),
                           p_perm=m.get('skill_p_perm'))
    json.dump(res, open(out_path, 'w'), ensure_ascii=False, indent=1,
              default=str)
    print(f"[{tf}] {res['verdict']} best={res.get('best')}", flush=True)
    del df, c, s_short, s_long, atr, sl_arr, ext, best
    gc.collect()


def main():
    order = TFS[::-1]                    # از D1 (سبک) به M1 (سنگین)
    for tf in order:
        judge_tf(tf)
    print('S951 scan تمام شد.', flush=True)


if __name__ == '__main__':
    main()
