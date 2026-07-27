# -*- coding: utf-8 -*-
"""
s332_m15_overlap_audit.py — ممیزیِ همپوشانیِ لایهٔ S332-M15 (Squeeze + r2 + hurst)
================================================================================
> قانونِ همپوشانیِ پروژه (غیرقابل چشم‌پوشی): پیش از افزودنِ هر لایه باید دقیقاً سنجید
> که با کدام لایه/لایه‌های فعال و چند درصد همپوشانی دارد — از طریقِ شبیه‌سازِ رویداد-محور —
> و امکانِ استفاده از بخشِ همپوشان به‌عنوان فیلتر را بررسی کرد.

لایهٔ من (این نشست): XAUUSD **M15**، سیگنالِ squeeze (sqz_pct=0.25, brk=6) + فیلترِ آماریِ
  بانک `r2(20)>0.58 & hurst(64)>0.55`، TP=285 SL=190 mh=64 → RQS+=91.2 (TP بزرگ / breakout).

لایه‌های squeeze-پایهٔ فعالِ طلا که **روی M15 هم هستند**:
  • S225  (S91 احیا) — squeeze روی M5/M15/M30/H1، ولی رویکردِ **معکوس**:
          TP کوچک/SL بزرگ (M15: TP40/SL300، WR=87.8٪، scalp). sqz_pct=0.15, brk=10.
  • S313  — squeeze روی H1/M30 (نه M15 مستقیم؛ TFِ متفاوت).

پرسشِ کلیدی (چون هم‌TF است): چند درصد از معاملاتِ **بار-ورودیِ** M15ِ من با معاملاتِ S225-M15
هم‌بار (±۲ کندل) یا هم‌روز هستند؟ و آیا فیلترِ من (r2+hurst) می‌تواند S225 یا squeezeِ خامِ
دیگری را بهبود دهد (استفاده از بخشِ همپوشان به‌عنوان فیلتر)؟
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
import strategies.s332_squeeze_rqs_revival as S
import strategies.bank_filters as BF


def s332_m15_trades():
    """معاملاتِ لایهٔ نهاییِ S332-M15 (squeeze + r2>0.58 & hurst>0.55)."""
    df = S.load_tf('XAUUSD', 'M15')
    sig = S.build_squeeze_signal(df, sqz_pct=0.25, breakout_lookback=6)
    r2 = BF.r2(df, 20)
    hu = BF.hurst(df, 64)
    fm = np.nan_to_num(((r2 > 0.58) & (hu > 0.55)).astype(float), nan=0.0).astype(bool)
    r, trades = S.evaluate(df, 'XAUUSD', sig, sl_pip=190, tp_pip=285, max_hold=64, filt=fm)
    return df, sig, fm, trades, r


def s225_m15_entry_bars(df):
    """بارهای ورودِ سیگنالِ پایهٔ S225 روی M15 (sqz_pct=0.15, breakout_lookback=10).

    S225 از همان منطقِ squeeze استفاده می‌کند ولی با پارامترهای متفاوت. برای مقایسهٔ
    منصفانهٔ «همپوشانیِ سیگنال» بارهای سیگنالِ خامِ آن را (بدون فیلترهای TF-محورِ آن) می‌گیریم.
    """
    sig225 = S.build_squeeze_signal(df, sqz_pct=0.15, breakout_lookback=10)
    bars = set(np.where(sig225)[0].tolist())
    return bars, len(bars)


def main():
    df, sig, fm, trades, r = s332_m15_trades()
    n = len(trades)
    dt = df['dt']
    print("=" * 76)
    print(f"ممیزیِ همپوشانیِ S332-M15 (Squeeze + r2>0.58 & hurst>0.55) — "
          f"{n} معامله | RQS+={r['rqs_score']:.1f}")
    print("=" * 76)

    entry_bars = [int(t['entry_bar']) for _, t in trades.iterrows()]
    entry_days = [pd.Timestamp(dt.iloc[b]).date() for b in entry_bars]

    # === 1) همپوشانیِ سیگنالِ پایه با S225-M15 (هم‌TF) ===
    s225_bars, n225 = s225_m15_entry_bars(df)
    s225_days = set(pd.Timestamp(dt.iloc[b]).date() for b in s225_bars)

    exact = sum(1 for b in entry_bars if b in s225_bars)
    near2 = sum(1 for b in entry_bars if any((b + k) in s225_bars for k in (-2, -1, 0, 1, 2)))
    sameday = sum(1 for d in entry_days if d in s225_days)
    print(f"\n— در برابر S225 (squeeze-پایهٔ M15، sqz=0.15 brk=10؛ {n225} بارِ سیگنال):")
    print(f"    هم‌بارِ دقیقِ ورود        : {exact}/{n} = {100*exact/n:.1f}%")
    print(f"    هم‌بار ±۲ کندل           : {near2}/{n} = {100*near2/n:.1f}%")
    print(f"    هم‌روزِ تقویمی            : {sameday}/{n} = {100*sameday/n:.1f}%")
    print(f"    توضیح: S225 رویکردِ معکوس دارد (TP40/SL300 scalp) — همان روزها، معاملهٔ متفاوت.")

    # === 2) استفاده از بخشِ همپوشان به‌عنوان فیلتر: آیا r2+hurst می‌تواند
    #        squeezeِ خامِ S225-پارامتر را روی M15 با TP کوچک (سبکِ S225) بهبود دهد؟ ===
    print(f"\n— بررسیِ «استفاده از بخشِ همپوشان به‌عنوان فیلتر» (قانونِ سومِ همپوشانی):")
    sig225 = S.build_squeeze_signal(df, sqz_pct=0.15, breakout_lookback=10)
    r2 = BF.r2(df, 20)
    hu = BF.hurst(df, 64)
    fm225 = np.nan_to_num(((r2 > 0.58) & (hu > 0.55)).astype(float), nan=0.0).astype(bool)
    # سبکِ S225-M15: TP کوچک / SL بزرگ
    for label, s, filt, tp, sl, mh in [
        ("S225-param خام (TP40/SL300)",        sig225, None,  40, 300, 96),
        ("S225-param + r2+hurst (فیلترِ من)",  sig225, fm225, 40, 300, 96),
        ("S225-param + r2+hurst، TP بزرگ",     sig225, fm225, 285, 190, 64),
    ]:
        rr, _ = S.evaluate(df, 'XAUUSD', s, sl_pip=sl, tp_pip=tp, max_hold=mh, filt=filt)
        m = rr['metrics']
        g = ''.join('1' if rr['gates'][x] else '0' for x in ['G0', 'G1', 'G2', 'G3', 'G4', 'G5'])
        tag = ' PASS' if rr['passed'] else ''
        print(f"    {label:34s} RQS={rr['rqs_score']:5.1f} WR={m['win_rate']:.1f} "
              f"PF={m['profit_factor']:.2f} n={m['n_trades']} {g}{tag}")

    # === 3) لایه‌های زمان‌محورِ فعال (day-of-month) ===
    S312_DOM = {10, 13, 20}
    S306_DOM = {28, 29, 30, 31, 1, 2, 3}
    S310_DOM = {25, 26, 27, 28, 29, 30, 31}
    doms = np.array([d.day for d in entry_days])
    print("\n— در برابر لایه‌های زمان‌محورِ فعالِ طلا (day-of-month):")
    for name, dom in [('S312 Mid-Month', S312_DOM), ('S306 Turn-of-Month', S306_DOM),
                      ('S310 End-of-Month', S310_DOM)]:
        hit = sum(1 for d in doms if d in dom)
        print(f"    {name:22s}: {hit}/{n} = {100*hit/n:.1f}%")

    print("\nنتیجه‌گیریِ همپوشانیِ M15 در فایلِ نتیجه ثبت می‌شود.")


if __name__ == '__main__':
    main()
