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

## ۵. نتیجهٔ بک‌تست (مرحلهٔ ۱) — ✅ پذیرفته شد (اولین لایهٔ price-action پروژه)

قاعدهٔ **High-2 / Low-2 bar-counting** روی `XAUUSD_M15` و `EURUSD_M15` آزموده شد
(۲ دارایی × ۲ جهت × ۲ جفت EMA × ۴ SL/TP × ۲ max_hold).

| دارایی | بهترین واریانت | net | WR | PF | حکم |
|---|---|---:|---:|---:|---|
| **XAUUSD** | long ema20/50 SL300/TP450 mh32 | **+$4,137** | ۴۸.۸٪ | ۱.۱۰ | ✅ **پذیرفته** |
| EURUSD | همه جهت‌ها | ruin (−$10k) | ۱۰–۲۴٪ | <۱ | ⛔ شکست |

**آزمون‌های پایداری (همه پاس):**
- walk-forward ۴-پنجره: W1..W4 **همه net مثبت** (+$411/+$104/+$825/+$2,641)، WR همه ≥۴۶٪.
- هر دو نیمه مثبت (h1=+$293، h2=+$3,844)؛ plateau: ۱۶/۳۲ واریانتِ طلا net مثبت.
- **لبهٔ مستقل تأییدشده:** ۴۳.۸٪ سیگنالِ خارج از پنجره‌های زمان-محور به‌تنهایی
  net=+$1,351، WR ۴۷.۳٪، PF ۱.۰۷ ⇒ لبهٔ ساختاریِ واقعی، نه بازتولیدِ لایه‌های موجود.

**ارتباط با پرتفوی:** لبهٔ نوِ ساختاری (اولین price-action bar-counting در سبد).
همپوشانیِ ۵۶٪ با لایه‌های زمان-محور ⇒ **تصمیمِ محافظه‌کارانهٔ ضدِ دوباره‌شماری:** فقط
سهمِ مستقلِ **+$1,351** به‌عنوان افزودهٔ رسمی ثبت شد. بخشِ همپوشان (WR ۵۰.۱٪) می‌تواند
به‌عنوان **فیلترِ تأیید** برای بالا بردنِ WR لایه‌های زمان-محورِ موجود به‌کار رود (راهِ اولِ پروژه).

- مستندِ کامل: [`results/S168_BrooksHigh2_NetProfit_+1351_ACCEPTED.md`](../../../results/S168_BrooksHigh2_NetProfit_+1351_ACCEPTED.md)
- کد: `strategies/s168_brooks_high2_low2.py` (+ walkforward/overlap/independent-edge validators)

**Δ سودِ خالصِ رسمی = +$1,351 ⇒ رکورد: +$221,895 → +$223,246.**

_وضعیت: ✅ **مرحلهٔ ۱ کتاب** (Bar-Counting) بررسی، بک‌تست و **پذیرفته** شد._

---

## ۶. مرحلهٔ ۲ کتاب — **CHAPTER 21: Spike and Channel Trend** — ⛔ رد شد

**منطقِ استخراج‌شده (نقلِ مکانیکیِ Brooks، فصلِ ۲۱):** هر روند دو فاز دارد — یک
**spike** (چند کندلِ روندِ قوی/شکافِ شکست، معمولاً در ساعتِ اولِ روز) و سپس یک
**pullback** کوتاه و بعد یک **channel**. قانونِ معاملاتیِ صریح: در bull channel
«**buy below the low of the prior bar**» و بخشی را برای swing نگه‌دار؛ هدفِ سود =
**measured move** (ارتفاعِ spike). این کاملاً از Bar-Counting (مرحلهٔ ۱) متفاوت است:
اینجا ملاک **ساختارِ دو-فازیِ spike→channel** است، نه شمارشِ pullback.

**ایدهٔ قابلِ آزمون:** تشخیصِ vectorized spike (پنجرهٔ کندلِ روندی با higher-high/low
و حرکتِ ≥ATR-mult)؛ ورودِ «زیرِ low کندلِ قبلی» در فازِ کانال؛ TP measured-move.

**ارتباط با پرتفوی و نتیجهٔ بک‌تست:**
- XAUUSD long: net کل **+$4,998** (WR ۴۹.۴٪، هر ۴ پنجره مثبت) — وسوسه‌انگیز.
- **اما همپوشانیِ ۴۶.۷٪ با لایه‌های زمان-محورِ موجود؛ سهمِ مستقل با TP ثابت فقط
  +$198 (PF ۱.۰۱ = بی‌لبه).** با measured-move سهمِ مستقل به +$2,660 رسید ولی
  **walk-forward همه را رد کرد** (W1/دورهٔ ۲۰۲۰ در همه واریانت‌ها منفی).
- EURUSD کاملاً شکست (مثلِ S168) — لبهٔ Brooks روی یورو تکرارپذیر نیست.

**حکم: ⛔ رد. Δ سودِ خالص = ۰. رکورد بدون تغییر = +$223,246.**
ارزشِ باقی‌مانده: بخشِ همپوشان می‌تواند در نشستِ آینده به‌عنوان **فیلترِ تأیید**
(راهِ اولِ پروژه) WR لایه‌های زمان-محورِ مرزی را بالا ببرد.

- مستندِ کامل: [`results/S169_BrooksSpikeChannel_NetProfit_223246_REJECTED.md`](../../../results/S169_BrooksSpikeChannel_NetProfit_223246_REJECTED.md)
- کد: `strategies/s169_brooks_spike_channel.py` (+ validate / measured_move / mm_walkforward)

_وضعیت: ✅ مرحلهٔ ۱ (Bar-Counting) پذیرفته + ✅ مرحلهٔ ۲ (Spike-and-Channel، فصل ۲۱)
بررسی و رد شد. فصل‌های باقی‌ماندهٔ کتاب برای نشست‌های آینده: **Signs of Strength (ف۱۹)،
Two Legs (ف۲۰)، Trend from the Open (ف۲۳)، Reversal/Trend-Resumption Day (ف۲۴/۲۵)،
Stairs/Broad Channel (ف۲۶)، Trend Lines/Channels (ف۱۳–۱۷)**._
