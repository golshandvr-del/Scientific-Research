#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S881 — جستجوی Path C روی **نیمهٔ اول** — Skew Flip (چرخشِ چولگی)

پیش‌ثبت: results/S881_PREREG_SkewFlip_PathC.md (commit 64038264)
⚠️ فقط نیمهٔ اولِ هر TF. نیمهٔ دوم = hold-out.

فضا (منجمد): p∈{34,55,89} · θ∈{0.618,1.0} · k∈{13,21} · b∈{1.0,1.5} · hold∈{55,89,144}
هندسه: SL = 1.6×ATR(89) منجمد per-TF.
"""
import sys, os, json, time, gc
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from strategies.s881_feasibility import skew_vec
from strategies.s880_entropy_collapse_scan import wr_of, atr_pip, uncond_wr

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, 'results', '_scan_S881')
os.makedirs(OUTDIR, exist_ok=True)

SPREAD_PIP = 3.3
A_SL = 1.6
P_LIST = (34, 55, 89)
T_LIST = (0.618, 1.0)
K_LIST = (13, 21)
B_LIST = (1.0, 1.5)
HOLD_LIST = (55, 89, 144)

TFS = ['M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20', 'M30',
       'H1', 'H2', 'H3', 'H4', 'H6', 'H8', 'H12', 'D1', 'W1', 'MN1']


def build_signals(S, theta, k):
    """چرخشِ چولگی — بدونِ نگاهِ جلو. long: منفیِ عمیق→مثبت؛ short قرینه."""
    n = len(S)
    below = S < -theta
    above = S > theta
    run_lo = np.zeros(n, dtype=bool)
    run_hi = np.zeros(n, dtype=bool)
    for j in range(1, k + 1):
        run_lo[j:] |= below[:-j]
        run_hi[j:] |= above[:-j]
    prev = np.concatenate(([np.nan], S[:-1]))
    with np.errstate(invalid='ignore'):
        long_sig = (S > 0) & (prev <= 0) & run_lo
        short_sig = (S < 0) & (prev >= 0) & run_hi
    return long_sig, short_sig


def scan_tf(tf):
    t0 = time.time()
    d = fd.load_fast('XAUUSD', tf)
    src = d['src']
    n_all = len(d['close'])
    half = n_all // 2
    import pandas as pd
    df1 = pd.DataFrame({c: np.asarray(d[c][:half], dtype=np.float64)
                        for c in ('open', 'high', 'low', 'close')})
    df1['time'] = np.asarray(d['time'][:half], dtype=np.int64)
    del d
    gc.collect()
    close = df1['close'].values
    apip = atr_pip(df1['high'].values, df1['low'].values, close, 89)
    out = {'tf': tf, 'src': src, 'n_all': int(n_all), 'half_idx': int(half),
           'atr89_median_pip': apip, 'sl_pip': None, 'configs': []}
    if apip is None or half < 500:
        out['skip'] = 'too few bars'
        return out
    sl = round(A_SL * apip, 1)
    out['sl_pip'] = sl

    rng = np.random.default_rng(881)
    ucache = {}
    for p in P_LIST:
        S = skew_vec(close, p)
        gc.collect()
        for theta in T_LIST:
            for k in K_LIST:
                ls, ss = build_signals(S, theta, k)
                nL, nS = int(ls.sum()), int(ss.sum())
                for b in B_LIST:
                    tp = round(b * sl, 1)
                    be = 100.0 * (sl + SPREAD_PIP) / (sl + tp)
                    for hold in HOLD_LIST:
                        tr = se.simulate_trades(df1, ls, ss, sl_pip=sl,
                                                tp_pip=tp, asset='XAUUSD',
                                                max_hold=hold,
                                                allow_overlap=False)
                        wr, n = wr_of(tr)
                        cfg = {'p': p, 'theta': theta, 'k': k, 'b': b,
                               'hold': hold, 'sl_pip': sl, 'tp_pip': tp,
                               'be_wr': round(be, 2), 'n': n,
                               'wr': None if wr is None else round(wr, 2),
                               'nL_sig': nL, 'nS_sig': nS}
                        if wr is not None and n >= 30:
                            nl_t = int((tr['direction'] == 'long').sum())
                            ns_t = n - nl_t
                            # WR جداگانهٔ سمت‌ها برای پیش‌بینیِ ابطال‌پذیرِ پیش‌ثبت
                            if nl_t > 0:
                                cfg['wr_long'] = round(100.0 * float(
                                    (tr[tr['direction'] == 'long']['pnl_pip'] > 0).mean()), 2)
                            if ns_t > 0:
                                cfg['wr_short'] = round(100.0 * float(
                                    (tr[tr['direction'] == 'short']['pnl_pip'] > 0).mean()), 2)
                            parts = []
                            for side, m in (('long', nl_t), ('short', ns_t)):
                                if m == 0:
                                    continue
                                key = (side, sl, tp, hold)
                                if key not in ucache:
                                    ucache[key] = uncond_wr(df1, side, max(m, 300),
                                                            sl, tp, hold, rng)
                                if ucache[key] is not None:
                                    parts.append((m, ucache[key]))
                            if parts:
                                uw = sum(m * w for m, w in parts) / sum(m for m, _ in parts)
                                cfg['uncond_wr'] = round(uw, 2)
                                cfg['lift'] = round(wr - uw, 2)
                                cfg['score'] = round((wr - uw) * np.sqrt(n), 1)
                        out['configs'].append(cfg)
        del S
        gc.collect()
    valid = [c for c in out['configs']
             if c.get('lift') is not None and c['wr'] > c['be_wr']
             and c['n'] >= 30 and c['lift'] > 0]
    out['best'] = max(valid, key=lambda c: c['score']) if valid else None
    out['elapsed_s'] = round(time.time() - t0, 1)
    return out


def main():
    for tf in (sys.argv[1:] or TFS):
        fp = os.path.join(OUTDIR, f'XAUUSD_{tf}.json')
        if os.path.exists(fp):
            print(tf, 'exists, skip', flush=True)
            continue
        try:
            res = scan_tf(tf)
        except FileNotFoundError as e:
            res = {'tf': tf, 'skip': str(e)}
        with open(fp, 'w') as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        b = res.get('best')
        print(tf, 'done', res.get('elapsed_s'), 's | best:',
              json.dumps(b, ensure_ascii=False) if b else 'None', flush=True)


if __name__ == '__main__':
    main()
