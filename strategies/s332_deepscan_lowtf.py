# -*- coding: utf-8 -*-
"""
S332 — اسکنِ عمیقِ TFهای پایین (H1/M30/M15/M5) — قانونِ بی‌نهایتِ بهبود + شناوری
================================================================================
یافتهٔ H4: فیلترِ ADX>22 & +DI>−DI کلید بود، اما در TFهای پایین WR به ۶۰ نمی‌رسد.
اینجا دو سلاحِ جدید (که در H4 لازم نشد):

  ۱) فیلترهای *سخت‌گیرانه‌ترِ چندگانه* (قانونِ بی‌نهایت): ADX قوی‌تر + شیبِ EMA +
     موقعیت نسبت به EMA + سقفِ RSI (اجتناب از خریدِ اشباع) + کفِ فاصله از باند.
  ۲) TP/SL *شناورِ ATR* (قانونِ شناوری — «هیچ چیز ثابت نیست»): به‌جای pipِ ثابت،
     SL=k_sl·ATR و TP=k_tp·ATR بر حسبِ نوسانِ همان کندل. این خودکار با رژیمِ
     نوسانیِ هر TF تطبیق می‌یابد.

خروجی تدریجی + شبکهٔ کوچک (ضدِ فریز).
اجرا:  python3 strategies/s332_deepscan_lowtf.py --sym XAUUSD --tf H1
"""
import os
import sys
import argparse
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import strategies.s332_squeeze_rqs_revival as S

MAXHOLD = {'M5': 288, 'M15': 96, 'M30': 64, 'H1': 48, 'H4': 24}


def gates_str(r):
    return ''.join('1' if r['gates'][x] else '0' for x in ['G0', 'G1', 'G2', 'G3', 'G4', 'G5'])


