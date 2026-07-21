# 🧩 راهنمای افزودنِ استراتژیِ جدید به APK

> ## 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> هدفِ پروژه فقط و فقط **«سودِ خالصِ بیشتر»** است — نه Win-Rate.
> تعریفِ رسمیِ سودِ خالص = **جمعِ سودِ دو ارز: XAUUSD + EURUSD**.
> WR فقط یک عددِ گزارشی است، نه هدف و نه قید.

---

## چرا این پوشه؟ (پاسخ به سؤالِ «آیا افزودنِ استراتژیِ جدید آسان است؟»)

**بله — کاملاً.** موتورِ APK (`engine.js`) اکنون یک **رجیستریِ استراتژی** است.
منطقِ تصمیم دیگر داخلِ یک تابعِ بزرگ hard-code نشده؛ هر استراتژی یک **فایلِ مستقل**
در همین پوشه است که خودش را در رجیستری ثبت می‌کند.

**افزودنِ استراتژیِ جدید = ۲ گام:**
1. یک فایلِ `.js` در این پوشه بساز.
2. یک خطِ `<script src="strategies/نامِ‌فایل.js">` در `index.html` (بعد از `engine.js`) اضافه کن.

هیچ نیازی به دستکاریِ `engine.js` نیست. ✅

---

## قالبِ استانداردِ یک استراتژی

```js
(function () {
  'use strict';
  window.GoldEngine.registerStrategy({
    id: 'my_new_strategy',              // شناسهٔ یکتا (انگلیسی، بدون فاصله)
    name: 'توضیحِ فارسیِ استراتژی',      // نامِ نمایشی در UI
    asset: 'XAUUSD',                     // 'XAUUSD' | 'EURUSD' | '*' (همه)
    enabled: true,                       // اختیاری؛ false = غیرفعال

    // evaluate یا یک تصمیمِ ENTRY برمی‌گرداند یا null (سیگنالی ندارم).
    evaluate: function (ctx) {
      // --- ctx شاملِ همهٔ اندیکاتورهای از پیش‌محاسبه‌شده است: ---
      // ctx.price, ctx.pricePrev  : قیمتِ بسته‌شدنِ کندلِ آخر و قبلی
      // ctx.midNow, ctx.midPrev   : میانهٔ سه‌MA (EMA50+EMA100+SMA200)/۳
      // ctx.e50, ctx.e200         : EMA50 و SMA200
      // ctx.rsiVal, ctx.atrVal    : RSI14 و ATR14
      // ctx.crossUp, ctx.crossDn  : آیا قیمت میانه را بالا/پایین قطع کرد؟
      // ctx.pip                   : اندازهٔ pip این دارایی
      // ctx.candles, ctx.closes, ctx.highs, ctx.lows, ctx.n
      // ctx.indicators            : dict آمادهٔ نمایش
      // helperها: ctx.r2, ctx.r5, ctx.distancePips
      //           ctx.SHORT_PARAMS, ctx.LONG_PARAMS
      //           ctx.EURUSD_ENTRY_HOUR, ctx.EURUSD_SL_PIP, ctx.EURUSD_TP_PIP

      if (/* شرطِ ورودِ تو اینجا */ false) return null;

      const p = ctx.price, pip = ctx.pip;
      return {
        state: 'ENTRY',
        side: 'long',                    // 'long' | 'short'
        headline: 'دلیلِ یک‌خطیِ ورود.',
        reasons: ['توضیحِ خطِ ۱', 'توضیحِ خطِ ۲'],
        entry: ctx.r2(p),
        sl: ctx.r2(p - 60 * pip),
        tp: ctx.r2(p + 400 * pip),
        instruction: 'به کاربر بگو چه‌کار کند.',
      };
    },
  });
})();
```

---

## چند نکتهٔ مهم

- **ترتیبِ اولویت:** استراتژی‌ها به ترتیبِ ثبت اجرا می‌شوند؛ **اولین** استراتژی‌ای که
  `ENTRY` بدهد برنده است. پس ترتیبِ `<script>`ها در `index.html` = اولویت.
- **بدونِ سیگنال:** اگر شرطِ ورود برقرار نیست، حتماً `null` برگردان.
- **مدیریتِ معامله (MANAGE):** توسطِ خودِ موتور به‌صورتِ مشترک انجام می‌شود؛ استراتژی
  فقط مسئولِ لحظهٔ **ورود** است.
- **سازگاری با پایتون:** اگر استراتژی معادلِ پایتونی دارد، حتماً با اسکریپت‌های
  `apk/_test/` صفر-اختلاف بودنش را بسنج (مثل کاری که برای سه استراتژیِ فعلی شد).

---

## استراتژی‌های فعالِ فعلی

| فایل | id | دارایی | ماشه |
|------|----|--------|------|
| `xau_midma_long.js` | `xau_midma_long` | XAUUSD | قطعِ صعودیِ میانهٔ سه‌MA (S67/S14) |
| `xau_midma_short.js` | `xau_midma_short` | XAUUSD | قطعِ نزولیِ میانهٔ سه‌MA (s118) |
| `eurusd_session_drift.js` | `eurusd_session_drift` | EURUSD | drift صعودیِ ساعتِ ۰ UTC (S73) |

> این سه استراتژی روی همان رکوردِ رسمیِ **+۹۵٬۶۴۵$** (XAUUSD+EURUSD) استوارند و
> خروجی‌شان **بایت‌به‌بایت** با موتورِ پایتونِ پروژه یکسان است (تأییدشده روی ۶۹۸۸ نمونه).
