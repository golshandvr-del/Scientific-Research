# -*- coding: utf-8 -*-
"""
S341c — نسخهٔ سریعِ اسکن: پیش‌محاسبهٔ فراکتال‌ها + رژیم (یک‌بار per-TF)، سپس فقط SL/TP/mh را می‌چرخاند.
منطقِ سیگنال بیت‌به‌بیت برابر با s341_brooks_swing_levels.swing_fade_signals است (تأییدشده در تستِ برابری).
"""
import sys
import numpy as np
import itertools

from engine import scalp_engine as se
from engine import indicator_bank as ib
from engine import rqs
from strategies.s341_brooks_swing_levels import _fractal_levels, load_tf

GRID_XAU = {
    'M5':  dict(sl=[180, 260], tp=[260, 390, 520], mh=[24, 48]),
    'M15': dict(sl=[280, 420], tp=[420, 620, 830], mh=[20, 40]),
    'M30': dict(sl=[380, 560], tp=[560, 840, 1120], mh=[18, 32]),
    'H1':  dict(sl=[520, 780], tp=[780, 1150, 1550], mh=[16, 28]),
    'H4':  dict(sl=[900, 1350], tp=[1350, 2000, 2700], mh=[14, 22]),
}
GRID_EUR = {
    'M5':  dict(sl=[14, 22], tp=[22, 33, 44], mh=[24, 48]),
    'M15': dict(sl=[22, 33], tp=[33, 50, 66], mh=[20, 40]),
    'M30': dict(sl=[30, 45], tp=[45, 68, 90], mh=[18, 32]),
}
W_GRID = [4, 5, 8]
BUF = [0.05, 0.15]
REGIME_GRID = [
    dict(chop_min=52, r2_max=0.40, er_max=0.30),
    dict(chop_min=58, r2_max=0.30, er_max=0.22),
    dict(chop_min=61.8, r2_max=0.22, er_max=0.16),
]
SECOND = [False, True]


def build_signal_fast(h, l, c, atr, reg_mask, last_sh, last_sl, side, buf_frac,
                      require_second, second_lookback=40):
    n = len(h)
    sig = np.zeros(n, dtype=bool)
    recent = []
    minstart = 0
    for i in range(minstart, n):
        if not reg_mask[i]:
            continue
        a = atr[i]
        if not (a > 0) or not np.isfinite(a):
            continue
        buf = buf_frac * a
        if side == 'short':
            lvl = last_sh[i]
            if not np.isfinite(lvl):
                continue
            trig = (h[i] > lvl + buf) and (c[i] < lvl)
        else:
            lvl = last_sl[i]
            if not np.isfinite(lvl):
                continue
            trig = (l[i] < lvl - buf) and (c[i] > lvl)
        if not trig:
            continue
        if require_second:
            recent = [x for x in recent if x >= i - second_lookback]
            recent.append(i)
            if len(recent) < 2:
                continue
        sig[i] = True
    return sig


def scan_one(asset, tf, verbose=True):
    df = load_tf(asset, tf)
    grid = (GRID_XAU if asset == 'XAUUSD' else GRID_EUR).get(tf)
    if grid is None:
        return None
    h = df['high'].to_numpy(float); l = df['low'].to_numpy(float); c = df['close'].to_numpy(float)
    atr = ib.atr_s(df, p=14).to_numpy()
    # پیش‌محاسبهٔ رژیم‌ها (chop_p=14, r2_p=20, er=er_lucas_11) یک‌بار
    ch = ib.chop(df, p=14).to_numpy()
    r2 = ib.r2(df, p=20).to_numpy()
    er = np.abs(ib.compute('er_lucas_11', df).to_numpy())
    finite = np.isfinite(ch) & np.isfinite(r2) & np.isfinite(er)
    # فراکتال‌ها per-w یک‌بار
    frac_cache = {w: _fractal_levels(h, l, w) for w in W_GRID}

    best = None
    for side in ('short', 'long'):
        for w in W_GRID:
            last_sh, last_sl = frac_cache[w]
            for buf in BUF:
                for reg in REGIME_GRID:
                    reg_mask = finite & (ch >= reg['chop_min']) & (r2 <= reg['r2_max']) & (er <= reg['er_max'])
                    for sec in SECOND:
                        sig = build_signal_fast(h, l, c, atr, reg_mask, last_sh, last_sl,
                                                side, buf, sec)
                        if sig.sum() < 30:
                            continue
                        long_sig = sig if side == 'long' else np.zeros(len(df), bool)
                        short_sig = sig if side == 'short' else np.zeros(len(df), bool)
                        for sl, tp, mh in itertools.product(grid['sl'], grid['tp'], grid['mh']):
                            if tp <= sl:
                                continue
                            tr = se.simulate_trades(df, long_sig, short_sig, sl_pip=sl, tp_pip=tp,
                                                    asset=asset, max_hold=mh, allow_overlap=False)
                            if tr is None or len(tr) < 30:
                                continue
                            r = rqs.compute_rqs(tr, asset, sl_pip=sl, tp_pip=tp)
                            score = r['rqs_score']
                            cfg = dict(side=side, w=w, buf=buf, sec=sec, sl=sl, tp=tp, mh=mh, **reg)
                            if best is None or score > best[0]:
                                best = (score, r, cfg)
                                if verbose and r['passed']:
                                    print('  ACCEPT-CAND', rqs.format_report(f'{asset}_{tf}_{side}', r), cfg, flush=True)
    return best


if __name__ == '__main__':
    order = [('XAUUSD', t) for t in ['M5', 'M15', 'M30', 'H1', 'H4']] + \
            [('EURUSD', t) for t in ['M5', 'M15', 'M30']]
    if len(sys.argv) > 2:
        order = [(sys.argv[1], sys.argv[2])]
    for asset, tf in order:
        b = scan_one(asset, tf, verbose=True)
        if b is None:
            print(f"{asset}-{tf:4s} | no grid", flush=True); continue
        score, r, cfg = b
        tag = 'ACCEPT ✅' if r['passed'] else 'reject'
        print(f"{asset}-{tf:4s} | best RQS {score:5.1f} | {tag}", flush=True)
        print('   ', rqs.format_report(f'{asset}_{tf}', r), flush=True)
        print('    cfg=', cfg, flush=True)
