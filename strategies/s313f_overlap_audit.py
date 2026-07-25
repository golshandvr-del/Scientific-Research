# -*- coding: utf-8 -*-
"""
s313f_overlap_audit.py — ممیزیِ همپوشانیِ S313 (Squeeze) با لایه‌های فعالِ طلا
================================================================================
> قانونِ همپوشانیِ پروژه: پیش از افزودنِ هر لایه، باید دقیقاً سنجید که با کدام
> لایه/لایه‌های فعال و چند درصد همپوشانی دارد (از طریقِ شبیه‌سازِ رویداد-محور).
>
> لایه‌های فعالِ طلا همگی زمان‌محورند (روزِ خاصِ ماه):
>   S306 Turn-of-Month  : dom ∈ {28,29,30,31,1,2,3} (حدوداً)
>   S310 End-of-Month   : dom ∈ {25..31}
>   S312 Mid-Month      : dom ∈ {10,13,20}
> S313 اندیکاتوری است (فشردگیِ بولینگر + ADX). انتظار: همپوشانیِ کم.
>
> روش: روزهای تقویمیِ ورودِ S313 (H1 و M30) را استخراج و درصدِ افتادنشان در
> پنجره‌های زمانیِ هر لایهٔ فعال را گزارش می‌کنیم (هم‌روز = بالاترین سطحِ محافظه‌کارانهٔ
> همپوشانی، چون آن لایه‌ها day-granularity دارند).
"""
import os
import sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import trade_simulator as TS
from strategies.sim_strategies import S313_SqueezeBreakout_Long

# پنجره‌های day-of-month لایه‌های فعالِ طلا
S312_DOM = {10, 13, 20}                       # Mid-Month
S306_DOM = {28, 29, 30, 31, 1, 2, 3}          # Turn-of-Month (محافظه‌کارانه)
S310_DOM = {25, 26, 27, 28, 29, 30, 31}       # End-of-Month


def s313_entry_days(tf, adx_min=0.0):
    df = TS.load_data(tf)
    asset = 'XAUUSD'
    kw = dict(sqz_pct=0.25, max_hold=48, sl_atr=3.2, tp_atr=2.15,
              closepos_min=0.55, be_trigger_atr=1.1, be_offset_atr=0.4, adx_min=adx_min)
    s = S313_SqueezeBreakout_Long(**kw)
    tr, _ = TS.simulate(df, s, asset, tf=tf, warmup=320, max_bars_hold=None)
    # entry_bar → تاریخِ تقویمی
    dt = df['dt']
    days = []
    for eb in tr['entry_bar'].values:
        if 0 <= eb < len(dt):
            days.append(dt.iloc[eb])
    days = np.array(days)
    dom = np.array([d.day for d in days])
    dates = np.array([d.date() for d in days])
    return tr, dom, dates


def audit(tf, adx_min):
    tr, dom, dates = s313_entry_days(tf, adx_min)
    n = len(dom)
    if n == 0:
        print(f"  {tf}: بدون معامله")
        return
    p312 = np.mean([d in S312_DOM for d in dom]) * 100
    p306 = np.mean([d in S306_DOM for d in dom]) * 100
    p310 = np.mean([d in S310_DOM for d in dom]) * 100
    any_time = np.mean([d in (S312_DOM | S306_DOM | S310_DOM) for d in dom]) * 100
    print(f"\n  ── {tf} (ADX≥{adx_min}) — n={n} ورود ──")
    print(f"     همپوشانیِ روز-محور با S312 Mid-Month (dom∈{{10,13,20}}): {p312:.1f}%")
    print(f"     همپوشانیِ روز-محور با S306 Turn-of-Month           : {p306:.1f}%")
    print(f"     همپوشانیِ روز-محور با S310 End-of-Month            : {p310:.1f}%")
    print(f"     همپوشانیِ کل با هر لایهٔ زمان‌محور                    : {any_time:.1f}%")
    print(f"     ⇒ سهمِ کاملاً مستقل (ناهمپوشان)                      : {100-any_time:.1f}%")


def main():
    print("#" * 74)
    print("# S313f — ممیزیِ همپوشانیِ Squeeze با لایه‌های فعالِ زمان‌محورِ طلا")
    print("#" * 74)
    audit('XAUUSD_H1', 0.0)     # لایهٔ H1 پذیرفته‌شده
    audit('XAUUSD_M30', 30.0)   # لایهٔ M30 پذیرفته‌شده (ADX≥30)
    print("\nتفسیر: چون S312/S306/S310 فقط چند روزِ ماه فعال‌اند، همپوشانیِ تصادفیِ")
    print("       مورد-انتظار ≈ مجموعِ نسبتِ آن روزها به کلِ ماه است. اگر همپوشانیِ")
    print("       واقعیِ S313 نزدیک یا کمتر از این پایه باشد ⇒ لایه عملاً مستقل است.")
    # پایهٔ تصادفی
    base = len(S312_DOM | S306_DOM | S310_DOM) / 30.0 * 100
    print(f"       پایهٔ تصادفیِ مورد-انتظار ≈ {base:.1f}% از روزهای ماه در این پنجره‌هاست.")


if __name__ == '__main__':
    main()
