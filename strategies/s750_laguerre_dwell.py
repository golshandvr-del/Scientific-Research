# -*- coding: utf-8 -*-
"""S750 — «اقامت در اشباع» (Laguerre Dwell Continuation)

پیش‌ثبت: results/S750_PREREG_LAGUERRE_DWELL.md (commit a6bd7a25 — پیش از هر آزمون نهایی)

پروتکل مسیر C (hold-out):
  ۱) کشف: فقط نیمه‌ی اول داده. ۶ پیکربندی خانواده (N ∈ {5,8,13} × دو سمت)
     ارزیابی و «یک» برنده با معیار از-پیش-اعلام‌شده انتخاب می‌شود:
       criterion = mean(pnl_pip)/std(pnl_pip) × √n   (آماره‌ی t-گونه؛ در همین
     فایل و پیش از اجرای آزمون ثبت شده است — جزئی‌سازیِ بند ۵ پیش‌ثبت، بدون
     تغییر خانواده یا هندسه).
  ۲) آزمون: «یک» آزمون واحد روی نیمه‌ی دوم با پیکربندی منجمد؛ n_trials=1.
     نال جای‌گشت K=500 (الگوی کانونی s346). H7 با تقسیم تودرتوی 60/40 درون holdout.

هندسه‌ی منجمد (غیر گرد، TP>SL، ATR-محور => خودتطبیق با هر TF):
  SL = 1.45 × ATR(89) [pip]   ·   TP = 1.618 × SL   ·   max_hold = 55
سیگنال منجمد:
  LR = laguerre_rsi(gamma=0.5)  [مقیاس ۰..۱۰۰ در این بانک]
  BUY  در لبه‌ی dwell_up == N  (LR > 80 برای N میله‌ی متوالی)
  SELL در لبه‌ی dwell_dn == N  (LR < 20 برای N میله‌ی متوالی)

داده: فقط data/mt5_full (loader s434). H4 از H1ِ mt5_full بازنمونه‌گیری می‌شود.
اجرا:  python3 strategies/s750_laguerre_dwell.py <TF>
خروجی: results/s750/<TF>.json  (چک‌پوینت «اندک اندک»)
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se           # noqa: E402
from engine import rqs2 as R2                   # noqa: E402
from engine import indicator_bank as ib         # noqa: E402
from tools import s434_fast_data as fd          # noqa: E402

ASSET = 'XAUUSD'
PIP = se.ASSETS[ASSET]['pip']

# ---- پارامترهای منجمدِ پیش‌ثبت‌شده (تغییر = ابطال پیش‌ثبت) ----
GAMMA = 0.5
THR_HI = 80.0
THR_LO = 100.0 - THR_HI
FAMILY_N = (5, 8, 13)
SL_K = 1.45
ATR_P = 89
RR = 1.618
MAX_HOLD = 55
SPLIT_FRAC = 0.50          # نیمه‌ی اول = کشف، نیمه‌ی دوم = holdout
INNER_H7 = 0.60            # تقسیم تودرتوی H7 درون holdout
PERM_K = 500
SEED = 75075

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', 's750')


def load_tf(tf):
    """داده‌ی کامل mt5_full؛ H4 صریحاً از H1 بازنمونه‌گیری می‌شود (قانون داده)."""
    if tf == 'H4':
        d1 = fd.load_fast(ASSET, 'H1')
        df1 = fd.as_dataframe(d1)
        t = pd.to_datetime(df1['time'], unit='s', utc=True)
        g = df1.set_index(t).resample('4h')
        df = pd.DataFrame({
            'open': g['open'].first(), 'high': g['high'].max(),
            'low': g['low'].min(), 'close': g['close'].last(),
            'volume': g['volume'].sum(),
        }).dropna()
        df.insert(0, 'time',
                  (df.index.astype('int64') // 10 ** 9).astype('int64'))
        df = df.reset_index(drop=True)
        src = d1['src'] + ' (resampled H1->H4)'
        return df, src
    d = fd.load_fast(ASSET, tf)
    return fd.as_dataframe(d), d['src']


def compute_dwells(close_vals):
    """LR یک‌بار محاسبه می‌شود (بهینه‌سازی حافظه برای M1 با ۵M کندل)."""
    import gc
    lr = ib.laguerre_rsi(pd.DataFrame({'close': close_vals}),
                         gamma=GAMMA).values
    up = lr > THR_HI
    dn = lr < THR_LO
    del lr
    gc.collect()
    du = _runlen(up)
    dd = _runlen(dn)
    del up, dn
    gc.collect()
    return du, dd


def _runlen(mask):
    """طول دنباله‌ی متوالی True منتهی به هر اندیس — برداری، بدون حلقه‌ی پایتونی."""
    n = len(mask)
    idx = np.arange(n, dtype=np.int64)
    last_false = np.where(~mask, idx, -1)
    np.maximum.accumulate(last_false, out=last_false)
    return np.where(mask, idx - last_false, 0).astype(np.int32)


def dwell_signals(du, dd, n_dwell):
    # لبه‌ی ورود به اقامت پایدار — یک سیگنال به‌ازای هر دوره‌ی اقامت
    return du == n_dwell, dd == n_dwell


def atr_pips(df):
    a = ib.atr_s(df, ATR_P).values.astype(np.float64)
    return a / PIP


def run_config(df, long_sig, short_sig, sl_arr, tp_arr):
    tr = se.simulate_trades(df, long_sig, short_sig, sl_arr, tp_arr, ASSET,
                            max_hold=MAX_HOLD, allow_overlap=False)
    return tr


def crit(tr):
    """معیار انتخاب کشف (از-پیش-اعلام‌شده): t-گونه = mean/std × √n."""
    if tr is None or len(tr) < 20:
        return -1e9
    p = tr['pnl_pip'].values
    s = p.std(ddof=1)
    if not np.isfinite(s) or s <= 0:
        return -1e9
    return float(p.mean() / s * np.sqrt(len(p)))


def build_null_perm(df, ls, ss, K=PERM_K, seed=SEED):
    """نال جای‌گشت کانونی (الگوی s346): جهت تصادفی روی بازده رو‌به‌جلوی hold."""
    sig_idx = np.where(ls | ss)[0]
    n = len(sig_idx)
    if n < 30:
        return None
    c = df['close'].values.astype(np.float64)
    rng = np.random.default_rng(seed)
    fwd = np.full(n, np.nan)
    for j, ei in enumerate(sig_idx):
        k = min(ei + MAX_HOLD, len(c) - 1)
        fwd[j] = c[k] - c[ei]
    fwd = fwd[np.isfinite(fwd)]
    if len(fwd) < 30:
        return None
    base_wins = fwd > 0
    wrs = []
    for _ in range(K):
        signs = rng.integers(0, 2, size=len(fwd)).astype(bool)
        w = np.where(signs, base_wins, ~base_wins)
        wrs.append(w.mean() * 100.0)
    wrs = np.asarray(wrs)
    ref = float(wrs.mean())
    side = dict(uncond_wr=ref, perm_mean=ref, perm_sd=float(wrs.std(ddof=1)),
                perm_max=float(wrs.max()), perm_k=int(K))
    return {'long': dict(side), 'short': dict(side)}


def main(tf):
    os.makedirs(OUT_DIR, exist_ok=True)
    out_file = os.path.join(OUT_DIR, f'{tf}.json')
    print(f'\n{"=" * 78}\n=== S750 Laguerre Dwell :: XAUUSD-{tf} ===', flush=True)

    df, src = load_tf(tf)
    n_bars = len(df)
    print(f'src={src}  bars={n_bars:,}', flush=True)
    out = dict(card=f'S750-XAUUSD-{tf}', asset=ASSET, tf=tf, src=src,
               bars=n_bars,
               frozen=dict(gamma=GAMMA, thr=THR_HI, family_N=list(FAMILY_N),
                           sl_k=SL_K, atr_p=ATR_P, rr=RR, hold=MAX_HOLD),
               protocol='C_holdout_prereg_a6bd7a25')

    warmup = max(ATR_P * 4, 400)
    if n_bars < warmup + 200:
        out['verdict'] = 'INCOMPLETE'
        out['note'] = 'TOO_SHORT'
        json.dump(out, open(out_file, 'w'), ensure_ascii=False, indent=1,
                  default=float)
        print('TOO_SHORT — INCOMPLETE', flush=True)
        return

    split = int(n_bars * SPLIT_FRAC)
    atr_p = atr_pips(df)
    sl_arr = SL_K * atr_p
    tp_arr = RR * sl_arr
    ok_geo = np.isfinite(sl_arr) & (sl_arr > 0)
    med_sl = float(np.nanmedian(sl_arr[ok_geo])) if ok_geo.any() else None
    med_tp = float(np.nanmedian(tp_arr[ok_geo])) if ok_geo.any() else None

    # ---------- فاز ۱: کشف — فقط نیمه‌ی اول ----------
    print(f'-- discovery: bars [0,{split}) --', flush=True)
    du, dd = compute_dwells(df['close'].values)
    disc = []
    for N in FAMILY_N:
        ls, ss = dwell_signals(du, dd, N)
        for side in ('long', 'short'):
            ls_d = ls.copy() if side == 'long' else np.zeros(n_bars, bool)
            ss_d = ss.copy() if side == 'short' else np.zeros(n_bars, bool)
            ls_d[split:] = False
            ss_d[split:] = False
            ls_d[:warmup] = False
            ss_d[:warmup] = False
            tr = run_config(df, ls_d, ss_d, sl_arr, tp_arr)
            n_tr = 0 if tr is None else len(tr)
            wr = float((tr['pnl_pip'] > 0).mean() * 100) if n_tr else None
            net = float(tr['pnl_pip'].sum()) if n_tr else None
            cval = crit(tr)
            disc.append(dict(N=N, side=side, n=n_tr, wr=wr, net_pip=net,
                             crit=cval))
            print(f'   N={N:>2} {side:<5} n={n_tr:>6} wr={wr} net={net} '
                  f'crit={cval:.2f}', flush=True)
    out['discovery'] = disc

    valid = [d for d in disc if d['crit'] > -1e8 and d['n'] >= 30]
    if not valid:
        out['verdict'] = 'UNPROVEN'
        out['note'] = 'discovery: no config with n>=30'
        json.dump(out, open(out_file, 'w'), ensure_ascii=False, indent=1,
                  default=float)
        print('UNPROVEN — no viable discovery config', flush=True)
        return
    win = max(valid, key=lambda d: d['crit'])
    print(f'-- winner: N={win["N"]} side={win["side"]} crit={win["crit"]:.2f} --',
          flush=True)
    out['winner'] = dict(N=win['N'], side=win['side'], crit=win['crit'])

    # ---------- فاز ۲: آزمون واحد روی holdout ----------
    ls, ss = dwell_signals(du, dd, win['N'])
    ls_h = ls.copy() if win['side'] == 'long' else np.zeros(n_bars, bool)
    ss_h = ss.copy() if win['side'] == 'short' else np.zeros(n_bars, bool)
    ls_h[:split] = False
    ss_h[:split] = False
    tr = run_config(df, ls_h, ss_h, sl_arr, tp_arr)
    n_tr = 0 if tr is None else len(tr)
    print(f'-- holdout: bars [{split},{n_bars}) trades={n_tr} --', flush=True)
    if n_tr == 0:
        out['verdict'] = 'UNPROVEN'
        out['note'] = 'holdout produced no trades'
        json.dump(out, open(out_file, 'w'), ensure_ascii=False, indent=1,
                  default=float)
        return
    wr_h = float((tr['pnl_pip'] > 0).mean() * 100)
    net_h = float(tr['pnl_pip'].sum())
    print(f'   WR={wr_h:.2f}%  net={net_h:.1f} pip', flush=True)

    null = build_null_perm(df, ls_h, ss_h)
    if null is None:
        print('   WARN: null unavailable (n<30) — H3 UNKNOWN', flush=True)

    inner_split = split + int((n_bars - split) * INNER_H7)
    bar_time = df['time'].values
    close = df['close'].values.astype(np.float64)

    r = R2.compute_rqs2(tr, ASSET, n_trials=1,
                        sl_pip=med_sl, tp_pip=med_tp,
                        bar_time=bar_time, null=null,
                        split_bar=inner_split, close=close)
    print(R2.format_rqs2(f'S750-{tf} HOLDOUT-C', r), flush=True)
    for nt in r.get('notes', []):
        print('  ·', nt, flush=True)

    out.update(n_holdout_trades=n_tr, holdout_wr=round(wr_h, 2),
               holdout_net_pip=round(net_h, 1),
               med_sl_pip=med_sl, med_tp_pip=med_tp,
               inner_split=inner_split, n_trials=1, perm_k=PERM_K,
               verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'),
               gates=r.get('gates'), metrics=r.get('metrics'),
               notes=r.get('notes'))
    json.dump(out, open(out_file, 'w'), ensure_ascii=False, indent=1,
              default=float)
    print(f'[checkpoint] {out_file}', flush=True)
    print('NOTE: protocol C — this holdout must NOT be re-tested after any '
          'retune. Verdict is final for this configuration.', flush=True)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'M1')
