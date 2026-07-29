# -*- coding: utf-8 -*-
"""
S344 — کاوشگرِ بهبودِ عمیق (deep probe) برای عبور از گلوگاهِ G0 (WR ≥ ۶۰٪).
پارادایم: RQS+ ≥ ۸۰. منبع لایه: فصلِ ۲۳ Brooks (trend-from-open first-pullback).

هدفِ این probe: بدونِ تقلبِ TP<SL (اشتباهِ رایجِ ۸)، با «انتخابی‌ترکردنِ setup»
(قانونِ همه‌چیز شناور + جعبه‌ابزار) WR را به ≥۶۰ برسانیم و RQS+ را بالا ببریم.

بهبودهای آزموده‌شده (هرکدام یک لایهٔ فیلترِ روی سیگنالِ پایه):
  A) فیلترِ جهتِ روندِ بلندمدت: long فقط اگر close > EMA(len)، short برعکس. (len غیررند)
  B) فیلترِ رژیمِ قوی‌تر: r2(p) ≥ آستانه‌های مختلف + ADX.
  C) پنجرهٔ زمانیِ سخت‌گیرانه: ورود فقط در بازهٔ باریکِ اوایلِ روز.
  D) TP/SL متحرک (trail) — scalp_engine trail_pip دارد.
  E) ترکیبِ همزمان (قانونِ همکاریِ بهبودها).
"""
import sys
import numpy as np
import pandas as pd

from engine import scalp_engine as se
from engine import rqs
from engine import indicator_bank as ib
from strategies.s344_brooks_trend_from_open import trend_from_open_signals, load_tf


def ema_np(x, length):
    a = 2.0 / (length + 1.0)
    out = np.empty_like(x, dtype=float)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def run_combo(df, asset, tf, side, base_kw, filters, sl, tp, maxhold,
              trail_pip=None, be_trigger_pip=None):
    """یک ترکیبِ بهبود را می‌سازد و RQS+ را برمی‌گرداند."""
    sig = trend_from_open_signals(df, tf, side, **base_kw)
    if sig.sum() < 30:
        return None
    n = len(df)
    mask = np.ones(n, bool)

    c = df['close'].to_numpy(float)

    # A) فیلترِ EMA بلندمدت
    if 'ema_len' in filters:
        e = ema_np(c, filters['ema_len'])
        mask &= (c > e) if side == 'long' else (c < e)

    # B) فیلترِ r2
    if 'r2_p' in filters:
        try:
            v = ib.r2(df, p=filters['r2_p']).to_numpy()
            mask &= (v >= filters['r2_th']) & np.isfinite(v)
        except Exception:
            pass

    # B') فیلترِ ADX
    if 'adx_th' in filters:
        try:
            a = ib.compute('adx', df).to_numpy()
            mask &= (a >= filters['adx_th']) & np.isfinite(a)
        except Exception:
            pass

    # C) پنجرهٔ زمانیِ سخت‌گیرانه (اندیسِ کندل درونِ روز)
    if 'day_from' in filters or 'day_to' in filters:
        dt = pd.to_datetime(df['time'], unit='s')
        day_id = dt.dt.floor('D').astype('int64').to_numpy()
        intr = np.zeros(n, int)
        start = {}
        for i in range(n):
            d = day_id[i]
            if d not in start:
                start[d] = i
            intr[i] = i - start[d]
        if 'day_from' in filters:
            mask &= intr >= filters['day_from']
        if 'day_to' in filters:
            mask &= intr <= filters['day_to']

    fsig = sig & mask
    if fsig.sum() < 30:
        return None

    long_sig = fsig if side == 'long' else np.zeros(n, bool)
    short_sig = fsig if side == 'short' else np.zeros(n, bool)
    tr = se.simulate_trades(df, long_sig, short_sig, sl_pip=sl, tp_pip=tp, asset=asset,
                            max_hold=maxhold, allow_overlap=False,
                            trail_pip=trail_pip, be_trigger_pip=be_trigger_pip)
    if tr is None or len(tr) < 30:
        return None
    r = rqs.compute_rqs(tr, asset, sl_pip=sl, tp_pip=tp)
    return r


def main(asset='XAUUSD', tf='M5'):
    df = load_tf(asset, tf)
    maxhold = {'M5': 48, 'M15': 32, 'M30': 24, 'H1': 20}.get(tf, 24)
    sc = 1.0 if asset == 'XAUUSD' else 0.06
    base_kw = dict(n_open=6, f_range=0.20, pull_max=0.50, min_spike_frac=0.20)

    # گریدِ بهبودها — روی side=long (سمتِ قویِ طلا)
    ema_lens = [None, 135, 170, 220]
    r2_opts = [None, (34, 0.34), (34, 0.45), (55, 0.45)]
    adx_opts = [None, 22, 28]
    day_windows = [None, (6, 40), (6, 24), (10, 60)]
    tpsl_opts = [(int(150 * sc), int(225 * sc)), (int(120 * sc), int(240 * sc)),
                 (int(135 * sc), int(270 * sc))]
    trail_opts = [None, int(90 * sc), int(120 * sc)]

    best = None
    tested = 0
    for side in ('long',):
        for ema_len in ema_lens:
            for r2o in r2_opts:
                for adx in adx_opts:
                    for dw in day_windows:
                        for (sl, tp) in tpsl_opts:
                            for trail in trail_opts:
                                filt = {}
                                if ema_len: filt['ema_len'] = ema_len
                                if r2o: filt['r2_p'] = r2o[0]; filt['r2_th'] = r2o[1]
                                if adx: filt['adx_th'] = adx
                                if dw: filt['day_from'] = dw[0]; filt['day_to'] = dw[1]
                                r = run_combo(df, asset, tf, side, base_kw, filt, sl, tp,
                                              maxhold, trail_pip=trail)
                                tested += 1
                                if r is None:
                                    continue
                                m = r['metrics']
                                gates = ''.join('1' if r['gates'][g] else '0'
                                                for g in ['G0', 'G1', 'G2', 'G3', 'G4', 'G5'])
                                cand = dict(rqs=r['rqs_score'], passed=r['passed'],
                                            wr=m['win_rate'], pf=m['profit_factor'],
                                            n=m['n_trades'], gates=gates,
                                            ema=ema_len, r2=r2o, adx=adx, dw=dw,
                                            sl=sl, tp=tp, trail=trail)
                                if best is None or cand['rqs'] > best['rqs']:
                                    best = cand
                                    print(f"[new best] RQS={cand['rqs']:.1f} {'ACC' if cand['passed'] else 'rej'} "
                                          f"G[{gates}] WR={cand['wr']:.1f} PF={cand['pf']:.2f} n={cand['n']} "
                                          f"ema={ema_len} r2={r2o} adx={adx} dw={dw} SL/TP={sl}/{tp} trail={trail}",
                                          flush=True)
    print(f"\n=== tested {tested} combos ===")
    if best:
        print(f"BEST: RQS={best['rqs']:.2f} passed={best['passed']} WR={best['wr']:.1f} "
              f"PF={best['pf']:.2f} n={best['n']} G[{best['gates']}]")
    return best


if __name__ == '__main__':
    a = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD'
    t = sys.argv[2] if len(sys.argv) > 2 else 'M5'
    main(a, t)
