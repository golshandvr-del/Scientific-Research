# -*- coding: utf-8 -*-
"""
S960 — «واگرایی جریان-قیمت کایل» (Kyle 1985 Flow-Price Divergence) · XAUUSD
================================================================================
پیش‌ثبت: `results/S960_PREREG_KYLE_FLOW_PRICE_DIVERGENCE.md`
(commit 04e7b5d6 — پیش از اجرای هر آزمونی، مسیر C اعلام شد).

فرضیه (Kyle 1985): Δp = λ·flow + noise. دو عدم‌تعادلِ قابل‌آزمون:
  * mode=against (Absorption): جریانِ شدید + قیمتِ ساکن ⇒ جذبِ نهادی ⇒ خلافِ جریان.
  * mode=with (λ-settlement): جریانِ شدید هنوز تسویه نشده ⇒ هم‌جهتِ جریان.

سیگنال (روی کندلِ i، پنجرهٔ p — همگی causal، ورود در openِ کندلِ بعد):
  flow_i = Σ sign(close-open)·vol / Σ vol   روی p کندلِ آخر (∈[-1,1])
  eff_i  = (close_i − close_{i-p}) / (ATR21_i · √p)
  ورود: |flow| ≥ F  و  |eff| ≤ E   (تلاشِ زیاد، نتیجهٔ کم)

خانوادهٔ منجمد (پیش‌ثبت §۲): p∈{13,21,34,55} × F∈{0.55,0.75} × E∈{0.34,0.55}
× mode∈{with,against} × هندسه∈{(1.0,1.618),(1.272,2.058)} = ۶۴ عضو/کارت.
max_hold = 3·p (متناسبِ TF — درسِ BUG-TFM). n_trials = 64×19 = **1216**.

مسیرِ چندگانگی C: کشف فقط روی نیمهٔ اولِ محورِ زمان؛ غربال n≥30 و
expectancy>0؛ یک finalist با بیشترین lift·√n؛ holdout یک بار لمس می‌شود.

مدلِ صفر: K=500 جای‌گشت (PERM_K_MIN)، سه تلهٔ s434 بسته:
  ۱) k = تعدادِ سیگنالِ نهایی؛ ۲) کنترل با همان هندسهٔ شناورِ ATR و همان
  max_hold؛ ۳) استخرِ eligible = warmup..n-mh-1؛ بی‌قید با allow_overlap=True.

قانونِ اندک‌اندک: هر TF بلافاصله در `results/_scan_S960/<TF>.json`.
EURUSD عمداً غایب است (استثنای صریحِ کاربر). SEED=960.
"""
import sys
import os
import json
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se          # noqa: E402
from engine import rqs2                        # noqa: E402
from tools import s434_fast_data as fd         # noqa: E402

OUT = 'results/_scan_S960'
os.makedirs(OUT, exist_ok=True)

SEED = 960
K_PERM = 500                                   # H3 نیازمندِ perm_k ≥ 500
ATR_WIN = 21
COST_PIP = 3.3                                 # اسپردِ کاملِ طلا (pip)

# ── خانوادهٔ قفل‌شده (پیش‌ثبت §۲) — ۴×۲×۲×۲×۲ = ۶۴ عضو ──────────────
P_LIST = [13, 21, 34, 55]
F_LIST = [0.55, 0.75]
E_LIST = [0.34, 0.55]
MODES = ['with', 'against']
GEOMS = [(1.0, 1.618), (1.272, 2.058)]         # (k_sl, k_tp) — همیشه TP>SL
N_TRIALS = 1216                                # 64 × 19 کارت — شمارشِ صادقانه

TFS = ['M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20', 'M30',
       'H1', 'H2', 'H3', 'H6', 'H8', 'H12', 'D1', 'W1', 'MN1']


