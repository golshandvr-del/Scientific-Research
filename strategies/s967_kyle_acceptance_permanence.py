# -*- coding: utf-8 -*-
"""
S967 — «ماندگاریِ پذیرفته‌شده» (Kyle Acceptance-Confirmed Permanence) · XAUUSD
================================================================================
پیش‌ثبت: `results/S967_PREREG_KYLE_ACCEPTANCE_PERMANENCE.md`
(commit e1b49850 — پیش از اجرای هر آزمونی).

پایهٔ منجمد = فینالیست S965 (جست‌وجو نمی‌شود):
  شوک در t: high−low ≥ 2.618×ATR21[t−1]  و  ρ=|body|/range ≥ 0.618؛ جهت sign(body_t).

رویداد دوکندلی جدید — کندل پذیرش t+1 (هیچ استفاده‌ای از t+2):
  (1) بدون بازگشت: صعودی  close[t+1] ≥ close[t] − L·(close[t]−open[t])؛ نزولی آینه‌ای.
  (2) آرام:        high[t+1]−low[t+1] ≤ A·ATR21[t−1].
ورود: open کندل t+2 (سیگنال روی ایندکس t+1 ⇒ موتور در open بعدی وارد می‌شود).
mode follow/against؛ براکت شناور از ATR21[t−1] (ATR رویداد)؛ hold=16.

خانواده: L{0.5,0.0} × A{0.618,1.0} × mode{2} × geom{2} = ۱۶ عضو/کارت. ۱۹ TF.
n_trials=924 (تجمعی صادقانه). مسیر C. SEED=967.

بازوهای تشخیصی (فقط نیمهٔ کشف، فقط گزارش):
  base  = S965 منجمد، ورود open t+1.
  delay = همان شوک‌ها، ورود open t+2 بدون شرط پذیرش (کنترل تأخیر، P2).

مدل صفر: عین S965/S966 — K=500، سه تلهٔ s434، perm_k=تعداد جایگشت‌ها،
chunked uncond (CH=25k, UNC_CAP=250k).
"""
import sys
import os
import gc
import json
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se          # noqa: E402
from engine import rqs2                        # noqa: E402
from tools import s434_fast_data as fd         # noqa: E402

OUT = 'results/_scan_S967'
os.makedirs(OUT, exist_ok=True)

SEED = 967
K_PERM = 500
ATR_WIN = 21
COST_PIP = 3.3
WARM = 250
MAX_HOLD = 16

# ── پایهٔ منجمد S965 ─────────────────────────────────────────────────────
TH = 2.618
RHO = 0.618

# ── خانوادهٔ قفل‌شده (پیش‌ثبت §۳) — ۲×۲×۲×۲ = ۱۶ عضو ────────────────────
L_LIST = [0.5, 0.0]
A_LIST = [0.618, 1.0]
MODES = ['follow', 'against']
GEOMS = [(1.0, 1.618), (1.272, 2.058)]
N_TRIALS = 924

TFS = ['MN1', 'W1', 'D1', 'H12', 'H8', 'H6', 'H3', 'H2', 'H1', 'M30', 'M20',
       'M15', 'M12', 'M10', 'M6', 'M5', 'M4', 'M3', 'M1']


def _views_df(d, end=None):
    sl = slice(None, end)
    return pd.DataFrame({'time': d['time'][sl], 'open': d['open'][sl],
                         'high': d['high'][sl], 'low': d['low'][sl],
                         'close': d['close'][sl], 'volume': d['volume'][sl]},
                        copy=False)


def _rollsum(x, w):
    n = len(x)
    cs = np.concatenate(([0.0], np.cumsum(x)))
    if w >= n:
        return cs[1:].copy()
    out = np.empty(n)
    out[:w - 1] = cs[1:w]
    out[w - 1:] = cs[w:] - cs[:n - w + 1]
    return out


