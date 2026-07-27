# -*- coding: utf-8 -*-
"""
S332 — اسکنِ سبک و هدفمند (کنترلِ بار: شبکهٔ کوچک، خروجِ تدریجی، ضدِ فریز)
================================================================================
درسِ نشستِ قبل: صدا زدنِ RQS+ کامل (walk-forward) روی شبکهٔ ۳۴۵۶-تایی سندباکس را
فریز کرد. اینجا یک شبکهٔ *کوچکِ هدفمند* (~۳۰–۵۰ ترکیب) می‌سازیم و برای هر ترکیب
RQS+ کامل را اجرا و بلافاصله چاپ می‌کنیم (تا اگر timeout شد، نتایجِ تا آن لحظه را
داشته باشیم). سیگنال یک‌بار ساخته می‌شود.

اجرا:  python3 strategies/s332_fastscan.py --sym XAUUSD --tf H4
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

# max_hold متناسبِ هر TF (تعدادِ کندل ≈ افقِ زمانیِ مشابه)
MAXHOLD = {'M5': 288, 'M15': 96, 'M30': 64, 'H1': 48, 'H4': 24}


def gates_str(r):
    return ''.join('1' if r['gates'][x] else '0' for x in ['G0', 'G1', 'G2', 'G3', 'G4', 'G5'])


def build_filters(df):
    """چند فیلترِ بهبود (بر پایهٔ اندیکاتورهای مختلف — ضدِ اشتباهِ #۳)."""
    c = df['close'].values.astype(float)
    adx_, pdi, mdi = S.adx(df, 14)
    r14 = S.rsi(c, 14)
    e50 = S.ema(c, 50)
    e100 = S.ema(c, 100)
    atr_ = S.atr(df, 14)
    atr_med = pd.Series(atr_).rolling(200, min_periods=50).median().values

    def clean(m):
        return np.nan_to_num(m.astype(float), nan=0.0).astype(bool)

    return {
        'none':            np.ones(len(df), dtype=bool),
        'adx>22':          clean(adx_ > 22),
        'adx>28':          clean(adx_ > 28),
        'pdi>mdi':         clean(pdi > mdi),
        'adx>22&pdi>mdi':  clean((adx_ > 22) & (pdi > mdi)),
        'adx>28&pdi>mdi':  clean((adx_ > 28) & (pdi > mdi)),
        'rsi50_78':        clean((r14 >= 50) & (r14 <= 78)),
        'adx>22&rsi50_78': clean((adx_ > 22) & (r14 >= 50) & (r14 <= 78)),
        'slope+&adx>22':   clean((e50 > e100) & (adx_ > 22)),
    }


def scan(sym, tf, sqz=0.25, brk=6):
    df = S.load_tf(sym, tf)
    if df is None:
        print(f"no data for {sym} {tf}")
        return
    mh = MAXHOLD[tf]
    sig = S.build_squeeze_signal(df, sqz_pct=sqz, breakout_lookback=brk)
    nsig = int(sig.sum())
    print(f"== {sym} {tf} | squeeze signals={nsig} | sqz={sqz} brk={brk} mh={mh} ==")
    if nsig < 40:
        print("  too few signals; skip")
        return
    filts = build_filters(df)

    # شبکهٔ هدفمند: TP/SL که در نشستِ قبل نزدیک بودند + BE ملایم.
    # اعدادِ غیررند (ضدِ اشتباهِ #۷).
    tpsl = [(300, 90), (300, 110), (250, 130), (400, 250), (500, 350),
            (350, 220), (280, 170), (220, 140), (170, 120)]
    be_opts = [None, 45, 70]
    filt_names = list(filts.keys())

    rows = []
    print(f"{'filt':16s} {'tp':>4s} {'sl':>4s} {'be':>4s} | {'WR':>5s} {'net':>8s} "
          f"{'PF':>5s} {'DD':>5s} {'MCL':>3s} {'n':>4s} | gates  RQS")
    tested = 0
    for fn in filt_names:
        fm = filts[fn]
        for (tp, sl) in tpsl:
            for be in be_opts:
                try:
                    r, tr = S.evaluate(df, sym, sig, sl_pip=sl, tp_pip=tp,
                                       max_hold=mh, be_trigger_pip=be, filt=fm)
                except Exception as e:
                    continue
                tested += 1
                m = r['metrics']
                if m.get('n_trades', 0) < 30:
                    continue
                g = gates_str(r)
                ng = g.count('1')
                rows.append((ng, m['net_profit'], fn, tp, sl, be, m['win_rate'],
                             m['profit_factor'], m['max_dd_pct'],
                             m['max_consec_losses'], m['n_trades'], g,
                             r['rqs_score'], r['passed']))
                if r['passed'] or ng >= 5:
                    print(f"{fn:16s} {tp:>4d} {sl:>4d} {str(be):>4s} | "
                          f"{m['win_rate']:>5.1f} {m['net_profit']:>8.0f} "
                          f"{m['profit_factor']:>5.2f} {m['max_dd_pct']:>5.1f} "
                          f"{m['max_consec_losses']:>3d} {m['n_trades']:>4d} | "
                          f"{g}  {r['rqs_score']:.1f}"
                          f"{'  <<<PASS' if r['passed'] else ''}")

    rows.sort(key=lambda x: (-int(x[13]), -x[0], -x[1]))
    print(f"\n-- tested={tested} | top 8 by pass/gates/net --")
    for b in rows[:8]:
        ng, net, fn, tp, sl, be, wr, pf, dd, mcl, n, g, rqsv, ok = b
        print(f"  {'PASS' if ok else '    '} ng={ng} RQS={rqsv:5.1f} net={net:>8.0f} "
              f"{fn:16s} tp={tp} sl={sl} be={be} WR={wr:.1f} PF={pf:.2f} "
              f"DD={dd:.1f} MCL={mcl} n={n} {g}")

    npass = sum(1 for r in rows if r[13])
    print(f"\n== {sym} {tf}: {npass} PASS out of {len(rows)} valid configs ==")
    return rows


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--sym', default='XAUUSD')
    ap.add_argument('--tf', default='H4')
    ap.add_argument('--sqz', type=float, default=0.25)
    ap.add_argument('--brk', type=int, default=6)
    a = ap.parse_args()
    scan(a.sym, a.tf, a.sqz, a.brk)
