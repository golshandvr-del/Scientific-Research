# -*- coding: utf-8 -*-
"""
s332_bank_scan.py — احیای squeeze (S132/S332) روی TFهای پایین با «فیلترهای عمیقِ بانک»

انگیزه (User Note): تا این‌جا squeeze فقط با ADX/DI فیلتر شد و TFهای پایین به دیوارِ
WR~۵۲٪ خوردند. اما بانکِ ۴۰۱-تایی ده‌ها فیلترِ رژیم/کیفیت‌روند دارد که امتحان نشده‌اند
(اشتباهِ رایجِ #۳). این اسکن آن‌ها را — تک و ترکیبی — روی squeeze آزمایش می‌کند.

طراحیِ ضدفریز:
  • سیگنالِ squeeze یک‌بار ساخته می‌شود.
  • کتابخانهٔ فیلتر (۲۷ ماسک) یک‌بار محاسبه می‌شود.
  • فاز ۱: هر فیلترِ تک × چند (TP,SL)ِ غیررندِ مخصوصِ TF.
  • فاز ۲: ترکیبِ ۲ و ۳ تاییِ بهترین فیلترها (قانونِ همکاریِ بهبودها).
  • خروجیِ افزایشی به فایلِ log (results/_s332_bank_<sym>_<tf>.log) — قابلِ خواندن حینِ اجرا.

اشتباهاتِ رعایت‌شده:
  #۶ TP/SL مخصوصِ هر TF (نه یکسان) — با مقیاسِ natr.
  #۷ اعدادِ غیررند (۳۳۵/۲۱۵ به‌جای ۳۰۰/۲۰۰).
  #۱/#۲/#۳ تمرکز بر فیلترهای پیچیدهٔ آماری/فراکتالی/چرخه، نه صرفاً زمان یا MA.
"""
import os
import sys
import argparse
import itertools
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import strategies.s332_squeeze_rqs_revival as S
import strategies.bank_filters as BF

# --- شبکهٔ (TP,SL)ِ غیررندِ مخصوصِ هر TF (pip) ---------------------------------
# طلا: pip=0.10 ⇒ TP=335pip یعنی ۳۳.۵$/oz. مقادیر عمداً غیررند (اشتباه #۷).
# هر TF بازهٔ حرکتِ متفاوتی دارد (اشتباه #۶): TF بالاتر → TP/SL بزرگ‌تر.
TPSL_GRID = {
    'M5':  [(135, 90), (175, 115), (215, 145)],
    'M15': [(215, 145), (285, 190), (365, 240)],
    'M30': [(285, 190), (365, 240), (475, 315)],
    'H1':  [(365, 240), (475, 315), (615, 405)],
    'H4':  [(475, 315), (615, 405), (785, 515)],
}
# یورو: pip=0.0001 ⇒ مقیاسِ کوچک‌تر (طلا/یورو حرکتِ pip متفاوت).
TPSL_GRID_EUR = {
    'M5':  [(28, 18), (37, 24), (48, 32)],
    'M15': [(37, 24), (48, 32), (63, 42)],
    'M30': [(48, 32), (63, 42), (82, 55)],
}
MAXHOLD = {'M5': 96, 'M15': 64, 'M30': 48, 'H1': 48, 'H4': 24}


def gates_str(r):
    return ''.join('1' if r['gates'][x] else '0' for x in ['G0', 'G1', 'G2', 'G3', 'G4', 'G5'])


