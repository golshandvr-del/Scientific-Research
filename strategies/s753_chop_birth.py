# -*- coding: utf-8 -*-
"""S753 — «تولد روند» (CHOP Collapse Trend Birth)

پیش‌ثبت: results/S753_PREREG_CHOP_TREND_BIRTH.md (commit شده پیش از هر آزمون)

چرخش راهبردی بلوک S750–S759: از فاز/چرخه (DSP الرز — سه‌بار سوخته) به
کارآیی مسیر (بُعد فرکتالی). مفهوم: docs/indicators/volatility.md بند ۴ —
سقوط CHOP از رنج (>61.8) به روند (<38.2) = تولد روند؛ ورود همسو با drift.

سیگنال (منجمد):
  رویداد: CH[i]<38.2 و CH[i-1]>=38.2 و max(CH[i-34..i-1])>61.8
  جهت درون‌زاد: BUY اگر close[i]>close[i-P] وگرنه SELL
خانواده: P ∈ {14,21,34}. هندسه: SL=1.45×ATR(89)، TP=1.618×SL، hold=55.
پروتکل: مسیر C — کشف نیمه‌ی اول، یک آزمون واحد نیمه‌ی دوم، نال K=500.

اجرا:  python3 strategies/s753_chop_birth.py <TF>
خروجی: results/s753/<TF>.json
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

FAMILY_P = (14, 21, 34)
THR_RANGE = 61.8
THR_TREND = 38.2
LOOKBACK_K = 34
SL_K = 1.45
ATR_P = 89
RR = 1.618
MAX_HOLD = 55
SPLIT_FRAC = 0.50
INNER_H7 = 0.60
PERM_K = 500
SEED = 75375

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', 's753')


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


def chop_lean(df, P):
    """همان chop بانک — pandas rolling برداری (روی M1 هم سریع است)."""
    h = df['high'].values; l = df['low'].values; c = df['close'].values
    n = len(c)
    prev_c = np.empty(n); prev_c[0] = c[0]; prev_c[1:] = c[:-1]
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c),
                                      np.abs(l - prev_c)))
    tr_s = pd.Series(tr)
    sum_tr = tr_s.rolling(P).sum().values
    hh = pd.Series(h).rolling(P).max().values
    ll = pd.Series(l).rolling(P).min().values
    rng = hh - ll
    rng[rng <= 0] = np.nan
    with np.errstate(divide='ignore', invalid='ignore'):
        ch = 100.0 * np.log10(sum_tr / rng) / np.log10(P)
    del tr, tr_s, sum_tr, hh, ll, rng, prev_c
    gc.collect()
    return ch


def birth_signals(df, P):
    """گذر CH به زیر 38.2 پس از حضور اخیر بالای 61.8؛ جهت = drift پنجره P."""
    ch = chop_lean(df, P)
    c = df['close'].values
    n = len(c)
    below = ch < THR_TREND
    cross_dn = np.zeros(n, bool)
    cross_dn[1:] = below[1:] & ~below[:-1] & np.isfinite(ch[:-1])
    was_range = (pd.Series(np.where(np.isfinite(ch), ch, -np.inf))
                 .rolling(LOOKBACK_K).max().shift(1).values > THR_RANGE)
    event = cross_dn & was_range
    drift_up = np.zeros(n, bool)
    drift_up[P:] = c[P:] > c[:-P]
    long_sig = event & drift_up
    short_sig = event & ~drift_up
    del ch, below, cross_dn, was_range, event, drift_up
    gc.collect()
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
    print(f'\n{"=" * 78}\n=== S753 CHOP Birth :: XAUUSD-{tf} ===', flush=True)

    df, src = load_tf(tf)
    n_bars = len(df)
    print(f'src={src}  bars={n_bars:,}', flush=True)
    out = dict(card=f'S753-XAUUSD-{tf}', asset=ASSET, tf=tf, src=src,
               bars=n_bars,
               frozen=dict(family_P=list(FAMILY_P), thr_range=THR_RANGE,
                           thr_trend=THR_TREND, lookback_k=LOOKBACK_K,
                           sl_k=SL_K, atr_p=ATR_P, rr=RR, hold=MAX_HOLD),
               protocol='C_holdout_prereg_S753')

    warmup = max(ATR_P * 4, 400)
    if n_bars < warmup + 200:
        out['verdict'] = 'INCOMPLETE'
        out['note'] = 'TOO_SHORT'
        json.dump(out, open(out_file, 'w'), ensure_ascii=False, indent=1,
                  default=float)
        print('TOO_SHORT — INCOMPLETE', flush=True)
        return

    split = int(n_bars * SPLIT_FRAC)
    sl_arr = SL_K * atr_pips(df)
    tp_arr = RR * sl_arr
    ok_geo = np.isfinite(sl_arr) & (sl_arr > 0)
    med_sl = float(np.nanmedian(sl_arr[ok_geo])) if ok_geo.any() else None
    med_tp = float(np.nanmedian(tp_arr[ok_geo])) if ok_geo.any() else None

    # ---------- کشف: نیمه‌ی اول ----------
    print(f'-- discovery: bars [0,{split}) --', flush=True)
    disc = []
    for P in FAMILY_P:
        ls, ss = birth_signals(df, P)
        ls_d = ls.copy(); ss_d = ss.copy()
        ls_d[split:] = False; ss_d[split:] = False
        ls_d[:warmup] = False; ss_d[:warmup] = False
        tr = se.simulate_trades(df, ls_d, ss_d, sl_arr, tp_arr, ASSET,
                                max_hold=MAX_HOLD, allow_overlap=False)
        n_tr = 0 if tr is None else len(tr)
        wr = float((tr['pnl_pip'] > 0).mean() * 100) if n_tr else None
        net = float(tr['pnl_pip'].sum()) if n_tr else None
        cval = crit(tr)
        disc.append(dict(P=P, n=n_tr, wr=wr, net_pip=net, crit=cval))
        print(f'   P={P:<3} n={n_tr:>6} wr={wr} net={net} crit={cval:.2f}',
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
    print(f'-- winner: P={win["P"]} crit={win["crit"]:.2f} --', flush=True)
    out['winner'] = dict(P=win['P'], crit=win['crit'])

    # ---------- یک آزمون واحد روی holdout ----------
    ls, ss = birth_signals(df, win['P'])
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
    print(R2.format_rqs2(f'S753-{tf} HOLDOUT-C', r), flush=True)
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
