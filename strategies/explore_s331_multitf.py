# -*- coding: utf-8 -*-
"""
S331 Multi-Timeframe — تعمیمِ لایهٔ احیاشدهٔ S331 به همهٔ تایم‌فریم‌ها و هر دو ارز
================================================================================
منطقِ هستهٔ S331 (احیای S79 با RQS+ روی XAUUSD M5):
    base   :  EMA(20) > EMA(100)  AND  RSI(21) < 35        (buy-dip در روند)
    filter :  slope100/ATR > θ    (فیلترِ قدرتِ روند — کلیدِ احیا)
    exec   :  SL/TP/hold مخصوصِ هر TF (اشتباهِ رایج #۶: TP/SL یکسان ممنوع)
    Long فقط.

قانونِ اول پروژه (مولتی‌تایم‌فریم اجباری): هر TF جداگانه سنجیده و گزارش می‌شود.
هر TF بهبودِ متناسبِ خود را می‌گیرد (θ و SL/TP/hold بهینهٔ همان TF).

اجرا:  python strategies/explore_s331_multitf.py  [ASSET]   (پیش‌فرض XAUUSD)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from engine import scalp_engine as se
from engine import rqs
from engine import indicators as ind


def load(asset_key, tf):
    df = pd.read_csv(f"data/{asset_key}_{tf}.csv")
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df.reset_index(drop=True)


def build_signals(df, slope_th):
    """سیگنالِ S331 با آستانهٔ slope مشخص."""
    close = df['close']
    ema20 = ind.ema(close, 20); ema100 = ind.ema(close, 100)
    rsi21 = ind.rsi(close, 21)
    atr14 = ind.atr(df, 14)
    slope100 = (ema100 - ema100.shift(20)) / atr14
    base = (ema20 > ema100) & (rsi21 < 35)
    mask = base & (slope100 > slope_th)
    long_sig = mask.fillna(False).values
    short_sig = np.zeros(len(df), dtype=bool)
    return long_sig, short_sig


def eval_cfg(df, asset, slope_th, sl, tp, hold):
    ls, ss = build_signals(df, slope_th)
    trades = se.simulate_trades(df, ls, ss, float(sl), float(tp), asset, max_hold=hold)
    r = rqs.compute_rqs(trades, asset, sl_pip=float(sl), tp_pip=float(tp))
    return r


def scan_tf(asset, tf, sl_grid, tp_grid, hold_grid, slope_grid):
    """اسکنِ per-TF برای یافتنِ بهترین پیکربندیِ RQS+ (بهبودِ متناسبِ همان TF)."""
    df = load(asset, tf)
    best = None
    passed = []
    for th in slope_grid:
        ls, ss = build_signals(df, th)
        if ls.sum() < 20:
            continue
        for sl in sl_grid:
            for tp in tp_grid:
                for hold in hold_grid:
                    trades = se.simulate_trades(df, ls, ss, float(sl), float(tp),
                                                asset, max_hold=hold)
                    r = rqs.compute_rqs(trades, asset, sl_pip=float(sl), tp_pip=float(tp))
                    rec = (r['rqs_score'], th, sl, tp, hold, r)
                    if r['passed']:
                        passed.append(rec)
                    if best is None or r['rqs_score'] > best[0]:
                        best = rec
    return df, best, passed


if __name__ == '__main__':
    asset = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD'
    print("=" * 110)
    print(f"S331 Multi-Timeframe —  ارز: {asset}")
    print("=" * 110)

    # گریدهای متناسب با مقیاسِ pip هر TF (طلا pip=0.10؛ حرکتِ TFهای بالا بزرگ‌تر)
    # برای طلا M5≈75pip، پس TFهای بالاتر بزرگ‌تر. یورو pip=0.0001 مقیاسِ متفاوت دارد.
    if asset == 'XAUUSD':
        tf_grids = {
            'M5':  dict(sl=[65, 75, 85],    tp=[48, 55, 65],    hold=[48, 60, 72], slope=[0.65, 0.75, 0.85]),
            'M15': dict(sl=[90, 110, 130],  tp=[70, 90, 110],   hold=[36, 48, 60], slope=[0.55, 0.7, 0.85]),
            'M30': dict(sl=[120, 150, 180], tp=[100, 130, 160], hold=[30, 42, 54], slope=[0.5, 0.65, 0.8]),
            'H1':  dict(sl=[170, 210, 260], tp=[140, 180, 230], hold=[24, 36, 48], slope=[0.5, 0.65, 0.8]),
        }
    else:  # EURUSD — مقیاسِ pip کوچک‌تر (فارکس)
        tf_grids = {
            'M5':  dict(sl=[14, 18, 22],  tp=[11, 14, 18],  hold=[48, 60, 72], slope=[0.65, 0.75, 0.85]),
            'M15': dict(sl=[20, 26, 32],  tp=[16, 22, 28],  hold=[36, 48, 60], slope=[0.55, 0.7, 0.85]),
            'M30': dict(sl=[28, 36, 44],  tp=[22, 30, 38],  hold=[30, 42, 54], slope=[0.5, 0.65, 0.8]),
            'H1':  dict(sl=[40, 52, 64],  tp=[32, 44, 56],  hold=[24, 36, 48], slope=[0.5, 0.65, 0.8]),
        }

    summary = []
    for tf, g in tf_grids.items():
        df, best, passed = scan_tf(asset, tf, g['sl'], g['tp'], g['hold'], g['slope'])
        score, th, sl, tp, hold, r = best
        m = r['metrics']
        status = '✅ ACCEPT' if r['passed'] else '❌ REJECT'
        print(f"\n--- {asset} {tf} ({len(df):,} کندل) ---")
        print(f"   بهترین: slope>{th} SL{sl}/TP{tp} hold{hold}  →  {status}  RQS={score}")
        print(f"   n={m['n_trades']} WR={m['win_rate']}% PF={m['profit_factor']} "
              f"DD={m['max_dd_pct']}% MCL={m['max_consec_losses']} p={m['p_value']}")
        gline = ' '.join(f"{k}:{'✓' if v else '✗'}" for k, v in r['gates'].items())
        print(f"   گیت‌ها: {gline}")
        print(f"   پیکربندی‌های پاس‌شده در این TF: {len(passed)}")
        summary.append((tf, r['passed'], score, th, sl, tp, hold, m))

    print("\n" + "=" * 110)
    print("خلاصهٔ مولتی‌تایم‌فریم:")
    for tf, ok, score, th, sl, tp, hold, m in summary:
        tag = '✅' if ok else '❌'
        print(f"  {tag} {asset} {tf:4s} | RQS={score:5.1f} | slope>{th} SL{sl}/TP{tp} h{hold} | "
              f"n={m['n_trades']} WR={m['win_rate']}% PF={m['profit_factor']}")
    accepted = [s for s in summary if s[1]]
    print(f"\nتایم‌فریم‌های احیاشده ({asset}): {[s[0] for s in accepted]}")
