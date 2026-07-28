# -*- coding: utf-8 -*-
"""
s336_diag_triggers.py — تشخیصِ نرخِ سیگنال و WRِ خامِ هر تریگرِ شورت
====================================================================
برای هر تریگرِ کاندیدا: تعداد سیگنال + WR خام با TP/SL کوچیکِ اسکالپ.
هدف: پیدا کردنِ تریگری که n بالا (پُرمعامله) و edge مثبت دارد.
واحد: pip طلا = 0.10$ ⇒ TP 40pip = 4$، SL 30pip = 3$.
"""
import numpy as np
from engine import scalp_engine as se
from engine import indicator_bank as ib


def build_triggers(df):
    """مجموعه‌ای از تریگرهای شورتِ mean-reversion (افراطِ صعودی ⇒ انتظارِ پولبک)."""
    n = len(df)
    trig = {}
    fisher = ib.compute('fisher', df).values
    crsi = ib.compute('crsi', df).values
    kdj = ib.compute('kdj_j', df).values
    z = ib.compute('zscore_fib_21', df).values
    ifish = ib.compute('ifish_rsi', df).values
    lag = ib.compute('laguerre_rsi', df).values

    def cross_down(arr, thr):
        out = np.zeros(n, bool)
        for i in range(1, n):
            if arr[i-1] >= thr and arr[i] < thr:
                out[i] = True
        return out

    # کراسِ نزولیِ fisher از قله (چرخش زودهنگام)
    fisher_turn = np.zeros(n, bool)
    for i in range(2, n):
        if fisher[i-1] > fisher[i] and fisher[i-2] < fisher[i-1] and fisher[i-1] > 4.0:
            fisher_turn[i] = True
    trig['fisher_turn>4'] = fisher_turn
    trig['crsi_cross_dn82'] = cross_down(crsi, 82.0)
    trig['crsi_cross_dn90'] = cross_down(crsi, 90.0)
    trig['kdj_cross_dn98'] = cross_down(kdj, 98.0)
    trig['zscore>1.76'] = (z > 1.76)
    trig['ifish_cross_dn0.9'] = cross_down(ifish, 0.9)
    trig['lag_cross_dn80'] = cross_down(lag, 80.0)
    return trig


def diag(asset='XAUUSD', tf='M5'):
    df = se.load_data(f'data/{asset}_{tf}.csv')
    n = len(df)
    trig = build_triggers(df)
    print(f"=== DIAG {asset}/{tf} n={n} === (raw triggers, no regime filter)")
    print(f"{'trigger':20s} {'n_sig':>6s}  {'TP/SL':>10s}  {'n_tr':>5s} {'WR':>5s} {'PF':>5s} {'DD':>5s}")
    # چند TP/Sلِ کوچیکِ اسکالپ (pip). آگاهانه TP>=SL تا از تلهٔ WR (اشتباه ۹) دور بمانیم
    for tp, sl in [(40, 40), (50, 40), (60, 45), (30, 30)]:
        for name, sig in trig.items():
            nsig = int(sig.sum())
            tr = se.simulate_trades(df, np.zeros(n, bool), sig, sl, tp, asset, 24, False)
            if len(tr) == 0:
                continue
            wr = (tr['outcome'] == 'win').mean() * 100
            gross = tr['pnl_pip'].sum()
            wins = tr.loc[tr.pnl_pip > 0, 'pnl_pip'].sum()
            loss = -tr.loc[tr.pnl_pip <= 0, 'pnl_pip'].sum()
            pf = wins / loss if loss > 0 else 9.99
            print(f"{name:20s} {nsig:>6d}  TP{tp:>3d}/SL{sl:<3d}  {len(tr):>5d} "
                  f"{wr:>5.1f} {pf:>5.2f}")
        print()


if __name__ == '__main__':
    diag('XAUUSD', 'M5')
