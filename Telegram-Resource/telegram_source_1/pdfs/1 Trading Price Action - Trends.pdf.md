# بررسیِ منبع (کتاب): `1 Trading Price Action - Trends.pdf`

> قانونِ شمارهٔ ۱ پروژه: هدف فقط **سودِ خالصِ بیشتر** (XAUUSD + EURUSD) است؛ WR تابعِ
> هدف نیست و فقط کفِ ۴۰٪ برای هر لایه اجباری است.

> **این یک کتابِ مرجع (۴۷۹ صفحه) است.** طبق پروتکل، در یک نشست تمام نمی‌شود؛ هر
> فصل/مفهوم یک مرحلهٔ تحقیق است و این فایل به‌مرور کامل می‌شود.

---

## ۱. چیستی

- **نوع:** کتابِ مرجعِ Price Action.
- **عنوان:** _Trading Price Action TRENDS: Technical Analysis of Price Charts Bar by
  Bar for the Serious Trader_.
- **نویسنده:** **Al Brooks** (ناشر: John Wiley & Sons). یکی از معتبرترین منابعِ
  خواندنِ بار-به-بارِ (bar-by-bar) نمودار در جهان.
- **حجم:** ۴۷۹ صفحه، ۲۵+ فصل در ۴ بخش (Part I–IV).
- **دارایی/تایم‌فریمِ هدفِ سازنده:** روشِ عمومی (Brooks عمدتاً روی E-mini S&P 5-min
  کار می‌کند)، اما اصولِ price action دارایی-ناوابسته‌اند و روی هر بازار/تایم‌فریم
  قابلِ اعمال‌اند.

### فهرستِ فصل‌ها (برای برنامه‌ریزیِ نشست‌های آینده)
Part I: Trend Bars/Doji/Climaxes، Breakouts/Trading Ranges/Reversals، Signal Bars،
Reversal Bars. Part II+: Second Entries، Late/Missed Entries، Pattern Evolution،
Trend Lines، Channels، Micro Channels، Swing Points، Signs of Strength، **Two Legs**،
Spike and Channel، Trending Trading Range، Trend from the Open، Reversal Day،
Trend Resumption، Stairs (Broad Channel).

---

## ۲. منطقِ استخراج‌شده — **مرحلهٔ ۱: Bar Counting (High 1/2, Low 1/2)**

بخشِ «BAR COUNTING BASICS: HIGH 1, HIGH 2, LOW 1, LOW 2» (ص. حولِ خطِ ۳۱۲۰ متن).

**تعریفِ دقیق (نقلِ مکانیکیِ Brooks):**
- در یک **bull flag / pullback** (اصلاحِ کوتاهِ نزولی درونِ روندِ صعودی):
  - اولین باری که `high > high[۱]` باشد ⇒ **High 1** (پایانِ legِ اولِ اصلاح).
  - سپس legِ دومِ اصلاح پایین می‌آید؛ باری که **دوباره** `high > high[۱]` شود ⇒
    **High 2** = **سیگنالِ ورودِ Long** (ادامهٔ روندِ صعودی).
- قرینه در **bear flag** (اصلاحِ صعودی درونِ روندِ نزولی):
  - `low < low[۱]` ⇒ **Low 1**؛ تکرارِ آن پس از legِ دوم ⇒ **Low 2** =
    **سیگنالِ ورودِ Short**.
- **قابِ ABC:** High 2/Low 2 همان اصلاحِ ABC است — A=legِ اول، B=نقطهٔ High1/Low1،
  C=legِ دوم؛ شکستِ C همان entry bar است. «اصلاحِ دو-پایه» (two-legged pullback)
  یکی از قوی‌ترین ستاپ‌های ادامهٔ روند نزدِ Brooks است.

**شرطِ زمینه (context):** این ستاپ فقط در **روندِ برقرار** معتبر است (نه در
trading range). Brooks تأکید می‌کند High 2 در روندِ صعودیِ واضح باید گرفته شود.

---

## ۳. ایدهٔ قابلِ آزمون برای پروژهٔ ما

قاعدهٔ کاملاً مکانیکیِ **High-2 / Low-2 bar-counting** روی `XAUUSD_M15` و
`EURUSD_M15`:
- تعیینِ رژیمِ روند با یک فیلترِ ساده (مثلاً شیبِ EMA۵۰ یا EMA۲۰>EMA۵۰).
- در روندِ صعودی: شمارشِ pullback؛ ورودِ Long روی تشکیلِ High 2.
- در روندِ نزولی: ورودِ Short روی تشکیلِ Low 2.
- SL زیر/بالای extremeِ اصلاح؛ TP نسبتِ R چندگانه؛ گیتِ سخت‌گیرانه (net>0 +
  هر ۴ پنجره + WR≥۴۰٪).

این با pullbackهای موجودِ پروژه (که همه MA/S-R محورند) فرق دارد: اینجا **ساختارِ
شمارشِ بار** ملاک است، نه فاصله تا MA.

---

## ۴. ارتباط با پرتفویِ فعلی

- **لبهٔ نو (بالقوه):** منطقِ bar-countingِ ABC نیازموده است؛ ممکن است ورودِ
  دقیق‌تری از pullbackهای MA-محور بدهد.
- **فیلترِ تأیید (بالقوه):** «تشکیلِ High 2/Low 2» می‌تواند شرطِ تأییدِ ورود برای
  لایه‌های روندیِ موجود باشد و WR لایه‌های سوخته را بالا ببرد.

---

## ۵. نتیجهٔ بک‌تست (مرحلهٔ ۱)

⏳ **در حالِ اجرا** — کد در `strategies/` (High-2/Low-2 bar-counting) نوشته می‌شود و
نتیجه در همین بخش و در `results/` مستند می‌شود.

_وضعیت: بخشِ Bar-Counting (مرحلهٔ ۱ کتاب) بررسی و منطق استخراج شد؛ گامِ بعد =
بک‌تستِ «High-2 / Low-2»._
