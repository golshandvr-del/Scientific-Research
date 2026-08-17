# -*- coding: utf-8 -*-
"""S751 — «گذر لاگر» (Laguerre Threshold Transit)

پیش‌ثبت: results/S751_PREREG_LAGUERRE_TRANSIT.md (commit 3985897b — پیش از هر آزمون)

استنتاج از S750 (REJECT ×19، همین بلوک): «اقامت در اشباع» دیرهنگام است؛
S382 (تنها ACCEPT بی‌فیلتر طلا) نشان داد لحظه‌ی «گذر» به اشباع طلاست.
S751 = ورود در نخستین میله‌ی عبورِ laguerre_rsi از آستانه (لبه‌ی تازه‌ی اشباع).

خانواده‌ی منجمد: γ ∈ {0.382, 0.5, 0.618} × دو سمت = ۶ پیکربندی.
سیگنال: BUY اگر LR[i]>80 و LR[i-1]<=80؛ SELL اگر LR[i]<20 و LR[i-1]>=20.
هندسه (بازاستفاده از S750، اعلام‌شده در پیش‌ثبت): SL=1.45×ATR(89)،
TP=1.618×SL، hold=55، بدون هم‌پوشانی.
پروتکل: مسیر C — کشف نیمه‌ی اول، یک آزمون واحد روی نیمه‌ی دوم (n_trials=1)،
نال جای‌گشت K=500، H7 تودرتو 60/40.

اجرا:  python3 strategies/s751_laguerre_transit.py <TF>
خروجی: results/s751/<TF>.json
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

# ---- منجمدِ پیش‌ثبت (تغییر = ابطال) ----
FAMILY_G = (0.382, 0.5, 0.618)
THR_HI = 80.0
THR_LO = 20.0
SL_K = 1.45
ATR_P = 89
RR = 1.618
MAX_HOLD = 55
SPLIT_FRAC = 0.50
INNER_H7 = 0.60
PERM_K = 500
SEED = 75175

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', 's751')


def load_tf(tf):
    """فقط mt5_full؛ H4 از H1 بازنمونه‌گیری (قانون داده)."""
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


def laguerre_rsi_lean(close_vals, g):
    """همان ریاضیات ib.laguerre_rsi اما float32 و کم‌حافظه (اثبات‌شده در S750:
    روی XAUUSD-H1 فقط ۱/۹۱۳۳۱ عدم‌تطابق آستانه؛ M1 با ۵M کندل بدون OOM)."""
    xv = np.asarray(close_vals, dtype=np.float32)
    n = len(xv)
    L0s = np.empty(n, np.float32); L1s = np.empty(n, np.float32)
    L2s = np.empty(n, np.float32); L3s = np.empty(n, np.float32)
    L0 = L1 = L2 = L3 = 0.0
    for i in range(n):
        pL0, pL1, pL2 = L0, L1, L2
        L0 = (1 - g) * xv[i] + g * L0
        L1 = -g * L0 + pL0 + g * L1
        L2 = -g * L1 + pL1 + g * L2
        L3 = -g * L2 + pL2 + g * L3
        L0s[i] = L0; L1s[i] = L1; L2s[i] = L2; L3s[i] = L3
    del xv
    cu = np.zeros(n, np.float32); cd = np.zeros(n, np.float32)
    for a, b in ((L0s, L1s), (L1s, L2s), (L2s, L3s)):
        diff = a - b
        np.add(cu, np.where(diff >= 0, diff, 0), out=cu)
        np.add(cd, np.where(diff < 0, -diff, 0), out=cd)
        del diff
    del L0s, L1s, L2s, L3s
    gc.collect()
    tot = cu + cd
    lr = np.where(tot != 0, 100.0 * cu / tot, 50.0).astype(np.float32)
    del cu, cd, tot
    gc.collect()
    return lr


def transit_signals(close_vals, g):
    """گذر از آستانه: BUY = LR عبور رو به بالا از 80؛ SELL = عبور رو به پایین از 20."""
    lr = laguerre_rsi_lean(close_vals, g)
    above = lr > THR_HI
    below = lr < THR_LO
    del lr
    gc.collect()
    long_sig = np.zeros(len(above), bool)
    short_sig = np.zeros(len(below), bool)
    long_sig[1:] = above[1:] & ~above[:-1]
    short_sig[1:] = below[1:] & ~below[:-1]
    del above, below
    gc.collect()
    return long_sig, short_sig


def atr_pips(df):
    return ib.atr_s(df, ATR_P).values.astype(np.float64) / PIP


def crit(tr):
    """معیار کشف از-پیش-اعلام‌شده: t-گونه = mean/std × √n."""
    if tr is None or len(tr) < 20:
        return -1e9
    p = tr['pnl_pip'].values
    s = p.std(ddof=1)
    if not np.isfinite(s) or s <= 0:
        return -1e9
    return float(p.mean() / s * np.sqrt(len(p)))


def build_null_perm(df, ls, ss, K=PERM_K, seed=SEED):
    """نال جای‌گشت کانونی (الگوی s346)."""
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
    print(f'\n{"=" * 78}\n=== S751 Laguerre Transit :: XAUUSD-{tf} ===', flush=True)

    df, src = load_tf(tf)
    n_bars = len(df)
    print(f'src={src}  bars={n_bars:,}', flush=True)
    out = dict(card=f'S751-XAUUSD-{tf}', asset=ASSET, tf=tf, src=src,
               bars=n_bars,
               frozen=dict(family_gamma=list(FAMILY_G), thr_hi=THR_HI,
                           thr_lo=THR_LO, sl_k=SL_K, atr_p=ATR_P, rr=RR,
                           hold=MAX_HOLD),
               protocol='C_holdout_prereg_3985897b')

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

    # ---------- فاز ۱: کشف — نیمه‌ی اول ----------
    print(f'-- discovery: bars [0,{split}) --', flush=True)
    disc = []
    for g in FAMILY_G:
        ls, ss = transit_signals(df['close'].values, g)
        for side in ('long', 'short'):
            ls_d = ls.copy() if side == 'long' else np.zeros(n_bars, bool)
            ss_d = ss.copy() if side == 'short' else np.zeros(n_bars, bool)
            ls_d[split:] = False; ss_d[split:] = False
            ls_d[:warmup] = False; ss_d[:warmup] = False
            tr = se.simulate_trades(df, ls_d, ss_d, sl_arr, tp_arr, ASSET,
                                    max_hold=MAX_HOLD, allow_overlap=False)
            n_tr = 0 if tr is None else len(tr)
            wr = float((tr['pnl_pip'] > 0).mean() * 100) if n_tr else None
            net = float(tr['pnl_pip'].sum()) if n_tr else None
            cval = crit(tr)
            disc.append(dict(g=g, side=side, n=n_tr, wr=wr, net_pip=net,
                             crit=cval))
            print(f'   g={g:<6} {side:<5} n={n_tr:>6} wr={wr} net={net} '
                  f'crit={cval:.2f}', flush=True)
            del ls_d, ss_d, tr
            gc.collect()
        del ls, ss
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
    print(f'-- winner: g={win["g"]} side={win["side"]} '
          f'crit={win["crit"]:.2f} --', flush=True)
    out['winner'] = dict(g=win['g'], side=win['side'], crit=win['crit'])

    # ---------- فاز ۲: یک آزمون واحد روی holdout ----------
    ls, ss = transit_signals(df['close'].values, win['g'])
    ls_h = ls if win['side'] == 'long' else np.zeros(n_bars, bool)
    ss_h = ss if win['side'] == 'short' else np.zeros(n_bars, bool)
    ls_h = ls_h.copy(); ss_h = ss_h.copy()
    ls_h[:split] = False; ss_h[:split] = False
    tr = se.simulate_trades(df, ls_h, ss_h, sl_arr, tp_arr, ASSET,
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

    null = build_null_perm(df, ls_h, ss_h)
    if null is None:
        print('   WARN: null unavailable (n<30) — H3 UNKNOWN', flush=True)

    inner_split = split + int((n_bars - split) * INNER_H7)
    r = R2.compute_rqs2(tr, ASSET, n_trials=1,
                        sl_pip=med_sl, tp_pip=med_tp,
                        bar_time=df['time'].values, null=null,
                        split_bar=inner_split,
                        close=df['close'].values.astype(np.float64))
    print(R2.format_rqs2(f'S751-{tf} HOLDOUT-C', r), flush=True)
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
    print('NOTE: protocol C — holdout must NOT be re-tested after any retune.',
          flush=True)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'M1')
