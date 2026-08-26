# -*- coding: utf-8 -*-
"""S756 — Month-Open AMR Expansion Continuation

پیش‌ثبت: results/S756_PREREG_MONTH_OPEN_EXPANSION.md (کامیت‌شده قبل از هر آزمون)

آنالوگ ماهانهٔ کلاس «انبساط خودمقیاس» (S770/S800/S602/S950):
  frac(t) = (close − monthOpen) / AMR12؛ state-cross در ±θ ⇒ تداوم در جهت عبور.
خانواده: θ ∈ {0.382, 0.618, 1.0}. هندسه: SL=1.45×ATR(89)، TP=1.618×SL، hold=55.
پروتکل: مسیر C — کشف نیمهٔ اول، تک‌آزمون نیمهٔ دوم، نال K=500، n_trials=1.

اجرا:  python3 strategies/s756_month_expansion.py <TF>
خروجی: results/s756/<TF>.json
"""
import gc
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

FAMILY_TH = (0.382, 0.618, 1.0)
SL_K = 1.45
ATR_P = 89
RR = 1.618
MAX_HOLD = 55
SPLIT_FRAC = 0.50
INNER_H7 = 0.60
PERM_K = 500
SEED = 75656

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', 's756')


def load_tf(tf):
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
        return df, d1['src'] + ' (resampled H1->H4)'
    d = fd.load_fast(ASSET, tf)
    return fd.as_dataframe(d), d['src']


def month_state(df):
    """frac = (close − monthOpen)/AMR12 — کاملاً علّی.

    monthOpen: open اولین بار ماه جاری.
    AMR12: میانگین رنج (high−low) ۱۲ ماه تقویمیِ کامل‌شدهٔ قبل — با shift(1)
    روی جدول ماهانه تا ماه جاری واردش نشود؛ سپس map به بارها.
    """
    t = pd.to_datetime(df['time'].values, unit='s', utc=True)
    mkey = t.year * 100 + t.month                       # کلید ماه
    mkey = np.asarray(mkey)

    o = df['open'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)

    s = pd.Series(np.arange(len(c)), index=mkey)
    first_idx = s.groupby(level=0).min()                # اولین بار هر ماه
    month_open_map = {k: o[v] for k, v in first_idx.items()}

    mh = pd.Series(h, index=mkey).groupby(level=0).max()
    ml = pd.Series(l, index=mkey).groupby(level=0).min()
    mrng = (mh - ml)                                    # رنج کامل هر ماه
    # AMR12 برای هر ماه = میانگین ۱۲ ماه قبل (خود ماه حذف — shift(1))
    amr = mrng.shift(1).rolling(12).mean()
    amr_map = amr.to_dict()

    m_open = np.array([month_open_map[k] for k in mkey])
    amr_arr = np.array([amr_map.get(k, np.nan) for k in mkey])
    with np.errstate(divide='ignore', invalid='ignore'):
        frac = (c - m_open) / amr_arr
    return frac


def cross_signals(frac, theta):
    n = len(frac)
    long_sig = np.zeros(n, bool)
    short_sig = np.zeros(n, bool)
    f0 = frac[:-1]
    f1 = frac[1:]
    ok = np.isfinite(f0) & np.isfinite(f1)
    long_sig[1:] = ok & (f0 < theta) & (f1 >= theta)
    short_sig[1:] = ok & (f0 > -theta) & (f1 <= -theta)
    return long_sig, short_sig


def atr_pips(df):
    return ib.atr_s(df, ATR_P).values.astype(np.float64) / PIP


def crit(tr):
    if tr is None or len(tr) < 20:
        return -1e9
    p = tr['pnl_pip'].values
    s = p.std(ddof=1)
    if not np.isfinite(s) or s <= 0:
        return -1e9
    return float(p.mean() / s * np.sqrt(len(p)))


def build_null_perm(df, ls, ss, K=PERM_K, seed=SEED):
    sig_idx = np.where(ls | ss)[0]
    if len(sig_idx) < 30:
        return None
    c = df['close'].values.astype(np.float64)
    rng = np.random.default_rng(seed)
    fwd = np.full(len(sig_idx), np.nan)
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
        wrs.append(np.where(signs, base_wins, ~base_wins).mean() * 100.0)
    wrs = np.asarray(wrs)
    ref = float(wrs.mean())
    side = dict(uncond_wr=ref, perm_mean=ref, perm_sd=float(wrs.std(ddof=1)),
                perm_max=float(wrs.max()), perm_k=int(K))
    return {'long': dict(side), 'short': dict(side)}


