# =============================================================================
# S954 — «آغازِ رژیمِ روند به روایتِ نسبتِ واریانس» (Lo–MacKinlay VR Onset)
# پیش‌ثبت: results/S954_PREREG_variance_ratio_onset.md (قبل از هر آزمون)
# دانشمند: Robert Merton (باند S950–S959)
#
# VR_q(t) = Var_W(q-bar returns ending ≤ t−1) / (q · Var_W(1-bar returns ≤ t−1))
# رویداد: VR_q(t) ≥ v و VR_q(t−1) < v (گذر تازه) ؛ follow = جهت drift_W ؛ fade = خلاف
# خانواده: q{5,8} × W{89,144} × v{1.272,1.618} × mode{follow,fade} = 16
# هندسه قفل از S950: SL=TP=2.058×ATR(89) (SMA-TR شیفت ۱) · mh=34 · بدون همپوشانی
# null کانونی RQS2 · دو-گذری کم‌حافظه · واریانس‌های غلتان با cumsum (O(n))
# =============================================================================
import sys, os, json, gc
sys.path.insert(0, '/home/user/webapp')
os.chdir('/home/user/webapp')
import numpy as np

from engine import scalp_engine as se, rqs2
from tools import s434_fast_data as fd
from strategies.s951_compression_breakout import zproxy, build_null_perm  # کانونی

ATR_WIN = 89
MAX_HOLD = 34
SL_K = 2.058
RR = 1.0
Q_LIST = [5, 8]
W_LIST = [89, 144]
V_LIST = [1.272, 1.618]
MODES = ['follow', 'fade']
N_TRIALS = 16                            # پیش‌ثبت
SEED = 20260905
K_PERM = 2000
SPLIT_FRAC = 0.7

OUT_DIR = 'results/_scan_S954'
os.makedirs(OUT_DIR, exist_ok=True)

TFS = ['D1', 'H12', 'H8', 'H6', 'H4', 'H3', 'H2', 'H1', 'M30', 'M20', 'M15',
       'M12', 'M10', 'M6', 'M5', 'M4', 'M3', 'M2', 'M1']


def sma_causal(x, p):
    kern = np.ones(p) / p
    return np.convolve(x, kern, mode='full')[:len(x)]


def rolling_var_causal(x, W):
    """واریانسِ نمونهٔ W مقدارِ آخرِ x **تا اندیس t−1** (خروجی در t). قبل از وارم‌آپ NaN."""
    n = len(x)
    cs = np.concatenate(([0.0], np.cumsum(x)))
    cs2 = np.concatenate(([0.0], np.cumsum(x * x)))
    out = np.full(n, np.nan)
    # پنجره [t−W, t−1] ⇒ جمع = cs[t] − cs[t−W]
    t = np.arange(W, n)
    s = cs[t] - cs[t - W]
    s2 = cs2[t] - cs2[t - W]
    var = (s2 - s * s / W) / (W - 1)
    out[W:] = np.maximum(var, 0.0)
    del cs, cs2, s, s2, var
    return out


