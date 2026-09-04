# -*- coding: utf-8 -*-
"""S985 — اسکنِ اکتشافیِ «آغازِ سمّیتِ جریان با طبقه‌بندیِ حجمِ توده‌ای» (فقط نیمهٔ اول — مسیر C)
================================================================================
پیش‌ثبت: results/S985_PREREG_BVC_FLOW_TOXICITY_ONSET.md (کامیت f8b29a17، پیش از این فایل)

تعریفِ منجمدِ رویداد (عیناً از پیش‌ثبت — Easley, López de Prado, O'Hara 2012، آنالوگِ ساعتِ زمانی):
  r_t = ln(close_t/close_{t-1}) ؛ σ_t = EWM-std(span=100) از r تا t-1 (شیفتِ ۱ — صفر نشت)
  z_t = r_t/σ_{t-1} ؛ V_buy = V_t·Φ(z_t) ؛ OI_t = V_t·(2Φ(z_t) − 1)
  TOX_t = Σ_{L}|OI| / Σ_{L} V        (آنالوگِ VPIN؛ تحتِ H0 میانگین ۰.۵)
  NF_t  = Σ_{L} OI                    (جریانِ خالصِ علامت‌دار)
  θ_L   = 0.5 + κ·(0.2887/√L)
  رویدادِ آغاز: TOX_t ≥ θ_L و TOX_{t-1} < θ_L (فقط عبورِ تازه).
  اصلی (ادامه): NF>0 ⇒ LONG، NF<0 ⇒ SHORT. آینه: برعکس.
  ورود در closeِ کندلِ رویداد (شبیه‌ساز: openِ بعدی). allow_overlap=False. max_hold=64.

فضا: 2 L × 3 κ × 2 جهت × 2 SL_k × 2 RR = 48 بازو/کارت × 19 TF = 912.
اجرا:  python3 strategies/s985_bvc_toxicity_scan.py --tf M1
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd
from scipy.stats import norm

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se          # noqa: E402
from tools import s434_fast_data as fd         # noqa: E402

OUT = 'results/_s985'
ASSET = 'XAUUSD'

WINDOWS = (21, 55)                 # L — عینِ پیش‌ثبت
KAPPAS = (1.5, 2.5, 3.5)           # κ در واحدِ sd تحتِ H0
GEOMS = tuple((k, rr) for k in (1.2, 1.8) for rr in (1.3, 1.6))  # TP>SL همیشه
MAX_HOLD = 64
ATR_P = 100
SIGMA_SPAN = 100
SD_U01 = 0.2887                    # انحرافِ معیارِ U(0,1) = 1/√12
N_ARMS_CARD = len(WINDOWS) * len(KAPPAS) * 2 * len(GEOMS)  # 48


def atr_arr(df, p=ATR_P):
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    pc = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1.0 / p, adjust=False).mean().to_numpy()


def theta_of(L, kappa):
    return 0.5 + kappa * (SD_U01 / np.sqrt(L))


def order_imbalance(df):
    """OI_t = V_t·(2Φ(z_t)−1) با σ شیفت‌خورده (صفر نشت). خروجی: (OI, V)."""
    c = df['close'].to_numpy(float)
    v = df['volume'].to_numpy(float)
    v = np.where(np.isfinite(v) & (v > 0), v, 0.0)
    r = np.zeros(len(c))
    r[1:] = np.log(c[1:] / c[:-1])
    sig = pd.Series(r).ewm(span=SIGMA_SPAN, adjust=False).std(bias=False).to_numpy()
    sig_prev = np.concatenate([[np.nan], sig[:-1]])       # σ_{t-1} — شیفتِ ۱
    with np.errstate(divide='ignore', invalid='ignore'):
        z = r / sig_prev
    z = np.where(np.isfinite(z), z, 0.0)
    oi = v * (2.0 * norm.cdf(z) - 1.0)
    # گرم‌شدن: تا SIGMA_SPAN کندل، OI صفر (بی‌رویداد)
    oi[:SIGMA_SPAN + 1] = 0.0
    return oi, v


def rolling_sum(x, L):
    cs = np.cumsum(np.insert(x, 0, 0.0))
    out = np.full(len(x), np.nan)
    out[L - 1:] = cs[L:] - cs[:-L]
    return out


def toxicity_signals(oi, v, L, kappa):
    """رویدادهای onset. خروجی: (long_cont, short_cont) بولی روی کندلِ رویداد
    (بازوی اصلی = ادامه در جهتِ NF). آینه = جابه‌جاییِ همین دو آرایه."""
    n = len(oi)
    sum_abs = rolling_sum(np.abs(oi), L)
    sum_v = rolling_sum(v, L)
    nf = rolling_sum(oi, L)
    with np.errstate(divide='ignore', invalid='ignore'):
        tox = sum_abs / sum_v
    tox = np.where(np.isfinite(tox), tox, np.nan)
    th = theta_of(L, kappa)
    above = tox >= th
    prev_below = np.concatenate([[False], (tox[:-1] < th)])
    onset = above & prev_below
    onset[:SIGMA_SPAN + L + 1] = False                     # گرم‌شدنِ کامل
    lc = onset & (nf > 0)
    sc = onset & (nf < 0)
    return lc, sc, tox


def binom_z(wins, n, p0):
    if n == 0:
        return 0.0
    se_ = np.sqrt(p0 * (1 - p0) / n)
    return ((wins / n) - p0) / se_ if se_ > 0 else 0.0


def scan_card(tf, verbose=True):
    t0 = time.time()
    d = fd.load_fast(ASSET, tf)
    df_all = fd.as_dataframe(d)
    n_all = len(df_all)
    half = n_all // 2
    df = df_all.iloc[:half].reset_index(drop=True)   # 🔒 فقط نیمهٔ اول (مسیر C)
    src = d['src']
    if verbose:
        print(f'[{tf}] src={src}', flush=True)
        print(f'[{tf}] bars_total={n_all:,}  bars_search={len(df):,} (نیمهٔ اول — مسیر C)', flush=True)

    a = atr_arr(df)
    pip = se.ASSETS[ASSET]['pip']
    sl_base_pip = float(np.nanmedian(a[ATR_P:])) / pip
    cost_pip = se.ASSETS[ASSET]['spread_pip'] + 2.0 * se.ASSETS[ASSET]['slip_pip']
    oi, v = order_imbalance(df)
    vol_zero_frac = float((v <= 0).mean())

    rows = []
    n_arms = 0
    for L in WINDOWS:
        for kappa in KAPPAS:
            lc, sc, tox = toxicity_signals(oi, v, L, kappa)
            n_evt = int(lc.sum() + sc.sum())
            tox_mean = float(np.nanmean(tox))
            for mode in ('main', 'mirror'):
                ls, ss = (lc, sc) if mode == 'main' else (sc, lc)
                for sl_k, rr in GEOMS:
                    n_arms += 1
                    sl_pip = sl_base_pip * sl_k
                    tp_pip = sl_pip * rr
                    t = se.simulate_trades(df, ls, ss, sl_pip, tp_pip, ASSET,
                                           max_hold=MAX_HOLD, allow_overlap=False)
                    n = len(t)
                    if n < 30:
                        continue
                    wins = int((t['outcome'] == 'win').sum())
                    wr = wins / n * 100.0
                    be = (sl_pip + cost_pip) / (sl_pip + tp_pip) * 100.0
                    lift = wr - be
                    z = binom_z(wins, n, be / 100.0)
                    net = float(t['pnl_pip'].sum())
                    rows.append(dict(L=L, kappa=kappa, theta=round(theta_of(L, kappa), 4),
                                     mode=mode, sl_k=sl_k, rr=rr,
                                     sl_pip=round(sl_pip, 2), tp_pip=round(tp_pip, 2),
                                     n_events=n_evt, n=n, wr=round(wr, 2),
                                     be=round(be, 2), lift=round(lift, 2),
                                     z=round(z, 2), net_pip=round(net, 1)))
            if verbose:
                print(f'[{tf}]   L={L} κ={kappa} θ={theta_of(L, kappa):.4f} '
                      f'tox_mean={tox_mean:.4f} events={n_evt}  ({time.time()-t0:.0f}s)', flush=True)
    rows.sort(key=lambda r: r['z'], reverse=True)
    out = dict(tf=tf, asset=ASSET, src=src, bars_total=n_all, bars_search=len(df),
               path='C (search=first half only)', n_arms=n_arms,
               declared_space=N_ARMS_CARD, vol_zero_frac=round(vol_zero_frac, 4),
               sl_base_pip=round(sl_base_pip, 2), cost_pip=cost_pip,
               max_hold=MAX_HOLD, elapsed_s=round(time.time() - t0, 1),
               results=rows)
    os.makedirs(OUT, exist_ok=True)
    with open(f'{OUT}/scan_{tf}.json', 'w') as f:
        json.dump(out, f, ensure_ascii=False)
    if verbose:
        print(f'[{tf}] arms={n_arms} valid(n>=30)={len(rows)} vol_zero={vol_zero_frac:.3f} '
              f'elapsed={out["elapsed_s"]}s', flush=True)
        print(f'[{tf}] ── ۱۰ بازوی برتر (بر z) ──', flush=True)
        for r in rows[:10]:
            print(f"  L={r['L']:<3} κ={r['kappa']:<4} {r['mode'][:4]:4s} slk={r['sl_k']} rr={r['rr']} "
                  f"n={r['n']:<6} wr={r['wr']:6.2f}% be={r['be']:5.2f}% "
                  f"lift={r['lift']:+6.2f}pp z={r['z']:+6.2f} net={r['net_pip']:+.0f}pip", flush=True)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--tf', default='M1')
    a = ap.parse_args()
    scan_card(a.tf)
