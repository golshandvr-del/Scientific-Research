# -*- coding: utf-8 -*-
"""
ابزارِ نقشهٔ امکان‌سنجیِ هندسی (RR Feasibility Map)
================================================================================
این ابزار **استراتژی نیست**؛ یک اندازه‌گیریِ *پیش از تحقیق* است که به یک پرسشِ
ساده جواب می‌دهد:

    «آیا این کارت با این هندسهٔ براکت، اصلاً **قابلِ برد** است؟»

چرا این ابزار لازم شد
---------------------
پروژه در سراسرِ خطِ لولهٔ S346/S347 قیدِ `RR = TP/SL = 1.0` را **منجمد** کرده بود
(`strategies/s347_ensemble.py:54`). این قید برای دفعِ اشتباهِ رایجِ #۸ گذاشته شده
بود — «TP کوچک‌تر از SL ⇒ بردها زیاد می‌افتند ⇒ WRِ جعلی». آن نگرانی درست است،
اما راه‌حلش **بیش از اندازه** جبران کرد: قیدِ `RR=1` هزینه را به یک مالیاتِ
غیرقابل‌پرداخت روی تایم‌فریم‌های پایین تبدیل کرد.

ریاضیاتِ ماجرا
--------------
هزینهٔ رفت‌وبرگشت `c` یک مقدارِ **ثابت بر حسبِ pip** است (اسپرد + اسلیپیج) و به
تایم‌فریم کاری ندارد. اما `ATR` با کوچک‌شدنِ تایم‌فریم **کوچک** می‌شود. پس نسبتِ
`c/ATR` — که ما آن را **بارِ هزینه** می‌نامیم — روی تایم‌فریم‌های پایین منفجر
می‌شود. سربه‌سرِ هزینه‌دار:

        BE  = (SL + c)  / (SL + TP)          ⇐ دروازهٔ H2 باید ۳pp از آن بالا بزند
        RBE = (SL + 2c) / (SL + TP)          ⇐ دروازهٔ H9 (تنشِ هزینه) = میلهٔ **واقعی**

با `TP = SL` (یعنی `RR=1`) این‌ها به `(1 + c/SL)/2` و `(1 + 2c/SL)/2` تبدیل
می‌شوند. یعنی وقتی `c/SL → 1`، سربه‌سر به **۱۰۰٪** میل می‌کند و کارت
**حسابی ناممکن** می‌شود — نه سخت، بلکه *ناممکن*.

اندازه‌گیریِ واقعی (این ابزار روی دادهٔ خودِ پروژه)
--------------------------------------------------
    EURUSD-M1 : c/ATR = 1.328 ⇒ سربه‌سرِ مقاومِ RR=1 برابر **۱۸۲.۸٪**
    EURUSD-M5 : c/ATR = 0.532 ⇒ سربه‌سرِ مقاومِ RR=1 برابر **۱۰۳.۳٪**

هر دو **بالای ۱۰۰٪**. یعنی هیچ استراتژیی، با هیچ درجه‌ای از مهارت، نمی‌توانست
این دو کارت را با هندسهٔ منجمدِ پروژه پاس کند. «مرگِ» این کارت‌ها یک
**مصنوعِ اندازه‌گیری** بود، نه یک خاصیتِ بازار.

⛔ تمایزِ حیاتی — این «دور زدنِ معیار» نیست
------------------------------------------
اشتباهِ #۸ درباره `RR < 1` است (TP کوچک‌تر از SL). این ابزار `RR > 1` را بررسی
می‌کند، یعنی **جهتِ مخالفِ** تقلب. با `RR>1`:
    • سربه‌سر **پایین** می‌آید ولی WRِ خام هم طبعاً **پایین** می‌آید،
    • پس هیچ WRِ رایگانی تولید نمی‌شود،
    • و دروازهٔ H2 هنوز «۳pp بالاتر از سربه‌سرِ *خودِ همان هندسه*» را می‌خواهد.
هندسه در هر دو طرفِ نامعادله ظاهر می‌شود، پس قابلِ بازی‌کردن نیست. آن‌چه `RR>1`
عوض می‌کند فقط این است که «فضایی برای پرداختِ هزینه» باز می‌شود.

خروجی
-----
برای هر کارت: بارِ هزینه، سربه‌سرِ خام/مقاوم روی شبکهٔ RR، و کمینهٔ RRِ لازم تا
میلهٔ مقاوم به یک سطحِ قابلِ‌دسترسِ صادقانه برسد.
"""
import sys
import os

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                    # noqa: E402
from engine.rqs2 import breakeven_wr_cost                # noqa: E402
from strategies.s346_geom import CARDS                    # noqa: E402

# شبکهٔ RR — اعدادِ فیبوناچی/غیر-رند، طبقِ اشتباهِ رایجِ #۷ (نه ۱.۵/۲/۳)
RR_GRID = (1.0, 1.272, 1.618, 2.058, 2.618, 3.236)

