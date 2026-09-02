"""
S905 — Drift Pullback Re-ignition · XAUUSD · RQS2 v2.6 · Path C
=================================================================
درفت ۸۹کندلهٔ برقرار + j کلوزِ متوالی خلاف‌درفت (پولبک) + اولین کلوزِ
هم‌جهتِ درفت = یالِ ورود در جهت درفت. کاملاً آناتومیک — بدون سطح/اندیکاتور.

پیش‌ثبت: results/S905_PREREGISTRATION.md (کامیت 486494fa، قبل از هر آزمون).
گرید منجمد: j∈{2,3} × k_sl∈{1.5,2.058} × RR∈{1.5,2.0} × hold∈{13,34} ⇒ N_eff=16.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import scalp_engine as se          # noqa: E402
from engine import rqs2                        # noqa: E402
from tools import s434_fast_data as fd         # noqa: E402

ASSET = 'XAUUSD'
OUT = os.path.join(ROOT, 'results', '_s905')

GRID_J = (2, 3)
GRID_KSL = (1.5, 2.058)
GRID_RR = (1.5, 2.0)
GRID_HOLD = (13, 34)
N_EFF = 16
assert len(GRID_J)*len(GRID_KSL)*len(GRID_RR)*len(GRID_HOLD) == N_EFF

W = 89          # پنجرهٔ درفت/ATR — ثابت، خارج از گرید (پیش‌ثبت §۲)
WARMUP = 91
SPLIT_FRAC = 0.60
K_PERM = 1000
SEED = 905


def atr_pip(d):
    h, l, c = d['high'], d['low'], d['close']
    pip = se.ASSETS[ASSET]['pip']
    prev_c = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    return pd.Series(tr).rolling(W).mean().values / pip


def build_features(d):
    """درفت W-کندله (causal تا t−1)."""
    c = d['close']
    drift = np.full(len(c), np.nan)
    drift[W + 1:] = c[W:-1] - c[:-W - 1]                      # close[t−1]−close[t−1−W]
    return drift


def build_signals(d, j, drift):
    """LONG: درفت↑ + j کندل نزولی متوالی در [t−j,t−1] + کندل t صعودی.
    SHORT قرینه. یال ذاتی: کندل t هم‌جهتِ درفت است پس نمی‌تواند عضو پولبک بعدی باشد."""
    o, c = d['open'], d['close']
    n = len(c)
    up = c > o
    dn = c < o

    def consec_prev(cond):
        """True در t اگر j کندلِ [t−j, t−1] همگی cond باشند."""
        ok = np.ones(n, dtype=bool)
        for q in range(1, j + 1):
            ok &= np.roll(cond, q)
        ok[:j] = False
        return ok

    with np.errstate(invalid='ignore'):
        ls = (drift > 0) & consec_prev(dn) & up
        ss = (drift < 0) & consec_prev(up) & dn
    ls = np.nan_to_num(ls, nan=False).astype(bool)
    ss = np.nan_to_num(ss, nan=False).astype(bool)
    ls[:WARMUP] = False
    ss[:WARMUP] = False
    return ls, ss


def sim_chunked(d, ls, ss, sl, tp, hold, chunk=600_000):
    """قطعه‌قطعه با هم‌ارزی اثبات‌شده (S903، کامیت f1a90276)."""
    n = len(d['close'])
    frames = []
    busy_until = -1
    a = 0
    while a < n:
        b = min(a + chunk, n)
        ext = min(b + hold + 2, n)
        dfc = pd.DataFrame({
            'time': d['time'][a:ext], 'open': d['open'][a:ext],
            'high': d['high'][a:ext], 'low': d['low'][a:ext],
            'close': d['close'][a:ext], 'volume': d['volume'][a:ext],
        }, copy=False)
        lsc = ls[a:ext].copy(); ssc = ss[a:ext].copy()
        lsc[b - a:] = False
        ssc[b - a:] = False
        if busy_until >= a + 1:
            cut = min(busy_until - a, ext - a)
            lsc[:cut] = False
            ssc[:cut] = False
        if lsc.any() or ssc.any():
            tr = se.simulate_trades(dfc, lsc, ssc, sl[a:ext], tp[a:ext],
                                    ASSET, max_hold=hold, allow_overlap=False)
            if tr is not None and len(tr):
                for col in ('signal_bar', 'entry_bar', 'exit_bar'):
                    tr[col] = tr[col] + a
                busy_until = max(busy_until, int(tr['exit_bar'].max()))
                frames.append(tr)
        del dfc, lsc, ssc
        a = b
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    del frames
    return out


def run_combo(d, atr, ls, ss, k_sl, rr, hold):
    sl = np.nan_to_num(np.clip(k_sl * atr, 5.0, None), nan=5.0)
    tp = rr * sl
    tr_ = sim_chunked(d, ls, ss, sl, tp, hold)
    if tr_ is None or len(tr_) == 0:
        return None
    wr = float((tr_['pnl_pip'] > 0).mean() * 100.0)
    net = float(tr_['pnl_pip'].sum())
    return dict(n=len(tr_), wr=round(wr, 3), net=round(net, 1))


def phase_discover(tf):
    os.makedirs(OUT, exist_ok=True)
    ckpt_fp = os.path.join(OUT, f'discover_{tf}.json')
    done = {}
    if os.path.exists(ckpt_fp):
        with open(ckpt_fp) as f:
            done = json.load(f).get('combos', {})
        print(f'[resume] {len(done)} combos checkpointed')

    d = fd.load_fast(ASSET, tf)
    src_full = d['src']
    print(f"DATA src={src_full} n_bars={d['n_bars']:,} span={d['span_years']}y",
          flush=True)
    n_all = int(d['n_bars'])
    split = int(n_all * SPLIT_FRAC)
    d1 = {kk: (v[:split] if isinstance(v, np.ndarray) else v) for kk, v in d.items()}
    del d
    import gc; gc.collect()
    atr = atr_pip(d1)
    drift = build_features(d1)

    t0 = time.time()
    results = dict(done)
    i = 0
    for j in GRID_J:
        ls, ss = build_signals(d1, j, drift)
        n_sig = int(ls.sum() + ss.sum())
        for k_sl in GRID_KSL:
            for rr in GRID_RR:
                for hold in GRID_HOLD:
                    i += 1
                    key = f'j{j}_k{k_sl}_rr{rr}_h{hold}'
                    if key in results:
                        continue
                    res = run_combo(d1, atr, ls, ss, k_sl, rr, hold)
                    results[key] = (res or dict(n=0)) | dict(n_sig=n_sig)
                    with open(ckpt_fp, 'w') as f:
                        json.dump(dict(tf=tf, split=split, n_bars=n_all,
                                       src=src_full, combos=results), f, indent=1)
                    v = results[key]
                    print(f'[{i:2d}/{N_EFF}] {key:<24} n={v.get("n",0):>6} '
                          f'wr={v.get("wr","-")} net={v.get("net","-")} '
                          f'sig={n_sig} ({time.time()-t0:.0f}s)', flush=True)

    floor = 400 if tf == 'M1' else 60
    best_key, best_score = None, -1e18
    for key, res in results.items():
        if res.get('n', 0) < floor:
            continue
        score = res['wr'] + 0.001 * res['net']
        if score > best_score:
            best_key, best_score = key, score
    locked = dict(tf=tf, split_bar=split, n_bars=n_all, src=src_full,
                  n_eff=N_EFF, criterion='wr+0.001*net', min_trades=floor,
                  best_key=best_key, best=results.get(best_key) if best_key else None,
                  score=round(best_score, 4) if best_key else None)
    with open(os.path.join(OUT, f'locked_{tf}.json'), 'w') as f:
        json.dump(locked, f, indent=2)
    print('\nLOCKED:', json.dumps(locked, indent=2))


def build_null_perm(d, ls, ss, hold, K=K_PERM, seed=SEED):
    sig_idx = np.where(ls | ss)[0]
    n = len(sig_idx)
    if n < 30:
        return None
    c = d['close']
    rng = np.random.default_rng(seed)
    N = len(c)
    fwd = np.full(n, np.nan)
    for j, ei in enumerate(sig_idx):
        kk = min(ei + hold, N - 1)
        fwd[j] = c[kk] - c[ei]
    fwd = fwd[np.isfinite(fwd)]
    if len(fwd) < 30:
        return None
    base_wins = fwd > 0
    m = len(fwd)
    wrs = np.empty(K)
    for t in range(K):
        signs = rng.integers(0, 2, size=m).astype(bool)
        wrs[t] = np.where(signs, base_wins, ~base_wins).mean() * 100.0
    ref = float(np.mean(wrs))
    side = dict(uncond_wr=ref, perm_mean=ref, perm_sd=float(np.std(wrs, ddof=1)),
                perm_max=float(np.max(wrs)), perm_k=int(K))
    return {'long': dict(side), 'short': dict(side)}


def parse_key(key):
    p = {}
    for tok in key.split('_'):
        if tok.startswith('j'):
            p['j'] = int(tok[1:])
        elif tok.startswith('k'):
            p['k_sl'] = float(tok[1:])
        elif tok.startswith('rr'):
            p['rr'] = float(tok[2:])
        elif tok.startswith('h'):
            p['hold'] = int(tok[1:])
    return p


def phase_final(tf):
    with open(os.path.join(OUT, f'locked_{tf}.json')) as f:
        locked = json.load(f)
    if not locked.get('best_key'):
        print('NO LOCKED CONFIG — no test to run.')
        return
    p = parse_key(locked['best_key'])
    print(f"FINAL S905 {tf} · locked={locked['best_key']} · "
          f"n_trials={N_EFF} · split_bar={locked['split_bar']}")
    d = fd.load_fast(ASSET, tf)
    assert d['src'] == locked['src'], 'data source changed since lock!'
    atr = atr_pip(d)
    drift = build_features(d)
    ls, ss = build_signals(d, p['j'], drift)
    sl = np.nan_to_num(np.clip(p['k_sl'] * atr, 5.0, None), nan=5.0)
    tp = p['rr'] * sl
    tr_ = sim_chunked(d, ls, ss, sl, tp, p['hold'])
    print(f'trades total={len(tr_)}')
    if len(tr_) == 0:
        print('ZERO trades — INCOMPLETE')
        return
    null = build_null_perm(d, ls, ss, p['hold'])
    sl_med = float(np.median(tr_['sl_pip'].values))
    tp_med = p['rr'] * sl_med
    res = rqs2.compute_rqs2(tr_, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                            bar_time=d['time'], null=null,
                            n_trials=N_EFF, split_bar=locked['split_bar'],
                            close=d['close'])
    out = dict(tf=tf, locked_key=locked['best_key'], src=d['src'],
               n_bars=int(d['n_bars']), span_years=d['span_years'],
               n_trades=int(len(tr_)), sl_med=round(sl_med, 1),
               tp_med=round(tp_med, 1), verdict=res['verdict'],
               score=res.get('rqs2_score'), gates=res.get('gates'),
               metrics=res.get('metrics'), notes=res.get('notes'))
    with open(os.path.join(OUT, f'final_{tf}.json'), 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nVERDICT={res['verdict']} score={res.get('rqs2_score')}")
    print(f"skill_p_perm={res.get('metrics', {}).get('skill_p_perm')}")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', choices=['discover', 'final'], required=True)
    ap.add_argument('--tf', default='M1')
    a = ap.parse_args()
    (phase_discover if a.phase == 'discover' else phase_final)(a.tf)
