# -*- coding: utf-8 -*-
"""S930 — «شکستِ تازهٔ اکسترممِ ماهِ قبل با کندلِ مطلع» (Informed Monthly-Extremum Break).

پیش‌ثبت: results/S930_PREREG_monthly_extremum_break.md (کامیت 0c5d32ce — پیش از این کد).

رویداد LONG : close[t] > PMH و close[t−1] ≤ PMH و اولین عبورِ ماهِ جاری (یک LONG/ماه)
رویداد SHORT: آینه با PML
بازوها: gated (ρ=|body|/range ≥ 0.618 هم‌جهت) · ungated · fade (فقط کنترلِ گزارشی)
براکتِ شناور: SL=1.272×ATR21[t−1]، TP=2.058×ATR21[t−1]، max_hold=16 — شبیه‌سازِ رسمی
engine/scalp_engine.simulate_trades (ورود openِ بعد، allow_overlap=False، اسپرد 3.3).
n_trials=38 (19 TF × 2 بازوی داوری‌شده).
"""
from __future__ import annotations

import gc
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import rqs2 as R                      # noqa: E402
from engine import scalp_engine as se             # noqa: E402
from tools import s434_fast_data as fd            # noqa: E402

ASSET = 'XAUUSD'
RHO = 0.618
K_SL, K_TP = 1.272, 2.058
MAX_HOLD = 16
ATR_P = 21
SPLIT_FRAC = 0.70
SEED = 20260905
N_TRIALS = 38
OUT = 'results/_s930'
LABEL = 'S930_InformedMonthlyExtremumBreak'
ARMS = ('gated', 'ungated')          # داوری‌شده
CONTROL = 'fade'                     # فقط گزارشی


# ───────────────────────────── ویژگی‌ها (علّی) ─────────────────────────────
def month_id(t_epoch: np.ndarray) -> np.ndarray:
    dt = pd.to_datetime(t_epoch, unit='s')
    return (dt.year * 12 + dt.month - 1).to_numpy().astype(np.int64)


def prev_month_extrema(high, low, mid):
    """PMH/PML: بیشینه/کمینهٔ ماهِ تقویمیِ *قبل* — NaN اگر ماهِ قبلِ مجاور در داده نباشد."""
    n = high.shape[0]
    pmh = np.full(n, np.nan); pml = np.full(n, np.nan)
    change = np.flatnonzero(np.diff(mid)) + 1
    starts = np.concatenate([[0], change])
    ends = np.concatenate([change, [n]])
    mids = mid[starts]
    hmax = np.array([high[s:e].max() for s, e in zip(starts, ends)])
    lmin = np.array([low[s:e].min() for s, e in zip(starts, ends)])
    for k in range(1, len(starts)):
        if mids[k] == mids[k - 1] + 1:
            pmh[starts[k]:ends[k]] = hmax[k - 1]
            pml[starts[k]:ends[k]] = lmin[k - 1]
    return pmh, pml


def atr_causal(high, low, close, p=ATR_P):
    n = high.shape[0]
    tr = np.zeros(n)
    tr[1:] = np.maximum.reduce([high[1:] - low[1:],
                                np.abs(high[1:] - close[:-1]),
                                np.abs(low[1:] - close[:-1])])
    cs = np.cumsum(tr)
    atr = np.full(n, np.nan)
    atr[p:] = (cs[p:] - cs[:-p]) / p            # mean(tr[i-p+1..i])
    atr_prev = np.full(n, np.nan)
    atr_prev[1:] = atr[:-1]                     # فقط گذشته
    return atr_prev


def first_cross_of_month(cond: np.ndarray, mid: np.ndarray) -> np.ndarray:
    out = np.zeros_like(cond)
    idx = np.flatnonzero(cond)
    seen = set()
    for i in idx:
        m = int(mid[i])
        if m not in seen:
            seen.add(m); out[i] = True
    return out