def features(df):
    """شوک منجمد S965 در t + آرایه‌های خام برای کندل پذیرش."""
    o = np.asarray(df['open'].values, dtype=np.float64)
    h = np.asarray(df['high'].values, dtype=np.float64)
    l = np.asarray(df['low'].values, dtype=np.float64)
    c = np.asarray(df['close'].values, dtype=np.float64)
    n = len(c)

    tr_arr = np.zeros(n)
    tr_arr[1:] = np.maximum.reduce([h[1:] - l[1:],
                                    np.abs(h[1:] - c[:-1]),
                                    np.abs(l[1:] - c[:-1])])
    atr = _rollsum(tr_arr, ATR_WIN) / ATR_WIN
    del tr_arr
    atr_prev = np.empty(n)          # ATR21[t−1] — علّی
    atr_prev[0] = atr[0]
    atr_prev[1:] = atr[:-1]
    del atr

    rng = h - l
    shock = (rng >= TH * atr_prev) & (rng > 0) & (atr_prev > 1e-12)
    body = c - o
    rho = np.divide(np.abs(body), rng, out=np.zeros_like(rng), where=rng > 0)
    body_sgn = np.sign(body)
    idx = np.arange(n)
    ev = shock & (idx >= WARM) & (body_sgn != 0) & (rho >= RHO)
    ev_up = ev & (body_sgn > 0)
    ev_dn = ev & (body_sgn < 0)
    return dict(o=o, h=h, l=l, c=c, rng=rng, atr_prev=atr_prev,
                ev_up=ev_up, ev_dn=ev_dn, n=n)


def acceptance_signals(F, L, A):
    """سیگنال روی ایندکس t+1 (کندل پذیرش) ⇒ ورود open t+2. ATR رویداد = atr_prev[t]."""
    n = F['n']
    o, c, rng, atr_prev = F['o'], F['c'], F['rng'], F['atr_prev']
    ev_up, ev_dn = F['ev_up'], F['ev_dn']
    acc_up = np.zeros(n, bool)
    acc_dn = np.zeros(n, bool)
    atr_ev = np.zeros(n)            # ATR رویداد منتقل‌شده به t+1
    if n < 2:
        return acc_up, acc_dn, atr_ev
    t = np.arange(n - 1)            # شوک در t، پذیرش در t+1
    body_t = c[t] - o[t]
    quiet = rng[t + 1] <= A * atr_prev[t]
    up_ok = ev_up[t] & quiet & (c[t + 1] >= c[t] - L * body_t)
    dn_ok = ev_dn[t] & quiet & (c[t + 1] <= c[t] - L * body_t)   # body_t<0 ⇒ c[t]+L|body|
    acc_up[t + 1] = up_ok
    acc_dn[t + 1] = dn_ok
    atr_ev[1:] = atr_prev[:-1]
    return acc_up, acc_dn, atr_ev


def delay_signals(F):
    """کنترل تأخیر: همان شوک‌ها، سیگنال روی t+1 بدون شرط ⇒ ورود open t+2."""
    n = F['n']
    du = np.zeros(n, bool)
    dd = np.zeros(n, bool)
    atr_ev = np.zeros(n)
    du[1:] = F['ev_up'][:-1]
    dd[1:] = F['ev_dn'][:-1]
    atr_ev[1:] = F['atr_prev'][:-1]
    return du, dd, atr_ev


def _run(df, ls, ss, atr_ref, k_sl, k_tp, asset, pip):
    sl_arr = np.maximum(k_sl * atr_ref / pip, 1e-9)
    tp_arr = np.maximum(k_tp * atr_ref / pip, 1e-9)
    tr = se.simulate_trades(df, ls, ss, sl_arr, tp_arr, asset,
                            max_hold=MAX_HOLD, allow_overlap=False)
    return tr, sl_arr, tp_arr


def discovery_stat(tr, k_sl, k_tp):
    if tr is None or len(tr) < 30:
        return None
    n = len(tr)
    exp_pip = float(tr['pnl_pip'].mean())
    if exp_pip <= 0:
        return None
    wr = float((tr['outcome'] == 'win').mean())
    sl_med = float(np.median(tr['sl_pip'].values))
    tp_med = sl_med * (k_tp / k_sl)
    be_rob = (sl_med + 2 * COST_PIP) / (sl_med + tp_med)
    lift = (wr - be_rob) * 100.0
    return dict(stat=lift * np.sqrt(n), n=n, wr=wr * 100,
                be_rob=be_rob * 100, lift=lift, exp_pip=exp_pip,
                sl_med=sl_med, tp_med=tp_med)


