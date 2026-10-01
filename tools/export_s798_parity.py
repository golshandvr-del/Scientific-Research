# -*- coding: utf-8 -*-
"""S798 — مرجعِ عددیِ پریتی برای پورتِ TS (web_tool/src/london_shock_s798.ts)

ماشینِ منجمدِ حکم (strategies/s798_final.py) را روی کلِ دادهٔ H8ِ mt5_full
اجرا می‌کند و برای هر سیگنال زمان، جهت و ATR[i−1]/SL (دلار) را می‌نویسد.
کنترلِ سلامت: باید ۷۹ سیگنال / ۷۹ معامله / WR 74.68 را بازتولید کند.
خروجی: results/_s798_parity/XAUUSD_H8.json
"""
import os, sys, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np, pandas as pd
from tools import s434_fast_data as fd
from engine import scalp_engine as se
import strategies.s798_final as S


def main():
    d = fd.load_fast('XAUUSD', 'H8'); df = fd.as_dataframe(d)
    assert 'mt5_full' in d['src']
    t = df['time'].values.astype(np.int64)
    o, h, l, c = [df[k].values for k in ('open', 'high', 'low', 'close')]
    hr = pd.to_datetime(df['time'], unit='s').dt.hour.values
    atr = S.atr21(h, l, c); valid = ~np.isnan(atr)
    sig = valid & (hr == S.HOUR) & (h - l >= S.THETA * atr) & (c != o)
    dirn = np.sign(c - o)
    ls = sig & (dirn > 0); ss = sig & (dirn < 0)
    sl = np.where(valid, S.KSL * atr / S.PIP, 0.0)
    tr = se.simulate_trades(df, ls, ss, sl, sl * S.RR, 'XAUUSD', max_hold=S.MH, allow_overlap=False)
    wr = round(100 * float((tr['pnl_pip'] > 0).mean()), 2)
    assert int(sig.sum()) == 79 and len(tr) == 79 and wr == 74.68, (int(sig.sum()), len(tr), wr)
    idx = np.where(sig)[0]
    tail = list(range(len(c) - 400, len(c)))
    out = dict(
        layer='S798', card='XAUUSD-H8', src=d['src'], bars=int(len(c)),
        health=dict(signals=int(sig.sum()), trades=int(len(tr)), wr=wr),
        rule=dict(hour_utc=S.HOUR, theta=S.THETA, ksl=S.KSL, rr=S.RR, mh=S.MH),
        signal_times=[int(t[i]) for i in idx],
        signal_dirs=[int(dirn[i]) for i in idx],
        signal_atr_prev=[float(atr[i]) for i in idx],
        signal_sl_usd=[float(S.KSL * atr[i]) for i in idx],
        trade_entry_times=[int(t[int(e)]) for e in tr['entry_bar'].values],
        bars_held_max=int(tr['bars_held'].max()),
        tail_times=[int(t[i]) for i in tail],
        tail_atr_prev=[float(atr[i]) for i in tail],
        shock_any_hour=int((valid & (h - l >= S.THETA * atr) & (c != o)).sum()),
    )
    od = os.path.join(ROOT, 'results', '_s798_parity'); os.makedirs(od, exist_ok=True)
    p = os.path.join(od, 'XAUUSD_H8.json')
    json.dump(out, open(p, 'w'), indent=1)
    print('[ok]', out['health'], 'shock_any_hour', out['shock_any_hour'], 'bars_held_max', out['bars_held_max'], '->', p)


if __name__ == '__main__':
    main()