def features(d, keep_aux=True):
    o, h, l, c = d['open'], d['high'], d['low'], d['close']
    n = c.shape[0]
    mid = month_id(d['time'])
    pmh, pml = prev_month_extrema(h, l, mid)
    atr_prev = atr_causal(h, l, c)
    prev_c = np.full(n, np.nan); prev_c[1:] = c[:-1]
    with np.errstate(invalid='ignore'):
        up_x = (c > pmh) & (prev_c <= pmh)
        dn_x = (c < pml) & (prev_c >= pml)
    first_two = np.isin(mid, np.unique(mid)[:2])
    valid = ~first_two & np.isfinite(atr_prev) & (atr_prev > 1e-12)
    up_x &= valid; dn_x &= valid
    up_first = first_cross_of_month(up_x, mid)
    dn_first = first_cross_of_month(dn_x, mid)
    rng_ = h - l
    body = c - o
    rho = np.divide(np.abs(body), rng_, out=np.zeros(n), where=rng_ > 0)
    inf_up = (rho >= RHO) & (body > 0); inf_dn = (rho >= RHO) & (body < 0)
    del rng_, body, rho, prev_c, up_x, dn_x, first_two
    if not keep_aux:                       # حافظه (M1 = 5M کندل): فقط ضروری‌ها
        del pmh, pml
        pmh = pml = None
    gc.collect()
    return dict(up=up_first, dn=dn_first, inf_up=inf_up, inf_dn=inf_dn,
                atr_prev=atr_prev, valid=valid, mid=mid, pmh=pmh, pml=pml)


def arm_signals(f, arm):
    if arm == 'gated':
        return f['up'] & f['inf_up'], f['dn'] & f['inf_dn']
    if arm == 'ungated':
        return f['up'].copy(), f['dn'].copy()
    if arm == 'fade':
        return f['dn'].copy(), f['up'].copy()
    raise ValueError(arm)


# ───────────────────────────── شبیه‌سازی و نول ─────────────────────────────
def _df(d):
    return pd.DataFrame(dict(open=d['open'], high=d['high'], low=d['low'], close=d['close']),
                        copy=False)


def simulate(df, ls, ss, sl_arr, tp_arr, overlap=False):
    return se.simulate_trades(df, ls, ss, sl_arr, tp_arr, ASSET,
                              max_hold=MAX_HOLD, allow_overlap=overlap)


def _wr(tr):
    return None if tr is None or len(tr) == 0 else float((tr['outcome'] == 'win').mean() * 100)


