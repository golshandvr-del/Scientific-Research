# بررسیِ منبع: `Entry Signal-(Brother's Academy).txt`

> قانونِ شمارهٔ ۱: تابعِ هدف = **سودِ خالصِ بیشتر** (XAUUSD + EURUSD)؛ WR کفِ ۴۰٪ دارد.
> مشخصاتِ حساب: `CONTRACT_SIZE=100`، طلا `3.3pip`، کمیسیون=صفر.

---

## ۱. چیستی

| ویژگی | مقدار |
|---|---|
| **نوع** | **سورسِ بازِ Pine Script v5 (TradingView)** — 🟢 **کاملاً خوانا، بالاترین ارزشِ تحقیقاتی**. |
| **نام** | `Entry Signal (Brother's Academy)` — © `Brothers_FX_Trading` (MPL 2.0). |
| **داراییِ هدفِ سازنده** | عمومی (overlay روی هر نماد)؛ منطق قابلِ اعمال بر طلا/EURUSD. |
| **سورس** | ✅ **باز و کامل** — کلِ منطقِ scoring استخراج شد. |

## ۲. منطقِ استخراج‌شده (سیستمِ امتیازیِ صریح)

یک سیستمِ **multi-factor confidence scoring** (۰ تا ۱۰۰) با اجزای زیر:

**الف) روندِ LTF (EMA stack):**
- `bullTrend = EMA20 > EMA50 > EMA200` (+۲۵ امتیاز)
- `bearTrend = EMA20 < EMA50 < EMA200` (+۲۵)

**ب) روندِ HTF (H4=240):**
- `htfBull = close(H4) > EMA200(H4)` (+۲۰) / `htfBear` (+۲۰)

**ج) شکستِ ساختار (BOS):**
- `bosBull = close > highest(high,10)[1]` (+۱۵) / `bosBear = close < lowest(low,10)[1]` (+۱۵)

**د) Order Block / Breaker / Retest (تعاریفِ ساده‌شدهٔ price-action):**
- `bullOB = close[1]<open[1] and close>high[1]` (+۱۵)
- `bullBreaker = low<low[1] and close>high[1]` (+۱۵)
- `bullRetest = low<=low[1] and close>high[1]` (+۱۰) — و آینهٔ نزولیِ همه.

**هـ) RSI:** `rsi>55` (+۱۰) / `rsi<45` (+۱۰).

**سیگنالِ نهایی (بسیار مهم — قانونِ صریح):**
```
buySignal  = bullTrend AND (bullOB OR bullBreaker) AND bullRetest AND confidence≥70
sellSignal = bearTrend AND (bearOB OR bearBreaker) AND bearRetest AND confidence≥70
```

> **این طلاست:** یک قانونِ ورودِ کاملاً معین، بدونِ ابهام، بدونِ look-ahead (همه بر close/[1])، و **بک‌تست‌پذیرِ مستقیم**. علاوه بر این یک «آستانهٔ اطمینان» صریح دارد که می‌تواند به‌عنوان **درجهٔ اطمینانِ سیگنال در سایت** (حالت «نزدیک شدن به سیگنال» وقتی confidence بین ۵۰–۷۰ است) استفاده شود.

## ۳. ایدهٔ قابلِ آزمون برای پروژهٔ ما

> **دو کاربردِ مستقیم:**
> 1. **لایهٔ مستقل:** پیاده‌سازیِ دقیقِ `buySignal/sellSignal` بالا روی XAUUSD و EURUSD (EMA20/50/200 + HTF H4 + BOS10 + OB/Breaker/Retest + RSI). قانون معین است → بک‌تستِ تمیز.
> 2. **موتورِ امتیازِ اطمینان برای سایت:** خودِ `confidence 0–100` نگاشتِ طبیعی به چهار حالتِ کارت دارد: `<50`=خنثی، `50–70`=نزدیک شدن به سیگنال، `≥70`=ورود. این می‌تواند منطقِ نمایشیِ کارت‌ها را غنی کند.

## ۴. ارتباط با پرتفویِ فعلی

- **لبهٔ نو:** ✅ **بالقوه** — ترکیبِ خاصِ «EMA-stack + HTF + BOS + OB/Breaker + Retest + RSI با آستانهٔ ۷۰» یک امضای مشخص است؛ باید درصدِ هم‌پوشانی با لایه‌های trend/breakout موجود سنجیده شود.
- **فیلترِ تأیید:** ✅✅ **بسیار ارزشمند** — هر یک از اجزا (به‌ویژه شرطِ سه‌گانهٔ `trend AND structure AND retest`) فیلترِ تأییدِ قدرتمندی است که می‌تواند WR لایه‌های سوختهٔ trend/breakout را بالا ببرد.

## ۵. نتیجهٔ بک‌تست

**N/A در این نشست** (طبق User Note فقط ساختِ md). **کاندیدای درجه‌یک مرحلهٔ بعد** — قانونِ ورودِ معین و بک‌تست‌پذیر + موتورِ امتیازِ اطمینانِ مناسب برای منطقِ چهارحالتهٔ کارت‌های سایت.

_وضعیت: ✅ بررسی‌شده (md ساخته شد). سورسِ باز Pine؛ سیستمِ scoring صریح و بک‌تست‌پذیر — یکی از باارزش‌ترین منابعِ این بخش. موردِ بعدی: `FX PREMIUM ZONE MT5 @free_fx_pro`._
