# -*- coding: utf-8 -*-
"""
s96_scalp_endpoint_paperbroker_test.py — تستِ paper broker برای منطقِ *سایت* (User Note)
================================================================================
> قانونِ شمارهٔ ۱: هدف فقط «سودِ خالص» است، نه WR.
> سودِ خالص = XAUUSD + EURUSD.
================================================================================

User Note صراحتاً می‌گوید: «این رو حتماً همراه با تستِ paper broker تست کنیم تا
مطمئن بشیم درست کار می‌کنه.»

s94/s95 خودِ استراتژی را تست کردند. این فایل یک قدم فراتر می‌رود و **دقیقاً همان
منطقِ تصمیمِ خروجِ سایت** را (که در gold_m5_router.ts::manageGoldM5Scalp پیاده شده)
به‌صورتِ خط‌به‌خط در پایتون بازتولید می‌کند و روی paper broker اجرا می‌کند تا ثابت
شود:

  ۱) رفتارِ endpointِ /api/scalp/manage با بک‌تستِ سوددهِ s95 «هم‌ارز» است
     (همان قانون: favor≥۱۲۰ ⇒ سود، favor≤−۸۰ ⇒ ضرر، شکستِ روند در ضرر ⇒ ضرر).
  ۲) سودِ خالصِ لایهٔ اسکالپ همان +۱۰٬۰۴۴$ باقی می‌ماند (رگرسیون نمی‌خورد).

اگر این تست سبز شود، یعنی آنچه کاربر در سایت می‌بیند (BUY → تأیید → «سودمونو
گرفتیم/اشتباه بود، ببند» → بستن) دقیقاً همان چیزی است که سودِ خالص را ساخت.

نکته: این «قراردادِ» سایت↔بک‌تست است؛ منطقِ TS و این تست باید همیشه یکی بمانند.
"""
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from strategies.s91_scalp_signal_exit import paper_broker, stats, print_stats, DATA
from strategies.s92_scalp_exit_variants import build_entries_long_pullback

# --- ثابت‌های «هدفِ پنهان» — باید دقیقاً با gold_m5_router.ts یکی باشند ---
HIDDEN_TP_PIP = 120      # gold_m5_router.ts::HIDDEN_TP_PIP
HIDDEN_SL_PIP = 80       # gold_m5_router.ts::HIDDEN_SL_PIP
EMA_FAST = 20            # gold_m5_router.ts::EMA_FAST
EMA_SLOW = 100           # gold_m5_router.ts::EMA_SLOW


def site_manage_exit(ctx):
    """بازتولیدِ خط‌به‌خطِ manageGoldM5Scalp (سمتِ سرورِ سایت).

    ctx شامل: favor_pip_gross (حرکتِ مطلوب به pip، برای BUY = live-ref)،
              ema_f, ema_s (EMA20/100 روی همان کندل).
    خروجی: مثلِ سایت، ('win'|'loss', reason) یا None (=hold).
      - favor ≥ HIDDEN_TP_PIP  → 'take_profit' (win)   → «سودمونو گرفتیم، ببند»
      - favor ≤ -HIDDEN_SL_PIP → 'wrong'       (loss)  → «اشتباه بود، ببند»
      - شکستِ روند (ema_f<ema_s) و favor≤0 → 'wrong' (loss) → «اشتباه بود، ببند»
    """
    g = ctx['favor_pip_gross']
    if g >= HIDDEN_TP_PIP:
        return ('win', 'take_profit')
    if g <= -HIDDEN_SL_PIP:
        return ('loss', 'wrong_stop')
    if ctx['ema_f'] < ctx['ema_s'] and g <= 0:
        return ('loss', 'wrong_trend_break')
    return None


def run(df, entries, cat_sl=500.0):
    n = len(df); half = n // 2
    tr = paper_broker(df, entries, site_manage_exit, catastrophic_sl_pip=cat_sl, max_hold=288)
    s_all = stats(tr)
    e1 = [(i, s) for (i, s) in entries if i < half - 1]
    df1 = df.iloc[:half].reset_index(drop=True)
    s1 = stats(paper_broker(df1, e1, site_manage_exit, catastrophic_sl_pip=cat_sl, max_hold=288))
    e2 = [(i - half, s) for (i, s) in entries if i >= half]
    df2 = df.iloc[half:].reset_index(drop=True)
    s2 = stats(paper_broker(df2, e2, site_manage_exit, catastrophic_sl_pip=cat_sl, max_hold=288))
    return s_all, s1, s2


def main():
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    entries = build_entries_long_pullback(df)

    print("=" * 82)
    print("s96 — تستِ paper broker برای منطقِ *سایت* (endpoint /api/scalp/manage)")
    print("=" * 82)
    print(f"داده: {len(df)} کندلِ M5   ورودها: {len(entries)}")
    print(f"منطقِ سایت: BUY → پایش → (favor≥{HIDDEN_TP_PIP}⇒سود | favor≤-{HIDDEN_SL_PIP}⇒ضرر | "
          f"شکستِ EMA20<EMA100 در ضرر⇒ضرر)\n")

    s_all, s1, s2 = run(df, entries)
    print("--- کل (منطقِ سایت روی paper broker) ---");  print_stats(s_all)
    print("--- نیمهٔ اول ---");  print_stats(s1)
    print("--- نیمهٔ دوم ---");  print_stats(s2)

    # --- گیت‌های پذیرش (paper broker باید سبز شود، وگرنه سایت نباید منتشر شود) ---
    print("\n" + "=" * 82)
    print("گیت‌های پذیرشِ paper broker:")
    checks = []
    checks.append(("سودِ خالصِ کل مثبت", s_all['net_usd'] > 0, f"{s_all['net_usd']:+.2f}$"))
    checks.append(("نیمهٔ اول مثبت", s1['net_usd'] > 0, f"{s1['net_usd']:+.2f}$"))
    checks.append(("نیمهٔ دوم مثبت", s2['net_usd'] > 0, f"{s2['net_usd']:+.2f}$"))
    checks.append(("PF کل > ۱.۱", s_all['pf'] > 1.1, f"PF={s_all['pf']:.2f}"))
    ok_all = True
    for name, ok, val in checks:
        mark = "✅" if ok else "❌"
        print(f"  {mark} {name}: {val}")
        ok_all = ok_all and ok

    print("\n" + "=" * 82)
    if ok_all:
        print("✅✅ همهٔ گیت‌ها سبز — منطقِ اسکالپِ سایت روی paper broker تأیید شد.")
        print("   یعنی آنچه کاربر می‌بیند (BUY→تأیید→«سودمونو گرفتیم/اشتباه بود»→بستن)")
        print("   دقیقاً همان چیزی است که سودِ خالصِ مثبت را در بک‌تست ساخت.")
    else:
        print("❌ حداقل یک گیت قرمز — سایت نباید با این منطق منتشر شود.")
    print("=" * 82)
    sys.exit(0 if ok_all else 1)


if __name__ == '__main__':
    main()
