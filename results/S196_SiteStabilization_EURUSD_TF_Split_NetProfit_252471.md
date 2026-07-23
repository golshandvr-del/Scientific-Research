# S196 — پایدارسازیِ سایت: بازیابیِ کارِ ازدست‌رفته + رفعِ باگِ حیاتی + تفکیکِ تایم‌فریمِ EURUSD

> **نوعِ نشست:** مهندسیِ محصول (نه کشفِ استراتژی).
> **سودِ خالصِ رکورد:** بدونِ تغییر = **+$252,471** (XAUUSD + EURUSD).
> **چرا سود تغییر نکرد؟** هیچ لایهٔ معاملاتیِ جدیدی اضافه/حذف نشد؛ فقط سایت پایدار و گسترش‌پذیر شد.

---

## ۱) زمینه: محیطِ ناپایدار کارِ نشستِ قبل را بلعید

طبقِ **HARD-RULE-SYSTEM DIRECTIVE** (checkpoint پس از هر تغییر)، در نشستِ قبل چند edit روی
`web_tool/src/index.tsx` انجام شده بود اما **پیش از commit، محیط ری‌ست شد** و کار از دست رفت.
هنگامِ ازسرگیری، وضعیتِ git این‌طور بود:

- آخرین commit موجود: `fcd9b79` — فقط آرایهٔ `ASSETS` را با کارت‌های `EURUSD-M15/M30/M1`
  (با `layer: 'placeholder'`) گسترش داده بود.
- اما `placeholderDecision`، branchِ `placeholder` در `decideAsset`، دریافتِ کندلِ
  per-timeframe (`tf`)، و `import type { RouterDecision }` **همگی غایب بودند**.
- ⇒ **کد در وضعیتِ شکسته بود**: کارت‌ها در ASSETS ثبت شده بودند ولی هیچ منطقی برای handle
  کردنشان وجود نداشت و `decideAsset` هنوز `15m` را هاردکد می‌کرد.

**درسِ روش‌شناختی (مهم برای نشست‌های بعد):** هرگز آرایهٔ پیکربندی (ASSETS) را در یک commit
جدا از منطقِ پشتیبانش commit نکن؛ commitِ «نیمه‌کاره» = کدِ شکسته روی محیطِ ناپایدار.

## ۲) بازسازی (rebuild)

سه edit روی `index.tsx` (هرکدام مطابقِ HARD-RULE جداگانه commit/push شد):

1. `import type { RouterDecision } from './router'` — بازگردانده شد.
2. `decideAsset`: به‌جای هاردکدِ `'15m'` حالا `tf = a.tf || '15m'` با `rangeFor`/`gapForTf`
   متناسبِ تایم‌فریم (M1 فقط ~۵ روز دادهٔ Yahoo دارد ⇒ range سبک‌تر). آستانهٔ دادهٔ
   placeholder سبک‌تر (۳۰ کندل به‌جای ۲۲۰) چون فقط داده/قیمت نمایش می‌دهد، نه تحلیلِ سنگین.
3. `placeholderDecision(a, result, tf)`: همیشه `NEUTRAL` با پیامِ صریحِ «در دستِ تحقیق» +
   چند شاخصِ پایه (RSI/ATR). type-safe مطابقِ `RouterDecision`.

## ۳) 🔴 باگِ حیاتی: کارتِ XAUUSD (M15) کاملاً کرش می‌کرد

پس از راه‌اندازیِ سرویس، تستِ `/api/decision` نشان داد:

```
XAUUSD | state = "MONDAY_ENTRY_HOURS is not defined"   ← کرش!
```

**ریشه:** در نشستِ قبل `timeGate` به لایهٔ **S140⁺⁺ (Monday)** در `router.ts` (خط ۴۳۵) اضافه
شده بود و به `MONDAY_ENTRY_HOURS` و `MONDAY_UTC_DAY` ارجاع می‌داد. این دو ثابت در
`monday_drift.ts` **export** شده بودند اما در بلوکِ `import { ... } from './monday_drift'`
داخلِ `router.ts` **گنجانده نشده بودند** ⇒ `ReferenceError` هنگامِ اجرا (نه هنگامِ build، چون
esbuild فقط bundle می‌کند و ارجاعِ سراسریِ حل‌نشده را runtime می‌گیرد).