def scan(sym, tf, sqz=0.25, brk=6):
    df = S.load_tf(sym, tf)
    if df is None:
        print(f"no data {sym} {tf}"); return
    mh = MAXHOLD[tf]
    c = df['close'].values.astype(float)
    sig = S.build_squeeze_signal(df, sqz_pct=sqz, breakout_lookback=brk)
    nsig = int(sig.sum())
    print(f"== {sym} {tf} | signals={nsig} sqz={sqz} brk={brk} mh={mh} ==")

    # اندیکاتورها
    adx_, pdi, mdi = S.adx(df, 14)
    r14 = S.rsi(c, 14)
    e20 = S.ema(c, 20); e50 = S.ema(c, 50); e100 = S.ema(c, 100)
    atr_ = S.atr(df, 14)

    def clean(m):
        return np.nan_to_num(m.astype(float), nan=0.0).astype(bool)

    # فیلترهای سخت‌گیرانهٔ چندگانه (قانونِ بی‌نهایت)
    strict = {
        'adx>25&pdi>mdi':          clean((adx_ > 25) & (pdi > mdi)),
        'adx>30&pdi>mdi':          clean((adx_ > 30) & (pdi > mdi)),
        'adx>25&pdi>mdi&rsi<72':   clean((adx_ > 25) & (pdi > mdi) & (r14 < 72)),
        'adx>25&pdi>mdi&e20>e50':  clean((adx_ > 25) & (pdi > mdi) & (e20 > e50)),
        'adx>30&pdi>mdi&rsi50_72': clean((adx_ > 30) & (pdi > mdi) & (r14 >= 50) & (r14 < 72)),
        'adx>28&pdi-mdi>8':        clean((adx_ > 28) & ((pdi - mdi) > 8)),
    }

    # هندسهٔ TP/SL: ترکیبی از pipِ ثابتِ بزرگ + شناورِ ATR
    fixed = [(500, 350), (600, 400), (450, 300), (550, 380)]
    atr_mult = [(4.0, 2.8), (5.0, 3.5), (3.5, 2.5), (6.0, 4.0)]  # (k_tp, k_sl)

    rows = []
    print(f"{'filt':26s} {'geom':>12s} | {'WR':>5s} {'net':>8s} {'PF':>5s} "
          f"{'DD':>5s} {'MCL':>3s} {'n':>4s} | gates  RQS")
    tested = 0
    for fn, fm in strict.items():
        # pip ثابت
        for (tp, sl) in fixed:
            try:
                r, tr = S.evaluate(df, sym, sig, sl_pip=sl, tp_pip=tp, max_hold=mh, filt=fm)
            except Exception:
                continue
            tested += 1
            m = r['metrics']
            if m.get('n_trades', 0) < 30:
                continue
            g = gates_str(r); ng = g.count('1')
            rows.append((r['passed'], ng, m['net_profit'], fn, f"{tp}/{sl}",
                         m['win_rate'], m['profit_factor'], m['max_dd_pct'],
                         m['max_consec_losses'], m['n_trades'], g, r['rqs_score']))
            if r['passed'] or ng >= 5:
                print(f"{fn:26s} {tp}/{sl:<7} | {m['win_rate']:>5.1f} {m['net_profit']:>8.0f} "
                      f"{m['profit_factor']:>5.2f} {m['max_dd_pct']:>5.1f} {m['max_consec_losses']:>3d} "
                      f"{m['n_trades']:>4d} | {g}  {r['rqs_score']:.1f}"
                      f"{'  <<<PASS' if r['passed'] else ''}")
        # شناورِ ATR
        for (ktp, ksl) in atr_mult:
            tp_vec = np.nan_to_num(ktp * atr_ / S.se.ASSETS[sym]['pip'], nan=0.0)
            sl_vec = np.nan_to_num(ksl * atr_ / S.se.ASSETS[sym]['pip'], nan=0.0)
            # جلوگیری از SL صفر
            sl_vec = np.where(sl_vec < 1, 1e9, sl_vec)  # سیگنال‌های بی‌ATR عملاً حذف
            try:
                r, tr = S.evaluate(df, sym, sig, sl_pip=sl_vec, tp_pip=tp_vec, max_hold=mh, filt=fm)
            except Exception:
                continue
            tested += 1
            m = r['metrics']
            if m.get('n_trades', 0) < 30:
                continue
            g = gates_str(r); ng = g.count('1')
            rows.append((r['passed'], ng, m['net_profit'], fn, f"ATR{ktp}/{ksl}",
                         m['win_rate'], m['profit_factor'], m['max_dd_pct'],
                         m['max_consec_losses'], m['n_trades'], g, r['rqs_score']))
            if r['passed'] or ng >= 5:
                print(f"{fn:26s} {'ATR'+str(ktp)+'/'+str(ksl):>12s} | {m['win_rate']:>5.1f} "
                      f"{m['net_profit']:>8.0f} {m['profit_factor']:>5.2f} {m['max_dd_pct']:>5.1f} "
                      f"{m['max_consec_losses']:>3d} {m['n_trades']:>4d} | {g}  {r['rqs_score']:.1f}"
                      f"{'  <<<PASS' if r['passed'] else ''}")

    rows.sort(key=lambda x: (-int(x[0]), -x[1], -x[2]))
    print(f"\n-- tested={tested} | top 8 --")
    for b in rows[:8]:
        ok, ng, net, fn, geom, wr, pf, dd, mcl, n, g, rqsv = b
        print(f"  {'PASS' if ok else '    '} ng={ng} RQS={rqsv:5.1f} net={net:>8.0f} "
              f"{fn:26s} {geom:>12s} WR={wr:.1f} PF={pf:.2f} DD={dd:.1f} MCL={mcl} n={n} {g}")
    npass = sum(1 for r in rows if r[0])
    print(f"\n== {sym} {tf}: {npass} PASS / {len(rows)} valid ==")
    return rows


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--sym', default='XAUUSD')
    ap.add_argument('--tf', default='H1')
    ap.add_argument('--sqz', type=float, default=0.25)
    ap.add_argument('--brk', type=int, default=6)
    a = ap.parse_args()
    scan(a.sym, a.tf, a.sqz, a.brk)
