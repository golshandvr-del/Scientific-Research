#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S672 — فاز جست‌وجو (فقط نیمهٔ نخست — مسیر C، PREREG f9dcde61 در git)

فرضیه (VSA/Tom Williams): پول‌بکِ خلافِ روند با خشکیِ حجمِ محلی + دامنهٔ تنگ
(No Supply/No Demand) سوختِ نهادی ندارد → ازسرگیریِ روند.

  * جست‌وجو فقط [0, n/2) — نگه‌داشت لمس نمی‌شود
  * خانواده: pt{50,200} × α{0.7,1.0} × k_sl{1,1.5,2} × RR{1.5,2} × side{L,S,both} = 72/TF
  * مبنای بی‌قیدِ «روند-شرطی»: ورودهای تصادفی فقط از بارهای هم‌روند (سواریِ روند خنثی)
  * چک‌پوینت: JSON هر TF در results/_scan_S672/

اجرا:  python3 strategies/s672_nosupply_search.py M1
"""
import gc
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se          # noqa: E402
from engine import indicator_bank as ib        # noqa: E402
from tools import s434_fast_data as fd         # noqa: E402

SEED = 20260823
PTS = (50, 200)          # دورهٔ SMA روند
ALPHAS = (0.7, 1.0)      # سقفِ دامنه نسبت به ATR20
K_SLS = (1.0, 1.5, 2.0)
RRS = (1.5, 2.0)
ATR_P = 100
ATR_RANGE_P = 20
N_UNCOND = 20000

MAX_HOLD = {  # منجمد — همان دیکشنری S670 PREREG
    'M1': 240, 'M3': 240, 'M4': 240, 'M5': 240, 'M6': 240,
    'M10': 120, 'M12': 120, 'M15': 120, 'M20': 120, 'M30': 120,
    'H1': 64, 'H2': 64, 'H3': 64,
    'H6': 32, 'H8': 32, 'H12': 32,
    'D1': 16, 'W1': 8, 'MN1': 8,
}

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_scan_S672')


def wr_of(tr):
    if tr is None or len(tr) == 0:
        return None
    return 100.0 * float((tr['pnl_pip'] > 0).mean())


def pf_of(tr):
    if tr is None or len(tr) == 0:
        return None
    p = tr['pnl_pip'].values
    gw = p[p > 0].sum()
    gl = -p[p < 0].sum()
    return float(gw / gl) if gl > 0 else 999.0


def run_tf(tf):
    t0 = time.time()
    d = fd.load_fast('XAUUSD', tf)
    df_full = fd.as_dataframe(d)
    n_full = len(df_full)
    half = n_full // 2
    df = df_full.iloc[:half].reset_index(drop=True).copy()
    del df_full
    d_src = d['src']
    d.clear(); gc.collect()
    n = len(df)
    mh = MAX_HOLD[tf]
    pip = se.ASSETS['XAUUSD']['pip']
    if 'mt5_full' not in d_src:
        print(f"[S672/{tf}] ⚠️ src={d_src} خارج از mt5_full — طبق تلهٔ E-16 رد شد",
              flush=True)
        return None
    print(f"[S672/{tf}] src={d_src} n_full={n_full} search_half={n} max_hold={mh}",
          flush=True)

    o = df['open'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    lo = df['low'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    v = df['volume'].values.astype(np.float64)

    atr_pip = ib.atr_s(df, ATR_P).values / pip
    atr20 = ib.atr_s(df, ATR_RANGE_P).values
    valid = np.isfinite(atr_pip) & (atr_pip > 0) & np.isfinite(atr20) & (atr20 > 0)
    valid[:max(ATR_P, ATR_RANGE_P) + 1] = False

    # شرطِ حجم (مشترک): خشکیِ محلی
    voldry = np.zeros(n, bool)
    voldry[2:] = (v[2:] < v[1:-2]) & (v[2:] < v[:-3])
    rng_bar = h - lo
    dn_bar = c < o
    up_bar = c > o

    # روندها
    trends = {}
    for pt in PTS:
        sma = np.convolve(c, np.ones(pt) / pt, mode='full')[:n]
        sma[:pt - 1] = np.nan
        upT = c > sma
        dnT = c < sma
        upT[:pt] = False
        dnT[:pt] = False
        trends[pt] = (upT, dnT)
        del sma
    gc.collect()

    rng = np.random.default_rng(SEED)

    # --- مبنای روند-شرطی: به تفکیک (pt, k_sl, rr, side) ---
    uncond = {}
    for pt in PTS:
        upT, dnT = trends[pt]
        for side, tmask in (('long', upT), ('short', dnT)):
            pool = np.where(valid & tmask)[0]
            if len(pool) < 100:
                for k_sl in K_SLS:
                    for rr in RRS:
                        uncond[(pt, k_sl, rr, side)] = dict(wr=None, n=0)
                continue
            n_samp = min(N_UNCOND, len(pool))
            pick = np.sort(rng.choice(len(pool), size=n_samp, replace=False))
            sig = np.zeros(n, bool); sig[pool[pick]] = True
            for k_sl in K_SLS:
                sl_arr = k_sl * atr_pip
                for rr in RRS:
                    tp_arr = rr * sl_arr
                    ls = sig if side == 'long' else np.zeros(n, bool)
                    ss = sig if side == 'short' else np.zeros(n, bool)
                    tr = se.simulate_trades(df, ls, ss, sl_arr, tp_arr, 'XAUUSD',
                                            max_hold=mh, allow_overlap=False)
                    uncond[(pt, k_sl, rr, side)] = dict(wr=wr_of(tr), n=int(len(tr)))
                    del tr
    gc.collect()
    print(f"[S672/{tf}] مبنای روند-شرطی اندازه‌گیری شد ({len(uncond)} سلول، "
          f"{time.time()-t0:.0f}s)", flush=True)

    # --- جست‌وجوی خانوادهٔ منجمد ---
    rows = []
    cfg_i = 0
    q1_end = n // 2  # برای معیار (f): دو ربعِ نیمهٔ جستجو
    for pt in PTS:
        upT, dnT = trends[pt]
        for alpha in ALPHAS:
            narrow = valid & (rng_bar < alpha * atr20)
            long_raw = upT & dn_bar & voldry & narrow    # No Supply
            short_raw = dnT & up_bar & voldry & narrow   # No Demand
            for k_sl in K_SLS:
                sl_arr = k_sl * atr_pip
                for rr in RRS:
                    tp_arr = rr * sl_arr
                    for side in ('long', 'short', 'both'):
                        cfg_i += 1
                        ls = long_raw if side in ('long', 'both') else np.zeros(n, bool)
                        ss = short_raw if side in ('short', 'both') else np.zeros(n, bool)
                        if not (ls.any() or ss.any()):
                            continue
                        tr = se.simulate_trades(df, ls, ss, sl_arr, tp_arr,
                                                'XAUUSD', max_hold=mh,
                                                allow_overlap=False)
                        n_tr = int(len(tr))
                        if n_tr == 0:
                            continue
                        wr = wr_of(tr)
                        pf_val = pf_of(tr)
                        if side == 'both':
                            nL = int((tr['direction'] == 'long').sum())
                            nS = n_tr - nL
                            refs, wts = [], []
                            for s2, cnt in (('long', nL), ('short', nS)):
                                u = uncond[(pt, k_sl, rr, s2)]['wr']
                                if u is not None and cnt > 0:
                                    refs.append(u * cnt); wts.append(cnt)
                            ref = sum(refs) / sum(wts) if wts else None
                        else:
                            ref = uncond[(pt, k_sl, rr, side)]['wr']
                        lift = (wr - ref) if ref is not None else None
                        # معیار (f): net دو ربع
                        eb = tr['entry_bar'].values
                        pnl = tr['pnl_pip'].values
                        net_q1 = float(pnl[eb < q1_end].sum())
                        net_q2 = float(pnl[eb >= q1_end].sum())
                        rows.append(dict(
                            pt=pt, alpha=alpha, side=side, k_sl=k_sl, rr=rr,
                            n=n_tr, wr=round(wr, 3),
                            ref_wr=None if ref is None else round(ref, 3),
                            lift=None if lift is None else round(lift, 3),
                            pf=round(pf_val, 3),
                            exp_pip=round(float(pnl.mean()), 3),
                            net_q1=round(net_q1, 1), net_q2=round(net_q2, 1),
                            lift_sqrt_n=None if lift is None
                            else round(float(lift * np.sqrt(n_tr)), 1)))
                        del tr
        gc.collect()
    dt = time.time() - t0
    rows.sort(key=lambda r: -(r['lift_sqrt_n'] if r['lift_sqrt_n'] is not None
                              else -1e9))
    out = dict(tf=tf, src=d_src, n_full=n_full, n_search=n, half_bar=half,
               seed=SEED, n_configs=cfg_i, max_hold=mh, elapsed_s=round(dt, 1),
               uncond={f"{k[0]}_{k[1]}x{k[2]}_{k[3]}": v for k, v in uncond.items()},
               top30=rows[:30], n_rows=len(rows))
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f'{tf}.json')
    with open(path, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"[S672/{tf}] تمام شد: {cfg_i} پیکربندی، {len(rows)} نتیجه، {dt:.0f}s → {path}",
          flush=True)
    if rows:
        print(f"[S672/{tf}] بهترین: {rows[0]}", flush=True)
    return out


if __name__ == '__main__':
    tfs = sys.argv[1:] or list(MAX_HOLD)
    for tf in tfs:
        run_tf(tf)
