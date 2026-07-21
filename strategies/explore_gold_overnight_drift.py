"""
explore_gold_overnight_drift.py — کشفِ «Overnight Drift» روی طلا (ایدهٔ نبوغ‌آمیزِ نو)
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ (بالاترین اولویت): معیارِ موفقیت فقط و فقط «سودِ خالصِ بیشتر»
> است — نه WR، نه PF، نه تعدادِ معامله. تعریفِ سودِ خالص = XAUUSD + EURUSD.

--------------------------------------------------------------------------------
تفکرِ نبوغ‌آمیز (User Note: «نبوغ‌آمیز فکر کن!»):
  دو ایدهٔ قبلی (lead-lag و رژیمِ DXY) صادقانه رد شدند (لبه < اسپرد). درسِ آن‌ها:
  «رابطهٔ DXY-EUR هم‌زمان است نه پیش‌رو».

  ایدهٔ نو از ادبیاتِ آکادمیک: **The Overnight Drift** (Lou, Polk & Skouras, JFE 2019)
  و Cooper-Cliff-Gulen (2008) نشان دادند بخشِ بزرگی از بازدهِ دارایی‌ها در دورهٔ
  *شبانه* (وقتی بازارِ اصلی بسته است) انباشته می‌شود، نه در ساعاتِ معاملاتیِ روز.
  علت‌های ساختاری: عدمِ‌تعادلِ سفارش در بازگشایی، ریسک-پریمیومِ نگه‌داریِ شبانه،
  و رفتارِ متفاوتِ نقدینگی.

  این پدیده روی **طلا** در این پروژه هرگز تست نشده. اگر وجود داشته باشد، یک لایهٔ
  **ساختاراً غیرِهم‌بسته** با همهٔ لایه‌های intraday-momentum (S67/Scalp/Squeeze/SHORT)
  می‌سازد — چون منبعِ سودش «نگه‌داری در بازهٔ زمانیِ خاصِ شبانه» است، نه ماشهٔ قیمتی.

روش (کشفِ ساختار، بدونِ look-ahead):
  ۱) هر «روزِ معاملاتی» را به دو بازه تقسیم می‌کنیم:
       • Overnight = از بسته‌شدنِ سشنِ US تا بازگشاییِ سشنِ بعد (شب).
       • Intraday  = ساعاتِ فعالِ روز.
  ۲) بازدهِ انباشتهٔ هر بازه را جدا می‌کنیم و t-stat می‌گیریم.
  ۳) اگر یکی از بازه‌ها بایاسِ جهت‌دارِ معنادار و بزرگ‌تر از اسپرد (۴pip طلا) بدهد،
     نامزدِ استراتژی است.

  تعریفِ بازه‌ها با UTC hour (طلا ~۲۴ساعته اما با سشن‌های آسیا/لندن/US):
     Asian/Overnight window ≈ ۲۱:۰۰ UTC (بستنِ US) تا ۰۷:۰۰ UTC (پیش از لندن).
================================================================================
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import numpy as np, pandas as pd
from scipy import stats
import warnings; warnings.filterwarnings('ignore')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')


def load(path):
    d = pd.read_csv(path)
    d['dt'] = pd.to_datetime(d['time'], unit='s')
    d = d.sort_values('dt').drop_duplicates('dt').reset_index(drop=True)
    return d


def main():
    print("=" * 92)
    print("  کشفِ «Overnight Drift» روی طلا (ادبیاتِ آکادمیک: Lou-Polk-Skouras 2019)")
    print("  قانونِ #۱: فقط سودِ خالص (XAUUSD + EURUSD). WR گزارشی است.")
    print("=" * 92, flush=True)

    df = load(os.path.join(DATA, 'XAUUSD_M15.csv'))
    df['hour'] = df['dt'].dt.hour
    df['dow'] = df['dt'].dt.dayofweek
    c = df['close'].values
    o = df['open'].values
    n = len(df)
    print(f"\n  طلا M15: {n:,} کندل  {df['dt'].min()} .. {df['dt'].max()}", flush=True)

    # بازدهِ هر کندل (close-to-close، بر حسبِ pip؛ طلا pip=0.1$)
    ret_pip = np.zeros(n)
    ret_pip[1:] = (c[1:] - c[:-1]) / 0.10
    hour = df['hour'].values

    # --- گامِ ۱: بازدهِ میانگین به‌تفکیکِ ساعتِ UTC (کدام ساعت‌ها drift دارند؟) ---
    print("\n  --- میانگینِ بازدهِ هر کندل به‌تفکیکِ ساعتِ UTC (pip) ---")
    print(f"  {'ساعت':>6}{'n':>9}{'میانگین(pip)':>16}{'t-stat':>10}")
    print("  " + "-" * 42)
    hour_stats = {}
    for hh in range(24):
        mask = hour == hh
        vals = ret_pip[mask]
        if len(vals) < 100:
            continue
        t, _ = stats.ttest_1samp(vals, 0.0)
        hour_stats[hh] = (len(vals), float(vals.mean()), float(t))
        star = " ✅" if abs(t) > 4 else (" ~" if abs(t) > 2 else "")
        print(f"  {hh:>6}{len(vals):>9}{vals.mean():>16.4f}{t:>10.2f}{star}")

    # --- گامِ ۲: تجمیعِ بازه‌ها (Overnight vs Intraday) ---
    print("\n  --- بازدهِ انباشتهٔ بازه‌ها (segment-level) ---")
    # Overnight = ساعاتِ ۲۱..۲۳ + ۰..۶ (شب/آسیا)؛ Intraday = ۷..۲۰ (لندن+US)
    overnight = (hour >= 21) | (hour <= 6)
    intraday = (hour >= 7) & (hour <= 20)
    for label, mask in [('Overnight (21-06 UTC، شب/آسیا)', overnight),
                        ('Intraday  (07-20 UTC، لندن+US) ', intraday)]:
        vals = ret_pip[mask]
        t, _ = stats.ttest_1samp(vals, 0.0)
        tot = vals.sum()
        star = " ✅" if abs(t) > 4 else (" ~" if abs(t) > 2 else "")
        print(f"  {label}: n={mask.sum():>7}  میانگین/کندل={vals.mean():>+7.4f}pip  "
              f"مجموع={tot:>+9,.0f}pip  t={t:>+6.2f}{star}")

    # --- گامِ ۳: «هولد شبانه» به‌عنوان استراتژیِ کاندید (خام، بدونِ هزینه) ---
    # ورود در open کندلی که ساعتش h_in است، خروج بعد از H کندل.
    print("\n  --- بایاسِ ورودِ ساعتِ خاص + هولدِ H کندل (خامِ pip، پیش از هزینه) ---")
    print(f"  {'ساعتِ ورود':>10}{'هولد(کندل)':>12}{'n':>7}{'میانگین(pip)':>15}{'t':>8}{'مجموع(pip)':>13}")
    print("  " + "-" * 66)
    best = []
    for h_in in [21, 22, 23, 0, 1, 2]:
        for H in [4, 8, 16, 24]:
            # سیگنال: کندلی که ساعتش h_in است ⇒ ورود در open کندلِ بعد
            entry = np.where(hour == h_in)[0]
            entry = entry[(entry + 1 + H) < n]
            if len(entry) < 100:
                continue
            # بازدهِ long از open ورود تا close پس از H کندل
            pnl = (c[entry + 1 + H] - o[entry + 1]) / 0.10
            t, _ = stats.ttest_1samp(pnl, 0.0)
            star = " ✅" if abs(t) > 4 else (" ~" if abs(t) > 2 else "")
            row = (h_in, H, len(entry), float(pnl.mean()), float(t), float(pnl.sum()))
            best.append(row)
            print(f"  {h_in:>10}{H:>12}{len(entry):>7}{pnl.mean():>15.3f}{t:>8.2f}{pnl.sum():>13,.0f}{star}")

    print("\n" + "=" * 92)
    if best:
        best_row = max(best, key=lambda r: abs(r[4]))
        print(f"  قوی‌ترین بایاسِ شبانه: ورودِ ساعت {best_row[0]}، هولد {best_row[1]} کندل ⇒ "
              f"میانگین {best_row[3]:+.2f}pip، t={best_row[4]:+.2f}")
        econ = abs(best_row[3]) > 4.0  # بزرگ‌تر از اسپردِ ۴pip طلا؟
        if abs(best_row[4]) > 4 and econ:
            print("  ⇒ لبهٔ شبانهٔ معنادار و بزرگ‌تر از اسپرد. ارزشِ ساختِ استراتژی دارد. ✅✅")
        elif abs(best_row[4]) > 4:
            print(f"  ⇒ معنادار اما مقدار ({best_row[3]:+.2f}pip) نزدیک/زیرِ اسپردِ ۴pip؛ باید با")
            print("     خروجِ هوشمند (TP/SL) آزمود که آیا سودِ خالصِ واقعی می‌دهد.")
        else:
            print("  ⇒ بایاسِ شبانهٔ قوی یافت نشد؛ صادقانه بررسیِ بیشتر لازم است.")
    print("=" * 92, flush=True)


if __name__ == '__main__':
    main()
