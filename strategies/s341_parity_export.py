# -*- coding: utf-8 -*-
"""
s341_parity_export.py — مرجعِ برابریِ TS↔Python برای S341-H1.
خروجی: strategies/s341_parity_ref.json = کندل‌های خامِ H1 + اندیس‌های سیگنالِ active پایتون
(هر کندلی که swing_fade_confluence_signals روی آن True است).
harnessِ Node همان کندل‌ها را به computeS341 می‌دهد (به‌صورتِ rolling) و باید دقیقاً همان
اندیس‌ها را active=true بدهد.
"""
import sys, os, json
sys.path.insert(0, '/home/user/webapp')
os.chdir('/home/user/webapp')
import numpy as np
from strategies.s341_brooks_swing_levels import load_tf
from strategies.s341_swing_fade_h1_revived import CONFIG, swing_fade_confluence_signals

def export_card(card):
    asset, tf = card.split('-')
    cfg = CONFIG[card]
    df = load_tf(asset, tf)
    sig = swing_fade_confluence_signals(df, cfg)
    idx = [int(i) for i in np.where(sig)[0]]
    candles = [
        {'time': int(df['time'].iloc[i]) if 'time' in df.columns else i,
         'open': round(float(df['open'].iloc[i]), 5),
         'high': round(float(df['high'].iloc[i]), 5),
         'low':  round(float(df['low'].iloc[i]), 5),
         'close': round(float(df['close'].iloc[i]), 5),
         'volume': float(df['volume'].iloc[i]) if 'volume' in df.columns else 0.0}
        for i in range(len(df))
    ]
    out = {'card': card,
           'cfg': {k: cfg[k] for k in cfg if isinstance(cfg[k], (int, float, str, bool))},
           'n': len(df), 'signal_idx': idx, 'candles': candles}
    # نامِ فایل: H1 → همان s341_parity_ref.json (سازگاریِ عقب‌رو)؛ بقیه → per-card
    fn = 'strategies/s341_parity_ref.json' if card == 'XAUUSD-H1' \
         else f'strategies/s341_parity_ref_{card}.json'
    with open(fn, 'w') as f:
        json.dump(out, f)
    print(f'[{card}] exported n={len(df)} candles, {len(idx)} active-signal bars -> {fn}')
    print(f'[{card}] first 10 signal idx:', idx[:10])

def main():
    cards = sys.argv[1:] or ['XAUUSD-M5', 'XAUUSD-M15', 'XAUUSD-M30', 'XAUUSD-H1']
    for card in cards:
        export_card(card)

if __name__ == '__main__':
    main()
