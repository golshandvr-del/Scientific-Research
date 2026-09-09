"""
s813_shock_pause.py — لایه‌ی S813: شوک → مکث → ادامه (پرچم) · XAUUSD
=====================================================================
پیش‌ثبت: results/S813_PREREG_SHOCK_PAUSE_CONTINUATION.md (کامیت c846ce51 — قبل از این کد)

قاعده (قفل، صفر پارامتر آزاد):
  شوک i   : range_i >= 1.618*ATR21[i-1]  و  rho_i = |c-o|/range >= 0.5
  مکث i+1 : high<=high_i, low>=low_i, range_{i+1} <= 0.618*range_i
  سیگنال روی i+1؛ جهت = sign(close_i - open_i)؛ ورود open i+2 (موتور)
  SL = 1.272*ATR21[i-1], TP = 2.058*ATR21[i-1], max_hold=16, allow_overlap=False
null: K=500 قرعه‌ی ورود غیرشرطی تصادفی (همان n، هندسه‌ی ATR21[i-1]، mh)، جهت 50/50؛
      uncond هر سمت از نمونه‌ی 10×n یک‌جهته.
مسیر B: n_trials=4 (H6,H8,H12,D1). کارت‌های غربال (M1..H4) با n_trials=19.

اجرا: python3 strategies/s813_shock_pause.py H8      # یک کارت + checkpoint git
"""
import os, sys, json, subprocess, argparse
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import scalp_engine as se   # noqa: E402
from engine import rqs2                 # noqa: E402
from tools import s434_fast_data as fd  # noqa: E402

OUTDIR = os.path.join(ROOT, 'results', '_s813')
SEED = 813
K_PERM = 500
THETA = 1.618
RHO_MIN = 0.5
PAUSE_K = 0.618
K_SL, K_TP = 1.272, 2.058
MAX_HOLD = 16
MAIN_CARDS = ['H6', 'H8', 'H12', 'D1']
N_TRIALS_MAIN = 4
N_TRIALS_SCREEN = 19
PIP = 0.1


def atr21_prev(h, l, c):
    """ATR21 تا کندل i-1 (اکیداً علّی): مقدار در ایندکس i = میانگین TR[i-21..i-1]."""
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    cs = np.concatenate([[0.0], np.cumsum(tr)])
    a = np.full(len(c), np.nan)
    a[21:] = (cs[21:] - cs[:-21]) / 21.0      # TR[i-21..i-1]
    return a


def build_signals(o, h, l, c):
    n = len(c)
    a_prev = atr21_prev(h, l, c)
    rng = h - l
    body = np.abs(c - o)
    with np.errstate(invalid='ignore', divide='ignore'):
        rho = np.where(rng > 0, body / rng, 0.0)
    shock = np.isfinite(a_prev) & (rng >= THETA * a_prev) & (rho >= RHO_MIN)
    idx = np.where(shock[:-2])[0]
    j = idx + 1
    pause = (h[j] <= h[idx]) & (l[j] >= l[idx]) & (rng[j] <= PAUSE_K * rng[idx])
    sig_i = idx[pause]          # کندل شوک
    sig = sig_i + 1             # کندل مکث = کندل سیگنال
    up = c[sig_i] > o[sig_i]
    ls = np.zeros(n, bool); ss = np.zeros(n, bool)
    ls[sig[up]] = True; ss[sig[~up]] = True
    slp = np.full(n, np.nan); tpp = np.full(n, np.nan)
    slp[sig] = K_SL * a_prev[sig_i] / PIP
    tpp[sig] = K_TP * a_prev[sig_i] / PIP
    # هندسه‌ی هر کندل برای null (بر اساس ATR21 تا یک کندل قبل از کندل شوک فرضی = i-1)
    sl_all = K_SL * a_prev / PIP
    tp_all = K_TP * a_prev / PIP
    base = dict(n_shock=int(len(idx)), n_pause=int(len(sig)))
    return ls, ss, slp, tpp, sl_all, tp_all, base, shock


def sim(df, ls, ss, slp, tpp):
    sl = np.where(np.isfinite(slp), slp, 30.0)
    tp = np.where(np.isfinite(tpp), tpp, 30.0)
    return se.simulate_trades(df, ls, ss, sl_pip=sl, tp_pip=tp, asset='XAUUSD',
                              max_hold=MAX_HOLD, allow_overlap=False)


def wr_of(tr):
    return float((tr['outcome'].values == 'win').mean() * 100) if tr is not None and len(tr) else np.nan


def build_null(df, n_sig, sl_all, tp_all, rng):
    n = len(df)
    valid = np.where(np.isfinite(sl_all))[0]
    valid = valid[(valid > 30) & (valid < n - MAX_HOLD - 2)]
    pl_, ps_ = [], []
    for k in range(K_PERM):
        pick = np.sort(rng.choice(valid, size=n_sig, replace=False))
        dirs = rng.integers(0, 2, n_sig)
        pl = np.zeros(n, bool); ps = np.zeros(n, bool)
        pl[pick[dirs == 1]] = True; ps[pick[dirs == 0]] = True
        ptr = sim(df, pl, ps, sl_all, tp_all)
        if ptr is None or len(ptr) == 0:
            continue
        isl = ptr['direction'].values == 'long'
        oc = ptr['outcome'].values == 'win'
        if isl.sum(): pl_.append(float(oc[isl].mean() * 100))
        if (~isl).sum(): ps_.append(float(oc[~isl].mean() * 100))
    big = np.sort(rng.choice(valid, size=min(len(valid), n_sig * 10), replace=False))
    bm = np.zeros(n, bool); bm[big] = True
    unc_l = wr_of(sim(df, bm, np.zeros(n, bool), sl_all, tp_all))
    unc_s = wr_of(sim(df, np.zeros(n, bool), bm, sl_all, tp_all))
    side = lambda arr, unc: dict(uncond_wr=round(unc, 4), perm_mean=round(float(np.mean(arr)), 4),
                                 perm_sd=round(float(np.std(arr)), 4), perm_max=round(float(np.max(arr)), 4),
                                 perm_k=len(arr))
    return {'long': side(pl_, unc_l), 'short': side(ps_, unc_s)}