def _report_stat(tr, k_sl, k_tp):
    """گزارش بازوی تشخیصی بدون غربال (n≥1)."""
    if tr is None or len(tr) == 0:
        return None
    n = len(tr)
    wr = float((tr['outcome'] == 'win').mean())
    sl_med = float(np.median(tr['sl_pip'].values))
    tp_med = sl_med * (k_tp / k_sl)
    be_rob = (sl_med + 2 * COST_PIP) / (sl_med + tp_med)
    return dict(n=n, wr=round(wr * 100, 2),
                lift=round((wr - be_rob) * 100.0, 3),
                exp_pip=round(float(tr['pnl_pip'].mean()), 2))


def _wr_of(tr):
    if tr is None or len(tr) == 0:
        return None
    return float((tr['outcome'] == 'win').mean() * 100.0)


def build_null(df, ls, ss, sl_arr, tp_arr, mh, asset, seed=SEED, K=K_PERM):
    n = len(df)
    sig_n = int((ls | ss).sum())
    if sig_n < 30:
        return None
    valid = np.zeros(n, bool)
    valid[WARM:n - mh - 1] = True
    z = np.zeros(n, bool)

    UNC_CAP = 250_000
    rng = np.random.default_rng(seed)
    vidx_all = np.flatnonzero(valid)
    if len(vidx_all) == 0:
        return None
    if len(vidx_all) > UNC_CAP:
        unc_idx = np.sort(rng.choice(vidx_all, size=UNC_CAP, replace=False))
    else:
        unc_idx = vidx_all
    unc_wins = 0
    unc_n = 0
    CH = 25_000
    for s0 in range(0, len(unc_idx), CH):
        pm = np.zeros(n, bool)
        pm[unc_idx[s0:s0 + CH]] = True
        tr_c = se.simulate_trades(df, pm, z, sl_arr, tp_arr, asset,
                                  max_hold=mh, allow_overlap=True)
        if tr_c is not None and len(tr_c):
            unc_wins += int((tr_c['outcome'] == 'win').sum())
            unc_n += int(len(tr_c))
        del tr_c, pm
        gc.collect()
    wr_unc = (unc_wins / unc_n * 100.0) if unc_n else None
    del unc_idx

    vidx = vidx_all
    k = min(sig_n, len(vidx))
    perm_wrs = []
    for _ in range(K):
        pick = rng.choice(vidx, size=k, replace=False)
        pm = np.zeros(n, bool)
        pm[pick] = True
        tr_p = se.simulate_trades(df, pm, z, sl_arr, tp_arr, asset,
                                  max_hold=mh, allow_overlap=False)
        w = _wr_of(tr_p)
        del tr_p, pm
        if w is not None:
            perm_wrs.append(w)
    pa = np.array(perm_wrs, float)
    side = dict(uncond_wr=wr_unc,
                perm_mean=float(pa.mean()) if pa.size else None,
                perm_sd=float(pa.std(ddof=1)) if pa.size > 1 else None,
                perm_max=float(pa.max()) if pa.size else None,
                perm_k=int(pa.size))
    return {'long': dict(side), 'short': dict(side),
            '_meta': {'n_perm': int(pa.size), 'draw_size': int(k),
                      'uncond_n': unc_n}}


def _split_of(d):
    t_arr = np.asarray(d['time'], dtype=np.int64)
    t_mid = (int(t_arr[0]) + int(t_arr[-1])) // 2
    return int(np.searchsorted(t_arr, t_mid))


def _discover_L(df1, L, asset, pip, F=None, want_controls=False):
    """کشفِ همهٔ اعضای یک L روی نیمهٔ اول. کنترل‌ها (base/delay) فقط اگر want_controls."""
    if F is None:
        F = features(df1)
    controls = None
    if want_controls:
        controls = {}
        for (k_sl, k_tp) in GEOMS:
            tag = f'{k_sl}/{k_tp}'
            tr_b, _, _ = _run(df1, F['ev_up'], F['ev_dn'], F['atr_prev'],
                              k_sl, k_tp, asset, pip)
            du, dd, atr_ev = delay_signals(F)
            tr_d, _, _ = _run(df1, du, dd, atr_ev, k_sl, k_tp, asset, pip)
            controls[tag] = dict(base=_report_stat(tr_b, k_sl, k_tp),
                                 delay=_report_stat(tr_d, k_sl, k_tp))
            del tr_b, tr_d, du, dd, atr_ev
    best = None
    for A in A_LIST:
        acc_up, acc_dn, atr_ev = acceptance_signals(F, L, A)
        for mode in MODES:
            ls, ss = (acc_up, acc_dn) if mode == 'follow' else (acc_dn, acc_up)
            for (k_sl, k_tp) in GEOMS:
                tr, _, _ = _run(df1, ls, ss, atr_ev, k_sl, k_tp, asset, pip)
                st = discovery_stat(tr, k_sl, k_tp)
                del tr
                if st is None:
                    continue
                if best is None or st['stat'] > best['stat']:
                    best = dict(L=L, A=A, mode=mode, k_sl=k_sl, k_tp=k_tp, **st)
        del acc_up, acc_dn, atr_ev
        gc.collect()
    return best, controls


