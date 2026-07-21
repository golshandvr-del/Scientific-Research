"""
explore_dxy_eurusd_leadlag.py — کشفِ ساختارِ lead-lag بین DXY و EURUSD
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **معیارِ موفقیت فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate (WR)، نه Profit
> Factor، نه تعدادِ معامله.** تعریفِ رسمیِ سودِ خالص = جمعِ سودِ XAUUSD + EURUSD.

--------------------------------------------------------------------------------
تفکرِ نبوغ‌آمیز (User Note این نشست: «نبوغ‌آمیز فکر کن!»):
  گلوگاهِ اثبات‌شدهٔ پروژه (PARADIGM §۶ نسخهٔ ۶) = «نبودِ جریانِ ساختاراً غیرِهم‌بسته».
  تقریباً همهٔ لایه‌ها «long طلا» یا مشتقاتِ آن‌اند؛ EURUSD فقط یک لایه (S73، drift
  ساعتِ ۰ UTC، صرفاً زمان-محور) دارد.

  فرضیهٔ بکر و تست‌نشده: EURUSD و DXY (شاخصِ دلار) ذاتاً معکوس‌اند. اگر DXY یک
  حرکتِ کوتاه‌مدتِ قوی داشته باشد ولی EURUSD هنوز کامل واکنش نداده باشد، یک
  **عدمِ‌تعادلِ لحظه‌ای (lead-lag / خطای هم‌انباشتگی)** وجود دارد که با ورود روی
  EURUSD در جهتِ اصلاحِ آن قابلِ بهره‌برداری است. چون این سیگنال از DXY می‌آید و
  نه از قیمتِ گذشتهٔ خودِ EURUSD (که random-walk است) و نه از طلا ⇒ نامزدِ یک
  **جریانِ ساختاراً غیرِهم‌بسته** است.

  ⚠️ ریسکِ روش‌شناختی که باید صادقانه بسنجیم: EUR ~۵۷٪ وزنِ DXY است ⇒ ممکن است
  رابطه *هم‌زمان* باشد نه *پیش‌رو*. فقط اگر با تأخیرِ واقعی (lag≥۱ کندل، بدونِ
  look-ahead) لبهٔ آماریِ معنادار ببینیم، ارزشِ ساختِ استراتژی دارد.

این اسکریپت فقط **کشفِ ساختار** است (نه استراتژی):
  ۱) هم‌ترازیِ زمانیِ DXY M15 و EURUSD M15 با merge_asof backward (بدونِ look-ahead).
  ۲) سنجشِ همبستگیِ هم‌زمان (lag 0) و پیش‌رو (DXY_return[t] → EURUSD_return[t+k]).
  ۳) سنجشِ خطای هم‌انباشتگی (z-score اسپردِ استانداردشده) و بازگشتِ آن.
  ۴) گزارشِ t-stat؛ اگر لبهٔ پیش‌رو معنادار نبود، صادقانه رد می‌کنیم.
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
    print("  کشفِ ساختارِ lead-lag بین DXY و EURUSD (نبوغ‌آمیز: جریانِ غیرِهم‌بستهٔ نو)")
    print("  قانونِ #۱: فقط سودِ خالص (XAUUSD + EURUSD). WR گزارشی است.")
    print("=" * 92, flush=True)

    eur = load(os.path.join(DATA, 'EURUSD_M15.csv'))
    dxy = load(os.path.join(DATA, 'DXY_M15.csv'))
    print(f"\n  EURUSD: {len(eur):,} کندل  {eur['dt'].min()} .. {eur['dt'].max()}")
    print(f"  DXY   : {len(dxy):,} کندل  {dxy['dt'].min()} .. {dxy['dt'].max()}", flush=True)

    # هم‌ترازیِ زمانی: برای هر کندلِ EURUSD، آخرین DXY که close آن <= زمانِ EURUSD است
    # (merge_asof backward ⇒ بدونِ look-ahead)
    m = pd.merge_asof(eur[['dt', 'close']].rename(columns={'close': 'eur'}),
                      dxy[['dt', 'close']].rename(columns={'close': 'dxy'}),
                      on='dt', direction='backward', tolerance=pd.Timedelta('15min'))
    m = m.dropna().reset_index(drop=True)
    print(f"  هم‌تراز: {len(m):,} کندلِ مشترک", flush=True)

    eurc = m['eur'].values
    dxyc = m['dxy'].values
    # بازده‌های log
    eur_ret = np.diff(np.log(eurc))
    dxy_ret = np.diff(np.log(dxyc))

    # ---- همبستگیِ هم‌زمان (lag 0) ----
    r0, p0 = stats.pearsonr(dxy_ret, eur_ret)
    print(f"\n  همبستگیِ هم‌زمانِ بازده (DXY[t], EUR[t]): r={r0:+.3f}  (انتظار: منفیِ قوی)")

    # ---- lead: DXY_return[t] → EURUSD_return[t+k]  (k≥1 ⇒ قابلِ بهره‌برداری) ----
    print(f"\n  {'lag k (کندل)':>14}{'corr(DXY[t],EUR[t+k])':>26}{'t-stat':>12}")
    print("  " + "-" * 54)
    lead_edges = []
    for k in range(1, 9):
        x = dxy_ret[:-k]
        y = eur_ret[k:]
        r, p = stats.pearsonr(x, y)
        t = r * np.sqrt((len(x) - 2) / max(1e-12, 1 - r * r))
        star = " ✅" if abs(t) > 4 else ""
        print(f"  {k:>14}{r:>26.4f}{t:>12.2f}{star}")
        lead_edges.append((k, r, t))

    # ---- خطای هم‌انباشتگی: z-score اسپردِ استانداردشده و بازگشتِ آن ----
    # اسپرد = log(EUR) + beta*log(DXY) (چون معکوس‌اند، beta>0). beta را با OLS رولینگ نمی‌گیریم
    # (look-ahead)؛ به‌جای آن z-scoreِ رولینگِ خودِ EUR نسبت به میانگین/انحرافِ گذشته را
    # با «شوکِ DXY» شرطی می‌کنیم.
    print(f"\n  --- آزمونِ عدمِ‌تعادلِ لحظه‌ای: وقتی DXY شوکِ قوی می‌دهد، EUR بعد چه می‌کند؟ ---")
    win = 20
    dxy_z = pd.Series(dxy_ret).rolling(win).apply(
        lambda a: (a[-1] - a[:-1].mean()) / (a[:-1].std() + 1e-12), raw=True).values
    # آیندهٔ EUR: بازده ۴ کندلِ بعد
    fwd = 4
    eur_fwd = np.full(len(eur_ret), np.nan)
    eur_fwd[:-fwd] = np.array([eurc[i + 1 + fwd] / eurc[i + 1] - 1 for i in range(len(eur_ret) - fwd)])

    print(f"  {'شرطِ شوکِ DXY':>26}{'n':>8}{'میانگینِ EUR_fwd(4)':>22}{'t-stat':>12}")
    print("  " + "-" * 68)
    shock_edges = []
    for label, mask in [
        ('DXY_z >= +2 (دلار جهش↑)', dxy_z >= 2.0),
        ('DXY_z >= +1.5', dxy_z >= 1.5),
        ('DXY_z <= -2 (دلار سقوط↓)', dxy_z <= -2.0),
        ('DXY_z <= -1.5', dxy_z <= -1.5),
    ]:
        mm = mask & np.isfinite(eur_fwd)
        if mm.sum() < 30:
            print(f"  {label:>26}{int(mm.sum()):>8}{'کم‌داده':>22}")
            continue
        vals = eur_fwd[mm]
        t, p = stats.ttest_1samp(vals, 0.0)
        star = " ✅" if abs(t) > 4 else (" ~" if abs(t) > 2 else "")
        print(f"  {label:>26}{int(mm.sum()):>8}{vals.mean() * 1e4:>19.2f}pip{t:>12.2f}{star}")
        shock_edges.append((label, int(mm.sum()), float(vals.mean()), float(t)))

    print("\n" + "=" * 92)
    print("  جمع‌بندیِ صادقانه:")
    best_lead_t = max(abs(t) for _, _, t in lead_edges)
    best_shock_t = max((abs(t) for _, _, _, t in shock_edges), default=0.0)
    print(f"    • قوی‌ترین t-statِ lead (k≥1): {best_lead_t:.2f}")
    print(f"    • قوی‌ترین t-statِ شوکِ DXY→EUR_fwd: {best_shock_t:.2f}")
    if best_lead_t > 4 or best_shock_t > 4:
        print("    ⇒ لبهٔ پیش‌روِ معنادار وجود دارد. ارزشِ ساختِ استراتژی را دارد. ✅")
    else:
        print("    ⇒ لبهٔ پیش‌روِ قوی یافت نشد (رابطه احتمالاً هم‌زمان است، نه پیش‌رو).")
        print("      طبقِ روشِ علمی، این مسیر را صادقانه کنار می‌گذاریم و به ایدهٔ بعد می‌رویم.")
    print("=" * 92, flush=True)


if __name__ == '__main__':
    main()