def baseline_no_pause(df, o, h, l, c, shock, sl_all, tp_all):
    """P2: پایه‌ی «شوک بدون شرط مکث، ورود در i+2» — فقط برای مقایسه، داوری نمی‌شود."""
    n = len(c)
    idx = np.where(shock[:-2])[0]
    sig = idx + 1
    up = c[idx] > o[idx]
    ls = np.zeros(n, bool); ss = np.zeros(n, bool)
    ls[sig[up]] = True; ss[sig[~up]] = True
    slp = np.full(n, np.nan); tpp = np.full(n, np.nan)
    slp[sig] = sl_all[idx]; tpp[sig] = tp_all[idx]
    tr = sim(df, ls, ss, slp, tpp)
    return dict(n=int(len(tr)), wr=round(wr_of(tr), 3),
                exp_pip=round(float(tr['pnl_pip'].mean()), 3) if len(tr) else None)


def git_ckpt(path, msg):
    try:
        subprocess.run(['git', 'add', path], cwd=ROOT, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-q', '-m', msg], cwd=ROOT, capture_output=True)
    except Exception as e:  # noqa: BLE001
        print('ckpt skipped:', e)


def run_card(tf):
    os.makedirs(OUTDIR, exist_ok=True)
    out_path = os.path.join(OUTDIR, f'judge_{tf}.json')
    if os.path.exists(out_path):
        print(f'{tf}: already judged — skip (no re-test)'); return json.load(open(out_path))
    d = fd.load_fast('XAUUSD', tf)
    assert 'mt5_full' in d['src'], 'E-16 trap: non-canonical data!'
    print('src:', d['src'], flush=True)
    df = fd.as_dataframe(d)
    o, h, l, c = (df[k].values.astype(np.float64) for k in ('open', 'high', 'low', 'close'))
    t = df['time'].values
    ls, ss, slp, tpp, sl_all, tp_all, base, shock = build_signals(o, h, l, c)
    n = len(df)
    print(f'{tf}: shocks={base["n_shock"]} pause-events={base["n_pause"]} '
          f'(long={int(ls.sum())}, short={int(ss.sum())})', flush=True)
    tr = sim(df, ls, ss, slp, tpp)
    ntr = 0 if tr is None else len(tr)
    rng = np.random.default_rng(SEED + TF_SEED[tf])
    res = dict(tf=tf, src=d['src'], **base, n_trades=int(ntr))
    if ntr < 10:
        res['verdict'] = 'INCOMPLETE (n<10)'; res['rqs2_score'] = 0.0
    else:
        null = build_null(df, int(ls.sum() + ss.sum()), sl_all, tp_all, rng)
        med_sl = float(np.nanmedian(slp[np.isfinite(slp)]))
        med_tp = float(np.nanmedian(tpp[np.isfinite(tpp)]))
        ntrials = N_TRIALS_MAIN if tf in MAIN_CARDS else N_TRIALS_SCREEN
        r = rqs2.compute_rqs2(tr, 'XAUUSD', sl_pip=med_sl, tp_pip=med_tp, bar_time=t,
                              null=null, n_trials=ntrials, split_bar=n // 2, close=c)
        r_sens = rqs2.compute_rqs2(tr, 'XAUUSD', sl_pip=med_sl, tp_pip=med_tp, bar_time=t,
                                   null=null, n_trials=8, split_bar=n // 2, close=c) \
            if tf in MAIN_CARDS else None
        res.update(null=null, n_trials=ntrials, verdict=r['verdict'], rqs2_score=r['rqs2_score'],
                   gates={k: r[k] for k in r if k[0] == 'H' and k[1:].isdigit()},
                   metrics=r['metrics'],
                   sens_n_trials_8=(dict(verdict=r_sens['verdict'], rqs2=r_sens['rqs2_score'])
                                    if r_sens else None),
                   baseline_no_pause=baseline_no_pause(df, o, h, l, c, shock, sl_all, tp_all),
                   line=rqs2.format_rqs2(f'S813-{tf}', r))
        print(res['line'], flush=True)
        print('P2 baseline (shock, no pause):', res['baseline_no_pause'], flush=True)
    json.dump(res, open(out_path, 'w'), indent=1, default=str)
    git_ckpt(out_path, f"S813 checkpoint {tf}: {res['verdict']} rqs2={res['rqs2_score']}")
    return res


TF_SEED = {tf: i for i, tf in enumerate(['M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20',
                                          'M30', 'H1', 'H2', 'H3', 'H4', 'H6', 'H8', 'H12', 'D1', 'W1', 'MN1'])}

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('tfs', nargs='+')
    a = ap.parse_args()
    for tf in a.tfs:
        run_card(tf)
