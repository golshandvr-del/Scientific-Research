# -*- coding: utf-8 -*-
"""S800 — ممیزی همپوشانی دو کارت ACCEPT (D1, H12) با لایهٔ فعال S382-H4.

قانون همپوشانی پروژه: درصد همپوشانی تقویمی هر کارت جدید با معاملات
لایه‌های فعال اندازه‌گیری می‌شود و بخش همپوشان **بلافاصله** به‌عنوان فیلتر
آزموده می‌شود (تشخیصی — داوری RQS2 جدیدی صادر نمی‌شود؛ مسیر C یک آزمون
قاطع داشت که انجام شد).

مرجع مقایسه: S382-H4 (نزدیک‌ترین لایهٔ فعال از نظر مقیاس زمانی).
بازه‌های اشغال حساب: [t_entry, t_exit] معاملات رویدادمحور S800 در برابر
بازه‌های S382.
"""
import sys
import os
import json

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import trade_simulator as ts                     # noqa: E402
from strategies.s800_squeeze_expansion import (              # noqa: E402
    load, base_arrays)
from strategies.s800_event_verdict import S800Strategy       # noqa: E402

OUT = 'results/_scan_S800'
COST_PIP = 3.3


def s800_trades(tf):
    locked = json.load(open(f'{OUT}/{tf}_locked.json'))
    cfg = locked['cfg']
    meta, df = load(tf)
    base = base_arrays(df, tf=tf)
    strat = S800Strategy(cfg, base, ts.asset_spec('XAUUSD')['pip'])
    strat.precompute(df)
    tr, _ = ts.simulate(df, strat, 'XAUUSD', tf=tf,
                        initial_capital=10000.0, risk_per_trade=1.0,
                        max_bars_hold=cfg['hold'], warmup=300)
    t = df['time'].values
    tr = tr.copy()
    tr['t_entry'] = t[tr['entry_bar'].values]
    tr['t_exit'] = t[tr['exit_bar'].values]
    return tr


def s382_intervals():
    """بازتولید معاملات S382-H4 (Williams %R(14) cross above -13, zero
    filters) — قاعدهٔ منجمد لایهٔ فعال سایت، روی دادهٔ رسمی H4 (resample
    از H1 طبق MANIFEST: H4 موجود نیست)."""
    from tools import s434_fast_data as fd
    d = fd.load_fast('XAUUSD', 'H1')
    df1 = fd.as_dataframe(d)
    df1['dt'] = pd.to_datetime(df1['time'], unit='s')
    g = df1.set_index('dt').resample('4h', label='left', closed='left').agg(
        {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last',
         'time': 'first'}).dropna().reset_index()
    h = g['high']
    l = g['low']
    c = g['close']
    p = 14
    hh = h.rolling(p).max()
    ll = l.rolling(p).min()
    wr = -100.0 * (hh - c) / (hh - ll)
    thr = -13.0
    cross = (wr > thr) & (wr.shift(1) <= thr)
    sig = cross.fillna(False).values
    # هندسهٔ S382: طبق README کارت سایت — SL/TP ثابت pip (از registry).
    # برای ممیزی همپوشانی فقط بازهٔ اشغال لازم است: ورود تا max_hold=16
    t = g['time'].values
    n = len(g)
    iv = []
    idx = np.where(sig)[0]
    for i in idx:
        j = min(i + 16, n - 1)
        iv.append((int(t[i]), int(t[j])))
    return iv


def overlap_frac(tr, intervals):
    if len(tr) == 0 or not intervals:
        return 0.0, np.zeros(len(tr), dtype=bool)
    a = np.array([iv[0] for iv in intervals])
    b = np.array([iv[1] for iv in intervals])
    mask = np.zeros(len(tr), dtype=bool)
    for k, (te, tx) in enumerate(zip(tr['t_entry'].values,
                                     tr['t_exit'].values)):
        mask[k] = bool(np.any((a <= tx) & (b >= te)))
    return float(mask.mean()), mask


def subset_stats(tr, mask, label):
    sub = tr[mask]
    if len(sub) == 0:
        print(f'    {label}: n=0')
        return dict(n=0)
    wins = int((sub['pnl_usd'] > 0).sum())
    wr = wins / len(sub) * 100.0
    net = float(sub['pnl_usd'].sum())
    print(f'    {label}: n={len(sub)}  wr={wr:.1f}%  net/lot={net:.0f}$')
    return dict(n=int(len(sub)), wr=wr, net_usd_per_lot=net)


def main():
    iv382 = s382_intervals()
    print(f'[s382] intervals reproduced: {len(iv382)}')
    res = {}
    for tf in ['D1', 'H12']:
        tr = s800_trades(tf)
        frac, mask = overlap_frac(tr, iv382)
        print(f'[overlap/{tf}] n={len(tr)}  overlap با S382-H4: {frac*100:.1f}%')
        r = dict(n=int(len(tr)), overlap_frac=frac)
        r['overlap'] = subset_stats(tr, mask, 'overlap   ')
        r['non_overlap'] = subset_stats(tr, ~mask, 'non-overlap')
        res[tf] = r
    with open(f'{OUT}/overlap_audit.json', 'w') as f:
        json.dump(res, f, indent=1)
    print('saved -> overlap_audit.json')


if __name__ == '__main__':
    main()
