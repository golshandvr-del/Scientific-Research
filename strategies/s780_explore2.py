# -*- coding: utf-8 -*-
"""
S780 — فاز اکتشاف، دور دوم (همچنان فقط نیمهٔ اول — مسیر C)
============================================================
یافتهٔ دور اول: تنها خانوادهٔ سالمِ اقتصادی، «تداوم چرخه‌ای» روی H1 است
(net مثبت پس از هزینهٔ کامل). M5 با وجود z بالا اقتصادی نیست (هزینه ۲۲٪ SL).

دور دوم روی M30 / H1 / H4-resampled:
  - سیگنال اجتماع (OR) رویدادهای trendflex و reflex → n بزرگ‌تر
  - شبکهٔ آستانهٔ ریزتر حول ناحیهٔ امیدبخش 1.0–2.3
  - هندسه‌های سخاوتمندتر (tp_atr تا 2.68) — هرگز TP<SL (ضداشتباه #8)
"""
import os, sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import indicator_bank as ib
from engine import scalp_engine as se
from tools import s434_fast_data as fd

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_s780')
os.makedirs(OUT_DIR, exist_ok=True)

ASSET = 'XAUUSD'
SPLIT_EPOCH = 1_541_749_500  # میانهٔ تقویمی دادهٔ کامل ≈ 2018-11-09

THRESHOLDS = [0.97, 1.17, 1.38, 1.61, 1.83, 2.07, 2.31]
GEOMS = [(1.87, 1.87), (1.87, 2.24), (1.87, 2.61), (1.53, 1.91), (2.23, 2.68)]
SIGSETS = ['trendflex', 'reflex', 'union']   # union = OR دو اندیکاتور


def resample_h1(df_h1: pd.DataFrame, minutes: int) -> pd.DataFrame:
    """بازنمونه‌گیری H4 از H1 — چون H4 در mt5_full نیست (دام E-16)."""
    t = pd.to_datetime(df_h1['time'], unit='s', utc=True)
    g = df_h1.copy(); g.index = t
    rule = f'{minutes}min'
    out = pd.DataFrame({
        'open':  g['open'].resample(rule, label='left', closed='left').first(),
        'high':  g['high'].resample(rule, label='left', closed='left').max(),
        'low':   g['low'].resample(rule, label='left', closed='left').min(),
        'close': g['close'].resample(rule, label='left', closed='left').last(),
        'volume': g['volume'].resample(rule, label='left', closed='left').sum(),
    }).dropna(subset=['open'])
    out['time'] = (out.index.view('int64') // 10**9).astype(np.int64)
    return out.reset_index(drop=True)


def atr_pips(df, period=34):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return float(np.nanmedian(pd.Series(tr).rolling(period).mean().values) / 0.10)


def event_cross(x, thr):
    x = np.asarray(x, dtype=float)
    prev = np.roll(x, 1); prev[0] = np.nan
    up = (prev < thr) & (x >= thr) & np.isfinite(prev)
    dn = (prev > -thr) & (x <= -thr) & np.isfinite(prev)
    return up, dn


def main():
    d = fd.load_fast(ASSET, 'H1')
    df_h1_full = fd.as_dataframe(d)
    print('H1 src:', d['src'], flush=True)
    d30 = fd.load_fast(ASSET, 'M30')
    frames = {
        'M30': fd.as_dataframe(d30),
        'H1': df_h1_full,
        'H4': resample_h1(df_h1_full, 240),
    }
    print('M30 src:', d30['src'], '| H4 resampled from H1:',
          len(frames['H4']), 'bars', flush=True)

    rows = []
    for tf, df_full in frames.items():
        df = df_full.loc[df_full['time'].values < SPLIT_EPOCH].reset_index(drop=True)
        ap = atr_pips(df)
        max_hold = fd.hold_bars_for(tf, 72)
        tf_v = np.asarray(ib.compute('trendflex', df), dtype=float)
        rx_v = np.asarray(ib.compute('reflex', df), dtype=float)
        for sigset in SIGSETS:
            for thr in THRESHOLDS:
                u1, d1s = event_cross(tf_v, thr)
                u2, d2s = event_cross(rx_v, thr)
                if sigset == 'trendflex':
                    up, dn = u1, d1s
                elif sigset == 'reflex':
                    up, dn = u2, d2s
                else:
                    up, dn = (u1 | u2), (d1s | d2s)
                for sl_atr, tp_atr in GEOMS:
                    sl_pip = round(sl_atr * ap, 1); tp_pip = round(tp_atr * ap, 1)
                    tr = se.simulate_trades(df, up, dn, sl_pip=sl_pip, tp_pip=tp_pip,
                                            asset=ASSET, max_hold=max_hold,
                                            allow_overlap=False)
                    n = len(tr)
                    if n < 50:
                        continue
                    wr = (tr['pnl_pip'] > 0).mean()
                    be = sl_pip / (sl_pip + tp_pip)
                    lift = (wr - be) * 100
                    z = (wr - be) * np.sqrt(n) / np.sqrt(be * (1 - be))
                    rows.append(dict(tf=tf, sigset=sigset, thr=thr, sl_atr=sl_atr,
                                     tp_atr=tp_atr, sl_pip=sl_pip, tp_pip=tp_pip,
                                     n=int(n), wr=round(wr*100, 2), be=round(be*100, 2),
                                     lift=round(lift, 2), z=round(z, 2),
                                     net_pip=round(float(tr['pnl_pip'].sum()), 1)))
        print(f'[{tf}] done', flush=True)

    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(OUT_DIR, 'explore2_first_half.csv'), index=False)
    print(f'\nconfigs this round: {len(out)}')
    ok = out[(out.net_pip > 0)].sort_values('z', ascending=False)
    print(ok.head(30).to_string(index=False))


if __name__ == '__main__':
    t0 = time.time(); main(); print(f'elapsed: {time.time()-t0:.1f}s')