def line(name, tp, sl, r):
    m = r['metrics']
    return (f"RQS={r['rqs_score']:5.1f} {'PASS' if r['passed'] else 'fail'} "
            f"{name:34s} tp={tp} sl={sl} WR={m['win_rate']:.1f} net={m['net_profit']:.0f} "
            f"PF={m['profit_factor']:.2f} DD={m['max_dd_pct']:.1f} MCL={m['max_consec_losses']} "
            f"n={m['n_trades']} {gates_str(r)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sym', default='XAUUSD')
    ap.add_argument('--tf', default='M5')
    ap.add_argument('--phase2', action='store_true', help='ترکیبِ ۲/۳ فیلتر هم اجرا شود')
    ap.add_argument('--top', type=int, default=8, help='چند فیلترِ برترِ فاز۱ وارد فاز۲ شوند')
    args = ap.parse_args()

    sym, tf = args.sym, args.tf
    df = S.load_tf(sym, tf)
    if df is None:
        print(f"داده موجود نیست: {sym} {tf}")
        return

    logpath = f"results/_s332_bank_{sym}_{tf}.log"
    os.makedirs('results', exist_ok=True)
    logf = open(logpath, 'w', encoding='utf-8')

    def out(s):
        print(s)
        logf.write(s + '\n')
        logf.flush()

    grid = (TPSL_GRID_EUR if sym == 'EURUSD' else TPSL_GRID).get(tf)
    if grid is None:
        out(f"شبکهٔ TP/SL برای {sym} {tf} تعریف نشده.")
        logf.close()
        return
    mh = MAXHOLD[tf]

    # ۱) سیگنالِ squeeze (یک‌بار)
    sig = S.build_squeeze_signal(df, sqz_pct=0.25, breakout_lookback=6)
    nsig = int(sig.sum())
    out(f"== {sym} {tf} | candles={len(df)} squeeze_signals={nsig} maxhold={mh} ==")
    out(f"== TP/SL grid={grid} ==")

    # ۲) کتابخانهٔ فیلتر (یک‌بار)
    out("... محاسبهٔ کتابخانهٔ فیلترهای بانک ...")
    lib = BF.build_filter_library(df)
    out(f"... {len(lib)} فیلتر آماده شد ...")

    # baseline بدونِ فیلتر (مرجع)
    out("\n--- baseline بدونِ فیلتر ---")
    best_base = None
    for tp, sl in grid:
        r, _ = S.evaluate(df, sym, sig, sl_pip=sl, tp_pip=tp, max_hold=mh)
        out("  " + line('no-filter', tp, sl, r))
        if best_base is None or r['metrics']['win_rate'] > best_base:
            best_base = r['metrics']['win_rate']

    # ---------------- فاز ۱: فیلترهای تک ----------------
    out("\n--- فاز ۱: فیلترهای تکِ بانک ---")
    scored = []  # (bestWR, bestRQS, name)
    passes = []
    for name, mask in lib.items():
        best_wr = -1
        best_rqs = -1
        best_r = None
        best_tpsl = None
        for tp, sl in grid:
            r, _ = S.evaluate(df, sym, sig, sl_pip=sl, tp_pip=tp, max_hold=mh, filt=mask)
            m = r['metrics']
            if m['n_trades'] < 30:
                continue
            if r['passed']:
                passes.append(line(name, tp, sl, r))
            if m['win_rate'] > best_wr:
                best_wr, best_rqs, best_r, best_tpsl = m['win_rate'], r['rqs_score'], r, (tp, sl)
        if best_r is not None:
            out("  " + line(name, best_tpsl[0], best_tpsl[1], best_r))
            scored.append((best_wr, best_rqs, name))

    scored.sort(reverse=True)
    out("\n--- برترین فیلترهای تک بر اساسِ WR ---")
    for wr, rq, nm in scored[:args.top]:
        out(f"  WR={wr:.1f} RQS={rq:.1f}  {nm}")

    # ---------------- فاز ۲: ترکیب‌ها ----------------
    if args.phase2 and len(scored) >= 2:
        top_names = [nm for _, _, nm in scored[:args.top]]
        out(f"\n--- فاز ۲: ترکیبِ ۲/۳تاییِ {len(top_names)} فیلترِ برتر (قانونِ همکاری) ---")
        combos = list(itertools.combinations(top_names, 2))
        if len(top_names) >= 3:
            combos += list(itertools.combinations(top_names, 3))
        for combo in combos:
            mask = np.ones(len(df), dtype=bool)
            for nm in combo:
                mask = mask & lib[nm]
            best_r = None
            best_tpsl = None
            for tp, sl in grid:
                r, _ = S.evaluate(df, sym, sig, sl_pip=sl, tp_pip=tp, max_hold=mh, filt=mask)
                if r['metrics']['n_trades'] < 30:
                    continue
                if r['passed']:
                    passes.append(line('+'.join(combo), tp, sl, r))
                if best_r is None or r['metrics']['win_rate'] > best_r['metrics']['win_rate']:
                    best_r, best_tpsl = r, (tp, sl)
            if best_r is not None:
                out("  " + line('+'.join(combo), best_tpsl[0], best_tpsl[1], best_r))

    # ---------------- خلاصه ----------------
    out("\n" + "=" * 70)
    if passes:
        out(f"✅ {len(passes)} ترکیبِ PASS یافت شد:")
        for p in passes:
            out("  " + p)
    else:
        out(f"❌ هیچ ترکیبی PASS نشد. بهترین WR baseline={best_base:.1f}, "
            f"بهترین WR با فیلتر={scored[0][0]:.1f}" if scored else "❌ هیچ نتیجه‌ای.")
    logf.close()
    print(f"\nلاگ ذخیره شد: {logpath}")


if __name__ == '__main__':
    main()