def discover_one_L(tf, L):
    """کشفِ یک L در پردازه‌ی جدا (M1 ضدِ OOM). کنترل‌ها با L اول ثبت می‌شوند."""
    d = fd.load_fast('XAUUSD', tf)
    for _k in ('hour', 'minute', 'dow'):
        d.pop(_k, None)
    split = _split_of(d)
    df1 = _views_df(d, end=split)
    pip = se.ASSETS['XAUUSD']['pip']
    best, controls = _discover_L(df1, L, 'XAUUSD', pip,
                                 want_controls=(L == L_LIST[0]))
    out = dict(tf=tf, L=L, split_bar=split, best=best, controls=controls)
    json.dump(out, open(f'{OUT}/partial_{tf}_L{L}.json', 'w'),
              ensure_ascii=False, indent=1, default=str)
    print(f'[{tf} L={L}] best={None if best is None else round(best["stat"], 1)}',
          flush=True)


def _no_survivor(tf, src, n_bars, split, controls, t0):
    rec = dict(tf=tf, src=src, n_bars=n_bars, split_bar=split,
               verdict='NO-SURVIVOR', controls=controls,
               note='هیچ عضوی غربالِ کشف (n>=30 و expectancy>0) را نگذراند',
               sec=round(time.time() - t0, 1))
    json.dump(rec, open(f'{OUT}/{tf}.json', 'w'), ensure_ascii=False, indent=1,
              default=str)
    return rec


def adjudicate_from_partials(tf):
    t0 = time.time()
    bests, controls, split = [], None, None
    for L in L_LIST:
        fp = f'{OUT}/partial_{tf}_L{L}.json'
        if not os.path.exists(fp):
            raise RuntimeError(f'partial missing: {fp}')
        rec = json.load(open(fp))
        split = rec['split_bar']
        if rec['best'] is not None:
            bests.append(rec['best'])
        if rec.get('controls'):
            controls = rec['controls']
    d = fd.load_fast('XAUUSD', tf)
    for _k in ('hour', 'minute', 'dow'):
        d.pop(_k, None)
    src, n_bars = d['src'], len(d['close'])
    if not bests:
        return _no_survivor(tf, src, n_bars, split, controls, t0)
    best = max(bests, key=lambda b: b['stat'])
    return _final_judge(tf, d, src, n_bars, split, best, controls, t0)


def judge_tf(tf):
    t0 = time.time()
    d = fd.load_fast('XAUUSD', tf)
    for _k in ('hour', 'minute', 'dow'):
        d.pop(_k, None)
    src, asset = d['src'], 'XAUUSD'
    pip = se.ASSETS[asset]['pip']
    n_bars = len(d['close'])
    split = _split_of(d)

    # ---------- کشف: فقط نیمه‌ی اولِ زمان ----------
    df1 = _views_df(d, end=split)
    F = features(df1)
    best, controls = None, None
    for i, L in enumerate(L_LIST):
        b, ctl = _discover_L(df1, L, asset, pip, F=F, want_controls=(i == 0))
        if ctl is not None:
            controls = ctl
        if b is not None and (best is None or b['stat'] > best['stat']):
            best = b
    del F, df1
    gc.collect()
    if best is None:
        return _no_survivor(tf, src, n_bars, split, controls, t0)
    return _final_judge(tf, d, src, n_bars, split, best, controls, t0)


def _falsifiers(best, controls):
    """P1/P2 از نیمهٔ کشف — فقط ثبت (داوری در MD)."""
    out = dict(p1_vs_base=None, p2_vs_delay=None, delay_lt_base=None)
    if controls is None or best is None:
        return out
    tag = f"{best['k_sl']}/{best['k_tp']}"
    ctl = controls.get(tag) or {}
    base, delay = ctl.get('base'), ctl.get('delay')
    if best['mode'] == 'follow':
        if base:
            out['p1_vs_base'] = bool(best['lift'] > base['lift'])
        if delay:
            out['p2_vs_delay'] = bool(best['lift'] > delay['lift'])
    if base and delay:
        out['delay_lt_base'] = bool(delay['lift'] < base['lift'])
    return out


