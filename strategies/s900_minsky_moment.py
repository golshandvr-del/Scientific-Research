"""
S900 — Minsky Moment Breakout · XAUUSD only · RQS2 v2.6 · Path C (hold-out)
============================================================================

فرضیه (هایمن مینسکی): ثبات، بی‌ثباتی می‌زاید. فشردگیِ عمیقِ ATR = انباشتِ
شکنندگی؛ شکستِ کلوزیِ محدودهٔ فشرده = «لحظهٔ مینسکی» و ادامهٔ حرکت.

پیش‌ثبت: results/S900_PREREGISTRATION.md (کامیت 3feef77d — قبل از هر آزمون).
گریدِ منجمد: L∈{21,34,55,89} × q_thr∈{0.55,0.70,0.85} × k_sl∈{1.5,2.5}
             × RR∈{1.5,2.0} × max_hold∈{34,89}  ⇒  N_eff = 96.

فازها:
  --phase discover --tf M1   : کشف فقط روی ۶۰٪ اول؛ چک‌پوینت هر ترکیب؛
                               در پایان پیکربندیِ قفل‌شده را JSON می‌کند.
                               (نیمهٔ دوم در این فاز هرگز لمس نمی‌شود.)
  --phase final --tf M1      : یک و فقط یک آزمون RQS2 روی کل داده با
                               split_bar و null اندازه‌گیری‌شده (K=1000, seed=900).

قواعد رعایت‌شده:
  * دادهٔ کامل از fd.load_fast (گزارش d['src'] — پادزهر E-16).
  * TP >= SL همیشه (RR>=1.5) — قانون بقای بودجه (اشتباه رایج ۸).
  * تقارن کامل long/short (وجه مشترک ACCEPTها).
  * پارامترهای کم، دوره‌های فیبوناچی (اشتباه رایج ۷).
  * z از تجمیع نمونه (M1، ۱۵.۶ سال)، نه انباشت فیلتر.
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
OUT = os.path.join(ROOT, 'results', '_s900')

# ---- گریدِ منجمدِ پیش‌ثبت‌شده (هیچ عددی خارج از این‌ها آزموده نمی‌شود) ----
GRID_L = (21, 34, 55, 89)
GRID_Q = (0.55, 0.70, 0.85)
GRID_KSL = (1.5, 2.5)
GRID_RR = (1.5, 2.0)
GRID_HOLD = (34, 89)
N_EFF = len(GRID_L) * len(GRID_Q) * len(GRID_KSL) * len(GRID_RR) * len(GRID_HOLD)
assert N_EFF == 96

ATR_P = 14
W_MED_MULT = 233 * 4          # پنجرهٔ میانهٔ بلند برای ATR نسبی
SPLIT_FRAC = 0.60
MIN_TRADES_DISCOVERY = 400    # کف پیش‌ثبت‌شده برای M1
MIN_TRADES_OTHER_TF = 60      # الحاقیهٔ ۱ پیش‌ثبت — برای TF≠M1
K_PERM = 1000
SEED = 900


def atr_pip(d):
    """ATR سادهٔ ۱۴ کندلی بر حسب pip (بدون pandas سنگین — حافظهٔ M1)."""
    h, l, c = d['high'], d['low'], d['close']
    pip = se.ASSETS[ASSET]['pip']
    prev_c = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    atr = pd.Series(tr).rolling(ATR_P).mean().values
    return atr / pip


def build_features(d):
    """ویژگی‌های مستقل از گرید — یک بار محاسبه می‌شوند."""
    atr = atr_pip(d)
    s = pd.Series(atr)
    med = s.rolling(W_MED_MULT, min_periods=W_MED_MULT).median().values
    with np.errstate(divide='ignore', invalid='ignore'):
        atr_rel = np.where(med > 0, atr / med, np.nan)
    return atr, atr_rel


def build_signals(d, atr_rel, L, q_thr):
    """شکستِ کلوزیِ محدودهٔ L کندلی در رژیم فشرده — متقارن."""
    h = pd.Series(d['high'])
    l = pd.Series(d['low'])
    c = d['close']
    # سقف/کف L کندلِ *قبل* از کندل جاری (shift(1) ⇒ forward-safe)
    rh = h.rolling(L).max().shift(1).values
    rl = l.rolling(L).min().shift(1).values
    compressed = atr_rel <= q_thr
    ls = compressed & (c > rh)
    ss = compressed & (c < rl)
    ls = np.nan_to_num(ls, nan=False).astype(bool)
    ss = np.nan_to_num(ss, nan=False).astype(bool)
    return ls, ss


def run_combo(df, d, atr, ls, ss, k_sl, rr, hold):
    sl = np.clip(k_sl * atr, 5.0, None)   # کفِ فنی: SL هرگز صفر/NaN نشود
    sl = np.nan_to_num(sl, nan=5.0)
    tp = rr * sl
    tr = se.simulate_trades(df, ls, ss, sl, tp, ASSET,
                            max_hold=hold, allow_overlap=False)
    if tr is None or len(tr) == 0:
        return None
    n = len(tr)
    wr = float((tr['pnl_pip'] > 0).mean() * 100.0)
    net = float(tr['pnl_pip'].sum())
    return dict(n=n, wr=round(wr, 3), net=round(net, 1), trades=tr)


def phase_discover(tf):
    os.makedirs(OUT, exist_ok=True)
    ckpt_fp = os.path.join(OUT, f'discover_{tf}.json')
    done = {}
    if os.path.exists(ckpt_fp):
        with open(ckpt_fp) as f:
            done = json.load(f).get('combos', {})
        print(f'[resume] {len(done)} combos already checkpointed')

    d = fd.load_fast(ASSET, tf)
    print(f"DATA src={d['src']}  n_bars={d['n_bars']:,}  span={d['span_years']}y")
    n_all = int(d['n_bars'])
    split = int(n_all * SPLIT_FRAC)

    # فقط ۶۰٪ اول — نیمهٔ دوم در فاز کشف وجود ندارد
    d1 = {k: (v[:split] if isinstance(v, np.ndarray) else v) for k, v in d.items()}
    df1 = fd.as_dataframe(d1)
    atr, atr_rel = build_features(d1)
    print(f'discovery bars={split:,} (first {SPLIT_FRAC:.0%})', flush=True)

    t0 = time.time()
    results = dict(done)
    i = 0
    for L in GRID_L:
        for q in GRID_Q:
            ls, ss = build_signals(d1, atr_rel, L, q)
            n_sig = int(ls.sum() + ss.sum())
            for k_sl in GRID_KSL:
                for rr in GRID_RR:
                    for hold in GRID_HOLD:
                        i += 1
                        key = f'L{L}_q{q}_k{k_sl}_rr{rr}_h{hold}'
                        if key in results:
                            continue
                        r = run_combo(df1, d1, atr, ls, ss, k_sl, rr, hold)
                        if r is None:
                            results[key] = dict(n=0)
                        else:
                            results[key] = dict(n=r['n'], wr=r['wr'],
                                                net=r['net'], n_sig=n_sig)
                        # چک‌پوینتِ «اندک اندک»
                        with open(ckpt_fp, 'w') as f:
                            json.dump(dict(tf=tf, split=split,
                                           n_bars=n_all, src=d['src'],
                                           combos=results), f, indent=1)
                        el = time.time() - t0
                        rr_ = results[key]
                        print(f'[{i:3d}/{N_EFF}] {key:<28} n={rr_.get("n",0):>5} '
                              f'wr={rr_.get("wr","-")} net={rr_.get("net","-")} '
                              f'({el:.0f}s)', flush=True)

    # ---- انتخاب طبق معیار پیش‌ثبت‌شده ----
    floor = MIN_TRADES_DISCOVERY if tf == 'M1' else MIN_TRADES_OTHER_TF
    best_key, best_score = None, -1e18
    for key, r in results.items():
        if r.get('n', 0) < floor:
            continue
        score = r['wr'] + 0.001 * r['net']
        if score > best_score:
            best_key, best_score = key, score
    locked = dict(tf=tf, split_bar=split, n_bars=n_all, src=d['src'],
                  n_eff=N_EFF, criterion='wr+0.001*net',
                  min_trades=floor,
                  best_key=best_key,
                  best=results.get(best_key) if best_key else None,
                  score=round(best_score, 4) if best_key else None)
    lock_fp = os.path.join(OUT, f'locked_{tf}.json')
    with open(lock_fp, 'w') as f:
        json.dump(locked, f, indent=2)
    print(f'\nLOCKED -> {lock_fp}')
    print(json.dumps(locked, indent=2))
    print('\nNEXT: commit the locked config, THEN run --phase final (touches '
          'the holdout exactly once).')


def build_null_perm(d, ls, ss, hold, K=K_PERM, seed=SEED):
    """نولِ کانونی به سبک s346: همان تعداد ورود، جهتِ تصادفی، K جای‌گشت."""
    sig_idx = np.where(ls | ss)[0]
    n = len(sig_idx)
    if n < 30:
        return None
    c = d['close']
    rng = np.random.default_rng(seed)
    fwd = np.full(n, np.nan)
    N = len(c)
    for j, ei in enumerate(sig_idx):
        k = min(ei + hold, N - 1)
        fwd[j] = c[k] - c[ei]
    fwd = fwd[np.isfinite(fwd)]
    if len(fwd) < 30:
        return None
    base_wins = fwd > 0
    m = len(fwd)
    wrs = np.empty(K)
    for t in range(K):
        signs = rng.integers(0, 2, size=m).astype(bool)
        w = np.where(signs, base_wins, ~base_wins)
        wrs[t] = w.mean() * 100.0
    ref = float(np.mean(wrs))
    side = dict(uncond_wr=ref, perm_mean=ref, perm_sd=float(np.std(wrs, ddof=1)),
                perm_max=float(np.max(wrs)), perm_k=int(K))
    return {'long': dict(side), 'short': dict(side)}


def parse_key(key):
    p = {}
    for tok in key.split('_'):
        if tok.startswith('L'):
            p['L'] = int(tok[1:])
        elif tok.startswith('q'):
            p['q'] = float(tok[1:])
        elif tok.startswith('k'):
            p['k_sl'] = float(tok[1:])
        elif tok.startswith('rr'):
            p['rr'] = float(tok[2:])
        elif tok.startswith('h'):
            p['hold'] = int(tok[1:])
    return p


def phase_final(tf):
    lock_fp = os.path.join(OUT, f'locked_{tf}.json')
    with open(lock_fp) as f:
        locked = json.load(f)
    if not locked.get('best_key'):
        print('NO LOCKED CONFIG (discovery failed floor) — verdict path: '
              'no test to run.')
        return
    p = parse_key(locked['best_key'])
    print(f"FINAL TEST S900 {tf} · locked={locked['best_key']} · "
          f"n_trials={N_EFF} · split_bar={locked['split_bar']}")

    d = fd.load_fast(ASSET, tf)
    assert d['src'] == locked['src'], 'data source changed since lock!'
    df = fd.as_dataframe(d)
    atr, atr_rel = build_features(d)
    ls, ss = build_signals(d, atr_rel, p['L'], p['q'])
    sl = np.nan_to_num(np.clip(p['k_sl'] * atr, 5.0, None), nan=5.0)
    tp = p['rr'] * sl
    tr = se.simulate_trades(df, ls, ss, sl, tp, ASSET,
                            max_hold=p['hold'], allow_overlap=False)
    print(f'trades total={len(tr)}')

    null = build_null_perm(d, ls, ss, p['hold'])
    sl_med = float(np.median(tr['sl_pip'].values))
    tp_med = p['rr'] * sl_med
    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=df['time'].values, null=null,
                          n_trials=N_EFF, split_bar=locked['split_bar'],
                          close=df['close'].values)
    out = dict(tf=tf, locked_key=locked['best_key'], src=d['src'],
               n_bars=d['n_bars'], span_years=d['span_years'],
               n_trades=int(len(tr)), sl_med=round(sl_med, 1),
               tp_med=round(tp_med, 1),
               verdict=r['verdict'], score=r.get('rqs2_score'),
               gates=r.get('gates'), metrics=r.get('metrics'),
               notes=r.get('notes'))
    fp = os.path.join(OUT, f'final_{tf}.json')
    with open(fp, 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nVERDICT={r['verdict']}  score={r.get('rqs2_score')}")
    print(f"skill_p_perm={r.get('metrics', {}).get('skill_p_perm')}")
    print(f'SAVED -> {fp}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', choices=['discover', 'final'], required=True)
    ap.add_argument('--tf', default='M1')
    a = ap.parse_args()
    if a.phase == 'discover':
        phase_discover(a.tf)
    else:
        phase_final(a.tf)
