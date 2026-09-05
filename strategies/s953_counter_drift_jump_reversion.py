# =============================================================================
# S953 — «بازگشت پس از جهشِ خلافِ رانش» (Counter-Drift Jump Reversion)
# پیش‌ثبت: results/S953_PREREG_counter_drift_jump_reversion.md (قبل از هر آزمون)
# دانشمند: Robert Merton (باند S950–S959)
#
# خانواده: k∈{2.6,3.4} × D∈{89,180} × timing∈{t0,t1} × mode∈{revert,continue} = 16
# رویداد: |r_t|>k·σ_t و sign(r_t)≠sign(drift_D(t)) ، drift_D(t)=c[t−1]−c[t−1−D]
# revert = ورود در جهتِ رانش (خلافِ جهش) · continue = کنترلِ داخلی (جهتِ جهش)
# t0 = ورود بعد از کندلِ جهش · t1 = یک کندل بعد، فقط اگر کندل t+1 جهش را ادامه نداده باشد
# هندسه قفل از S950: SL=TP=2.058×ATR(89) (SMA-TR شیفت ۱) · mh=34 · بدون همپوشانی
# null کانونی RQS2 (درسِ ERRATUM S951/S952) · دو-گذری کم‌حافظه (درسِ M1)
# =============================================================================
import sys, os, json, gc
sys.path.insert(0, '/home/user/webapp')
os.chdir('/home/user/webapp')
import numpy as np

from engine import scalp_engine as se, rqs2
from tools import s434_fast_data as fd
from strategies.s951_compression_breakout import zproxy, build_null_perm  # کانونی (اصلاح‌شده)

BV_WIN = 89
MAX_HOLD = 34
SL_K = 2.058
RR = 1.0
K_LIST = [2.6, 3.4]
D_LIST = [89, 180]
TIMINGS = ['t0', 't1']
MODES = ['revert', 'continue']
N_TRIALS = 16                            # پیش‌ثبت
SEED = 20260905
K_PERM = 2000
SPLIT_FRAC = 0.7

OUT_DIR = 'results/_scan_S953'
os.makedirs(OUT_DIR, exist_ok=True)

TFS = ['D1', 'H12', 'H8', 'H6', 'H4', 'H3', 'H2', 'H1', 'M30', 'M20', 'M15',
       'M12', 'M10', 'M6', 'M5', 'M4', 'M3', 'M2', 'M1']


def sma_causal(x, p):
    kern = np.ones(p) / p
    return np.convolve(x, kern, mode='full')[:len(x)]


def features(df):
    """r، σ_BV علّی (bv[t]=bv_full[t−2]) و ATR(89) علّی — عین S950."""
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
    bv[2:] = bv_full[:n - 2]
    sigma = np.sqrt(np.maximum(bv * (np.pi / 2.0), 0.0))
    del absr, prod, bv_full, bv
    tr_arr = np.zeros(n)
    tr_arr[1:] = np.maximum.reduce([h[1:] - l[1:],
                                    np.abs(h[1:] - c[:-1]),
                                    np.abs(l[1:] - c[:-1])])
    atr_full = sma_causal(tr_arr, BV_WIN)
    atr = np.zeros(n)
    atr[1:] = atr_full[:-1]
    del tr_arr, atr_full
    gc.collect()
    return c, r, sigma, atr


def drift_sign(c, D):
    """sign(c[t−1] − c[t−1−D]) — int8، صفر تا وارم‌آپ."""
    n = len(c)
    ds = np.zeros(n, dtype=np.int8)
    ds[D + 1:] = np.sign(c[D:-1] - c[:-(D + 1)]).astype(np.int8)
    return ds


def member_signals(r, sigma, ds, k, D, timing, mode):
    """بولین‌های long/short برای یک عضو. ورود در کندلِ بعدِ سیگنال (موتور)."""
    n = len(r)
    warm = BV_WIN + 2 + D
    ok = np.arange(n) >= warm
    up = ok & (sigma > 0) & (r > k * sigma) & (ds < 0)     # جهش بالا، رانش پایین
    dn = ok & (sigma > 0) & (r < -k * sigma) & (ds > 0)    # جهش پایین، رانش بالا
    if timing == 't1':
        # سیگنال به t+1 منتقل می‌شود، فقط اگر کندل t+1 جهش را ادامه نداده باشد
        up1 = np.zeros(n, dtype=bool); dn1 = np.zeros(n, dtype=bool)
        cont_up = r > sigma                                 # ادامهٔ جهشِ بالا در t+1
        cont_dn = r < -sigma
        up1[1:] = up[:-1] & ~cont_up[1:]
        dn1[1:] = dn[:-1] & ~cont_dn[1:]
        up, dn = up1, dn1
    if mode == 'revert':
        return dn, up          # long بعد از جهشِ پایین (رانش بالا)، short بعد از جهشِ بالا
    return up, dn              # continue: جهتِ جهش (کنترل)


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
    c, r, sigma, atr = features(df)
    sl64 = np.maximum(SL_K * atr / pip, 1e-9)
    tp64 = sl64 if RR == 1.0 else sl64 * RR
    del atr; gc.collect()
    n = len(r)

    # ── گذر ۱: کشف — فقط پارامترهای برنده ──
    best = None; members = []
    for D in D_LIST:
        ds = drift_sign(c, D)
        for k in K_LIST:
            for timing in TIMINGS:
                for mode in MODES:
                    ls, ss = member_signals(r, sigma, ds, k, D, timing, mode)
                    n_sig = int(ls.sum() + ss.sum())
                    if n_sig < 30:
                        members.append(dict(k=k, D=D, timing=timing, mode=mode, n_sig=n_sig, z=-99))
                        del ls, ss; continue
                    tr = se.simulate_trades(df, ls, ss, sl64, tp64, 'XAUUSD',
                                            max_hold=MAX_HOLD, allow_overlap=False)
                    del ls, ss
                    sl_med = float(np.median(tr['sl_pip'].values)) if len(tr) else 0.0
                    z, info = zproxy(tr, sl_med, sl_med * RR)
                    members.append(dict(k=k, D=D, timing=timing, mode=mode, n_sig=n_sig,
                                        z=round(z, 2), **(info or {})))
                    if best is None or z > best['z']:
                        best = dict(k=k, D=D, timing=timing, mode=mode, z=z, sl_med=sl_med)
                    del tr; gc.collect()
        del ds; gc.collect()

    res = dict(tf=tf, src=d['src'], n_bars=n, members=members)
    if best is None or best['z'] < 1.0:
        res['verdict'] = 'NO-CANDIDATE'
        res['best'] = None if best is None else {x: best[x] for x in ('k', 'D', 'timing', 'mode', 'z')}
    else:
        # ── گذر ۲: فقط برنده + rqs2 ──
        ds = drift_sign(c, best['D'])
        ls, ss = member_signals(r, sigma, ds, best['k'], best['D'], best['timing'], best['mode'])
        del ds, r, sigma; gc.collect()
        tr = se.simulate_trades(df, ls, ss, sl64, tp64, 'XAUUSD',
                                max_hold=MAX_HOLD, allow_overlap=False)
        del sl64, tp64; gc.collect()
        null = build_null_perm(df, ls, ss, MAX_HOLD, K=K_PERM, seed=SEED)
        res['entry_idx'] = np.where(ls | ss)[0].tolist()   # برای آزمونِ همپوشانی با S950
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
        res['best'] = dict(k=best['k'], D=best['D'], timing=best['timing'], mode=best['mode'],
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
    print('S953 scan تمام شد.', flush=True)
