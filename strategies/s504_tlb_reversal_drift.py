# -*- coding: utf-8 -*-
"""
S504 — Three-Line-Break reversal line (Nison) × 60-trading-day drift convention gate
XAUUSD · 19 TFs · data/mt5_full (15.6y) · RQS2 v2.6 (untouched judge)

Prereg: results/S504_PREREG_TLB_REVERSAL_DRIFT_ALIGNED.md (commit b9e44c34, BEFORE any test)
This script is committed BEFORE execution. Zero free parameters; every constant inherited:
  drift K = bars/day × 60          (S604 / S966)
  SL = 1.272×ATR21, TP = 2.058×ATR21, hold = 16   (S965 / S919)
  K_PERM = 500, seed = 504, SPLIT_FRAC = 0.60, SEED = 20260813
Falsifiers F1..F5 executed before any judge call (prereg §5).
"""
import os, sys, json, time, warnings
warnings.filterwarnings('ignore')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import numpy as np
import pandas as pd
import engine.scalp_engine as se
import engine.rqs2 as rqs2

ASSET = 'XAUUSD'
OUT = 'results/_scan_S504'
os.makedirs(OUT, exist_ok=True)

# 19 TFs of data/mt5_full (prereg §3.3); run order: slow -> fast so cheap cards report first
TFS = ['MN1', 'W1', 'D1', 'H12', 'H8', 'H6', 'H4', 'H3', 'H2', 'H1',
       'M30', 'M20', 'M15', 'M12', 'M10', 'M6', 'M5', 'M4', 'M3', 'M1']
TFS = [t for t in TFS if os.path.exists(f'data/mt5_full/{ASSET}_{t}.csv')]
assert len(TFS) == 19, TFS

BARS_PER_DAY = {'M1': 1440, 'M3': 480, 'M4': 360, 'M5': 288, 'M6': 240, 'M10': 144,
                'M12': 120, 'M15': 96, 'M20': 72, 'M30': 48, 'H1': 24, 'H2': 12,
                'H3': 8, 'H4': 6, 'H6': 4, 'H8': 3, 'H12': 2, 'D1': 1}
def drift_K(tf):
    if tf == 'W1': return 12
    if tf == 'MN1': return 3
    return BARS_PER_DAY[tf] * 60

ATR_P = 21
SL_K, TP_K = 1.272, 2.058
MAX_HOLD = 16
K_PERM = 500
NULL_SEED = 504
SEED = 20260813
SPLIT_FRAC = 0.60
N_TRIALS = 2 * len(TFS)            # RAW + DRIFT per TF (prereg §4)
F1_LO, F1_HI = 0.10, 0.90
F2_MIN_GAIN = 1.0
F3_N_MIN = 60

PIP = se.ASSETS[ASSET]['pip']
COST = se.ASSETS[ASSET]['spread_pip'] + 2 * se.ASSETS[ASSET].get('slip_pip', 0.0)


def save(name, obj):
    with open(os.path.join(OUT, name), 'w') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=str)


def load(tf):
    df = se.load_data(f'data/mt5_full/{ASSET}_{tf}.csv')
    return df


def atr_pip(df, p=ATR_P):
    h = df['high'].to_numpy(float); l = df['low'].to_numpy(float); c = df['close'].to_numpy(float)
    pc = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.c_[h - l, np.abs(h - pc), np.abs(l - pc)], axis=1)
    atr = pd.Series(tr).ewm(alpha=1.0 / p, adjust=False, min_periods=p).mean().to_numpy()
    atr = np.r_[np.nan, atr[:-1]]                       # causal: ATR21[t-1]
    return atr / PIP


def tlb_reversals(close):
    """Nison Three-Line-Break. Returns (long_rev, short_rev) boolean arrays:
    True at bar t where a reversal line of that colour is drawn on close[t]."""
    n = len(close)
    long_rev = np.zeros(n, bool); short_rev = np.zeros(n, bool)
    lines = []  # list of (color, top, bottom)
    j = 1
    while j < n and close[j] == close[0]:
        j += 1
    if j >= n:
        return long_rev, short_rev
    color = 1 if close[j] > close[0] else -1
    lines.append((color, max(close[0], close[j]), min(close[0], close[j])))
    for t in range(j + 1, n):
        c = close[t]
        col, top, bot = lines[-1]
        W = lines[-3:]
        if col == 1:
            if c > top:
                lines.append((1, c, top))
            elif c < min(b for _, _, b in W):
                lines.append((-1, bot, c)); short_rev[t] = True
        else:
            if c < bot:
                lines.append((-1, bot, c))
            elif c > max(tp for _, tp, _ in W):
                lines.append((1, c, top)); long_rev[t] = True
    return long_rev, short_rev


def drift_sign(close, K):
    d = np.full(len(close), np.nan)
    d[K + 1:] = close[K:-1] - close[:-K - 1]            # close[t-1] - close[t-1-K]
    return d