def build_null(df, valid, sl_arr, tp_arr, n_long, n_short, rng, k_perm, verbose=True):
    """دوقلوی سخت به تفکیکِ سمت با همان شبیه‌ساز/براکتِ شناور/max_hold."""
    n = len(df)
    pool = np.flatnonzero(valid[:n - MAX_HOLD - 1])
    null = {}
    UNC_CAP = 100_000
    for side, n_side in (('long', n_long), ('short', n_short)):
        d = dict(uncond_wr=None, perm_mean=None, perm_sd=None, perm_max=None, perm_k=None)
        if n_side >= 1 and pool.size > 0:
            st = max(1, pool.size // UNC_CAP)
            unc = pool[::st]
            wins = 0; m = 0
            for s0 in range(0, unc.size, 25_000):
                mask = np.zeros(n, bool); mask[unc[s0:s0 + 25_000]] = True
                z = np.zeros(n, bool)
                tr = simulate(df, mask if side == 'long' else z,
                              z if side == 'long' else mask, sl_arr, tp_arr, overlap=True)
                if tr is not None and len(tr):
                    wins += int((tr['outcome'] == 'win').sum()); m += len(tr)
                del tr; gc.collect()
            d['uncond_wr'] = 100.0 * wins / m if m else None
            k = min(n_side, pool.size)
            wrs = []
            for _ in range(k_perm):
                pick = rng.choice(pool, size=k, replace=False)
                mask = np.zeros(n, bool); mask[pick] = True
                z = np.zeros(n, bool)
                tr = simulate(df, mask if side == 'long' else z,
                              z if side == 'long' else mask, sl_arr, tp_arr)
                w = _wr(tr)
                if w is not None:
                    wrs.append(w)
            if wrs:
                a = np.asarray(wrs)
                d.update(perm_mean=float(a.mean()),
                         perm_sd=float(a.std(ddof=1)) if a.size > 1 else None,
                         perm_max=float(a.max()), perm_k=int(a.size))
        null[side] = d
        if verbose:
            print(f'      null {side:<5} uncond={d["uncond_wr"]} perm_mean={d["perm_mean"]} '
                  f'sd={d["perm_sd"]} k={d["perm_k"]}', flush=True)
    return null


# ───────────────────────────── راستی‌آزمایی ─────────────────────────────
def verify(n=20000, seed=5) -> float:
    rng = np.random.default_rng(seed)
    t = 1_400_000_000 + np.arange(n) * 14400          # H4 مصنوعی
    c = 1800 + np.cumsum(rng.normal(0, 3, n))
    o = np.concatenate([[c[0]], c[:-1]]) + rng.normal(0, 0.5, n)
    h = np.maximum(o, c) + np.abs(rng.normal(0, 2, n))
    l = np.minimum(o, c) - np.abs(rng.normal(0, 2, n))
    d = dict(time=t, open=o, high=h, low=l, close=c)
    f = features(d, keep_aux=True)
    s = pd.DataFrame(dict(high=h, low=l, close=c), index=pd.to_datetime(t, unit='s'))
    mh = s['high'].resample('MS').max().shift(1); ml = s['low'].resample('MS').min().shift(1)
    ref_pmh = mh.reindex(s.index, method='ffill').to_numpy()
    ref_pml = ml.reindex(s.index, method='ffill').to_numpy()
    m = np.isfinite(f['pmh']) & np.isfinite(ref_pmh)
    worst = float(np.max(np.abs(f['pmh'][m] - ref_pmh[m])))
    m = np.isfinite(f['pml']) & np.isfinite(ref_pml)
    worst = max(worst, float(np.max(np.abs(f['pml'][m] - ref_pml[m]))))
    tr = pd.concat([s['high'] - s['low'], (s['high'] - s['close'].shift()).abs(),
                    (s['low'] - s['close'].shift()).abs()], axis=1).max(axis=1)
    tr.iloc[0] = 0.0
    ref_atr = tr.rolling(ATR_P).mean().shift(1).to_numpy()
    m = np.isfinite(ref_atr) & np.isfinite(f['atr_prev'])
    worst = max(worst, float(np.max(np.abs(ref_atr[m] - f['atr_prev'][m]))))
    df = pd.DataFrame(dict(mid=f['mid'],
                           up=((s['close'] > ref_pmh) & (s['close'].shift() <= ref_pmh)).to_numpy(),
                           valid=f['valid']))
    df['up'] &= df['valid']
    ref_first = (df.groupby('mid')['up'].cumsum().eq(1) & df['up']).to_numpy()
    worst = max(worst, float(np.sum(ref_first != f['up'])))
    cut = n // 2
    d2 = {k: v.copy() for k, v in d.items()}
    for k in ('open', 'high', 'low', 'close'):
        d2[k][cut:] += rng.normal(0, 50, n - cut)
    f2 = features(d2)
    la = int(np.sum(f['up'][:cut] != f2['up'][:cut]) + np.sum(f['dn'][:cut] != f2['dn'][:cut]))
    worst = max(worst, float(la))
    print(f'  synthetic: up_first={int(f["up"].sum())} dn_first={int(f["dn"].sum())} '
          f'months={len(np.unique(f["mid"]))} look-ahead diffs={la}')
    return worst


# ───────────────────────────── کارت ─────────────────────────────
def run_card(tf: str, verbose=True) -> dict:
    os.makedirs(OUT, exist_ok=True)
    d = fd.load_fast(ASSET, tf)
    n = int(d['n_bars'])
    print(f"\n{'='*84}\n=== {LABEL} :: {ASSET}_{tf}  bars={n:,}  "
          f"span={d['span_years']}y\n    src={d['src']}  ({d['first_utc']} → {d['last_utc']})", flush=True)
    for k in ('volume', 'hour', 'minute', 'dow'):   # حافظه: ستون‌های بی‌استفاده
        d.pop(k, None)
    f = features(d, keep_aux=False)
    pip = se.ASSETS[ASSET]['pip']
    ok = np.isfinite(f['atr_prev'])
    sl_arr = np.where(ok, K_SL * f['atr_prev'] / pip, 1e-9)
    tp_arr = np.where(ok, K_TP * f['atr_prev'] / pip, 1e-9)
    del ok; f['atr_prev'] = None; f['mid'] = None; gc.collect()
    df = _df(d)
    split_bar = int(SPLIT_FRAC * n)
    k_perm = 500 if n > 1_500_000 else 1000
    out = dict(card=f'{ASSET}_{tf}', src=d['src'], bars=n, first_utc=d['first_utc'],
               last_utc=d['last_utc'], span_years=d['span_years'], seed=SEED,
               events_up=int(f['up'].sum()), events_dn=int(f['dn'].sum()), arms={})
    print(f"    monthly first-crosses: up={out['events_up']} dn={out['events_dn']}", flush=True)
    for arm in ARMS + (CONTROL,):
        ls, ss = arm_signals(f, arm)
        tr = simulate(df, ls, ss, sl_arr, tp_arr)
        rec = dict(n_signals=int(ls.sum() + ss.sum()))
        if tr is None or len(tr) < 5:
            rec['verdict'] = 'NO_TRADES'; rec['n_trades'] = 0 if tr is None else int(len(tr))
            out['arms'][arm] = rec; print(f'    [{arm}] NO_TRADES', flush=True); continue
        nL = int((tr['direction'] == 'long').sum()); nS = int((tr['direction'] == 'short').sum())
        sl_med = float(np.median(tr['sl_pip'])); tp_med = sl_med * (K_TP / K_SL)
        rec.update(n_trades=int(len(tr)), n_long=nL, n_short=nS, wr=_wr(tr),
                   sl_pip_med=sl_med, tp_pip_med=tp_med)
        print(f'    [{arm}] trades={len(tr)} (L={nL} S={nS}) wr={rec["wr"]:.2f} '
              f'SLmed={sl_med:.1f} TPmed={tp_med:.1f}', flush=True)
        rng = np.random.default_rng(SEED)
        null = build_null(df, f['valid'], sl_arr, tp_arr, nL, nS, rng, k_perm, verbose)
        res = R.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med, bar_time=d['time'],
                             close=d['close'], null=null, n_trials=N_TRIALS, split_bar=split_bar)
        print(R.format_rqs2(f"{LABEL}_{arm}_{ASSET}_{tf}", res), flush=True)
        rec.update(null=null, k_perm=k_perm, rqs2=res, verdict=res['verdict'],
                   judged=(arm in ARMS))
        out['arms'][arm] = rec
        tr.to_csv(f'{OUT}/{ASSET}_{tf}_{arm}_trades.csv', index=False)
        del tr; gc.collect()
    judged = [(a, out['arms'][a]) for a in ARMS if 'rqs2' in out['arms'][a]]
    if judged:
        best = max(judged, key=lambda kv: kv[1]['rqs2']['rqs2_score'])
        out['verdict'] = best[1]['verdict']; out['best_arm'] = best[0]
        out['best_score'] = best[1]['rqs2']['rqs2_score']
    else:
        out['verdict'] = 'NO_TRADES'
    with open(f'{OUT}/{ASSET}_{tf}_rqs2.json', 'w') as fh:
        json.dump(out, fh, ensure_ascii=False, default=str)
    print(f"    ==> card verdict: {out['verdict']} (best arm {out.get('best_arm')} "
          f"{out.get('best_score')})", flush=True)
    return out


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'verify':
        w = verify()
        print(f'PMH/PML + ATR21 + first-cross + look-ahead worst |Δ| = {w:.3e}')
        sys.exit(0 if w < 1e-9 else 1)
    run_card(sys.argv[1] if len(sys.argv) > 1 else 'M1')
