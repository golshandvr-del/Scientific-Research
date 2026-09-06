# -*- coding: utf-8 -*-
"""S758 — Dow Swing-Structure Continuation (کف بالاتر → شکست سقف میانی)

پیش‌ثبت: results/S758_PREREG_SWING_STRUCTURE_CONT.md (کامیت 7f43e637 — قبل از هر آزمون)

رویداد (لانگ): پیوت‌های فراکتال علّی با نیم‌پهنای L (تأیید در i+L).
  دو پیوت‌کف آخر l2 > l1 (HL) و پیوت‌سقف میانی h بین آن‌ها؛
  سیگنال در t: close[t] > h و close[t-1] <= h (لبهٔ اول) و close[t] > l2؛
  کیفیت: (h - l1) >= 1.0 × ATR89[t-1]. شورت آینه‌ای.
خانواده: L ∈ {3,5,8}. هندسه: SL=1.45×ATR89، TP=1.618×SL، hold=55.
پروتکل: مسیر C — کشف نیمهٔ اول، تک‌آزمون نیمهٔ دوم، n_trials=1.
نول: بی‌قیدِ همان‌براکت به تفکیک سمت + K=500 قرعهٔ جایگشتی (کانون s346/S965).

اجرا:  python3 strategies/s758_swing_structure.py <TF>
خروجی: results/s758/<TF>.json
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

FAMILY_L = (3, 5, 8)
LEG_K = 1.0
SL_K = 1.45
ATR_P = 89
RR = 1.618
MAX_HOLD = 55
SPLIT_FRAC = 0.50
INNER_H7 = 0.60
PERM_K = 500
UNC_CAP = 250_000
SEED = 75858

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', 's758')


def load_tf(tf):
    if tf == 'H4':
        d1 = fd.load_fast(ASSET, 'H1')
        assert 'mt5_full' in d1['src'], f"data fallback detected: {d1['src']}"
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
    assert 'mt5_full' in d['src'], f"data fallback detected: {d['src']}"
    return fd.as_dataframe(d), d['src']


def _fractal_pivots(h, l, L):
    """bar i سقف است اگر high[i] بیشینهٔ پنجرهٔ مرکزی [i-L, i+L]؛ تأیید در i+L."""
    n = len(h)
    if n < 2 * L + 1:
        return np.zeros(n, bool), np.zeros(n, bool)
    rmax = pd.Series(h).rolling(2 * L + 1, center=True).max().values
    rmin = pd.Series(l).rolling(2 * L + 1, center=True).min().values
    with np.errstate(invalid='ignore'):
        ph = np.isfinite(rmax) & (h >= rmax)
        pl = np.isfinite(rmin) & (l <= rmin)
    return ph, pl


def structure_signals(df, L, atr_pip_arr):
    """سیگنال‌های ساختار داو — کاملاً علّی (پیوت فقط از i+L به بعد شناخته می‌شود)."""
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    n = len(c)
    ph, pl = _fractal_pivots(h, l, L)

    long_sig = np.zeros(n, bool)
    short_sig = np.zeros(n, bool)

    # زمان تأیید هر پیوت = idx + L
    conf_h = np.zeros(n, bool)
    conf_l = np.zeros(n, bool)
    hi_idx = np.flatnonzero(ph) + L
    lo_idx = np.flatnonzero(pl) + L
    conf_h[hi_idx[hi_idx < n]] = True
    conf_l[lo_idx[lo_idx < n]] = True

    # حالت: آخرین دو کف/سقف تأییدشده و بالاترین سقف / پایین‌ترین کف بین آن‌ها
    l1_i = l2_i = -1          # اندیس پیوت‌کف (نه زمان تأیید)
    h1_i = h2_i = -1
    # سقف‌ها/کف‌های تأییدشده به ترتیب — برای یافتن میانی
    hs_conf = []               # اندیس پیوت‌سقف‌های تأییدشده (مرتب)
    ls_conf = []

    # کشِ میانی برای حالت فعلی
    mid_hh = np.nan            # بالاترین سقف میانی برای ساختار HL
    mid_ll = np.nan            # پایین‌ترین کف میانی برای ساختار LH
    hl_valid = False
    lh_valid = False

    def _mid_high(a, b):
        best = np.nan
        for p in reversed(hs_conf):
            if p <= a:
                break
            if p < b:
                v = h[p]
                if not np.isfinite(best) or v > best:
                    best = v
        return best

    def _mid_low(a, b):
        best = np.nan
        for p in reversed(ls_conf):
            if p <= a:
                break
            if p < b:
                v = l[p]
                if not np.isfinite(best) or v < best:
                    best = v
        return best

    for t in range(1, n):
        changed = False
        if conf_h[t]:
            p = t - L
            hs_conf.append(p)
            h1_i, h2_i = h2_i, p
            changed = True
        if conf_l[t]:
            p = t - L
            ls_conf.append(p)
            l1_i, l2_i = l2_i, p
            changed = True
        if changed:
            hl_valid = l1_i >= 0 and l2_i >= 0 and l[l2_i] > l[l1_i]
            mid_hh = _mid_high(l1_i, l2_i) if hl_valid else np.nan
            hl_valid = hl_valid and np.isfinite(mid_hh)
            lh_valid = h1_i >= 0 and h2_i >= 0 and h[h2_i] < h[h1_i]
            mid_ll = _mid_low(h1_i, h2_i) if lh_valid else np.nan
            lh_valid = lh_valid and np.isfinite(mid_ll)

        atr_prev = atr_pip_arr[t - 1]
        if not np.isfinite(atr_prev) or atr_prev <= 0:
            continue

        if hl_valid and (mid_hh - l[l1_i]) / PIP >= LEG_K * atr_prev:
            if c[t] > mid_hh and c[t - 1] <= mid_hh and c[t] > l[l2_i]:
                long_sig[t] = True
        if lh_valid and (h[h1_i] - mid_ll) / PIP >= LEG_K * atr_prev:
            if c[t] < mid_ll and c[t - 1] >= mid_ll and c[t] < h[h2_i]:
                short_sig[t] = True
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


def build_null(df, ls, ss, sl_arr, tp_arr, lo, hi, K=PERM_K, seed=SEED):
    """نولِ بی‌قیدِ همان‌براکت به تفکیک سمت (s346/S965) + K قرعهٔ جایگشتی.

    استخر: کندل‌های [lo, hi−MAX_HOLD−1) (همان hold-out).
    uncond_wr_side: ورودِ آن سمت روی هر کندل استخر (chunked، allow_overlap=True).
    perm: K قرعه به اندازهٔ n سیگنالِ همان سمت از استخر ⇒ mean/sd/max.
    """
    n = len(df)
    n_long = int(ls.sum())
    n_short = int(ss.sum())
    if n_long + n_short < 30:
        return None
    valid = np.zeros(n, bool)
    valid[lo:max(lo, hi - MAX_HOLD - 1)] = True
    vidx = np.flatnonzero(valid)
    if len(vidx) < 100:
        return None
    rng = np.random.default_rng(seed)
    unc_idx = vidx if len(vidx) <= UNC_CAP else \
        np.sort(rng.choice(vidx, size=UNC_CAP, replace=False))
    z = np.zeros(n, bool)
    out = {}
    meta = {}
    CH = 25_000
    for side, n_sig in (('long', n_long), ('short', n_short)):
        wins = tot = 0
        outcomes = np.zeros(n, np.int8)   # 1 win / -1 loss / 0 none
        for s0 in range(0, len(unc_idx), CH):
            m = np.zeros(n, bool)
            m[unc_idx[s0:s0 + CH]] = True
            tr = se.simulate_trades(df, m if side == 'long' else z,
                                    z if side == 'long' else m,
                                    sl_arr, tp_arr, ASSET,
                                    max_hold=MAX_HOLD, allow_overlap=True)
            if tr is not None and len(tr):
                w = tr['pnl_pip'].values > 0
                wins += int(w.sum())
                tot += int(len(tr))
                sb = tr['signal_bar'].values.astype(int)
                outcomes[sb] = np.where(w, 1, -1)
            del tr
            gc.collect()
        unc_wr = (wins / tot * 100.0) if tot else None
        pm = []
        if n_sig >= 1 and tot:
            pool = np.flatnonzero(outcomes != 0)
            k = min(n_sig, len(pool))
            if k >= 5:
                for _ in range(K):
                    pick = rng.choice(pool, size=k, replace=False)
                    pm.append((outcomes[pick] > 0).mean() * 100.0)
        pa = np.asarray(pm, float)
        out[side] = dict(uncond_wr=unc_wr,
                         perm_mean=float(pa.mean()) if pa.size else unc_wr,
                         perm_sd=float(pa.std(ddof=1)) if pa.size > 1 else None,
                         perm_max=float(pa.max()) if pa.size else unc_wr,
                         perm_k=int(pa.size))
        meta[side] = dict(uncond_n=tot, draw=int(n_sig), n_perm=int(pa.size))
    out['_meta'] = meta
    return out


def _dump(out, out_file):
    json.dump(out, open(out_file, 'w'), ensure_ascii=False, indent=1,
              default=float)


def main(tf):
    os.makedirs(OUT_DIR, exist_ok=True)
    out_file = os.path.join(OUT_DIR, f'{tf}.json')
    print(f'\n{"=" * 78}\n=== S758 SwingStructure :: XAUUSD-{tf} ===', flush=True)

    df, src = load_tf(tf)
    n_bars = len(df)
    print(f'src={src}  bars={n_bars:,}', flush=True)
    out = dict(card=f'S758-XAUUSD-{tf}', asset=ASSET, tf=tf, src=src,
               bars=n_bars,
               frozen=dict(family_L=list(FAMILY_L), leg_k=LEG_K, sl_k=SL_K,
                           atr_p=ATR_P, rr=RR, hold=MAX_HOLD,
                           null='side-split uncond same-bracket + perm K=500'),
               protocol='C_holdout_prereg_S758')

    warmup = max(ATR_P * 4, 400)
    if n_bars < warmup + 200:
        out['verdict'] = 'INCOMPLETE'
        out['note'] = 'TOO_SHORT'
        _dump(out, out_file)
        print('TOO_SHORT — INCOMPLETE', flush=True)
        return

    split = int(n_bars * SPLIT_FRAC)
    atr_arr = atr_pips(df)
    sl_arr = SL_K * atr_arr
    tp_arr = RR * sl_arr
    ok_geo = np.isfinite(sl_arr) & (sl_arr > 0)
    med_sl = float(np.nanmedian(sl_arr[ok_geo])) if ok_geo.any() else None
    med_tp = float(np.nanmedian(tp_arr[ok_geo])) if ok_geo.any() else None

    # ---------- کشف: نیمهٔ اول (فقط دادهٔ نیمهٔ اول به تابع داده می‌شود) ----------
    print(f'-- discovery: bars [0,{split}) --', flush=True)
    df_d = df.iloc[:split].reset_index(drop=True)
    disc = []
    for L in FAMILY_L:
        ls, ss = structure_signals(df_d, L, atr_arr[:split])
        ls[:warmup] = False
        ss[:warmup] = False
        tr = se.simulate_trades(df_d, ls, ss, sl_arr[:split], tp_arr[:split],
                                ASSET, max_hold=MAX_HOLD, allow_overlap=False)
        n_tr = 0 if tr is None else len(tr)
        wr = float((tr['pnl_pip'] > 0).mean() * 100) if n_tr else None
        net = float(tr['pnl_pip'].sum()) if n_tr else None
        cval = crit(tr)
        nl, nsh = int(ls.sum()), int(ss.sum())
        disc.append(dict(L=L, n=n_tr, n_long_sig=nl, n_short_sig=nsh,
                         wr=wr, net_pip=net, crit=cval))
        print(f'   L={L:<3} sig(L/S)={nl}/{nsh} n={n_tr:>6} wr={wr} '
              f'net={net} crit={cval:.2f}', flush=True)
        del ls, ss, tr
        gc.collect()
    del df_d
    gc.collect()
    out['discovery'] = disc

    valid = [d for d in disc if d['crit'] > -1e8 and d['n'] >= 30]
    if not valid:
        out['verdict'] = 'UNPROVEN'
        out['note'] = 'discovery: no config with n>=30'
        _dump(out, out_file)
        print('UNPROVEN — no viable discovery config', flush=True)
        return
    win = max(valid, key=lambda d: d['crit'])
    print(f'-- winner: L={win["L"]} crit={win["crit"]:.2f} --', flush=True)
    out['winner'] = dict(L=win['L'], crit=win['crit'])

    # ---------- یک آزمون واحد روی holdout ----------
    ls, ss = structure_signals(df, win['L'], atr_arr)
    ls[:split] = False
    ss[:split] = False
    tr = se.simulate_trades(df, ls, ss, sl_arr, tp_arr, ASSET,
                            max_hold=MAX_HOLD, allow_overlap=False)
    n_tr = 0 if tr is None else len(tr)
    print(f'-- holdout: bars [{split},{n_bars}) sig(L/S)={int(ls.sum())}/'
          f'{int(ss.sum())} trades={n_tr} --', flush=True)
    if n_tr == 0:
        out['verdict'] = 'UNPROVEN'
        out['note'] = 'holdout produced no trades'
        _dump(out, out_file)
        return
    wr_h = float((tr['pnl_pip'] > 0).mean() * 100)
    net_h = float(tr['pnl_pip'].sum())
    print(f'   WR={wr_h:.2f}%  net={net_h:.1f} pip', flush=True)

    null = build_null(df, ls, ss, sl_arr, tp_arr, split, n_bars)
    if null is None:
        print('   WARN: null unavailable — H3 UNKNOWN', flush=True)
    else:
        for sd_ in ('long', 'short'):
            nd = null[sd_]
            print(f'   null[{sd_}]: uncond={nd["uncond_wr"]} '
                  f'perm_mean={nd["perm_mean"]} perm_sd={nd["perm_sd"]} '
                  f'k={nd["perm_k"]}', flush=True)

    inner_split = split + int((n_bars - split) * INNER_H7)
    r = R2.compute_rqs2(tr, ASSET, n_trials=1,
                        sl_pip=med_sl, tp_pip=med_tp,
                        bar_time=df['time'].values, null=null,
                        split_bar=inner_split,
                        close=df['close'].values.astype(np.float64))
    print(R2.format_rqs2(f'S758-{tf} HOLDOUT-C', r), flush=True)
    for nt in r.get('notes', []):
        print('  ·', nt, flush=True)

    out.update(n_holdout_trades=n_tr, holdout_wr=round(wr_h, 2),
               holdout_net_pip=round(net_h, 1),
               n_long_sig=int(ls.sum()), n_short_sig=int(ss.sum()),
               med_sl_pip=med_sl, med_tp_pip=med_tp,
               null=null, inner_split=inner_split, n_trials=1, perm_k=PERM_K,
               verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'),
               gates=r.get('gates'), metrics=r.get('metrics'),
               notes=r.get('notes'))
    _dump(out, out_file)
    print(f'[checkpoint] {out_file}', flush=True)
    print('NOTE: protocol C — holdout must NOT be re-tested.', flush=True)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'M1')
