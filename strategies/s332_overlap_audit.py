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


def s332_h4_entry_days():
    """روزهای تقویمیِ ورودِ لایهٔ نهاییِ S332 روی XAUUSD H4."""
    df = S.load_tf('XAUUSD', 'H4')
    sig = S.build_squeeze_signal(df, sqz_pct=0.25, breakout_lookback=6)
    adx_, pdi, mdi = S.adx(df, 14)
    fm = np.nan_to_num(((adx_ > 22) & (pdi > mdi)).astype(float), nan=0.0).astype(bool)
    r, trades = S.evaluate(df, 'XAUUSD', sig, sl_pip=350, tp_pip=500, max_hold=24, filt=fm)
    # trades: ساختارِ scalp_engine — ستونِ entry_idx یا مشابه
    dt = df['dt'].values
    days = []
    ebars = []
    # کشفِ نامِ ستونِ ایندکسِ ورود
    if isinstance(trades, dict):
        keys = list(trades.keys())
    else:
        keys = list(getattr(trades, 'columns', []))
    return df, trades, keys


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
    df, trades, keys = s332_h4_entry_days()
    print("scalp_engine trade keys/cols:", keys)
    print("type(trades):", type(trades))
    # نمونهٔ اولین رکورد
    if isinstance(trades, list) and trades:
        print("sample trade[0]:", trades[0])
    elif hasattr(trades, 'iloc'):
        print(trades.head(3))


if __name__ == '__main__':
    main()
