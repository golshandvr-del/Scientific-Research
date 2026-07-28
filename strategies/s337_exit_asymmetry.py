# -*- coding: utf-8 -*-
"""
s337_exit_asymmetry.py — تزِ نهاییِ نشست: WR بالا از راهِ خروج، نه ورود
============================================================================
کشفِ S337_WR_Floor: هر ورودِ ساده با TP=SL روی XAU به WRِ ~۴۶٪ قفل است.
تز: اگر ورودِ ذاتاً ~۵۰٪ را با TPِ نزدیک + trailing/breakeven ترکیب کنیم، آنگاه:
  - اکثرِ معاملات به TPِ نزدیک می‌رسند → WR بالا (واقعی، نه تقلبِ #۹)،
  - بازنده‌ها با trailingِ ساختارمحور کوچک می‌شوند نه SLِ بزرگِ ثابت،
  - و شاید G1/RQS+ پاس شود.

این اسکریپت TPِ نزدیک را با be_trigger/trail مختلف روی نردبانِ TF می‌سنجد.
SL اسمی = 2.0×ATR (بزرگ، تا زود stop نخوریم)؛ trail بازنده را مدیریت می‌کند.
همه اندیکاتورها shift(1). بدون look-ahead.
"""
import numpy as np
import pandas as pd
from engine import scalp_engine as se, rqs
from engine import indicator_bank as ib

TF_BARS_PER_DAY = {'M5': 288, 'M15': 96, 'M30': 48, 'H1': 24, 'H4': 6}
TFS = ['M5', 'M15', 'M30', 'H1']


def load(asset, tf):
    return se.load_data(f'data/{asset}_{tf}.csv')


def atr_pips(df, asset, period=14):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    atr = pd.Series(tr).rolling(period).mean().values
    pip = 0.1 if 'XAU' in asset else 0.0001
    return atr / pip


def metrics(tr):
    if tr is None or len(tr) == 0:
        return 0, 0.0, 0.0
    wr = (tr['outcome'] == 'win').mean() * 100
    wins = tr.loc[tr.pnl_pip > 0, 'pnl_pip'].sum()
    loss = -tr.loc[tr.pnl_pip <= 0, 'pnl_pip'].sum()
    pf = wins / loss if loss > 0 else 9.99
    return len(tr), wr, pf


def build_signals(df, asset):
    """ورودِ خنثیِ روند-follow (چون ثابت شد جهت بی‌اثر است، ساده‌ترین را می‌گیریم)."""
    hurst = ib.compute('hurst', df).shift(1).values
    r2 = ib.compute('r2_fib_55', df).shift(1).values
    hma = ib.compute('hma_fib_34', df)
    slope = (hma - hma.shift(3)).shift(1).values
    up = (hurst > 0.5) & (r2 > 0.55) & (slope > 0)
    dn = (hurst > 0.5) & (r2 > 0.55) & (slope < 0)
    return (pd.Series(np.nan_to_num(up, nan=0).astype(bool)),
            pd.Series(np.nan_to_num(dn, nan=0).astype(bool)))


def scan(asset='XAUUSD'):
    print(f"\n=== EXIT-ASYMMETRY SCAN {asset} === TPِ نزدیک + trailing/BE روی نردبانِ TF")
    print("تز: WRِ واقعیِ بالا از راهِ خروجِ نامتقارن. SL اسمی=2.0×ATR (بزرگ). "
          "TP و trail بر حسبِ ATR.\n")
    print(f"{'TF':>4} {'TPx':>4} {'BEx':>4} {'TRx':>4} {'n':>6} {'/day':>6} "
          f"{'WR%':>6} {'PF':>6} {'RQS':>6} {'gate':>7}")
    print("-" * 66)

    best = None
    for tf in TFS:
        df = load(asset, tf)
        if len(df) < 500:
            continue
        days = len(df) / TF_BARS_PER_DAY[tf]
        long_sig, short_sig = build_signals(df, asset)
        atr_med = float(np.nanmedian(atr_pips(df, asset)))
        sl = atr_med * 2.0  # SL اسمیِ بزرگ

        # TPِ نزدیک (کسری از ATR) × ترکیب‌های BE/trail
        for tp_x in [0.5, 0.8, 1.1]:
            tp = atr_med * tp_x
            for be_x, tr_x in [(0.3, 0.5), (0.5, 0.8), (0.4, 0.6), (None, 0.5), (0.3, None)]:
                be = atr_med * be_x if be_x else None
                trl = atr_med * tr_x if tr_x else None
                tr = se.simulate_trades(df, long_sig, short_sig, sl, tp, asset,
                                        24, False, be_trigger_pip=be, trail_pip=trl)
                if tr is None or len(tr) < 30:
                    continue
                tr = tr.copy(); tr['tp_pip'] = float(tp)
                n, wr, pf = metrics(tr)
                res = rqs.compute_rqs(tr, asset, sl, tp)
                rq = res.get('rqs_plus', res.get('rqs', 0)) if isinstance(res, dict) else 0
                g = res.get('gates', {}) if isinstance(res, dict) else {}
                gate = ''.join('1' if g.get(k) else '0' for k in sorted(g)) if g else '------'
                # فقط ردیف‌های جالب را چاپ کن (WR>=55 یا RQS>0)
                if wr >= 55 or rq > 0:
                    print(f"{tf:>4} {tp_x:>4.1f} {str(be_x):>4} {str(tr_x):>4} {n:>6} "
                          f"{n/days:>6.2f} {wr:>6.1f} {pf:>6.2f} {rq:>6.1f} {gate:>7}")
                if best is None or rq > best[0]:
                    best = (rq, tf, tp_x, be_x, tr_x, n, wr, pf, gate)

    print("\n--- بهترین RQS+ یافت‌شده ---")
    if best:
        rq, tf, tpx, bex, trx, n, wr, pf, gate = best
        print(f"TF={tf} TPx={tpx} BEx={bex} TRx={trx} n={n} WR={wr:.1f}% PF={pf:.2f} "
              f"RQS+={rq:.1f} gates={gate}")


if __name__ == '__main__':
    import sys
    scan(sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD')