def run(df, lsig, ssig, sl, tp):
    return se.simulate_trades(df, lsig, ssig, sl, tp, ASSET,
                              max_hold=MAX_HOLD, allow_overlap=False)


def wr_of(tr):
    return 100.0 * float(np.mean(tr['pnl_pip'] > 0)) if tr is not None and len(tr) else None


def build_null(df, valid_long, valid_short, sl, tp, n_long, n_short, rng):
    """Two-sided measured null (S770 pattern) in the CONDITIONED space (S523/S502).
    valid_long: indices where LONG entry is allowed (drift>0 for DRIFT variant; all valid for RAW)."""
    null = {}
    zero = np.zeros(len(df), bool)
    for side, vi, n_side in (('long', valid_long, n_long), ('short', valid_short, n_short)):
        d = dict(uncond_wr=None, perm_mean=None, perm_sd=None, perm_max=None, perm_k=0)
        if n_side >= 1 and len(vi) > n_side:
            sig = np.zeros(len(df), bool); sig[vi] = True
            tr_all = se.simulate_trades(df, sig if side == 'long' else zero,
                                        zero if side == 'long' else sig,
                                        sl, tp, ASSET, max_hold=MAX_HOLD, allow_overlap=True)
            if len(tr_all):
                d['uncond_wr'] = wr_of(tr_all)
            wrs = []
            for _ in range(K_PERM):
                pb = vi[np.sort(rng.choice(len(vi), size=n_side, replace=False))]
                sig = np.zeros(len(df), bool); sig[pb] = True
                tr_p = se.simulate_trades(df, sig if side == 'long' else zero,
                                          zero if side == 'long' else sig,
                                          sl, tp, ASSET, max_hold=MAX_HOLD, allow_overlap=True)
                w = wr_of(tr_p)
                if w is not None:
                    wrs.append(w)
            if wrs:
                a = np.asarray(wrs)
                d.update(perm_mean=float(a.mean()), perm_sd=float(a.std(ddof=1)),
                         perm_max=float(a.max()), perm_k=int(len(a)))
        null[side] = d
    return null


def judge(tag, df, tr, sl, tp, null):
    dt_all = df['dt']
    entry_dt = dt_all.to_numpy()[tr['entry_bar'].to_numpy(int)].astype('datetime64[s]').astype(np.int64)
    q = np.quantile(entry_dt, SPLIT_FRAC)
    holdout = entry_dt >= q
    np.random.seed(SEED)
    # floating ATR bracket -> engine receives the median (project convention S770/S965; RR invariant)
    sl_med = float(np.nanmedian(tr['sl_pip'].to_numpy(float)))
    tp_med = sl_med * (TP_K / SL_K)
    v = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med, bar_time=dt_all, null=null,
                          close=df['close'], holdout_mask=holdout, n_trials=N_TRIALS,
                          allow_overlap=False)
    m = v['metrics']; g = v['gates']
    gates = ' '.join(f"H{i}:{'✓' if g.get('H%d' % i) else '✗'}" for i in range(11))
    print(f"{tag} | {v['verdict']} RQS2={v['rqs2_score']:.1f} | n={m.get('n_trades')} "
          f"WR={m.get('win_rate')} lift={m.get('skill_lift_pp')} z={m.get('skill_z')} "
          f"PF={m.get('profit_factor')} | {gates}", flush=True)
    return v


