# -*- coding: utf-8 -*-
"""
s344_parity_export.py — مرجعِ برابریِ TS↔Python برای S344 (XAUUSD-M15 SHORT).
خروجی: strategies/s344_parity_ref.json = کندل‌های خامِ M15 + اندیس‌های سیگنالِ active پایتون
(هر کندلی که trend_from_open_signals روی آن True است، با پارامترهای پذیرفته‌شدهٔ کارت).
harnessِ Node همان کندل‌ها را به computeS344 می‌دهد (به‌صورتِ rolling) و باید دقیقاً همان
اندیس‌ها را active=true بدهد.
"""
import sys, os, json
sys.path.insert(0, '/home/user/webapp')
os.chdir('/home/user/webapp')
import numpy as np
from strategies.s344_brooks_trend_from_open import trend_from_open_signals, load_tf

# پارامترهای پذیرفته‌شدهٔ کارت XAUUSD-M15 (از اسکن: reg=r2h جدا اعمال می‌شود در سایت،
# اما سیگنالِ هندسیِ خام همینجاست؛ فیلترِ رژیم در TS داخلِ computeS344 چک می‌شود، پس
# برای parityِ «سیگنالِ هندسی» فیلتر رژیم را جدا نگه می‌داریم و در harness هم‌سنگ می‌کنیم).
CARD = 'XAUUSD-M15'
PARAMS = dict(side='short', n_open=4, f_range=0.20, pull_max=0.62,
              adr_lb=14, min_spike_frac=0.20)


def export_card(card):
    asset, tf = card.split('-')
    df = load_tf(asset, tf)
    sig = trend_from_open_signals(df, tf, **PARAMS)
    idx = [int(i) for i in np.where(sig)[0]]
    candles = [
        {'time': int(df['time'].iloc[i]),
         'open': round(float(df['open'].iloc[i]), 3),
         'high': round(float(df['high'].iloc[i]), 3),
         'low':  round(float(df['low'].iloc[i]), 3),
         'close': round(float(df['close'].iloc[i]), 3),
         'volume': float(df['volume'].iloc[i]) if 'volume' in df.columns else 0.0}
        for i in range(len(df))
    ]
    out = {'card': card, 'params': PARAMS,
           'n': len(df), 'signal_idx': idx, 'candles': candles}
    fn = 'strategies/s344_parity_ref.json'
    with open(fn, 'w') as f:
        json.dump(out, f)
    print(f'[{card}] exported n={len(df)} candles, {len(idx)} active-signal bars -> {fn}')
    print(f'[{card}] first 10 signal idx:', idx[:10])
    print(f'[{card}] last  5 signal idx:', idx[-5:])


if __name__ == '__main__':
    export_card(CARD)
