# -*- coding: utf-8 -*-
"""
S332 — کاوشِ متمرکزِ XAUUSD روی TFهای دادهٔ بزرگ (M15/M5)
================================================================================
چرا این فایل جداست: M15/M5 روی XAUUSD ۱۵۰٬۰۰۰ کندل دارند و اسکنِ شبکهٔ بزرگ
سندباکس را فریز می‌کند. اینجا فقط چند ترکیبِ **هدفمند** (برگرفته از موفقیتِ H4)
آزموده می‌شود و خروجی مرحله‌به‌مرحله در یک فایلِ log نوشته می‌شود تا حتی اگر
فرایند قطع شد، نتایجِ به‌دست‌آمده از دست نرود (ضدِ فریز + ضدِ ازدست‌رفتنِ کار).

ترکیب‌های هدفمند (منطق):
  - فیلترِ برندهٔ H4: ADX>22 & +DI>−DI  (رژیمِ روندِ صعودیِ واقعی)
  - نسخهٔ سخت‌گیرانه‌تر برای TF پایین‌تر و نویزی‌تر: ADX>25/28 & (+DI−−DI)>8
  - TP/SL بزرگ (اجازهٔ دویدنِ روند) — همان فلسفهٔ H4
اجرا:
  python3 strategies/s332_m15_probe.py --tf M15
  python3 strategies/s332_m15_probe.py --tf M5
"""
import sys, os, argparse, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import strategies.s332_squeeze_rqs_revival as S


def gates_str(r):
    return ''.join('1' if r['gates'][x] else '0' for x in ['G0', 'G1', 'G2', 'G3', 'G4', 'G5'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tf', default='M15')
    ap.add_argument('--sqz', type=float, default=0.25)
    ap.add_argument('--brk', type=int, default=6)
    a = ap.parse_args()

    sym = 'XAUUSD'
    logpath = f"results/_s332_{sym}_{a.tf}_probe.log"
    def log(msg):
        print(msg, flush=True)
        with open(logpath, 'a') as f:
            f.write(msg + "\n")

    open(logpath, 'w').close()  # reset
    t0 = time.time()
    df = S.load_tf(sym, a.tf)
    if df is None or len(df) == 0:
        log(f"NO DATA {sym} {a.tf}")
        return
    mh = {'M5': 96, 'M15': 96, 'M30': 64, 'H1': 48, 'H4': 24}[a.tf]
    sig = S.build_squeeze_signal(df, sqz_pct=a.sqz, breakout_lookback=a.brk)
    n_sig = int(np.nansum(sig))
    log(f"== {sym} {a.tf} | candles={len(df)} squeeze signals={n_sig} mh={mh} sqz={a.sqz} brk={a.brk} ==")

    # اندیکاتورها یک‌بار
    adx_, pdi, mdi = S.adx(df, 14)
    c = df['close'].values.astype(float)
    r_ = S.rsi(c, 14)

    def mk(cond):
        return np.nan_to_num(cond.astype(float), nan=0.0).astype(bool)

    filters = {
        'adx>22&pdi>mdi':        mk((adx_ > 22) & (pdi > mdi)),
        'adx>25&pdi>mdi':        mk((adx_ > 25) & (pdi > mdi)),
        'adx>28&(pdi-mdi)>8':    mk((adx_ > 28) & ((pdi - mdi) > 8)),
        'adx>25&pdi>mdi&rsi50_80': mk((adx_ > 25) & (pdi > mdi) & (r_ >= 50) & (r_ <= 80)),
    }

    # TP/SL بزرگ (فلسفهٔ H4) — مقادیرِ غیررند برای ضدِ اشتباهِ #۷
    grids = [(500, 350), (450, 300), (600, 400), (400, 250), (350, 220)]

    log(f"{'filt':<24} {'tp':>4} {'sl':>4} | {'WR':>5} {'net':>8} {'PF':>5} {'DD':>5} {'MCL':>3} {'n':>4} | gates  RQS")
    best = []
    for fn, fm in filters.items():
        for tp, sl in grids:
            r, tr = S.evaluate(df, sym, sig, sl_pip=sl, tp_pip=tp, max_hold=mh, filt=fm)
            m = r['metrics']
            if m.get('n_trades', 0) < 30:
                continue
            g = gates_str(r)
            passed = r['passed']
            log(f"{fn:<24} {tp:>4} {sl:>4} | {m['win_rate']:>5.1f} {m['net_profit']:>8.0f} "
                f"{m['profit_factor']:>5.2f} {m['max_dd_pct']:>5.1f} {m['max_consec_losses']:>3d} "
                f"{m['n_trades']:>4d} | {g}  {r['rqs_score']:.1f}" + ("  <<<PASS" if passed else ""))
            best.append((r['rqs_score'], passed, fn, tp, sl, m, g))

    best.sort(key=lambda x: -x[0])
    npass = sum(1 for b in best if b[1])
    log(f"\n== {sym} {a.tf}: {npass} PASS / {len(best)} valid | elapsed={time.time()-t0:.0f}s ==")
    log("-- top 5 by RQS --")
    for rq, ps, fn, tp, sl, m, g in best[:5]:
        log(f"  RQS={rq:5.1f} {'PASS' if ps else 'fail'} {fn:<22} tp={tp} sl={sl} "
            f"WR={m['win_rate']:.1f} net={m['net_profit']:.0f} PF={m['profit_factor']:.2f} "
            f"DD={m['max_dd_pct']:.1f} MCL={m['max_consec_losses']} n={m['n_trades']} {g}")


if __name__ == '__main__':
    main()
