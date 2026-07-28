# -*- coding: utf-8 -*-
"""
s336_diag_direction.py — کدام جهت روی XAU/M5 edge دارد؟ (سوالِ بنیادین)
======================================================================
درسِ اسکنِ کلِ بانک: تریگرِ افراطِ صعودی برای SHORT، با هیچ فیلتری PF>1 با n بالا
نمی‌دهد. پس فرضِ بنیادین را می‌آزماییم: آیا mean-reversion اصلاً روی M5 کار می‌کند؟
آیا momentum/continuation بهتر است؟ هر دو جهت و هر دو منطق را کنار هم می‌گذاریم.

منطق‌ها:
  MR-short : افراطِ صعودی (crsi بالا) ⇒ شورت  [انتظارِ بازگشت]
  MR-long  : افراطِ نزولی (crsi پایین) ⇒ لانگ  [انتظارِ بازگشت]
  MO-short : شکستِ نزولی (close < پایین‌ترین N) ⇒ شورت  [انتظارِ ادامه]
  MO-long  : شکستِ صعودی (close > بالاترین N) ⇒ لانگ  [انتظارِ ادامه]
"""
import numpy as np
from engine import scalp_engine as se
from engine import indicator_bank as ib


def run(asset='XAUUSD', tf='M5'):
    df = se.load_data(f'data/{asset}_{tf}.csv')
    n = len(df)
    close = df['close'].values
    crsi = ib.compute('crsi', df).values

    # breakout channels (Donchian-style) با دوره‌های غیررند
    def rolling_max(arr, w):
        s = np.full(len(arr), np.nan)
        for i in range(w, len(arr)):
            s[i] = arr[i-w:i].max()
        return s

    def rolling_min(arr, w):
        s = np.full(len(arr), np.nan)
        for i in range(w, len(arr)):
            s[i] = arr[i-w:i].min()
        return s

    W = 21
    hh = rolling_max(close, W)
    ll = rolling_min(close, W)

    logics = {}
    logics['MR-short(crsi>82)'] = (np.r_[False, (crsi[:-1] >= 82) & (crsi[1:] < 82)], 'short')
    logics['MR-long(crsi<18)'] = (np.r_[False, (crsi[:-1] <= 18) & (crsi[1:] > 18)], 'long')
    logics['MO-short(brk<ll21)'] = ((close < ll), 'short')
    logics['MO-long(brk>hh21)'] = ((close > hh), 'long')

    print(f"=== DIRECTION DIAG {asset}/{tf} n={n} ===")
    print(f"{'logic':22s} {'dir':>5s} {'TP/SL':>9s} {'n_tr':>6s} {'WR':>5s} {'PF':>5s} {'net(pip)':>9s}")
    for tp, sl in [(50, 40), (40, 50), (60, 45), (45, 60)]:
        for name, (sigmask, direction) in logics.items():
            sig = np.asarray(sigmask, bool)
            if direction == 'short':
                tr = se.simulate_trades(df, np.zeros(n, bool), sig, sl, tp, asset, 24, False)
            else:
                tr = se.simulate_trades(df, sig, np.zeros(n, bool), sl, tp, asset, 24, False)
            if len(tr) < 50:
                continue
            wr = (tr['outcome'] == 'win').mean() * 100
            wins = tr.loc[tr.pnl_pip > 0, 'pnl_pip'].sum()
            loss = -tr.loc[tr.pnl_pip <= 0, 'pnl_pip'].sum()
            pf = wins / loss if loss > 0 else 9.99
            flag = '  <== PF>1' if pf > 1.0 else ''
            print(f"{name:22s} {direction:>5s} TP{tp}/SL{sl:<3d} {len(tr):>6d} "
                  f"{wr:>5.1f} {pf:>5.2f} {tr['pnl_pip'].sum():>9.0f}{flag}")
        print()


if __name__ == '__main__':
    run('XAUUSD', 'M5')
