# -*- coding: utf-8 -*-
"""
s336_diag_regime.py — آیا فیلترِ رژیم، edgeِ شورتِ mean-reversion را مثبت می‌کند؟
================================================================================
درسِ تشخیصِ قبلی: تریگرِ افراطِ صعودی به‌تنهایی WR~۴۷٪ و PF~۰.۸ (edge منفی) می‌دهد،
چون طلا trend-following است و overextension اغلب ادامه می‌یابد.

تز: mean-reversion فقط در رژیمِ *range/choppy* کار می‌کند. پس فیلترِ رژیمِ معکوسِ
trend می‌گذاریم: hurst پایین (ضدِ persistence)، chop بالا (بی‌روند)، r2 پایین.
تریگرِ پایه: fisher_turn>4 (بهترین PF در تشخیص قبلی).
"""
import numpy as np
from engine import scalp_engine as se
from engine import indicator_bank as ib
from strategies.s336_diag_triggers import build_triggers


def diag(asset='XAUUSD', tf='M5'):
    df = se.load_data(f'data/{asset}_{tf}.csv')
    n = len(df)
    trig = build_triggers(df)
    base = trig['fisher_turn>4']

    # ماسک‌های رژیم (shift(1) امن)
    def s(nm):
        return ib.compute(nm, df).shift(1)
    hurst = s('hurst').values
    chop = s('chop').values
    r2 = s('r2').values
    zc = s('zscore_fib_21').values

    print(f"=== REGIME DIAG {asset}/{tf} — trigger=fisher_turn>4 (raw n={int(base.sum())}) ===")
    print(f"{'regime filter':28s} {'n_tr':>6s} {'WR':>5s} {'PF':>5s} {'net$':>9s}")

    def evalmask(label, mask, tp=50, sl=40):
        sig = base & mask
        tr = se.simulate_trades(df, np.zeros(n, bool), sig, sl, tp, asset, 24, False)
        if len(tr) < 20:
            print(f"{label:28s} {len(tr):>6d}  (too few)")
            return
        wr = (tr['outcome'] == 'win').mean() * 100
        wins = tr.loc[tr.pnl_pip > 0, 'pnl_pip'].sum()
        loss = -tr.loc[tr.pnl_pip <= 0, 'pnl_pip'].sum()
        pf = wins / loss if loss > 0 else 9.99
        net = tr['pnl_pip'].sum() * 0.10 * 100  # pip->$ per 1 lot (pip_value=10 => *10? keep pip*contract)
        print(f"{label:28s} {len(tr):>6d} {wr:>5.1f} {pf:>5.2f} {tr['pnl_pip'].sum():>9.0f}pip")

    T = np.ones(n, bool)
    evalmask('no filter (baseline)', T)
    # رژیمِ range: hurst پایین
    for h in [0.50, 0.45, 0.40]:
        evalmask(f'hurst<{h}', hurst < h)
    # chop بالا = بی‌روند
    for c in [55, 61.8, 68]:
        evalmask(f'chop>{c}', chop > c)
    # r2 پایین = بدونِ روندِ خطی
    for rr in [0.30, 0.20, 0.10]:
        evalmask(f'r2<{rr}', r2 < rr)
    # ترکیب: range واقعی
    evalmask('hurst<.45 & chop>55', (hurst < 0.45) & (chop > 55))
    evalmask('hurst<.45 & r2<.2', (hurst < 0.45) & (r2 < 0.2))
    evalmask('chop>55 & r2<.2', (chop > 55) & (r2 < 0.2))
    evalmask('hurst<.45 & chop>55 & r2<.2', (hurst < 0.45) & (chop > 55) & (r2 < 0.2))
    # + افراطِ قوی‌تر
    evalmask('range & zscore>2.0', (hurst < 0.45) & (chop > 55) & (zc > 2.0))


if __name__ == '__main__':
    diag('XAUUSD', 'M5')
