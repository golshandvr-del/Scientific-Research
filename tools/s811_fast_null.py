"""
s811_fast_null.py — صفر سنجیده‌ی **سریع** برای S811 (numba)
================================================================================

چرا این فایل وجود دارد: لایه‌ی برنده‌ی S811 روی هولد‌اوت ~۱۱۶هزار معامله دارد.
صفر K=500 با موتور رویدادمحور پایتونی روزها طول می‌کشد. این ابزار همان
معناشناسی دقیق `se.simulate_trades` را (برای حالت بدون BE/trailing) در numba
بازتولید می‌کند:

  - ورود: open[si+1] (slip=0 برای XAUUSD)
  - چک TP/SL از خود کندل ورود؛ هر دو در یک کندل ⇒ باخت (بدترین حالت)
  - تایم‌اوت: بستن با close[min(entry+mh, n)-1]
  - outcome: win ⇔ pnl_pip = gross/pip − spread > 0  (اسپرد 3.3 پیپ)
  - allow_overlap=False: تا exit_bar معامله‌ی جاری، سیگنال جدید مصرف نمی‌شود

اعتبارسنجی اجباری: WR لایه‌ی واقعی از این مسیر با WR خروجی se.simulate_trades
مقایسه می‌شود؛ اختلاف > 0.05pp ⇒ توقف کامل (هیچ صفر نامعتبری ذخیره نمی‌شود).

طرح صفر (عین پیش‌ثبت S811): جهتِ هر سیگنال تصادفی می‌شود؛ کندل‌های سیگنال،
هندسه، max_hold و قانون عدم‌همپوشانی ثابت می‌مانند. K=500.
خط مبنای بی‌قید هر سمت: همه‌ی سیگنال‌ها همان‌سمت + عدم‌همپوشانی.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
from numba import njit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import scalp_engine as se          # noqa: E402
from tools import s434_fast_data as fd         # noqa: E402

OUT_DIR = os.path.join(ROOT, 'results', '_s811')
SPLIT_EPOCH = 1546300800
SEED = 812
N_PERM = 500


@njit(cache=True)
def precompute_outcomes(o, h, l, c, sig_idx, sl_d, tp_d, mh, spread_pip, pip):
    """برای هر سیگنال، نتیجه‌ی (win?, exit_bar) هر دو جهت را پیش‌محاسبه می‌کند."""
    m = len(sig_idx)
    n = len(o)
    win_L = np.zeros(m, np.int8); win_S = np.zeros(m, np.int8)
    exit_L = np.zeros(m, np.int64); exit_S = np.zeros(m, np.int64)
    valid = np.zeros(m, np.int8)
    for k in range(m):
        si = sig_idx[k]
        eb = si + 1
        if eb >= n:
            continue
        valid[k] = 1
        fill = o[eb]
        end = min(eb + mh, n)
        # LONG
        slp = fill - sl_d; tpp = fill + tp_d
        out = -1; xb = end - 1
        for j in range(eb, end):
            hs = l[j] <= slp; ht = h[j] >= tpp
            if hs and ht:
                out = 0; xb = j; break
            elif ht:
                out = 1; xb = j; break
            elif hs:
                out = 0; xb = j; break
        if out == 1:
            gross = tp_d
        elif out == 0:
            gross = -sl_d
        else:
            gross = c[xb] - fill
        win_L[k] = 1 if (gross / pip - spread_pip) > 0 else 0
        exit_L[k] = xb
        # SHORT
        slp = fill + sl_d; tpp = fill - tp_d
        out = -1; xb = end - 1
        for j in range(eb, end):
            hs = h[j] >= slp; ht = l[j] <= tpp
            if hs and ht:
                out = 0; xb = j; break
            elif ht:
                out = 1; xb = j; break
            elif hs:
                out = 0; xb = j; break
        if out == 1:
            gross = tp_d
        elif out == 0:
            gross = -sl_d
        else:
            gross = fill - c[xb]
        win_S[k] = 1 if (gross / pip - spread_pip) > 0 else 0
        exit_S[k] = xb
    return win_L, win_S, exit_L, exit_S, valid


@njit(cache=True)
def nonoverlap_wr(sig_idx, dirs, win_L, win_S, exit_L, exit_S, valid):
    """شمارش برد/کل به‌ازای هر سمت با قانون عدم‌همپوشانی. dirs: 1=long, 0=short."""
    busy = -1
    wins_l = 0; n_l = 0; wins_s = 0; n_s = 0
    for k in range(len(sig_idx)):
        if valid[k] == 0:
            continue
        eb = sig_idx[k] + 1
        if eb <= busy:
            continue
        if dirs[k] == 1:
            n_l += 1; wins_l += win_L[k]; busy = exit_L[k]
        else:
            n_s += 1; wins_s += win_S[k]; busy = exit_S[k]
    return wins_l, n_l, wins_s, n_s


def main():
    summary = json.load(open(os.path.join(OUT_DIR, 'winner.json')))
    w = summary['winner']
    print('winner:', w)

    d = fd.load_fast('XAUUSD', 'M1')
    print('src:', d['src'])
    z = np.load(os.path.join(OUT_DIR, 'features_m1.npz'))
    roof = z['roof']
    n = len(d['open'])
    up = np.zeros(n, bool); dn = np.zeros(n, bool)
    up[1:] = (roof[1:] > 0) & (roof[:-1] <= 0)
    dn[1:] = (roof[1:] < 0) & (roof[:-1] >= 0)
    # برنده: logic=cycle, gate=none
    ls, ss = up, dn
    t = d['time']
    second = t >= SPLIT_EPOCH
    ls2, ss2 = ls & second, ss & second

    cfg = se.ASSETS['XAUUSD']
    pip, spread = cfg['pip'], cfg['spread_pip']
    sl_d, tp_d = w['sl'] * pip, w['tp'] * pip
    mh = w['mh']

    o = np.ascontiguousarray(d['open'], dtype=np.float64)
    hi = np.ascontiguousarray(d['high'], dtype=np.float64)
    lo = np.ascontiguousarray(d['low'], dtype=np.float64)
    c = np.ascontiguousarray(d['close'], dtype=np.float64)

    sig = ls2 | ss2
    sig_idx = np.where(sig)[0].astype(np.int64)
    true_dirs = np.where(ls2[sig_idx], 1, 0).astype(np.int8)
    print('holdout signals:', len(sig_idx))

    win_L, win_S, exit_L, exit_S, valid = precompute_outcomes(
        o, hi, lo, c, sig_idx, sl_d, tp_d, mh, spread, pip)

    # --- اعتبارسنجی مقابل موتور رسمی: روی برش 400k کندلی (محدودیت RAM/OOM) ---
    import pandas as pd
    s0 = int(np.searchsorted(t, SPLIT_EPOCH))
    s1 = min(s0 + 400_000, n)
    dfv = pd.DataFrame({'open': o[s0:s1], 'high': hi[s0:s1],
                        'low': lo[s0:s1], 'close': c[s0:s1]})
    trv = se.simulate_trades(dfv, ls2[s0:s1], ss2[s0:s1], sl_pip=w['sl'],
                             tp_pip=w['tp'], asset='XAUUSD', max_hold=mh,
                             allow_overlap=False)
    wr_ref = float((trv['outcome'].values == 'win').mean() * 100)
    del dfv
    vmask = (sig_idx >= s0) & (sig_idx < s1 - 1)
    v_idx = (sig_idx[vmask] - s0).astype(np.int64)
    v_dirs = true_dirs[vmask]
    wL, wS, eL, eS, vv = precompute_outcomes(
        o[s0:s1], hi[s0:s1], lo[s0:s1], c[s0:s1], v_idx, sl_d, tp_d, mh,
        spread, pip)
    wl_v, nl_v, ws_v, ns_v = nonoverlap_wr(v_idx, v_dirs, wL, wS, eL, eS, vv)
    wr_fast_v = (wl_v + ws_v) / (nl_v + ns_v) * 100
    print(f'validation(slice {s1-s0} bars): fast WR={wr_fast_v:.4f} vs '
          f'engine WR={wr_ref:.4f} (n {nl_v+ns_v} vs {len(trv)})')
    if abs(wr_fast_v - wr_ref) > 0.05:
        raise SystemExit('⛔ fast-null diverges from engine — abort')
    wl, nl, ws, ns = nonoverlap_wr(sig_idx, true_dirs, win_L, win_S,
                                   exit_L, exit_S, valid)
    wr_fast = (wl + ws) / (nl + ns) * 100
    print(f'holdout layer (fast engine): WR={wr_fast:.4f} n={nl+ns} '
          f'(long {nl}, short {ns})')

    # --- خط مبنای بی‌قید هر سمت ---
    all_long = np.ones(len(sig_idx), np.int8)
    all_short = np.zeros(len(sig_idx), np.int8)
    wl_u, nl_u, _, _ = nonoverlap_wr(sig_idx, all_long, win_L, win_S, exit_L, exit_S, valid)
    _, _, ws_u, ns_u = nonoverlap_wr(sig_idx, all_short, win_L, win_S, exit_L, exit_S, valid)
    uncond_long = wl_u / nl_u * 100
    uncond_short = ws_u / ns_u * 100
    print(f'uncond: long={uncond_long:.3f} ({nl_u})  short={uncond_short:.3f} ({ns_u})')

    # --- K=500 جای‌گشت جهت ---
    rng = np.random.default_rng(SEED)
    pl, ps = [], []
    for k in range(N_PERM):
        dirs = (rng.random(len(sig_idx)) < 0.5).astype(np.int8)
        wl, nl, ws, ns = nonoverlap_wr(sig_idx, dirs, win_L, win_S,
                                       exit_L, exit_S, valid)
        if nl:
            pl.append(wl / nl * 100)
        if ns:
            ps.append(ws / ns * 100)
        if (k + 1) % 100 == 0:
            print(f'  perm {k+1}/{N_PERM}', flush=True)
    out = {
        'long': dict(uncond_wr=uncond_long,
                     perm_mean=float(np.mean(pl)), perm_sd=float(np.std(pl)),
                     perm_max=float(np.max(pl)), perm_k=len(pl)),
        'short': dict(uncond_wr=uncond_short,
                      perm_mean=float(np.mean(ps)), perm_sd=float(np.std(ps)),
                      perm_max=float(np.max(ps)), perm_k=len(ps)),
        'validation': dict(wr_fast=wr_fast, wr_engine=wr_ref,
                           n_fast=int(nl_u + ns_u), n_engine=int(len(tr))),
    }
    print(json.dumps(out, indent=1))
    with open(os.path.join(OUT_DIR, 'null_holdout.json'), 'w') as f:
        json.dump(out, f, indent=1)
    print('[done] null saved')


if __name__ == '__main__':
    main()
