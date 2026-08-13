#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S620 — فاز جست‌وجو (فقط نیمهٔ نخستِ داده — مسیر C پیش‌ثبت‌شده در commit 554faa1e)

قضیهٔ ادعایی: خروج Laguerre RSI از ناحیهٔ اشباع روی XAUUSD نقطهٔ چرخش مومنتوم را
با مهارت فراتر از مبنای بی‌قیدِ اندازه‌گیری‌شده علامت می‌زند.

قوانین رعایت‌شده:
  * دادهٔ کامل ۱۵.۶ ساله فقط از tools.s434_fast_data (ضد تلهٔ E-16؛ src چاپ می‌شود)
  * جست‌وجو فقط روی بارهای [0, n/2) — نیمهٔ نگه‌داشت هرگز لمس نمی‌شود
  * خانوادهٔ منجمد: gamma×th×side×k_sl×RR = 4×3×3×3×2 = 216 پیکربندی در هر TF
  * مبنا: اندازه‌گیری‌شده (ورود بی‌قید نمونه‌گیری‌شده با همان هندسه) — هرگز نظری
  * قانون بودجه: RR ≥ 1 (TP ≥ SL) — همیشه
  * قانون اندک‌اندک: خروجی هر TF بلافاصله JSON در results/_scan_S620/

