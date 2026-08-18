#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S891 «رژیمِ بازتابی» — اجرای پیش‌ثبت‌شده (مسیرِ C).

قرارداد: results/S891_PREREG_ReflexiveRegime_Xauusd_MTF.md (کامیت 4ae94d8d)
  - رویداد: گذرِ hurst(64) از آستانهٔ چارکیِ q (قفل روی نیمهٔ اکتشاف).
  - جهت: علامتِ close[t]−close[t−Ls] (follow) یا آینه (fade).
  - خانواده: q∈{0.72,0.86} × Ls∈{21,55} × {follow,fade} = ۸ پیکربندی/TF.
  - N_trials = 152 (۸×۱۹). کشف ۷۰٪ اول؛ یک آزمونِ RQS2 روی کل با split_bar.
  - SL=1.5×ATR(100) میانهٔ اکتشاف؛ TP=1.5×SL؛ hold=64؛ no-overlap؛ موتورِ رسمی.
  - null: جای‌گشتِ جهتِ تصادفی K=1000 seed=891.

اجرا:  python3 strategies/s891_reflexive_regime.py M15
"""
import sys, os, json, gc
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from tools import s434_fast_data as fd
from engine import rqs2
from engine import scalp_engine as se
from strategies.s891_power_scout import hurst_fast

ASSET = 'XAUUSD'
PIP = 0.1
SPREAD_PIP = 3.3
QS = [0.72, 0.86]
LSS = [21, 55]
HP = 64
SL_ATR_MULT = 1.5
RR = 1.5
MAX_HOLD = 64
N_TRIALS = 152
NULL_K = 1000
NULL_SEED = 891
OUT = 'results/_s891'


def atr_series(df, n=100):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).rolling(n).mean().values


def signals(c, hu, thr, Ls, fade=False):
    above = hu > thr
    prev = np.roll(above, 1); prev[0] = False
    cross = above & ~prev
    cross[:HP + Ls + 2] = False
    up = c > np.roll(c, Ls)
    lb = cross & up
    sb = cross & ~up
    if fade:
        lb, sb = sb, lb
    return lb, sb


def build_null(c, ls, ss, K=NULL_K, seed=NULL_SEED):
    sig_idx = np.where(ls | ss)[0]
    n = len(sig_idx)
    if n < 30:
        return None
    fwd = np.full(n, np.nan)
    for j, ei in enumerate(sig_idx):
        k = min(ei + MAX_HOLD, len(c) - 1)
        fwd[j] = c[k] - c[ei]
    fwd = fwd[np.isfinite(fwd)]
    if len(fwd) < 30:
        return None
    base_wins = fwd > 0
    rng = np.random.default_rng(seed)
    wrs = []
    for _ in range(K):
        signs = rng.integers(0, 2, size=len(fwd)).astype(bool)
        w = np.where(signs, base_wins, ~base_wins)
        wrs.append(w.mean() * 100.0)
    wrs = np.array(wrs)
    ref = float(np.mean(wrs))
    side = dict(uncond_wr=ref, perm_mean=ref, perm_sd=float(np.std(wrs)),
                perm_max=float(np.max(wrs)), perm_k=K)
    return {'long': dict(side), 'short': dict(side)}


def run_tf(tf):
    print('=' * 72)
    print(f"S891 Reflexive Regime · XAUUSD-{tf} · path C (prereg 4ae94d8d)")
    print('=' * 72, flush=True)
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    if 'volume' in df.columns:
        df = df.drop(columns=['volume'])
    src = d.get('src', '?')
    del d; gc.collect()
    N = len(df)
    split = int(N * 0.70)
    print(f"src={src}  bars={N}  split={split}", flush=True)

    a = atr_series(df.iloc[:split], 100)
    med_atr = float(np.nanmedian(a))
    del a; gc.collect()
    sl_pip = SL_ATR_MULT * med_atr / PIP
    tp_pip = RR * sl_pip
    be = (sl_pip + SPREAD_PIP) / (sl_pip + tp_pip) * 100.0
    print(f"medATR={med_atr:.4f}  SL={sl_pip:.2f}pip  TP={tp_pip:.2f}pip  BE={be:.2f}%", flush=True)

    c = df['close'].values
    hu_full = hurst_fast(c, HP)
    hu_disc = hu_full[:split]
    huv = hu_disc[np.isfinite(hu_disc)]
    dfe = df.iloc[:split]

    # ---------- کشف: فقط ۷۰٪ اول ----------
    best = None
    for q in QS:
        thr = float(np.quantile(huv, q))
        for Ls in LSS:
            for fade in (False, True):
                ls_e, ss_e = signals(c[:split], hu_disc, thr, Ls, fade)
                tr = se.simulate_trades(dfe, ls_e, ss_e, sl_pip=sl_pip,
                                        tp_pip=tp_pip, asset=ASSET,
                                        max_hold=MAX_HOLD, allow_overlap=False)
                if tr is None or len(tr) < 40:
                    del ls_e, ss_e; gc.collect(); continue
                n = len(tr); wr = float((tr['pnl_pip'] > 0).mean() * 100)
                net = float(tr['pnl_pip'].sum())
                score = wr + 0.001 * net
                tag = f"q{q}·Ls{Ls}{'·fade' if fade else '·follow'}"
                print(f"  {tag:>18}: n={n:>6}  WR={wr:6.2f}%  net={net:>10.1f}  score={score:7.3f}", flush=True)
                if best is None or score > best['score']:
                    best = dict(q=q, thr=thr, Ls=Ls, fade=fade, score=score,
                                is_n=n, is_wr=round(wr, 2), is_net=round(net, 1))
                del tr, ls_e, ss_e; gc.collect()
    if best is None:
        _save(tf, dict(card=f'XAUUSD-{tf}', verdict='INCOMPLETE',
                       reason='discovery <40 trades all configs', src=src))
        print("DISCOVERY EMPTY → INCOMPLETE")
        return

    print(f"\nLOCKED: q={best['q']} thr={best['thr']:.5f} Ls={best['Ls']} "
          f"fade={best['fade']}  IS: n={best['is_n']} WR={best['is_wr']}%", flush=True)

    # ---------- آزمونِ نهایی: کل داده، یک بار ----------
    ls, ss = signals(c, hu_full, best['thr'], best['Ls'], best['fade'])
    tr = se.simulate_trades(df, ls, ss, sl_pip=sl_pip, tp_pip=tp_pip,
                            asset=ASSET, max_hold=MAX_HOLD, allow_overlap=False)
    null = build_null(c, ls, ss)
    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_pip, tp_pip=tp_pip,
                          bar_time=df['time'].values, null=null,
                          n_trials=N_TRIALS, split_bar=split, close=c)
    n_all = len(tr); wr_all = float((tr['pnl_pip'] > 0).mean() * 100)
    hm = tr['entry_bar'].values >= split
    oos_n = int(hm.sum())
    oos_wr = float((tr.loc[hm, 'pnl_pip'] > 0).mean() * 100) if oos_n else None
    print(f"\nFULL: n={n_all}  WR={wr_all:.2f}%  net={float(tr['pnl_pip'].sum()):.1f}pip")
    print(f"OOS: n={oos_n}  WR={oos_wr}")
    print(f"VERDICT: {r.get('verdict')}  score={r.get('rqs2_score')}")
    print(f"gates: {r.get('gates')}")
    print(f"notes: {r.get('notes')[:5]}", flush=True)

    _save(tf, dict(card=f'XAUUSD-{tf}', prereg='4ae94d8d', src=src, bars=N,
                   split=split, sl_pip=round(sl_pip, 2), tp_pip=round(tp_pip, 2),
                   locked=best, n=n_all, wr=round(wr_all, 2),
                   net_pip=round(float(tr['pnl_pip'].sum()), 1),
                   oos_n=oos_n, oos_wr=round(oos_wr, 2) if oos_wr else None,
                   null=null, rqs2=r))
    tr.to_csv(f'{OUT}/trades_XAUUSD-{tf}.csv', index=False)


def _save(tf, res):
    os.makedirs(OUT, exist_ok=True)
    with open(f'{OUT}/rqs2_XAUUSD-{tf}.json', 'w') as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print(f"saved → {OUT}/rqs2_XAUUSD-{tf}.json", flush=True)


if __name__ == '__main__':
    run_tf(sys.argv[1] if len(sys.argv) > 1 else 'M1')
