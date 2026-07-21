"""
explore_dxy_regime_eurusd.py — آیا «رژیمِ روندِ DXY» یک گیتِ جهتِ سوددهِ برون‌زا
   برای EURUSD است؟ (تعمیقِ ایدهٔ نبوغ‌آمیز)
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ (بالاترین اولویت): معیارِ موفقیت فقط و فقط «سودِ خالصِ بیشتر»
> است — نه WR. تعریفِ سودِ خالص = XAUUSD + EURUSD.

--------------------------------------------------------------------------------
یافتهٔ اکتشافِ قبلی (explore_dxy_eurusd_leadlag):
  • همبستگیِ هم‌زمانِ بازده r=−0.86 (DXY↑ ⇒ EUR↓، بسیار قوی و هم‌زمان).
  • لبهٔ پیش‌روِ تک‌کندلی خام ضعیف است (~۰.۴pip < اسپرد) ⇒ به‌تنهایی سودده نیست.

تعمیقِ نبوغ‌آمیز: به‌جای «شوکِ تک‌کندلیِ DXY»، از **جهتِ روندِ کندِ DXY** (میانگینِ
متحرک) به‌عنوان یک **گیتِ جهتِ برون‌زا** استفاده کنیم. منطق:
  - DXY یک شاخصِ کلانِ دلار است؛ روندِ چند-روزهٔ آن اطلاعاتِ *ماکروِ* پایدار دارد.
  - چون EURUSD در M15 خودش random-walk است (autocorr≈۰)، یک گیتِ جهت که از
    *منبعِ دیگری* (DXY) بیاید می‌تواند لبه بسازد بدونِ اینکه به قیمتِ گذشتهٔ EUR
    وابسته باشد ⇒ نامزدِ جریانِ غیرِهم‌بسته با طلا و مکملِ S73 (که فقط زمان-محور است).

فرضیهٔ اصلی: **وقتی DXY در روندِ نزولی است (دلار ضعیف)، EURUSD بایاسِ صعودیِ
پایدار دارد.** این را به‌تفکیکِ رژیمِ DXY می‌سنجیم و بازدهِ آتیِ EUR را گزارش می‌کنیم.

⚠️ همه با merge_asof backward (بدونِ look-ahead). گیتِ DXY فقط از داده‌ای که close
آن ≤ زمانِ ورودِ EUR است ساخته می‌شود.
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
    print("  آیا «رژیمِ روندِ DXY» یک گیتِ جهتِ سوددهِ برون‌زا برای EURUSD است؟")
    print("  قانونِ #۱: فقط سودِ خالص (XAUUSD + EURUSD). WR گزارشی است.")
    print("=" * 92, flush=True)

    eur = load(os.path.join(DATA, 'EURUSD_M15.csv'))
    dxy = load(os.path.join(DATA, 'DXY_M15.csv'))

    # گیتِ روندِ DXY: شیبِ EMA روی close خودِ DXY (فقط تا کندلِ جاری)
    for span in (50, 100, 200):
        dxy[f'ema{span}'] = dxy['close'].ewm(span=span, adjust=False).mean()
    dxy['ema_slope50'] = dxy['ema50'].diff()
    dxy['above200'] = (dxy['close'] > dxy['ema200']).astype(float)
    dxy['below200'] = (dxy['close'] < dxy['ema200']).astype(float)

    m = pd.merge_asof(
        eur[['dt', 'close']].rename(columns={'close': 'eur'}),
        dxy[['dt', 'ema50', 'ema200', 'ema_slope50', 'above200', 'below200']],
        on='dt', direction='backward', tolerance=pd.Timedelta('15min'))
    m = m.dropna().reset_index(drop=True)
    print(f"\n  هم‌تراز: {len(m):,} کندلِ مشترک", flush=True)

    eurc = m['eur'].values
    n = len(m)

    # بازدهِ آتیِ EUR در افق‌های مختلف (pip) — forward-safe (فقط برای ارزیابیِ لبه)
    def fwd_ret(h):
        r = np.full(n, np.nan)
        r[:-h] = (eurc[h:] / eurc[:-h] - 1.0)
        return r

    print("\n  --- بایاسِ آتیِ EUR به‌تفکیکِ رژیمِ روندِ DXY (میانگین بر حسبِ pip) ---")
    print("  فرضیه: DXY نزولی (دلار ضعیف) ⇒ EUR بایاسِ صعودی؛ DXY صعودی ⇒ EUR بایاسِ نزولی.\n")

    dxy_down = m['below200'].values > 0.5          # دلار زیرِ EMA200 = روندِ نزولیِ دلار
    dxy_up = m['above200'].values > 0.5            # دلار بالای EMA200 = روندِ صعودیِ دلار
    dxy_slope_dn = m['ema_slope50'].values < 0     # شیبِ کوتاه‌مدتِ دلار نزولی
    dxy_slope_up = m['ema_slope50'].values > 0

    for h in (4, 8, 16, 32):
        fr = fwd_ret(h)
        print(f"  ── افقِ {h} کندل ({h*15}min) ──")
        for label, mask in [
            ('DXY<EMA200 (دلار ضعیف)   ', dxy_down),
            ('DXY>EMA200 (دلار قوی)    ', dxy_up),
            ('DXY slope<0 (دلار نزولی) ', dxy_slope_dn),
            ('DXY slope>0 (دلار صعودی) ', dxy_slope_up),
            ('ضعیف ∧ نزولی (هم‌جهت↓$)   ', dxy_down & dxy_slope_dn),
            ('قوی ∧ صعودی (هم‌جهت↑$)    ', dxy_up & dxy_slope_up),
        ]:
            mm = mask & np.isfinite(fr)
            if mm.sum() < 100:
                continue
            vals = fr[mm]
            t, _ = stats.ttest_1samp(vals, 0.0)
            star = " ✅" if abs(t) > 4 else (" ~" if abs(t) > 2 else "")
            print(f"    {label} n={mm.sum():>7}  میانگین={vals.mean()*1e4:>+7.2f}pip  t={t:>+7.2f}{star}")
        print()

    print("=" * 92)
    print("  تفسیر: اگر رژیمِ «دلار ضعیف» بایاسِ صعودیِ EUR با t>4 و مقدارِ اقتصادیِ")
    print("  بزرگ‌تر از اسپرد (~۱pip) بدهد ⇒ گیتِ جهتِ برون‌زای سودده. آن‌گاه استراتژی می‌سازیم.")
    print("=" * 92, flush=True)


if __name__ == '__main__':
    main()