def card(tf):
    t0 = time.time()
    df = load(tf)
    c = df['close'].to_numpy(float)
    n = len(df)
    atr = atr_pip(df)
    sl = SL_K * atr; tp = TP_K * atr
    K = drift_K(tf)
    dr = drift_sign(c, K)
    lrev, srev = tlb_reversals(c)
    warm = max(K + 2, ATR_P + 2)
    valid = np.zeros(n, bool); valid[warm:n - MAX_HOLD - 2] = True
    valid &= np.isfinite(sl) & (sl > 0) & np.isfinite(dr)

    raw_l = lrev & valid; raw_s = srev & valid
    dr_l = raw_l & (dr > 0); dr_s = raw_s & (dr < 0)
    mir_l = raw_l & (dr < 0); mir_s = raw_s & (dr > 0)          # F5 mirror control

    res = dict(tf=tf, bars=n, K=K, n_raw_sig=int(raw_l.sum() + raw_s.sum()),
               n_drift_sig=int(dr_l.sum() + dr_s.sum()))
    print(f"\n[{tf}] bars={n:,} K={K} raw_sig={res['n_raw_sig']} drift_sig={res['n_drift_sig']} "
          f"(L{int(dr_l.sum())}/S{int(dr_s.sum())})", flush=True)

    tr_raw = run(df, raw_l, raw_s, sl, tp)
    tr_dr = run(df, dr_l, dr_s, sl, tp)
    tr_mir = run(df, mir_l, mir_s, sl, tp)
    res.update(n_raw=int(len(tr_raw)), wr_raw=wr_of(tr_raw),
               n_drift=int(len(tr_dr)), wr_drift=wr_of(tr_dr),
               n_mirror=int(len(tr_mir)), wr_mirror=wr_of(tr_mir))
    print(f"   RAW n={res['n_raw']} WR={res['wr_raw']} | DRIFT n={res['n_drift']} WR={res['wr_drift']} "
          f"| MIRROR n={res['n_mirror']} WR={res['wr_mirror']}", flush=True)

    # ---- falsifiers (prereg §5) --------------------------------------------
    dead = []
    if res['n_raw_sig'] == 0:
        dead.append('F0 no raw events')
    else:
        removed = 1.0 - res['n_drift_sig'] / res['n_raw_sig']
        res['gate_removed_frac'] = removed
        if removed < F1_LO or removed > F1_HI:
            dead.append(f'F1 gate removes {removed:.1%} (outside 10-90%)')
    if res['n_drift'] < F3_N_MIN:
        dead.append(f"F3 n_drift={res['n_drift']} < {F3_N_MIN}")
    if res['wr_raw'] is not None and res['wr_drift'] is not None:
        if res['wr_drift'] < res['wr_raw'] + F2_MIN_GAIN:
            dead.append(f"F2 WR_drift {res['wr_drift']:.2f} < WR_raw {res['wr_raw']:.2f}+1.0")
    res['falsifiers_dead'] = dead
    if dead:
        print(f"   DEAD (no judge call): {dead}", flush=True)
        res['verdict'] = 'SELF-REJECT'; res['sec'] = round(time.time() - t0, 1)
        save(f'{tf}.json', res)
        return res

    # ---- conditioned null + F4 -------------------------------------------
    rng = np.random.default_rng(NULL_SEED)
    vl = np.where(valid & (dr > 0))[0]; vs = np.where(valid & (dr < 0))[0]
    nl = int((tr_dr['direction'] == 'long').sum())
    ns = int(len(tr_dr) - nl)
    null = build_null(df, vl, vs, sl, tp, nl, ns, rng)
    res['null'] = null
    print(f"   null: long={json.dumps(null['long'])} short={json.dumps(null['short'])}", flush=True)
    # F4: raw lift vs conditioned uncond (trade-weighted)
    refs = [(null[s]['uncond_wr'], k) for s, k in (('long', nl), ('short', ns)) if null[s]['uncond_wr'] is not None and k > 0]
    if refs:
        ref = sum(w * k for w, k in refs) / sum(k for _, k in refs)
        res['uncond_ref'] = ref
        if res['wr_drift'] - ref <= 0:
            dead.append(f"F4 raw lift {res['wr_drift'] - ref:.2f} <= 0")
    if res['wr_mirror'] is not None and res['wr_mirror'] >= res['wr_drift']:
        res['F5_mirror_flag'] = True
        print(f"   F5 FLAG: mirror WR {res['wr_mirror']:.2f} >= drift WR {res['wr_drift']:.2f} -> UNPROVEN cap", flush=True)
    if dead:
        print(f"   DEAD (no judge call): {dead}", flush=True)
        res['falsifiers_dead'] = dead; res['verdict'] = 'SELF-REJECT'
        res['sec'] = round(time.time() - t0, 1); save(f'{tf}.json', res)
        return res

    # ---- single judge call ----------------------------------------------
    v = judge(f'S504-{tf}-DRIFT', df, tr_dr, sl, tp, null)
    res['verdict'] = v['verdict']; res['rqs2'] = v['rqs2_score']
    res['metrics'] = v['metrics']; res['gates'] = v['gates']; res['notes'] = v.get('notes')
    if res.get('F5_mirror_flag') and v['verdict'] == 'ACCEPT':
        res['verdict'] = 'UNPROVEN'; print('   -> capped to UNPROVEN by F5 (prereg §5)', flush=True)
    res['sec'] = round(time.time() - t0, 1)
    save(f'{tf}.json', res)
    return res


def main():
    print('=' * 88)
    print(f'S504 — TLB reversal × drift-60d | XAUUSD | {len(TFS)} TFs | n_trials={N_TRIALS} | prereg b9e44c34')
    print('=' * 88, flush=True)
    only = sys.argv[1:] or TFS
    summary = []
    for tf in only:
        try:
            r = card(tf)
        except Exception as e:
            r = dict(tf=tf, verdict='ERROR', error=repr(e)); print(f'[{tf}] ERROR {e!r}', flush=True)
        summary.append({k: r.get(k) for k in ('tf', 'verdict', 'rqs2', 'n_raw', 'wr_raw', 'n_drift',
                                              'wr_drift', 'n_mirror', 'wr_mirror', 'falsifiers_dead')})
        save('summary.json', summary)
    print('\nDONE'); print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
