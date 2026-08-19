#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S892 «رانشِ جلسه‌ای» — اجرای پیش‌ثبت‌شده (مسیرِ C).

قرارداد: results/S892_PREREG_AsianSessionDrift_Xauusd_MTF.md (کامیت b0f8770a)
  - رویداد: اولین کندلِ ساعتِ H سرور در هر روز؛ جهتِ ثابتِ dir.
  - خانواده: H∈{0..23} × dir∈{long,short} = ۴۸ پیکربندی/TF؛ N_trials=912.
  - کشف ۷۰٪ اول؛ یک آزمونِ RQS2 روی کل با split_bar.
  - SL=1.5×ATR(100) میانهٔ اکتشاف؛ TP=1.5×SL؛ hold=4h معادلِ کندل؛ no-overlap.
  - null: جای‌گشتِ جهتِ تصادفی K=1000 seed=892.

اجرا:  python3 strategies/s892_session_drift.py M15
"""
import sys, os, json, gc, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from tools import s434_fast_data as fd
from engine import rqs2
from engine import scalp_engine as se

ASSET = 'XAUUSD'
PIP = 0.1
SPREAD_PIP = 3.3
SL_ATR_MULT = 1.5
RR = 1.5
HOLD_HOURS = 4
N_TRIALS = 912
NULL_K = 1000
NULL_SEED = 892
OUT = 'results/_s892'

TF_MIN = {'M1':1,'M3':3,'M4':4,'M5':5,'M6':6,'M10':10,'M12':12,'M15':15,
          'M20':20,'M30':30,'H1':60,'H2':120,'H3':180,'H6':360,'H8':480,
          'H12':720,'D1':1440,'W1':10080,'MN1':43200}


def atr_series(df, n=100):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).rolling(n).mean().values


def hour_first_mask(times, H):
    """True در اولین کندلی که ساعتش H است و کندلِ قبلی ساعتش H نبود."""
    hrs = pd.to_datetime(times, unit='s').hour.values
    is_h = hrs == H
    prev = np.roll(is_h, 1); prev[0] = False
    return is_h & ~prev


def build_null(c, ls, ss, hold, K=NULL_K, seed=NULL_SEED):
    sig_idx = np.where(ls | ss)[0]
    n = len(sig_idx)
    if n < 30:
        return None
    fwd = np.full(n, np.nan)
    for j, ei in enumerate(sig_idx):
        k = min(ei + hold, len(c) - 1)
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
    print(f"S892 Session-Hour Drift · XAUUSD-{tf} · path C (prereg b0f8770a)")
    print('=' * 72, flush=True)
    if TF_MIN[tf] >= 1440:
        _save(tf, dict(card=f'XAUUSD-{tf}', verdict='INCOMPLETE',
                       reason='hour-of-day concept undefined at >=D1'))
        print("TF has no hour structure → INCOMPLETE")
        return
    hold = max(2, math.ceil(HOLD_HOURS * 60 / TF_MIN[tf]))
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    if 'volume' in df.columns:
        df = df.drop(columns=['volume'])
    src = d.get('src', '?')
    del d; gc.collect()
    N = len(df)
    split = int(N * 0.70)
    print(f"src={src}  bars={N}  split={split}  hold={hold} bars", flush=True)

    a = atr_series(df.iloc[:split], 100)
    med_atr = float(np.nanmedian(a))
    del a; gc.collect()
    sl_pip = SL_ATR_MULT * med_atr / PIP
    tp_pip = RR * sl_pip
    be = (sl_pip + SPREAD_PIP) / (sl_pip + tp_pip) * 100.0
    print(f"SL={sl_pip:.2f}pip TP={tp_pip:.2f}pip BE={be:.2f}%", flush=True)

    times = df['time'].values
    c = df['close'].values
    dfe = df.iloc[:split]
    z = np.zeros(split, dtype=bool)

    # ---------- کشف: فقط ۷۰٪ اول ----------
    best = None
    for H in range(24):
        ev = hour_first_mask(times[:split], H)
        if ev.sum() < 40:
            continue
        for dr in ('long', 'short'):
            ls_e = ev if dr == 'long' else z
            ss_e = ev if dr == 'short' else z
            tr = se.simulate_trades(dfe, ls_e, ss_e, sl_pip=sl_pip,
                                    tp_pip=tp_pip, asset=ASSET,
                                    max_hold=hold, allow_overlap=False)
            if tr is None or len(tr) < 40:
                continue
            n = len(tr); wr = float((tr['pnl_pip'] > 0).mean() * 100)
            net = float(tr['pnl_pip'].sum())
            score = wr + 0.001 * net
            if best is None or score > best['score']:
                best = dict(H=H, dir=dr, score=score, is_n=n,
                            is_wr=round(wr, 2), is_net=round(net, 1))
                print(f"  new best: H={H:>2} {dr:<5} n={n:>5} WR={wr:6.2f}% net={net:>9.1f}", flush=True)
            del tr; gc.collect()
    if best is None:
        _save(tf, dict(card=f'XAUUSD-{tf}', verdict='INCOMPLETE',
                       reason='discovery <40 trades all configs', src=src))
        print("DISCOVERY EMPTY → INCOMPLETE")
        return

    print(f"\nLOCKED: H={best['H']} dir={best['dir']}  "
          f"IS: n={best['is_n']} WR={best['is_wr']}%", flush=True)

    # ---------- آزمونِ نهایی: کل داده، یک بار ----------
    ev = hour_first_mask(times, best['H'])
    zf = np.zeros(N, dtype=bool)
    ls = ev if best['dir'] == 'long' else zf
    ss = ev if best['dir'] == 'short' else zf
    tr = se.simulate_trades(df, ls, ss, sl_pip=sl_pip, tp_pip=tp_pip,
                            asset=ASSET, max_hold=hold, allow_overlap=False)
    null = build_null(c, ls, ss, hold)
    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_pip, tp_pip=tp_pip,
                          bar_time=times, null=null,
                          n_trials=N_TRIALS, split_bar=split, close=c)
    n_all = len(tr); wr_all = float((tr['pnl_pip'] > 0).mean() * 100)
    hm = tr['entry_bar'].values >= split
    oos_n = int(hm.sum())
    oos_wr = float((tr.loc[hm, 'pnl_pip'] > 0).mean() * 100) if oos_n else None
    print(f"\nFULL: n={n_all} WR={wr_all:.2f}% net={float(tr['pnl_pip'].sum()):.1f}pip")
    print(f"OOS: n={oos_n} WR={oos_wr}")
    print(f"VERDICT: {r.get('verdict')}  score={r.get('rqs2_score')}")
    print(f"gates: {r.get('gates')}")
    print(f"notes: {r.get('notes')[:5]}", flush=True)

    _save(tf, dict(card=f'XAUUSD-{tf}', prereg='b0f8770a', src=src, bars=N,
                   split=split, hold=hold, sl_pip=round(sl_pip, 2),
                   tp_pip=round(tp_pip, 2), locked=best, n=n_all,
                   wr=round(wr_all, 2),
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
