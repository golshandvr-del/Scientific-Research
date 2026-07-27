# -*- coding: utf-8 -*-
"""
s332_overlap_audit.py — ممیزیِ همپوشانیِ لایهٔ S332 (Squeeze+ADX/DI روی H4)
================================================================================
> قانونِ همپوشانیِ پروژه: پیش از افزودنِ هر لایه باید دقیقاً سنجید که با کدام
> لایه/لایه‌های فعال و چند درصد همپوشانی دارد — از طریقِ شبیه‌سازِ رویداد-محور.

لایه‌های squeeze-پایهٔ فعالِ طلا:
  S313  Squeeze→Breakout روی H1 و M30 (ATR-scaled، max_hold=48، BE-trailing)
  S225  Squeeze WR60 روی M5/M15/M30/H1
لایهٔ من: همان سیگنالِ پایهٔ squeeze ولی روی **H4** با فیلترِ ADX>22&+DI>−DI و TP/SL ثابت.

پرسشِ کلیدیِ همپوشانی: چون TFها متفاوت‌اند، معیارِ منصفانه = همپوشانیِ **زمانی**.
چند درصد از معاملاتِ H4ِ من در **همان روزِ تقویمی** یک معاملهٔ S313-H1/M30 باز می‌شوند؟
(هم‌روز = محافظه‌کارانه‌ترین و بالاترین برآوردِ همپوشانی.)

روش:
  1) معاملاتِ S332-H4 (منطقِ نهایی) را با موتورِ scalp_engine استخراج می‌کنیم (زمانِ ورود).
  2) روزهای ورودِ S313 روی H1 و M30 را از sim_strategies استخراج می‌کنیم.
  3) اشتراک/تفاضلِ مجموعهٔ روزها + درصدِ معاملاتِ هم‌پوشان گزارش می‌شود.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
import strategies.s332_squeeze_rqs_revival as S
from engine import trade_simulator as TS
from strategies.sim_strategies import S313_SqueezeBreakout_Long


def s332_h4_trades():
    """معاملاتِ لایهٔ نهاییِ S332 روی XAUUSD H4 + روزهای تقویمیِ ورود/بازه."""
    df = S.load_tf('XAUUSD', 'H4')
    sig = S.build_squeeze_signal(df, sqz_pct=0.25, breakout_lookback=6)
    adx_, pdi, mdi = S.adx(df, 14)
    fm = np.nan_to_num(((adx_ > 22) & (pdi > mdi)).astype(float), nan=0.0).astype(bool)
    r, trades = S.evaluate(df, 'XAUUSD', sig, sl_pip=350, tp_pip=500, max_hold=24, filt=fm)
    dt = df['dt']
    entry_days = []          # روزِ ورودِ هر معامله
    span_days = []           # مجموعهٔ روزهای پوشش‌دادهٔ هر معامله (entry..exit)
    for _, tr in trades.iterrows():
        eb, xb = int(tr['entry_bar']), int(tr['exit_bar'])
        ed = pd.Timestamp(dt.iloc[eb]).date()
        xd = pd.Timestamp(dt.iloc[min(xb, len(df) - 1)]).date()
        entry_days.append(ed)
        span_days.append(set(pd.date_range(ed, xd, freq='D').date))
    return df, trades, entry_days, span_days, r


def s313_entry_days(tf):
    df = TS.load_data('XAUUSD_' + tf)
    kw = dict(sqz_pct=0.25, max_hold=48, sl_atr=3.2, tp_atr=2.15,
              closepos_min=0.55, be_trigger_atr=1.1, be_offset_atr=0.4, adx_min=0.0)
    s = S313_SqueezeBreakout_Long(**kw)
    tr, _ = TS.simulate(df, s, 'XAUUSD', tf=tf, warmup=320, max_bars_hold=None)
    dt = df['dt']
    days = set()
    for eb in tr['entry_bar'].values:
        d = pd.Timestamp(dt.iloc[int(eb)]).date()
        days.add(d)
    return days, len(tr)


def main():
    df, trades, entry_days, span_days, r = s332_h4_trades()
    n = len(trades)
    print("=" * 74)
    print(f"ممیزیِ همپوشانیِ S332 (Squeeze+ADX/DI، XAUUSD H4) — {n} معامله | RQS+={r['rqs_score']:.1f}")
    print("=" * 74)

    # لایه‌های squeeze-پایهٔ فعال: S313 روی H1 و M30
    for tf in ['H1', 'M30']:
        try:
            s313_days, n313 = s313_entry_days(tf)
        except Exception as e:
            print(f"[S313 {tf}] خطا: {e}")
            continue
        # همپوشانیِ هم‌روز: چند معاملهٔ H4ِ من روزی وارد شده که S313-{tf} هم آن روز وارد شده؟
        same_day = sum(1 for ed in entry_days if ed in s313_days)
        # همپوشانیِ هم‌بازه: چند معاملهٔ H4 حداقل یک روزِ مشترک با روزهای ورودِ S313 دارد؟
        span_hit = sum(1 for sp in span_days if sp & s313_days)
        print(f"\n— در برابر S313-{tf} (n={n313} معامله، {len(s313_days)} روزِ ورودِ یکتا):")
        print(f"    همپوشانیِ هم‌روزِ ورود : {same_day}/{n} = {100*same_day/n:.1f}%")
        print(f"    همپوشانیِ هم‌بازه(entry..exit): {span_hit}/{n} = {100*span_hit/n:.1f}%")

    # لایه‌های زمان‌محورِ فعالِ طلا (day-of-month)
    S312_DOM = {10, 13, 20}
    S306_DOM = {28, 29, 30, 31, 1, 2, 3}
    S310_DOM = {25, 26, 27, 28, 29, 30, 31}
    doms = np.array([d.day for d in entry_days])
    print("\n— در برابر لایه‌های زمان‌محورِ فعالِ طلا (day-of-month):")
    for name, dom in [('S312 Mid-Month', S312_DOM), ('S306 Turn-of-Month', S306_DOM),
                      ('S310 End-of-Month', S310_DOM)]:
        hit = sum(1 for d in doms if d in dom)
        print(f"    {name:22s}: {hit}/{n} = {100*hit/n:.1f}%")

    print("\nنتیجه‌گیریِ همپوشانی در فایلِ نتیجه ثبت می‌شود.")


if __name__ == '__main__':
    main()