**چرا خطرناک بود؟** این مهم‌ترین کارتِ پروژه است (XAUUSD M15 = خانهٔ لایه‌های رکوردساز
S67/S139/S140⁺⁺/S141/S143⁺⁺). کاربر عملاً کارتِ اصلی را از کار افتاده می‌دید.

**رفع:** افزودنِ `MONDAY_ENTRY_HOURS, MONDAY_UTC_DAY` به import block ⇒ کارت سالم شد
(state = NEUTRAL درست).

**درس:** build موفق ≠ کدِ سالم. برای Cloudflare Workers حتماً **runtime test**
(`curl /api/decision`) لازم است، نه فقط `npm run build`.

## ۴) تفکیکِ تایم‌فریمِ EURUSD (درخواستِ کاربر)

پیش از این EURUSD فقط یک کارتِ M5 داشت (لایهٔ S73). حالا هم‌ساختار با طلا:

| کارت | layer | tf | وضعیت |
|------|-------|----|-------|
| EURUSD | scalp | 5m | لایهٔ فعالِ S73 (Session-Open Drift) |
| EURUSD-M15 | placeholder | 15m | قالبِ خام — در دستِ تحقیق |
| EURUSD-M30 | placeholder | 30m | قالبِ خام — در دستِ تحقیق |
| EURUSD-M1 | placeholder | 1m | قالبِ خام — در دستِ تحقیق |

قالبِ خام صریحاً می‌گوید تا کشفِ لبه‌ای با **WR≥۴۰٪ و سودِ خالصِ مثبت** سیگنالِ ورود نمی‌دهد
(وفادار به قانونِ شمارهٔ ۱). این کارت‌ها **کاندیدای اصلیِ تحقیقِ بعدی‌اند** (راهِ سوم: یافتنِ
لایهٔ جدید برای تایم‌فریم‌های بازِ EURUSD).

## ۵) وقتِ ایران + شمارشِ معکوسِ زنده (تکمیلِ فرانت‌اند)

- `utcHourToIran` (UTC+3:30 ثابت — ایران از ۱۴۰۱ DST ندارد). تست: S73 (0 UTC)→۰۳:۳۰،
  S140⁺⁺ (18 UTC)→۲۱:۳۰، S139 (22 UTC)→۰۱:۳۰، S141/S164 (13 UTC)→۱۶:۳۰. ✅ همه درست.
- `msUntilGate` + `fmtCountdown` + `tickCountdowns` (تیکِ ۱ ثانیه‌ای) ⇒ کاربر «چند روز و
  HH:MM:SS تا فعال‌شدنِ سیگنال» را زنده می‌بیند. برای S164 (قیدِ روزِ ماه) countdown داده
  نمی‌شود چون قابلِ پیش‌بینیِ ساده نیست (پیامِ شفاف نمایش داده می‌شود).
- badgeِ «در دستِ تحقیق» (آیکنِ فلاسک) برای کارت‌های placeholder اضافه شد.

## ۶) تستِ نهایی

```
XAUUSD       | swing       | NEUTRAL     ✅ (باگ رفع شد)
XAUUSD-M5    | scalp       | NEUTRAL     ✅
EURUSD       | scalp       | NEUTRAL     | timeGate[0h, open=false] ✅
EURUSD-M15   | placeholder | NEUTRAL     ✅
EURUSD-M30   | placeholder | NEUTRAL     ✅
EURUSD-M1    | placeholder | NEUTRAL     ✅
```

- فرانت‌اند: هیچ خطای JS (فقط warning استانداردِ Tailwind CDN). `.asset-card` رندر شد.
- `/api/decision`: هر ۶ کارت سالم.

## ۷) تصمیم

**پذیرش (محصول).** سود خالص بدون تغییر (+$252,471). سایت حالا پایدار، بدونِ کرش، و
گسترش‌پذیر است. کاندیدای تحقیقِ بعدی: پُر کردنِ کارت‌های placeholderِ EURUSD با لایهٔ
اثبات‌شده، یا ادامهٔ بررسیِ منابعِ `Telegram-Resource`.