اجرا:  python3 strategies/s620_laguerre_exit_search.py M1
"""
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se            # noqa: E402
from engine import indicator_bank as ib          # noqa: E402
from tools import s434_fast_data as fd           # noqa: E402

SEED = 20260812                       # منجمد در PREREG
GAMMAS = (0.4, 0.5, 0.6, 0.7)         # منجمد
THS = (10.0, 15.0, 20.0)              # منجمد (مقیاس 0..100 بانک ≡ 0.10/0.15/0.20)
K_SLS = (1.0, 1.5, 2.0)               # SL = k × ATR(100)
RRS = (1.0, 1.5)                      # TP = RR × SL؛ RR≥1 (قانون بودجه)
ATR_P = 100
N_UNCOND = 20000                      # حجم نمونهٔ مبنای بی‌قید در هر (هندسه×سمت)

MAX_HOLD = {  # منجمد در PREREG
    'M1': 240, 'M3': 240, 'M4': 240, 'M5': 240, 'M6': 240,
    'M10': 120, 'M12': 120, 'M15': 120, 'M20': 120, 'M30': 120,
    'H1': 64, 'H2': 64, 'H3': 64,
    'H6': 32, 'H8': 32, 'H12': 32,
    'D1': 16, 'W1': 8, 'MN1': 8,
}

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_scan_S620')


def wr_of(tr):
    if tr is None or len(tr) == 0:
        return None
    return 100.0 * float((tr['pnl_pip'] > 0).mean())


def run_tf(tf):
    t0 = time.time()
    d = fd.load_fast('XAUUSD', tf)
    df_full = fd.as_dataframe(d)
    n_full = len(df_full)
    half = n_full // 2                      # مرز جست‌وجو/نگه‌داشت (منجمد)
    df = df_full.iloc[:half].reset_index(drop=True)
    n = len(df)
    mh = MAX_HOLD[tf]
    pip = se.ASSETS['XAUUSD']['pip']
    print(f"[S620/{tf}] src={d['src']}  n_full={n_full}  search_half={n}  "
          f"{df['time'].iloc[0]} → {df['time'].iloc[-1]}  max_hold={mh}", flush=True)

    # --- هندسهٔ ATR-محور (پایه) ---
    atr_price = ib.atr_s(df, ATR_P).values
    atr_pip = atr_price / pip
    valid = np.isfinite(atr_pip) & (atr_pip > 0)
    valid[:ATR_P + 1] = False
    vidx = np.where(valid)[0]
    if len(vidx) < 500:
        print(f"[S620/{tf}] داده ناکافی — رد", flush=True)
        return {'tf': tf, 'skip': 'insufficient_data', 'n_search': n}

    rng = np.random.default_rng(SEED)

    # --- مبنای بی‌قیدِ اندازه‌گیری‌شده: به تفکیک (k_sl, rr, side) ---
    uncond = {}
    n_samp = min(N_UNCOND, len(vidx))
    pick = np.sort(rng.choice(len(vidx), size=n_samp, replace=False))
    ub = vidx[pick]
    base_sig = np.zeros(n, dtype=bool)
    base_sig[ub] = True
    for k_sl in K_SLS:
        sl_arr = k_sl * atr_pip
        for rr in RRS:
            tp_arr = rr * sl_arr
            for side in ('long', 'short'):
                ls = base_sig if side == 'long' else np.zeros(n, bool)
                ss = base_sig if side == 'short' else np.zeros(n, bool)
                tr = se.simulate_trades(df, ls, ss, sl_arr, tp_arr, 'XAUUSD',
                                        max_hold=mh, allow_overlap=False)
                uncond[(k_sl, rr, side)] = dict(wr=wr_of(tr), n=int(len(tr)))
    print(f"[S620/{tf}] مبنای بی‌قید اندازه‌گیری شد "
          f"({len(uncond)} هندسه×سمت، {n_samp} نمونه، {time.time()-t0:.0f}s)",
          flush=True)

    # --- جست‌وجوی خانوادهٔ منجمد ---
    rows = []
    cfg_i = 0
    for gamma in GAMMAS:
        lag = ib.laguerre_rsi(df, gamma).values
        prev = np.roll(lag, 1)
        prev[0] = 50.0
        for th in THS:
            # خروج از اشباع فروش → LONG؛ خروج از اشباع خرید → SHORT (متقارن)
            long_raw = (prev < th) & (lag >= th) & valid
            short_raw = (prev > 100.0 - th) & (lag <= 100.0 - th) & valid
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
                        tr = se.simulate_trades(df, ls, ss, sl_arr, tp_arr, 'XAUUSD',
                                                max_hold=mh, allow_overlap=False)
                        n_tr = int(len(tr))
                        if n_tr == 0:
                            continue
                        wr = wr_of(tr)
                        # مبنای وزنی به سمت (الگوی s431/s432)
                        if side == 'both':
                            nL = int((tr['direction'] == 'long').sum())
                            nS = n_tr - nL
                            refs, wts = [], []
                            for s2, cnt in (('long', nL), ('short', nS)):
                                u = uncond[(k_sl, rr, s2)]['wr']
                                if u is not None and cnt > 0:
                                    refs.append(u * cnt)
                                    wts.append(cnt)
                            ref = sum(refs) / sum(wts) if wts else None
                        else:
                            ref = uncond[(k_sl, rr, side)]['wr']
                        lift = (wr - ref) if ref is not None else None
                        exp_pip = float(np.mean(tr['pnl_pip']))
                        rows.append(dict(
                            gamma=gamma, th=th, side=side, k_sl=k_sl, rr=rr,
                            n=n_tr, wr=round(wr, 3),
                            ref_wr=None if ref is None else round(ref, 3),
                            lift=None if lift is None else round(lift, 3),
                            exp_pip=round(exp_pip, 3),
                            lift_sqrt_n=None if lift is None
                            else round(lift * np.sqrt(n_tr), 1)))
    dt = time.time() - t0
    rows.sort(key=lambda r: -(r['lift_sqrt_n'] if r['lift_sqrt_n'] is not None
                              else -1e9))
    out = dict(tf=tf, src=d['src'], n_full=n_full, n_search=n, half_bar=half,
               seed=SEED, n_configs=cfg_i, max_hold=mh,
               elapsed_s=round(dt, 1),
               uncond={f"{k[0]}x{k[1]}_{k[2]}": v for k, v in uncond.items()},
               top20=rows[:20], n_rows=len(rows))
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f'{tf}.json')
    with open(path, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    best = rows[0] if rows else None
    print(f"[S620/{tf}] تمام شد: {cfg_i} پیکربندی، {len(rows)} نتیجه، "
          f"{dt:.0f}s → {path}", flush=True)
    if best:
        print(f"[S620/{tf}] بهترین: {best}", flush=True)
    return out


if __name__ == '__main__':
    tfs = sys.argv[1:] or ['M1']
    for tf in tfs:
        run_tf(tf)
