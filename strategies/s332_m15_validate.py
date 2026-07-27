# -*- coding: utf-8 -*-
"""
s332_m15_validate.py — اعتبارسنجیِ نهاییِ کشفِ M15 + انتشار به سایرِ TFها

کشفِ نجات‌دهنده: squeeze + (r2>0.58 & hurst>0.55)، TP=285, SL=190, mh=64
  ⇒ XAUUSD M15: RQS+=91.2 (هر ۶ گیت).

این اسکریپت سه کار می‌کند:
  ۱) آزمونِ همسایگیِ ضدِ overfit: ۱۰ همسایهٔ نزدیکِ (r2,hurst,tp,sl) — چند تا PASS/نزدیک؟
  ۲) گزارشِ کاملِ walk-forward (۴ پنجره) و نیمه‌ها برای پیکربندیِ برنده.
  ۳) اعمالِ همین منطق (با TP/SL مقیاسِ TF) روی M30/H1/H4 و EURUSD M5/M15/M30 —
     شاید TFِ دیگری هم زنده شود (قانونِ مولتی‌تایم‌فریم).

خروجی: results/_s332_m15_validate.log
"""
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import strategies.s332_squeeze_rqs_revival as S
import strategies.bank_filters as BF


def gates_str(r):
    return ''.join('1' if r['gates'][x] else '0' for x in ['G0', 'G1', 'G2', 'G3', 'G4', 'G5'])


def run(df, sym, r2t, hut, tp, sl, mh):
    sig = S.build_squeeze_signal(df, sqz_pct=0.25, breakout_lookback=6)
    r2v = BF.r2(df, 20)
    hu = BF.hurst(df, 64)
    mask = np.nan_to_num(((r2v > r2t) & (hu > hut)).astype(float), nan=0.0).astype(bool)
    r, tr = S.evaluate(df, sym, sig, sl_pip=sl, tp_pip=tp, max_hold=mh, filt=mask)
    return r, tr


def main():
    logf = open('results/_s332_m15_validate.log', 'w', encoding='utf-8')

    def out(s):
        print(s)
        logf.write(s + '\n')
        logf.flush()

    # پیکربندیِ برنده
    df15 = S.load_tf('XAUUSD', 'M15')
    out("=" * 72)
    out("۱) اعتبارسنجیِ کاملِ پیکربندیِ برنده — XAUUSD M15")
    out("   squeeze + r2>0.58 & hurst>0.55 | TP=285 SL=190 mh=64")
    out("=" * 72)
    r, tr = run(df15, 'XAUUSD', 0.58, 0.55, 285, 190, 64)
    m = r['metrics']
    out(f"RQS+={r['rqs_score']:.1f} passed={r['passed']} gates={gates_str(r)}")
    for k in ['n_trades', 'win_rate', 'net_profit', 'profit_factor', 'max_dd_pct',
              'max_consec_losses', 'expectancy']:
        if k in m:
            out(f"   {k:20s} = {m[k]}")
    # walk-forward دستی: ۴ پنجرهٔ برابر روی معاملات
    if hasattr(tr, '__len__') and len(tr) >= 8:
        nets = tr['net_usd'].to_numpy() if hasattr(tr, 'columns') and 'net_usd' in tr.columns else None
        if nets is not None:
            q = len(nets) // 4
            wins = [nets[i * q:(i + 1) * q].sum() for i in range(4)]
            half = [nets[:len(nets) // 2].sum(), nets[len(nets) // 2:].sum()]
            out(f"   walk-forward نِت (۴ پنجره): {[round(x) for x in wins]}")
            out(f"   نیمه‌ها: {[round(x) for x in half]}")

    # ۲) آزمونِ همسایگی
    out("\n" + "=" * 72)
    out("۲) آزمونِ همسایگیِ ضدِ overfit (۱۲ همسایهٔ نزدیک)")
    out("=" * 72)
    neigh = [
        (0.55, 0.55, 285, 190), (0.60, 0.55, 285, 190), (0.58, 0.53, 285, 190),
        (0.58, 0.57, 285, 190), (0.58, 0.55, 270, 180), (0.58, 0.55, 300, 200),
        (0.58, 0.55, 285, 175), (0.58, 0.55, 285, 205), (0.56, 0.54, 285, 190),
        (0.60, 0.56, 285, 190), (0.58, 0.55, 260, 175), (0.58, 0.55, 310, 205),
    ]
    passc = 0
    nearc = 0
    for r2t, hut, tp, sl in neigh:
        r, _ = run(df15, 'XAUUSD', r2t, hut, tp, sl, 64)
        g = gates_str(r)
        mm = r['metrics']
        status = 'PASS' if r['passed'] else ('near' if g.count('1') >= 5 else 'fail')
        if r['passed']:
            passc += 1
        if g.count('1') >= 5:
            nearc += 1
        out(f"   r2>{r2t} hurst>{hut} tp={tp} sl={sl}: RQS={r['rqs_score']:5.1f} {status:4s} "
            f"WR={mm['win_rate']:.1f} PF={mm['profit_factor']:.2f} n={mm['n_trades']} {g}")
    out(f"\n   نتیجهٔ همسایگی: {passc}/12 کاملاً PASS، {nearc}/12 حداقل ۵گیت (near+pass).")
    out(f"   {'✅ پایدار (نه overfit تصادفی)' if nearc >= 7 else '⚠️ حساس به پارامتر'}")

    # ۳) همین منطق روی سایرِ TFها/دارایی‌ها
    out("\n" + "=" * 72)
    out("۳) اعمالِ همین فیلتر (r2>0.58 & hurst>0.55) روی سایرِ TFها")
    out("=" * 72)
    # TP/SL مقیاسِ TF (غیررند) — همان نسبتِ ~1.5 که در M15 کار کرد
    other = [
        ('XAUUSD', 'M30', 385, 255, 48),
        ('XAUUSD', 'H1', 515, 345, 48),
        ('XAUUSD', 'H4', 285, 190, 24),  # همان نسبت روی H4 هم (مقایسه با فیلترِ ADX قبلی)
        ('EURUSD', 'M5', 48, 32, 96),
        ('EURUSD', 'M15', 63, 42, 64),
        ('EURUSD', 'M30', 82, 55, 48),
    ]
    for sym, tf, tp, sl, mh in other:
        df = S.load_tf(sym, tf)
        if df is None:
            out(f"   {sym} {tf}: داده موجود نیست")
            continue
        try:
            r, _ = run(df, sym, 0.58, 0.55, tp, sl, mh)
            mm = r['metrics']
            out(f"   {sym} {tf} tp={tp} sl={sl}: RQS={r['rqs_score']:5.1f} "
                f"{'PASS' if r['passed'] else 'fail'} WR={mm['win_rate']:.1f} "
                f"PF={mm['profit_factor']:.2f} DD={mm['max_dd_pct']:.1f} n={mm['n_trades']} {gates_str(r)}")
        except Exception as e:
            out(f"   {sym} {tf}: خطا {e}")

    logf.close()


if __name__ == '__main__':
    main()
