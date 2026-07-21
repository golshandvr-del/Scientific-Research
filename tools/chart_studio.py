# -*- coding: utf-8 -*-
"""
chart_studio.py — استودیوی رندرِ چارتِ کندل‌استیک برای الگوشناسیِ بصری.
خروجی: تصاویرِ PNG در /tmp/charts/ که با «چشم» بررسی می‌شوند.
"""
import os
import pandas as pd
import numpy as np
import mplfinance as mpf

DATA = '/home/user/webapp/data'
OUT = '/tmp/charts'
os.makedirs(OUT, exist_ok=True)


def load(sym, tf):
    df = pd.read_csv(f'{DATA}/{sym}_{tf}.csv')
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    df = df.set_index('dt')
    df = df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low',
                            'close': 'Close', 'volume': 'Volume'})
    return df[['Open', 'High', 'Low', 'Close', 'Volume']]


def render(sym, tf, start_idx, n, label, mavs=(20, 50)):
    df = load(sym, tf)
    seg = df.iloc[start_idx:start_idx + n]
    d0 = seg.index[0].strftime('%Y-%m-%d')
    d1 = seg.index[-1].strftime('%Y-%m-%d')
    fname = f'{OUT}/{sym}_{tf}_{label}.png'
    mc = mpf.make_marketcolors(up='#26a69a', down='#ef5350', edge='inherit',
                               wick='inherit', volume='in')
    style = mpf.make_mpf_style(marketcolors=mc, gridstyle=':', gridcolor='#cccccc',
                               facecolor='white', figcolor='white')
    mpf.plot(seg, type='candle', style=style, mav=mavs, volume=True,
             title=f'{sym} {tf} | {label} | {d0} -> {d1} ({n} bars)',
             figsize=(20, 10), savefig=dict(fname=fname, dpi=72, bbox_inches='tight'))
    print(f'saved {fname}  ({d0} -> {d1})')
    return fname


if __name__ == '__main__':
    import sys
    # پیش‌فرض: مرورِ کلانِ D1 در طولِ ۱۵ سال
    df = load('XAUUSD', 'D1')
    N = len(df)
    print(f'D1 total bars: {N}')