def main(tf):
    os.makedirs(OUT_DIR, exist_ok=True)
    out_file = os.path.join(OUT_DIR, f'{tf}.json')
    print(f'\n{"=" * 78}\n=== S756 MonthExpansion :: XAUUSD-{tf} ===', flush=True)

    df, src = load_tf(tf)
    n_bars = len(df)
    print(f'src={src}  bars={n_bars:,}', flush=True)
    out = dict(card=f'S756-XAUUSD-{tf}', asset=ASSET, tf=tf, src=src,
               bars=n_bars,
               frozen=dict(family_theta=list(FAMILY_TH), amr_months=12,
                           sl_k=SL_K, atr_p=ATR_P, rr=RR, hold=MAX_HOLD),
               protocol='C_holdout_prereg_S756')

    warmup = max(ATR_P * 4, 400)
    if n_bars < warmup + 200:
        out['verdict'] = 'INCOMPLETE'
        out['note'] = 'TOO_SHORT'
        json.dump(out, open(out_file, 'w'), ensure_ascii=False, indent=1,
                  default=float)
        print('TOO_SHORT — INCOMPLETE', flush=True)
        return

    split = int(n_bars * SPLIT_FRAC)
    atr_arr = atr_pips(df)
    sl_arr = SL_K * atr_arr
    tp_arr = RR * sl_arr
    ok_geo = np.isfinite(sl_arr) & (sl_arr > 0)
    med_sl = float(np.nanmedian(sl_arr[ok_geo])) if ok_geo.any() else None
    med_tp = float(np.nanmedian(tp_arr[ok_geo])) if ok_geo.any() else None

    frac = month_state(df)

    # ---------- کشف: نیمهٔ اول ----------
    print(f'-- discovery: bars [0,{split}) --', flush=True)
    disc = []
    for th in FAMILY_TH:
        ls, ss = cross_signals(frac, th)
        ls_d = ls.copy(); ss_d = ss.copy()
        ls_d[split:] = False; ss_d[split:] = False
        ls_d[:warmup] = False; ss_d[:warmup] = False
        tr = se.simulate_trades(df, ls_d, ss_d, sl_arr, tp_arr, ASSET,
                                max_hold=MAX_HOLD, allow_overlap=False)
        n_tr = 0 if tr is None else len(tr)
        wr = float((tr['pnl_pip'] > 0).mean() * 100) if n_tr else None
        net = float(tr['pnl_pip'].sum()) if n_tr else None
        cval = crit(tr)
        disc.append(dict(theta=th, n=n_tr, wr=wr, net_pip=net, crit=cval))
        print(f'   th={th:<5} n={n_tr:>6} wr={wr} net={net} crit={cval:.2f}',
              flush=True)
        del ls, ss, ls_d, ss_d, tr
        gc.collect()
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
    print(f'-- winner: th={win["theta"]} crit={win["crit"]:.2f} --', flush=True)
    out['winner'] = dict(theta=win['theta'], crit=win['crit'])

    # ---------- یک آزمون واحد روی holdout ----------
    ls, ss = cross_signals(frac, win['theta'])
    ls[:split] = False; ss[:split] = False
    tr = se.simulate_trades(df, ls, ss, sl_arr, tp_arr, ASSET,
                            max_hold=MAX_HOLD, allow_overlap=False)
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

    null = build_null_perm(df, ls, ss)
    if null is None:
        print('   WARN: null unavailable (n<30) — H3 UNKNOWN', flush=True)

    inner_split = split + int((n_bars - split) * INNER_H7)
    r = R2.compute_rqs2(tr, ASSET, n_trials=1,
                        sl_pip=med_sl, tp_pip=med_tp,
                        bar_time=df['time'].values, null=null,
                        split_bar=inner_split,
                        close=df['close'].values.astype(np.float64))
    print(R2.format_rqs2(f'S756-{tf} HOLDOUT-C', r), flush=True)
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
    print('NOTE: protocol C — holdout must NOT be re-tested.', flush=True)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'M1')