def features(df, p):
    """flow(p)، eff(p)، ATR21 — همگی تا closeِ کندلِ i (causal، ورود i+1)."""
    o = df['open'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    v = df['volume'].values.astype(np.float64)
    n = len(c)

    sgn_vol = np.sign(c - o) * v
    kern = np.ones(p)
    num = np.convolve(sgn_vol, kern, mode='full')[:n]      # Σ آخرین p مقدار تا i
    den = np.convolve(v, kern, mode='full')[:n]
    flow = np.where(den > 0, num / np.maximum(den, 1e-12), 0.0)

    # ATR21 (میانگینِ سادهٔ TR تا و شاملِ کندلِ i — در closeِ i معلوم است)
    tr_arr = np.zeros(n)
    tr_arr[1:] = np.maximum.reduce([h[1:] - l[1:],
                                    np.abs(h[1:] - c[:-1]),
                                    np.abs(l[1:] - c[:-1])])
    atr = np.convolve(tr_arr, np.ones(ATR_WIN) / ATR_WIN, mode='full')[:n]

    eff = np.zeros(n)
    eff[p:] = (c[p:] - c[:-p]) / np.maximum(atr[p:] * np.sqrt(p), 1e-12)
    return flow, eff, atr


def member_signals(flow, eff, F, E, mode, warm):
    """ماسکِ long/short یک عضو."""
    n = len(flow)
    valid = np.arange(n) >= warm
    hit = valid & (np.abs(flow) >= F) & (np.abs(eff) <= E)
    up = hit & (flow > 0)
    dn = hit & (flow < 0)
    if mode == 'with':
        return up, dn
    return dn, up


def geometry(atr, k_sl, k_tp, pip):
    sl_pip = np.maximum(k_sl * atr / pip, 1e-9)
    tp_pip = np.maximum(k_tp * atr / pip, 1e-9)
    return sl_pip, tp_pip


def run_member(df, flow, eff, atr, F, E, mode, k_sl, k_tp, p, asset, pip):
    warm = max(ATR_WIN, p) + 2
    ls, ss = member_signals(flow, eff, F, E, mode, warm)
    sl_arr, tp_arr = geometry(atr, k_sl, k_tp, pip)
    tr = se.simulate_trades(df, ls, ss, sl_arr, tp_arr, asset,
                            max_hold=3 * p, allow_overlap=False)
    return tr, ls, ss, sl_arr, tp_arr


def discovery_stat(tr, rr):
    """آمارِ کشف (فقط نیمهٔ اول): lift_proxy·√n با lift = wr − BE_robust."""
    if tr is None or len(tr) < 30:
        return None
    n = len(tr)
    exp_pip = float(tr['pnl_pip'].mean())
    if exp_pip <= 0:                                       # غربالِ پیش‌ثبت
        return None
    wr = float((tr['outcome'] == 'win').mean())
    sl_med = float(np.median(tr['sl_pip'].values))
    tp_med = sl_med * rr
    be_rob = (sl_med + 2 * COST_PIP) / (sl_med + tp_med)   # BE محافظه‌کار
    lift = (wr - be_rob) * 100.0
    return dict(stat=lift * np.sqrt(n), n=n, wr=wr * 100,
                be_rob=be_rob * 100, lift=lift, exp_pip=exp_pip,
                sl_med=sl_med, tp_med=tp_med)


def _wr_of(tr):
    if tr is None or len(tr) == 0:
        return None
    return float((tr['outcome'] == 'win').mean() * 100.0)


def build_null(df, ls, ss, sl_arr, tp_arr, mh, asset, seed=SEED, K=K_PERM):
    """مدلِ صفر با سه تلهٔ s434 بسته + K=500.

    تلهٔ ۱: k = تعدادِ سیگنالِ نهایی.
    تلهٔ ۲: کنترل با **همان** آرایه‌های شناورِ sl/tp و همان mh (بدون trail/BE
            مثلِ خودِ سیگنال — هندسهٔ یکسان).
    تلهٔ ۳: استخرِ eligible = warmup..n-mh-1؛ بی‌قید با allow_overlap=True.
    """
    n = len(df)
    sig_n = int((ls | ss).sum())
    if sig_n < 30:
        return None
    warmup = ATR_WIN + max(P_LIST) + 2
    valid = np.zeros(n, bool)
    valid[warmup:n - mh - 1] = True
    z = np.zeros(n, bool)

    tr_unc = se.simulate_trades(df, valid, z, sl_arr, tp_arr, asset,
                                max_hold=mh, allow_overlap=True)
    wr_unc = _wr_of(tr_unc)

    rng = np.random.default_rng(seed)
    vidx = np.flatnonzero(valid)
    k = min(sig_n, len(vidx))
    perm_wrs = []
    for i in range(K):
        pick = rng.choice(vidx, size=k, replace=False)
        pm = np.zeros(n, bool)
        pm[pick] = True
        tr_p = se.simulate_trades(df, pm, z, sl_arr, tp_arr, asset,
                                  max_hold=mh, allow_overlap=False)
        w = _wr_of(tr_p)
        if w is not None:
            perm_wrs.append(w)
    pa = np.array(perm_wrs, float)
    side = dict(uncond_wr=wr_unc,
                perm_mean=float(pa.mean()) if pa.size else None,
                perm_sd=float(pa.std(ddof=1)) if pa.size > 1 else None,
                perm_max=float(pa.max()) if pa.size else None,
                perm_k=int(k))
    # لایه دوسویه است ⇒ هر دو سمت همان مبنا (کنترل جهت‌آگنوستیک است؛
    # blend_null با وزنِ معاملاتِ هر سمت ترکیب می‌کند).
    return {'long': dict(side), 'short': dict(side),
            '_meta': {'n_perm': int(pa.size), 'k': int(k),
                      'uncond_n': 0 if tr_unc is None else int(len(tr_unc))}}


def judge_tf(tf):
    t0 = time.time()
    d = fd.load_fast('XAUUSD', tf)
    df = fd.as_dataframe(d)
    src = d['src']
    asset = 'XAUUSD'
    pip = se.ASSETS[asset]['pip']
    n_bars = len(df)
    t_arr = df['time'].values.astype(np.int64)
    # split = نقطهٔ میانیِ محورِ **زمان** (پیش‌ثبت §۳)
    t_mid = (int(t_arr[0]) + int(t_arr[-1])) // 2
    split = int(np.searchsorted(t_arr, t_mid))

    # ---------- کشف: فقط نیمهٔ اولِ زمان ----------
    df1 = df.iloc[:split].reset_index(drop=True)
    best = None
    for p in P_LIST:
        flow1, eff1, atr1 = features(df1, p)
        for F in F_LIST:
            for E in E_LIST:
                for mode in MODES:
                    for (k_sl, k_tp) in GEOMS:
                        tr, *_ = run_member(df1, flow1, eff1, atr1, F, E,
                                            mode, k_sl, k_tp, p, asset, pip)
                        st = discovery_stat(tr, k_tp / k_sl)
                        if st is None:
                            continue
                        if best is None or st['stat'] > best['stat']:
                            best = dict(p=p, F=F, E=E, mode=mode,
                                        k_sl=k_sl, k_tp=k_tp, **st)
    if best is None:
        rec = dict(tf=tf, src=src, n_bars=n_bars, split_bar=split,
                   verdict='NO-SURVIVOR',
                   note='هیچ عضوی غربالِ کشف (n>=30 و expectancy>0) را نگذراند',
                   sec=round(time.time() - t0, 1))
        json.dump(rec, open(f'{OUT}/{tf}.json', 'w'), ensure_ascii=False, indent=1)
        return rec

    # ---------- داوریِ یک‌باره روی کلِ داده (holdout یک بار لمس می‌شود) ----------
    p, F, E = best['p'], best['F'], best['E']
    mode, k_sl, k_tp = best['mode'], best['k_sl'], best['k_tp']
    mh = 3 * p
    flow, eff, atr = features(df, p)
    tr, ls, ss, sl_arr, tp_arr = run_member(df, flow, eff, atr, F, E, mode,
                                            k_sl, k_tp, p, asset, pip)
    if tr is None or len(tr) == 0:
        rec = dict(tf=tf, src=src, verdict='NO-TRADES', best=best,
                   n_bars=n_bars, split_bar=split)
        json.dump(rec, open(f'{OUT}/{tf}.json', 'w'), ensure_ascii=False, indent=1)
        return rec

    sl_med = float(np.median(tr['sl_pip'].values))
    tp_med = sl_med * (k_tp / k_sl)
    null = build_null(df, ls, ss, sl_arr, tp_arr, mh, asset)
    res = rqs2.compute_rqs2(tr, asset, sl_pip=sl_med, tp_pip=tp_med,
                            bar_time=df['time'].values, null=null,
                            n_trials=N_TRIALS, split_bar=split,
                            close=df['close'].values)
    m = res['metrics']
    rec = dict(tf=tf, src=src, n_bars=n_bars, split_bar=split,
               member=dict(p=p, F=F, E=E, mode=mode, k_sl=k_sl, k_tp=k_tp,
                           max_hold=mh, sl_pip_med=round(sl_med, 2),
                           tp_pip_med=round(tp_med, 2)),
               discovery={k: (round(v, 3) if isinstance(v, float) else v)
                          for k, v in best.items()},
               null_meta=(null or {}).get('_meta'),
               verdict=res['verdict'], score=res['rqs2_score'],
               gates={g: (None if v is None else bool(v))
                      for g, v in res['gates'].items()},
               n=int(m.get('n_trades', 0)), wr=m.get('win_rate'),
               pf=m.get('profit_factor'), net=m.get('net_profit'),
               lift=m.get('skill_lift_pp'), z=m.get('skill_z'),
               p_perm=m.get('skill_p_perm'),
               notes=res['notes'][:8], sec=round(time.time() - t0, 1))
    json.dump(rec, open(f'{OUT}/{tf}.json', 'w'), ensure_ascii=False, indent=1,
              default=str)
    return rec


def main():
    only = sys.argv[1:] if len(sys.argv) > 1 else TFS
    for tf in only:
        try:
            rec = judge_tf(tf)
            print(f"[{tf}] verdict={rec.get('verdict')} score={rec.get('score')} "
                  f"n={rec.get('n')} wr={rec.get('wr')} lift={rec.get('lift')} "
                  f"z={rec.get('z')} ({rec.get('sec')}s)", flush=True)
        except Exception as e:                                     # noqa: BLE001
            print(f"[{tf}] ERROR {e!r}", flush=True)
            json.dump(dict(tf=tf, error=repr(e)),
                      open(f'{OUT}/{tf}.json', 'w'))


if __name__ == '__main__':
    main()