def features(df):
    c = df['close'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    n = len(c)
    r = np.zeros(n)
    r[1:] = np.log(c[1:] / c[:-1])
    tr_arr = np.zeros(n)
    tr_arr[1:] = np.maximum.reduce([h[1:] - l[1:],
                                    np.abs(h[1:] - c[:-1]),
                                    np.abs(l[1:] - c[:-1])])
    atr_full = sma_causal(tr_arr, ATR_WIN)
    atr = np.zeros(n)
    atr[1:] = atr_full[:-1]
    del tr_arr, atr_full
    gc.collect()
    return c, r, atr


def variance_ratio(r, q, W):
    """VR_q(t) با پنجرهٔ W (همه تا t−1). rq_t = Σ_{j=0}^{q−1} r_{t−j} (بازدهِ q-کندلیِ منتهی به t)."""
    n = len(r)
    cs = np.concatenate(([0.0], np.cumsum(r)))
    rq = np.zeros(n)
    rq[q:] = cs[q + 1:] - cs[1:n - q + 1]          # Σ r_{t−q+1..t}
    del cs
    v1 = rolling_var_causal(r, W)
    vq = rolling_var_causal(rq, W)                  # پنجره‌های همپوشان — استاندارد Lo–MacKinlay
    del rq
    vr = np.full(n, np.nan)
    ok = np.isfinite(v1) & np.isfinite(vq) & (v1 > 0)
    vr[ok] = vq[ok] / (q * v1[ok])
    # وارم‌آپ: rq فقط از q معتبر است ⇒ اولین پنجرهٔ سالم از q+W
    vr[:q + W + 1] = np.nan
    del v1, vq, ok
    return vr


def drift_sign(c, W):
    n = len(c)
    ds = np.zeros(n, dtype=np.int8)
    ds[W + 1:] = np.sign(c[W:-1] - c[:-(W + 1)]).astype(np.int8)
    return ds


def member_signals(vr, ds, v, mode):
    n = len(vr)
    prev = np.full(n, np.nan); prev[1:] = vr[:-1]
    cross = np.isfinite(vr) & np.isfinite(prev) & (vr >= v) & (prev < v)
    del prev
    up = cross & (ds > 0)
    dn = cross & (ds < 0)
    if mode == 'follow':
        return up, dn
    return dn, up


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
        d.pop(kx, None)
    gc.collect()
    df = fd.as_dataframe(d)
    pip = se.ASSETS['XAUUSD']['pip']
    c, r, atr = features(df)
    sl64 = np.maximum(SL_K * atr / pip, 1e-9)
    tp64 = sl64 if RR == 1.0 else sl64 * RR
    del atr; gc.collect()
    n = len(r)

    best = None; members = []
    for W in W_LIST:
        ds = drift_sign(c, W)
        for q in Q_LIST:
            vr = variance_ratio(r, q, W)
            for v in V_LIST:
                for mode in MODES:
                    ls, ss = member_signals(vr, ds, v, mode)
                    n_sig = int(ls.sum() + ss.sum())
                    if n_sig < 30:
                        members.append(dict(q=q, W=W, v=v, mode=mode, n_sig=n_sig, z=-99))
                        del ls, ss; continue
                    tr = se.simulate_trades(df, ls, ss, sl64, tp64, 'XAUUSD',
                                            max_hold=MAX_HOLD, allow_overlap=False)
                    del ls, ss
                    sl_med = float(np.median(tr['sl_pip'].values)) if len(tr) else 0.0
                    z, info = zproxy(tr, sl_med, sl_med * RR)
                    members.append(dict(q=q, W=W, v=v, mode=mode, n_sig=n_sig,
                                        z=round(z, 2), **(info or {})))
                    if best is None or z > best['z']:
                        best = dict(q=q, W=W, v=v, mode=mode, z=z, sl_med=sl_med)
                    del tr; gc.collect()
            del vr; gc.collect()
        del ds; gc.collect()

    res = dict(tf=tf, src=d['src'], n_bars=n, members=members)
    if best is None or best['z'] < 1.0:
        res['verdict'] = 'NO-CANDIDATE'
        res['best'] = None if best is None else {x: best[x] for x in ('q', 'W', 'v', 'mode', 'z')}
    else:
        ds = drift_sign(c, best['W'])
        vr = variance_ratio(r, best['q'], best['W'])
        ls, ss = member_signals(vr, ds, best['v'], best['mode'])
        del ds, vr, r; gc.collect()
        tr = se.simulate_trades(df, ls, ss, sl64, tp64, 'XAUUSD',
                                max_hold=MAX_HOLD, allow_overlap=False)
        del sl64, tp64; gc.collect()
        null = build_null_perm(df, ls, ss, MAX_HOLD, K=K_PERM, seed=SEED)
        res['entry_idx'] = np.where(ls | ss)[0].tolist()
        del ls, ss; gc.collect()
        split = int(n * SPLIT_FRAC)
        rq = rqs2.compute_rqs2(tr, 'XAUUSD', sl_pip=best['sl_med'],
                               tp_pip=best['sl_med'] * RR,
                               bar_time=df['time'].values, null=null,
                               n_trials=N_TRIALS, split_bar=split,
                               close=df['close'].values)
        mtr = rq['metrics']
        res['verdict'] = rq['verdict']; res['rqs2_score'] = rq['rqs2_score']
        res['gates'] = {g: (None if x is None else bool(x)) for g, x in rq['gates'].items()}
        res['best'] = dict(q=best['q'], W=best['W'], v=best['v'], mode=best['mode'],
                           z_proxy=round(best['z'], 2), n=len(tr),
                           wr=round(100 * float((tr['pnl_pip'] > 0).mean()), 2),
                           sl_med=round(best['sl_med'], 1),
                           skill_z=mtr.get('skill_z'), lift_pp=mtr.get('skill_lift_pp'),
                           p_perm=mtr.get('skill_p_perm'),
                           pf=mtr.get('profit_factor'), maxdd=mtr.get('max_dd_pct'))
    json.dump(res, open(out_path, 'w'), ensure_ascii=False, indent=1, default=str)
    print(f"[{tf}] {res['verdict']} score={res.get('rqs2_score')} best={res.get('best')}", flush=True)


if __name__ == '__main__':
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    for tf in (only or TFS):
        judge_tf(tf)
        gc.collect()
    print('S954 scan تمام شد.', flush=True)
