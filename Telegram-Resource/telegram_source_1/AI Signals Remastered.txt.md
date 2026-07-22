# بررسیِ منبع: `AI Signals Remastered.txt`

> قانونِ شمارهٔ ۱: تابعِ هدف = **سودِ خالصِ بیشتر** (XAUUSD + EURUSD)؛ WR کفِ ۴۰٪ دارد.
> مشخصاتِ حساب: `CONTRACT_SIZE=100`، طلا `3.3pip`، کمیسیون=صفر.

---

## ۱. چیستی

| ویژگی | مقدار |
|---|---|
| **نوع** | **سورسِ بازِ Pine Script v5** (TradingView) — ارزشِ تحقیقاتیِ بالا (منطق کاملاً خواناست). |
| **نام/سازنده** | «AI Signal - Remastered» © SirAlgo / `@moneymovesalgo`. |
| **overlay** | روی چارت (`overlay=true`). |

## ۲. منطقِ استخراج‌شده (از سورسِ Pine)

سه مؤلفهٔ اصلی:

1. **Supertrendِ اصلاح‌شده با Keltner** (هستهٔ سیگنال):
   - `keltner_channel`: `ma = SMA(src, kel_len)` و باند = `ma ± (high−low)`؛ `rangec = upper−lower`.
   - باندها: `upperBand = src + factor*rangec`، `lowerBand = src − factor*rangec` (با `factor = sensitivity = 2.8` پیش‌فرض، `kel_length=10`).
   - جهت مثلِ Supertrend کلاسیک با trailing باندها تعیین می‌شود.
   - **سیگنال:** `bull = crossover(close, supertrend)` → BUY؛ `bear = crossunder(close, supertrend)` → SELL.

2. **EMA Energy Ribbon:** ۱۵ EMA روی `high` با دوره‌های ۹ تا ۵۱ (گام ۳)؛ سبز اگر `close≥ema` وگرنه قرمز — تصویری از هم‌راستاییِ روند (نه سیگنالِ مستقل).

3. **Trend Catcher:** `crossover(EMA(close,10), EMA(close,20))` = روندِ صعودی/نزولی (تأییدِ ثانویه).

4. **ابزارِ TP/SL:** SL مبتنی بر **فرکتال** (`useFractal`)؛ برچسب/خطِ TP&SL روی چارت.

## ۳. ایدهٔ قابلِ آزمون برای پروژهٔ ما

**فرضیهٔ بک‌تست‌پذیر روی XAUUSD/EURUSD:**
1. Supertrendِ Keltner-محور را پیاده کن (`factor=2.8`, `kel_len=10`).
2. **ورود:** BUY در crossover، SELL در crossunder.
3. **فیلترِ هم‌راستایی:** فقط وقتی جهتِ Trend Catcher (EMA10 vs EMA20) با سیگنال هم‌جهت است (کاهشِ سیگنالِ خلافِ روند → افزایشِ WR).
4. **SL:** آخرین فرکتالِ مخالف؛ **TP:** `close ± 2×ATR(30)` (مطابقِ `y1/y2` در سورس).

## ۴. ارتباط با پرتفویِ فعلی

- **لبهٔ نو:** Supertrend-Keltner یک واریانتِ نسبتاً متمایز از Supertrendِ ATR-محورِ معمول است؛ می‌تواند لبهٔ تازه بدهد.
- **فیلترِ تأیید:** ✅ **Trend Catcher (EMA10/20)** یک فیلترِ ساده و آمادهٔ هم‌راستایی است که روی لایه‌های روندیِ سوخته قابلِ افزودن است.
- **ربط به سایت:** بخشِ فرکتال-SL و `2×ATR` TP مستقیماً به **کارتِ مدیریتِ معامله** (TP/SL متحرک) پروژه مربوط است و می‌تواند خامیِ آن بخش را بهبود دهد.

## ۵. نتیجهٔ بک‌تست

**N/A** — طبق User Note فقط md بررسی ساخته شد. **کاندیدِ باارزش** (سورسِ باز + منطقِ شفاف +
ابزارِ TP/SL) برای نشستِ تستِ آینده ثبت شد. Δ سودِ خالص = آزموده‌نشده.

_وضعیت: ✅ بررسی‌شده. سورسِ Pine کامل خوانده شد؛ منطقِ Supertrend-Keltner + Trend Catcher + فرکتال-SL استخراج و به فرضیهٔ بک‌تست‌پذیر ترجمه شد. موردِ بعدی بررسی می‌شود._