# ATR مرجع برای اندازه‌گیریِ مقیاسِ کارت. دورهٔ ۲۱ = عضوِ میانیِ P_LIST پروژه.
ATR_P = 21

# میلهٔ «قابلِ‌دسترسِ صادقانه»: یک لایهٔ واقعی روی این پروژه در بهترین حالت
# WRِ ۵۵–۶۰٪ داده است، پس اگر سربه‌سرِ **مقاوم** زیرِ این عدد نیاید، کارت
# عملاً بی‌امید است. عدد محافظه‌کارانه انتخاب شده تا ادعا کم‌برآورد شود.
REACHABLE_WR = 52.0


def atr_pip(df, asset, p=ATR_P):
    """ATRِ ساده (میانگینِ TR) بر حسبِ **pip** — مقیاس‌ناوردا بینِ دارایی‌ها."""
    h = df['high'].values.astype('float64')
    l = df['low'].values.astype('float64')
    c = df['close'].values.astype('float64')
    prev_c = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    a = pd.Series(tr).rolling(p).mean().values
    return a / se.ASSETS[asset]['pip']


def cost_pip(asset):
    """هزینهٔ رفت‌وبرگشت بر حسبِ pip — اسپردِ کامل + اسلیپیجِ دو طرف."""
    cfg = se.ASSETS[asset]
    return float(cfg['spread_pip']) + 2.0 * float(cfg['slip_pip'])


def min_rr_for(sl_pip, cost, target_wr=REACHABLE_WR, stress=2.0):
    """
    کمینهٔ RR تا سربه‌سرِ *مقاوم* به `target_wr` برسد.

        (SL + stress*c) / (SL + RR*SL) = target
        ⇒ RR = (SL + stress*c) / (target * SL) - 1
    """
    t = target_wr / 100.0
    if sl_pip <= 0 or t <= 0:
        return float('inf')
    return (sl_pip + stress * cost) / (t * sl_pip) - 1.0


def measure(card, asset, path, sl_k=1.0):
    df = se.load_data(path)
    a = atr_pip(df, asset)
    sl = float(np.nanmedian(a)) * sl_k
    c = cost_pip(asset)
    row = {
        'card': card, 'asset': asset, 'bars': len(df),
        'days': int((df['dt'].max() - df['dt'].min()).days),
        'atr_pip': float(np.nanmedian(a)), 'sl_pip': sl, 'cost_pip': c,
        'cost_burden': c / sl if sl > 0 else float('inf'),
        'min_rr': min_rr_for(sl, c),
    }
    for rr in RR_GRID:
        row[f'be_{rr}'] = breakeven_wr_cost(sl, rr * sl, c)
        row[f'rbe_{rr}'] = breakeven_wr_cost(sl, rr * sl, 2.0 * c)
    return row


def main(sl_k=1.0):
    rows = [measure(k, a, p, sl_k) for k, (a, p) in CARDS.items()]

    print("=" * 96)
    print(f"RR FEASIBILITY MAP   ·   SL = {sl_k:.3f} x ATR{ATR_P}   ·   "
          f"reachable-WR bar = {REACHABLE_WR:.0f}%")
    print("=" * 96)
    print(f"{'card':<12}{'c/SL':>7}{'ATRpip':>9}{'minRR':>7}  |  "
          + ''.join(f"{('RBE@'+str(r)):>10}" for r in RR_GRID))
    print('-' * 96)
    for r in rows:
        cells = []
        for rr in RR_GRID:
            v = r[f'rbe_{rr}']
            cells.append(f"{v:>10.1f}" if v <= 100.0 else f"{'IMPOSSIBLE':>10}")
        print(f"{r['card']:<12}{r['cost_burden']:>7.3f}{r['atr_pip']:>9.2f}"
              f"{r['min_rr']:>7.2f}  |  " + ''.join(cells))
    print('-' * 96)
    print("RBE = ROBUST breakeven WR% = (SL+2c)/(SL+TP)  ⇐ gate H9, the REAL bar")
    print("minRR = smallest RR that pulls the ROBUST bar down to "
          f"{REACHABLE_WR:.0f}%")
    print()

    imposs = [r for r in rows if r['rbe_1.0'] > 100.0]
    if imposs:
        print("⛔ CARDS ARITHMETICALLY UNWINNABLE AT THE FROZEN RR=1 GEOMETRY:")
        for r in imposs:
            print(f"     {r['card']:<12} robust breakeven = {r['rbe_1.0']:.1f}% "
                  f"(> 100% ⇒ NO strategy could ever pass)")
        print("   ⇒ their previous 'death' is a MEASUREMENT ARTEFACT, not a")
        print("     market property. They must be re-judged at RR > 1.")
    return rows


if __name__ == '__main__':
    k = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    main(k)
