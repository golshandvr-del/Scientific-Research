#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S874 — «ادامهٔ حرکتِ آسان» (Ease-of-Movement Continuation, Arms 1989) · XAUUSD چند-TF
پیاده‌سازی دقیق پیش‌ثبت results/S874_PREREG_EASE_OF_MOVEMENT_CONTINUATION.md

قرارداد (منجمد):
  body=close−open · rvol=vol/median(vol[t−55..t−1]) · ease=|body|/ATR21[t−1]/rvol
  event = ease≥1.618 ∧ |body|≥1.0×ATR21[t−1] ∧ rvol≤1.0 ؛ فقط لبه (t−1 event نبود)
  جهت follow=sign(body) · گونه‌ها {plain, gated(drift-90 هم‌علامت)} (n_trials=2)
  هندسه S965: SL=1.272×ATR21[t−1] · TP=2.058×ATR21[t−1] · max_hold=16 · overlap ممنوع
  مسیر C: IS نیمهٔ اول، نال K=200، گیت z_IS≥2.0؛ داوری کل دوره K=1000
  SEED=20260826 (IS) / 20260827 (داوری)
"""
import os, sys, json, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se
from engine import rqs2 as R
from tools import s434_fast_data as fd

SEED = 20260826
K_PERM = 1000
K_IS = 200
N_TRIALS = 2
Z_IS_MIN = 2.0
ATR_P = 21
VOL_W = 55
EASE_MIN = 1.618
BODY_MIN = 1.0
RVOL_MAX = 1.0
DRIFT_K = 90
SL_K = 1.272
TP_K = 2.058
MAX_HOLD = 16
ASSET = 'XAUUSD'
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'results', '_s874')

TFS = ['M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20', 'M30',
       'H1', 'H2', 'H3', 'H4', 'H6', 'H8', 'H12', 'D1', 'W1', 'MN1']

VARIANTS = ['plain', 'gated']


def atr_wilder(df, p=ATR_P):
    h = df['high'].astype(float); l = df['low'].astype(float)
    c = df['close'].astype(float); pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / p, adjust=False).mean()


def detect_events(df):
    """خروجی: idx (لبه‌ها), dir=sign(body), drift_ok(bool) برای gated, ATR21[t−1]."""
    o = df['open'].to_numpy(float); c = df['close'].to_numpy(float)
    v = df['volume'].to_numpy(float)
    n = len(df)
    a_prev = atr_wilder(df).shift(1).to_numpy(float)          # ATR21[t−1] علّی
    vmed = pd.Series(v).shift(1).rolling(VOL_W, min_periods=VOL_W).median().to_numpy(float)
    body = c - o
    with np.errstate(divide='ignore', invalid='ignore'):
        rvol = v / vmed
        ease = np.abs(body) / a_prev / rvol
    warm = np.arange(n) >= max(VOL_W + 1, ATR_P * 3, DRIFT_K + 1)
    ok = (warm & np.isfinite(ease) & np.isfinite(rvol) & np.isfinite(a_prev)
          & (a_prev > 0) & (rvol > 0)
          & (ease >= EASE_MIN) & (np.abs(body) >= BODY_MIN * a_prev) & (rvol <= RVOL_MAX))
    prev_ok = np.roll(ok, 1); prev_ok[0] = False
    edge = ok & ~prev_ok
    idx = np.nonzero(edge)[0]
    idx = idx[idx < n - 1]
    dr = np.sign(body[idx]).astype(int)
    keep = dr != 0
    idx, dr = idx[keep], dr[keep]
    drift = np.full(n, np.nan)
    drift[DRIFT_K + 1:] = c[DRIFT_K:-1] - c[:-(DRIFT_K + 1)]  # close[t−1]−close[t−1−90]
    drift_ok = np.sign(drift[idx]) == dr
    return idx, dr, drift_ok, a_prev


def sim(df, ev_idx, sides, sl_arr, tp_arr):
    n = len(df)
    ls = np.zeros(n, dtype=bool); ss = np.zeros(n, dtype=bool)
    sd = np.asarray(sides)
    ls[ev_idx[sd > 0]] = True; ss[ev_idx[sd < 0]] = True
    ls[-1] = False; ss[-1] = False
    return se.simulate_trades(df, ls, ss, sl_pip=sl_arr, tp_pip=tp_arr,
                              asset=ASSET, max_hold=MAX_HOLD, allow_overlap=False)


def wr_of(tr):
    if tr is None or len(tr) == 0:
        return np.nan, 0
    return 100.0 * (tr['pnl_pip'] > 0).mean(), len(tr)


def variant_events(idx, dr, drift_ok, gate):
    m = drift_ok if gate == 'gated' else np.ones(len(idx), bool)
    return idx[m], dr[m]


FORCE_ADJ = False  # --adjudicate: حکم رسمی موتور برای برنده‌ی IS حتی زیر گیت (قانون «هر شماره یک حکم»)


def process_tf(tf):
    t0 = time.time()
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d); src = d.get('src')
    n = len(df)
    close = df['close'].to_numpy(float)
    idx, dr, drift_ok, a_prev = detect_events(df)
    a_fill = np.where(np.isfinite(a_prev) & (a_prev > 0), a_prev, np.nan)
    a_fill = pd.Series(a_fill).bfill().ffill().to_numpy(float)
    sl_arr = np.maximum(SL_K * a_fill / 0.1, 1e-9)
    tp_arr = np.maximum(TP_K * a_fill / 0.1, 1e-9)
    split = n // 2

    out = dict(tf=tf, src=src, bars=n, split_bar=split, max_hold=MAX_HOLD,
               n_events=int(len(idx)), n_events_gated=int(drift_ok.sum()),
               n_long=int((dr > 0).sum()), n_short=int((dr < 0).sum()),
               sl_median_pip=float(np.nanmedian(sl_arr[idx])) if len(idx) else None)
    if len(idx) < 60:
        out['verdict'] = 'NO_EVENTS'
        out['elapsed_s'] = round(time.time() - t0, 1)
        return out

    # ---- IS ----
    rng = np.random.default_rng(SEED)
    rows = []
    for gate in VARIANTS:
        sel_all, sides_all = variant_events(idx, dr, drift_ok, gate)
        m = sel_all < split
        sel, sides = sel_all[m], sides_all[m]
        if len(sel) < 30:
            rows.append(dict(gate=gate, mode='follow', n=int(len(sel)), wr=np.nan,
                             lift=np.nan, z_is=np.nan, note='n<30 in IS'))
            continue
        wrs = []
        for j in range(K_IS):
            rd = rng.choice([-1, 1], size=len(sel))
            tr = sim(df, sel, rd, sl_arr, tp_arr)
            if len(tr):
                wrs.append(100.0 * (tr['pnl_pip'] > 0).mean())
        mu, sd = (np.mean(wrs), np.std(wrs, ddof=1)) if len(wrs) > 2 else (np.nan, np.nan)
        tr = sim(df, sel, sides, sl_arr, tp_arr)
        wr, cnt = wr_of(tr)
        z = (wr - mu) / sd if (sd and sd > 0 and np.isfinite(wr)) else np.nan
        rows.append(dict(gate=gate, mode='follow', n=cnt, wr=wr, null_mu=mu, null_sd=sd,
                         lift=(wr - mu) if np.isfinite(wr) else np.nan, z_is=z,
                         pnl_pip=float(tr['pnl_pip'].sum()) if cnt else 0.0))
    out['is_grid'] = rows
    valid = [r for r in rows if np.isfinite(r.get('z_is', np.nan))]
    winner = max(valid, key=lambda r: r['z_is']) if valid else None
    out['winner'] = winner
    if winner is None or (winner['z_is'] < Z_IS_MIN and not FORCE_ADJ):
        out['verdict'] = 'DEAD_IS'
        out['elapsed_s'] = round(time.time() - t0, 1)
        return out

    # ---- داوری کامل ----
    gate = winner['gate']
    sel_full, sides_full = variant_events(idx, dr, drift_ok, gate)
    tr_full = sim(df, sel_full, sides_full, sl_arr, tp_arr)

    rng2 = np.random.default_rng(SEED + 1)
    wrs = []; wl = []; ws = []
    for j in range(K_PERM):
        rd = rng2.choice([-1, 1], size=len(sel_full))
        tr = sim(df, sel_full, rd, sl_arr, tp_arr)
        if len(tr):
            wrs.append(100.0 * (tr['pnl_pip'] > 0).mean())
            for s, acc in (('long', wl), ('short', ws)):
                mm = tr['direction'] == s
                if mm.any():
                    acc.append(100.0 * (tr.loc[mm, 'pnl_pip'] > 0).mean())

    def blk(arr):
        arr = np.asarray(arr if arr else wrs, float)
        return dict(uncond_wr=float(arr.mean()), perm_mean=float(arr.mean()),
                    perm_sd=float(arr.std(ddof=1)), perm_max=float(arr.max()),
                    perm_k=int(len(arr)))
    null_ps = {'long': blk(wl), 'short': blk(ws)}

    sl_eff = float(tr_full['sl_pip'].mean()) if len(tr_full) else float(np.nanmedian(sl_arr))
    kw = dict(sl_pip=sl_eff, tp_pip=sl_eff * (TP_K / SL_K),
              bar_time=df['time'].to_numpy(), close=close, null=null_ps, split_bar=split)
    res = R.compute_rqs2(tr_full, ASSET, n_trials=N_TRIALS, **kw)
    try:  # تنش چندگانگی (اطلاعاتی)
        rs = R.compute_rqs2(tr_full, ASSET, n_trials=20, **kw)
        out['stress_n20'] = {k: rs.get(k) for k in ('verdict', 'rqs2_score')}
    except Exception as e:
        out['stress_n20'] = dict(error=str(e))
    out['full'] = dict(n=len(tr_full), wr=wr_of(tr_full)[0],
                       pnl_pip=float(tr_full['pnl_pip'].sum()),
                       null_flat=dict(mean=float(np.mean(wrs)),
                                      sd=float(np.std(wrs, ddof=1)), k=len(wrs)))
    out['forced_adjudication'] = bool(winner['z_is'] < Z_IS_MIN)
    out['rqs2'] = {k: res.get(k) for k in ('verdict', 'rqs2_score', 'gates')}
    out['rqs2_metrics'] = res.get('metrics')
    out['verdict'] = res.get('verdict')
    out['score'] = res.get('rqs2_score')
    out['elapsed_s'] = round(time.time() - t0, 1)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    global FORCE_ADJ
    args = [a for a in sys.argv[1:] if a != '--adjudicate']
    FORCE_ADJ = '--adjudicate' in sys.argv
    only = args if args else TFS
    for tf in only:
        ck = os.path.join(OUT, f'checkpoint_{tf}{"_ADJ" if FORCE_ADJ else ""}.json')
        if os.path.exists(ck):
            print(f'[skip] {tf}', flush=True)
            continue
        print(f'[run ] {tf} ...', flush=True)
        try:
            out = process_tf(tf)
        except Exception as e:
            import traceback; traceback.print_exc()
            out = dict(tf=tf, error=str(e))
        with open(ck, 'w') as f:
            json.dump(out, f, ensure_ascii=False, indent=1, default=str)
        w = out.get('winner') or {}
        print(f"[done] {tf}: verdict={out.get('verdict')} score={out.get('score')} "
              f"n_ev={out.get('n_events')} winner={w.get('gate')} z_is={w.get('z_is')} "
              f"({out.get('elapsed_s')}s)", flush=True)


if __name__ == '__main__':
    main()
