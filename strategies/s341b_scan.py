# -*- coding: utf-8 -*-
"""
S341b — اسکنِ کاملِ مولتی‌TF/دوجفت‌ارز برای S341 (Brooks Ch.17 swing-level fade).
قانونِ مولتی‌تایم‌فریم: از XAUUSD M1 شروع، همهٔ TFها و هر دو جفت‌ارز.
هر ترکیب: grid روی رژیمِ رنج + TP/SL غیررندِ per-TF + پنجرهٔ فراکتال + بافر + سیگنالِ دوم.
RQS+ داورِ نهایی است (G1 خودش بازیِ TP<SL را veto می‌کند، پس امن است).
"""
import sys
import numpy as np
import itertools

from engine import scalp_engine as se
from engine import rqs
from strategies.s341_brooks_swing_levels import swing_fade_signals, load_tf

# TP/SL غیررند (نه 100/200) — per-TF مقیاس‌ها متفاوت. واحد = pip طلا (0.1$) / pip یورو.
# برای طلا pip=0.1 ⇒ SL 220pip = 22$/oz. برای یورو pip=0.0001.
GRID_XAU = {
    'M1':  dict(sl=[120, 180], tp=[170, 260, 340], w=[4, 6], mh=[30, 60]),
    'M5':  dict(sl=[180, 260], tp=[260, 390, 520], w=[5, 8], mh=[24, 48]),
    'M15': dict(sl=[280, 420], tp=[420, 620, 830], w=[5, 8], mh=[20, 40]),
    'M30': dict(sl=[380, 560], tp=[560, 840, 1120], w=[5, 8], mh=[18, 32]),
    'H1':  dict(sl=[520, 780], tp=[780, 1150, 1550], w=[5, 8], mh=[16, 28]),
    'H4':  dict(sl=[900, 1350], tp=[1350, 2000, 2700], w=[4, 7], mh=[14, 22]),
}
GRID_EUR = {
    'M5':  dict(sl=[14, 22], tp=[22, 33, 44], w=[5, 8], mh=[24, 48]),
    'M15': dict(sl=[22, 33], tp=[33, 50, 66], w=[5, 8], mh=[20, 40]),
    'M30': dict(sl=[30, 45], tp=[45, 68, 90], w=[5, 8], mh=[18, 32]),
}

# رژیمِ رنج: chop بالا، r2 پایین، er پایین (fade فقط در رنج — قلبِ فصل ۱۷)
REGIME_GRID = [
    dict(chop_min=52, r2_max=0.40, er_max=0.30),
    dict(chop_min=58, r2_max=0.30, er_max=0.22),
    dict(chop_min=61.8, r2_max=0.22, er_max=0.16),   # سخت‌گیرانه (فیبوناچی 61.8)
]
BUF = [0.05, 0.15]
SECOND = [False, True]


def scan_one(asset, tf, verbose=False):
    df = load_tf(asset, tf)
    grid = (GRID_XAU if asset == 'XAUUSD' else GRID_EUR).get(tf)
    if grid is None:
        return None
    best = None
    for side in ('short', 'long'):
        for w, buf, reg, sec in itertools.product(grid['w'], BUF, REGIME_GRID, SECOND):
            sig = swing_fade_signals(df, side, w=w, buf_frac=buf,
                                     require_second=sec, second_lookback=40, **reg)
            if sig.sum() < 30:
                continue
            for sl, tp, mh in itertools.product(grid['sl'], grid['tp'], grid['mh']):
                if tp <= sl:
                    continue  # TP باید > SL باشد تا بازیِ WR کاذب رخ ندهد (ضدِ اشتباه #۸)
                long_sig = sig if side == 'long' else np.zeros(len(df), bool)
                short_sig = sig if side == 'short' else np.zeros(len(df), bool)
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
                        print('  ACCEPT-CAND', rqs.format_report(f'{asset}_{tf}_{side}', r), cfg)
    return best


if __name__ == '__main__':
    targets = []
    order = [('XAUUSD', t) for t in ['M1', 'M5', 'M15', 'M30', 'H1', 'H4']] + \
            [('EURUSD', t) for t in ['M5', 'M15', 'M30']]
    if len(sys.argv) > 1:
        order = [(sys.argv[1], sys.argv[2])]
    print(f"{'COMBO':16s} | best RQS | verdict")
    for asset, tf in order:
        b = scan_one(asset, tf, verbose=True)
        if b is None:
            print(f"{asset}-{tf:4s} | no grid")
            continue
        score, r, cfg = b
        tag = 'ACCEPT ✅' if r['passed'] else 'reject'
        print(f"{asset}-{tf:4s} | {score:5.1f} | {tag}")
        print('   ', rqs.format_report(f'{asset}_{tf}', r))
        print('    cfg=', cfg)