def _final_judge(tf, d, src, n_bars, split, best, controls, t0):
    """داوریِ یک‌باره روی کلِ داده (holdout یک بار لمس می‌شود)."""
    asset = 'XAUUSD'
    pip = se.ASSETS[asset]['pip']
    df = _views_df(d)
    F = features(df)
    acc_up, acc_dn, atr_ev = acceptance_signals(F, best['L'], best['A'])
    ls, ss = (acc_up, acc_dn) if best['mode'] == 'follow' else (acc_dn, acc_up)
    tr, sl_arr, tp_arr = _run(df, ls, ss, atr_ev, best['k_sl'], best['k_tp'],
                              asset, pip)
    del F, acc_up, acc_dn
    if tr is None or len(tr) == 0:
        rec = dict(tf=tf, src=src, verdict='NO-TRADES', best=best,
                   n_bars=n_bars, split_bar=split)
        json.dump(rec, open(f'{OUT}/{tf}.json', 'w'), ensure_ascii=False,
                  indent=1, default=str)
        return rec

    sl_med = float(np.median(tr['sl_pip'].values))
    tp_med = sl_med * (best['k_tp'] / best['k_sl'])
    null = build_null(df, ls, ss, sl_arr, tp_arr, MAX_HOLD, asset)
    res = rqs2.compute_rqs2(tr, asset, sl_pip=sl_med, tp_pip=tp_med,
                            bar_time=df['time'].values, null=null,
                            n_trials=N_TRIALS, split_bar=split,
                            close=df['close'].values)
    mt = res['metrics']
    rec = dict(tf=tf, src=src, n_bars=n_bars, split_bar=split,
               member=dict(th=TH, rho=RHO, L=best['L'], A=best['A'],
                           mode=best['mode'], k_sl=best['k_sl'],
                           k_tp=best['k_tp'], max_hold=MAX_HOLD,
                           entry='open t+2',
                           sl_pip_med=round(sl_med, 2),
                           tp_pip_med=round(tp_med, 2)),
               discovery={k: (round(v, 3) if isinstance(v, float) else v)
                          for k, v in best.items()},
               controls=controls,
               falsifiers=_falsifiers(best, controls),
               null_meta=(null or {}).get('_meta'),
               verdict=res['verdict'], score=res['rqs2_score'],
               gates={g: (None if v is None else bool(v))
                      for g, v in res['gates'].items()},
               n=int(mt.get('n_trades', 0)), wr=mt.get('win_rate'),
               pf=mt.get('profit_factor'), net=mt.get('net_profit'),
               lift=mt.get('skill_lift_pp'), z=mt.get('skill_z'),
               p_perm=mt.get('skill_p_perm'),
               notes=res['notes'][:8], sec=round(time.time() - t0, 1))
    json.dump(rec, open(f'{OUT}/{tf}.json', 'w'), ensure_ascii=False, indent=1,
              default=str)
    return rec


def _line(tf, rec):
    return (f"[{tf}] verdict={rec.get('verdict')} score={rec.get('score')} "
            f"n={rec.get('n')} wr={rec.get('wr')} lift={rec.get('lift')} "
            f"z={rec.get('z')} fals={rec.get('falsifiers')} ({rec.get('sec')}s)")


def main():
    if len(sys.argv) >= 4 and sys.argv[1] == 'discover':
        discover_one_L(sys.argv[2], float(sys.argv[3]))
        return
    if len(sys.argv) >= 3 and sys.argv[1] == 'adjudicate':
        tf = sys.argv[2]
        print(_line(tf, adjudicate_from_partials(tf)), flush=True)
        return
    only = sys.argv[1:] if len(sys.argv) > 1 else TFS
    for tf in only:
        try:
            print(_line(tf, judge_tf(tf)), flush=True)
        except Exception as e:                                     # noqa: BLE001
            print(f"[{tf}] ERROR {e!r}", flush=True)
            json.dump(dict(tf=tf, error=repr(e)),
                      open(f'{OUT}/{tf}.json', 'w'))
        gc.collect()


if __name__ == '__main__':
    main()
