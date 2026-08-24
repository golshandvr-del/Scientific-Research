# -*- coding: utf-8 -*-
"""
S800 — تأیید رویدادمحور + سنجش همپوشانی با لایه‌های ACCEPT موجود
================================================================================
الزام راهنما: حکم نهایی و اندازه‌گیری همپوشانی باید با شبیه‌ساز رویدادمحور
(`engine/trade_simulator.py` — یک حساب، یک پوزیشن باز) انجام شود.

دو کارت ACCEPTشده در داوری برداری:
  D1 : p=55, q=20, filter=none, k=1.272, rr=1.0,   hold=21
  H12: p=21, q=30, filter=none, k=2.058, rr=1.618, hold=34

همپوشانی: نسبت کندل‌های ورود مشترک با کارت‌های هم‌TF موجود سایت (S382-H4،
S312-M30، S356-H1 و ...) — چون هیچ لایهٔ فعالی روی D1/H12 نیست، همپوشانی
زمانی رویدادی با ورودهای همان روز/نیم‌روز لایه‌های دیگر گزارش می‌شود.
"""
import sys
import os
import json

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import trade_simulator as ts                 # noqa: E402
from strategies.s800_squeeze_expansion import (          # noqa: E402
    load, base_arrays, donch_signals)

OUT = 'results/_scan_S800'


class S800Strategy:
    """پیاده‌سازی advise(ctx) — همان منطق برداری، سببی."""

    def __init__(self, cfg, base, pip):
        self.cfg = cfg
        self.base = base
        self.pip = pip
        self.hh = None
        self.ll = None

    def precompute(self, df):
        p = self.cfg['p']
        h = pd.Series(df['high'].values)
        l = pd.Series(df['low'].values)
        self.hh = h.rolling(p).max().shift(1).values
        self.ll = l.rolling(p).min().shift(1).values

    def advise(self, ctx):
        i = ctx.i
        if ctx.in_position():
            return None
        cfg = self.cfg
        b = self.base
        if not np.isfinite(self.hh[i]) or not np.isfinite(b['sqz'][i]):
            return None
        if not (b['sqz'][i] < cfg['q']):
            return None
        slp = b['sl_pip'][i]
        if not np.isfinite(slp) or slp <= 0:
            return None
        c = ctx.price()
        sl_d = slp * cfg['k'] * self.pip
        tp_d = sl_d * cfg['rr']
        if c > self.hh[i]:
            return dict(action='LONG', sl=c - sl_d, tp=c + tp_d)
        if c < self.ll[i]:
            return dict(action='SHORT', sl=c + sl_d, tp=c - tp_d)
        return None


def run_event(tf, cfg):
    meta, df = load(tf)
    base = base_arrays(df, tf=tf)
    strat = S800Strategy(cfg, base, ts.asset_spec('XAUUSD')['pip'])
    strat.precompute(df)
    trades, eq = ts.simulate(df, strat, 'XAUUSD', tf=tf,
                             initial_capital=10000.0, risk_per_trade=1.0,
                             max_bars_hold=cfg['hold'], warmup=300)
    n = len(trades)
    if n == 0:
        return None, None, df
    wins = int((trades['pnl_usd'] > 0).sum())
    eqf = float(eq[-1]) if hasattr(eq, '__len__') else float(eq)
    return trades, dict(n=n, wins=wins, wr=wins / n * 100.0,
                        final_equity=eqf,
                        ret_pct=(eqf / 10000.0 - 1) * 100.0), df


def main():
    res = {}
    for tf in ['D1', 'H12']:
        locked = json.load(open(f'{OUT}/{tf}_locked.json'))
        cfg = locked['cfg']
        trades, s, df = run_event(tf, cfg)
        if s is None:
            print(f'[event/{tf}] هیچ معامله‌ای — ناسازگاری!', flush=True)
            continue
        vec = json.load(open(f'{OUT}/{tf}_judge.json'))
        dwr = s['wr'] - vec['wr']
        print(f"[event/{tf}] n={s['n']} (برداری {vec['n']})  "
              f"wr={s['wr']:.1f}% (برداری {vec['wr']:.1f}%)  Δwr={dwr:+.1f}pp  "
              f"equity={s['final_equity']:.0f}$  ret={s['ret_pct']:+.1f}%",
              flush=True)
        # ورودهای رویدادی برای سنجش همپوشانی
        cols = [c for c in trades.columns]
        entry_bars = trades['entry_bar'].values if 'entry_bar' in cols else None
        entry_times = (df['time'].values[entry_bars]
                       if entry_bars is not None else None)
        res[tf] = dict(cfg=cfg, event=s, vec_n=vec['n'], vec_wr=vec['wr'],
                       delta_wr=dwr, columns=cols,
                       entry_times=[int(t) for t in entry_times]
                       if entry_times is not None else None)
    with open(f'{OUT}/event_verdict.json', 'w') as f:
        json.dump(res, f, indent=1, default=str)
    print('saved -> event_verdict.json', flush=True)


if __name__ == '__main__':
    main()
