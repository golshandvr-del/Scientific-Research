# -*- coding: utf-8 -*-
"""
s345_parity_export.py — مرجعِ برابریِ TS↔Python برای S345 (هر دو کارتِ پذیرفته‌شده).

خروجی: strategies/s345_parity_ref_<CARD>.json = کندل‌های خام + اندیسِ کندل‌هایی که
سیگنالِ نهاییِ پایتون (هندسه AND رژیم AND فیلترِ بهبود) روی آن‌ها True است.

harnessِ Node همان کندل‌ها را به computeS345 می‌دهد (پنجرهٔ دنباله‌دار) و باید دقیقاً
همان اندیس‌ها را active=true بدهد.

کارت‌ها:
  XAUUSD-M15 LONG  : nOpen=4 k=1.1 slope=0.05 win=(0.40,0.95) + r2(34)≤0.55 + dom>3
  EURUSD-M30 SHORT : nOpen=6 k=0.8 slope=0.18 win=(0.40,0.95) + r2(34)≤0.55
"""
import sys, os, json

sys.path.insert(0, '/home/user/webapp')
os.chdir('/home/user/webapp')

import numpy as np
import pandas as pd

from strategies.s345_brooks_reversal_day import reversal_day_signals, load_tf
from engine import indicator_bank as ib

CARDS = {
    'XAUUSD-M15': dict(
        asset='XAUUSD', tf='M15', side='long',
        n_open=4, k_spike=1.1, slope_min_frac=0.05,
        entry_from_frac=0.40, entry_to_frac=0.95,
        r2_max=0.55, drop_tom=True,
    ),
    'EURUSD-M30': dict(
        asset='EURUSD', tf='M30', side='short',
        n_open=6, k_spike=0.8, slope_min_frac=0.18,
        entry_from_frac=0.40, entry_to_frac=0.95,
        r2_max=0.55, drop_tom=False,
    ),
}


def export_card(card):
    p = CARDS[card]
    df = load_tf(p['asset'], p['tf'])

    geo = reversal_day_signals(
        df, p['tf'], p['side'],
        n_open=p['n_open'], k_spike=p['k_spike'],
        slope_min_frac=p['slope_min_frac'],
        entry_from_frac=p['entry_from_frac'],
        entry_to_frac=p['entry_to_frac'],
    )

    # رژیمِ r2_lo — verbatim منطبق با s345_scan._build_regime_cache
    r2v = ib.r2(df, p=34).to_numpy()
    reg = (r2v <= p['r2_max']) & np.isfinite(r2v)

    sig = geo & reg

    # فیلترِ بهبود: حذفِ Turn-of-Month (روزهای ۱..۳ ماه)
    if p['drop_tom']:
        dt = pd.DatetimeIndex(pd.to_datetime(df['time'], unit='s'))
        sig = sig & np.asarray(dt.day > 3, dtype=bool)

    idx = [int(i) for i in np.where(sig)[0]]
    rnd = 3 if p['asset'] == 'XAUUSD' else 6
    candles = [
        {'time': int(df['time'].iloc[i]),
         'open': round(float(df['open'].iloc[i]), rnd),
         'high': round(float(df['high'].iloc[i]), rnd),
         'low': round(float(df['low'].iloc[i]), rnd),
         'close': round(float(df['close'].iloc[i]), rnd),
         'volume': float(df['volume'].iloc[i]) if 'volume' in df.columns else 0.0}
        for i in range(len(df))
    ]
    out = {'card': card, 'params': p, 'n': len(df),
           'signal_idx': idx, 'candles': candles}
    fn = f'strategies/s345_parity_ref_{card.replace("-", "_")}.json'
    with open(fn, 'w') as f:
        json.dump(out, f)
    print(f'[{card}] exported n={len(df)} candles, {len(idx)} active-signal bars -> {fn}')
    print(f'[{card}] first 10 signal idx: {idx[:10]}')
    print(f'[{card}] last  5 signal idx: {idx[-5:]}')


if __name__ == '__main__':
    which = sys.argv[1] if len(sys.argv) > 1 else 'ALL'
    for c in (CARDS if which == 'ALL' else [which]):
        export_card(c)
