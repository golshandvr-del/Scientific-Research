# سایتِ دستیارِ تصمیمِ چند-دارایی 🧭

> ## ⚠️ معیارِ موفقیت (پارادایمِ فعلی — RQS+) — مرجع: [`../docs/RQS_ROBUST_QUALITY_SCORE.md`](../docs/RQS_ROBUST_QUALITY_SCORE.md)
> معیارِ رسمیِ پذیرش/ردِ هر لایه اکنون **`RQS+ ≥ ۸۰٪`** است (نه سودِ خالص و نه WR). هر لایه باید
> از **۶ گیتِ veto** (WR≥۶۰ ، edge با p<0.05 ، PF≥۱.۳ ، maxDD≤۸٪ و MCL≤۸ ، walk-forward ۴/۴ ،
> expectancy>۰.۵×spread) عبور کند و نمرهٔ وزنیِ ≥۸۰٪ بگیرد.
> این سایت یک **دستیارِ تصمیمِ چند-دارایی و ۴-حالته** است: برای هر کارت (ترکیبِ جفت‌ارز×تایم‌فریم)
> یک ماشینِ حالتِ **خنثی → نزدیک‌شدن به سیگنال → ورود (TP/SL) → مدیریتِ معامله**. پشتِ صحنه یک
> **رجیستریِ ماژولار** (`src/strategy_registry.ts` → `runCard`) لایه‌های احیاشدهٔ همان کارت را اجرا
> و تصمیمِ نهایی را انتخاب می‌کند؛ کاربر فقط تصمیمِ نهایی را می‌بیند. گذارِ ورود→مدیریت وابسته به
> ثبتِ معاملهٔ کاربر است.

> ## 🧩 معماریِ فعلی: رجیستریِ ماژولارِ لایه‌های احیاشده (RQS+ ≥ ۸۰٪)
> مغزِ تصمیم از استراتژی‌های تک‌تکِ قدیمی (S63/S66/S164 …) به یک رجیستریِ ماژولار منتقل شد:
> - **`src/revived_strategies.ts`** — ۶ لایهٔ بی‌ماژول (S321/S322/S323/S324/S328/S330) + آداپترِ
>   مشترکِ `rawToDecision` (خامِ سیگنال → تصمیمِ ۴-حالته).
> - **`src/strategy_registry.ts`** — جدولِ `CARD_LAYERS` (کارت→لایه‌های ACCEPTED) + تابعِ `runCard`
>   (اجرای همهٔ لایه‌های کارت، انتخابِ تصمیمِ اصلی بر پایهٔ رتبهٔ حالت + probability، جمعِ لایه‌های
>   هم‌جهت در `otherLayers`).
>
> **۷ کارتِ فعال و لایه‌های ACCEPTED:**
>
> | کارت | لایه‌ها |
> |------|---------|
> | XAUUSD-M5  | S330·S328·S327·S326 |
> | XAUUSD-M15 | **S332**·S324·S322·S323·S310·S312 |
> | XAUUSD-M30 | S313·S324·S321·S327·S326·S323·S312 |
> | XAUUSD-H1  | S313·S328·S327·S323·S312 |
> | XAUUSD-H4  | **S332**·S327 |
> | EURUSD-M15 | S326 |
> | EURUSD-M30 | S327 |
>
> افزودنِ کارت/لایهٔ جدید **فقط این دو جدول** را تغییر می‌دهد (ماژولار/توسعه‌پذیر). روترهای قدیمی
> (`router.ts`/`eurusd_router.ts`/`gold_*_router.ts`) دیگر در مسیرِ تصمیم نیستند؛ فقط `computeLots`
> و `manageGoldM5Scalp` هنوز از آن‌ها استفاده می‌شود.

> ### 🧹 بازطراحیِ کامل (User Note)
> UI فقط شاملِ کارتِ هر دارایی با **یک باکسِ ماشینِ حالتِ ۴-وضعیتی** + جدولِ اختیاریِ شاخص‌هاست
> (برای شفافیت). هیچ نمودار، بخشِ تحقیقی، سودِ خالص، یا اطلاعاتِ اضافه به کاربر نشان داده نمی‌شود.
> در حالتِ ENTRY/APPROACHING، **لایه‌های هم‌جهتِ همزمان** (`otherLayers`) به‌صورتِ تاشو نمایش داده
> می‌شوند و در هر حالت (حتی NEUTRAL) **لایهٔ ناظر** (`sourceLayer`) ذکر می‌شود.

> ## 🧠 معماریِ ماژولارِ گره‌محور (ROS2-مانند — طبقِ [`../webplan.md`](../webplan.md))
> سایت در حالِ بازچیده‌شدن به گره‌های مستقل با **قراردادِ پیامِ نسخه‌دار** است. روشِ ایمن:
> **Strangler-Fig** — هر گره به‌صورتِ *افزودنی* اضافه می‌شود و یک **هارنسِ تستِ برابری**
> (`tools/decision_parity.mjs`، hashِ طلایی `bf0615639cd1e59d`) تضمین می‌کند خروجیِ `/api/decision`
> بیت‌به‌بیت ثابت بماند.
>
> | گره | مسیر | قرارداد | کار | حالت |
> |---|---|---|---|---|
> | 🚌 EventBus | `src/bus/` | — | pub/sub رویدادها (`bar.closed@…`) — پلِ replay↔live | فعال |
> | 💹 Price Feed | `src/price/` | `PriceFeed@v1` | تغذیهٔ قیمت + `HistoryStore` (Disk/Memory) + Heartbeatِ کهنگی | فعال |
> | 📊 Indicators | `src/indicators/` | `IndicatorSnapshot@v1` | رجیستریِ کش‌دارِ ۱۴ اندیکاتور (شاملِ Alligator/GMMA/Ichimoku) | فعال |
> | 🛰️ Regime Radar | `src/regime/` | `RegimeInfo@v1` | تشخیصِ رژیم با آستانه‌های خودکالیبرِ صدکیِ per-TF | **سایه‌ای** |
> | ⚙️ Runtime | `src/runtime/` | `CardDecision@v1` | مرزِ رسمیِ اجرای لایه‌ها (`runCardTyped`) | فعال |
> | 🏛️ Layer Council | `src/council/` | `CouncilVerdict@v1` | رأی‌گیریِ اجماعی (اجماع/اکثریت/تضاد) | **سایه‌ای** |
> | 📒 Live RQS Ledger | `src/ledger/` | `LiveRqs@v1` | RQS+ زنده از نتیجهٔ واقعیِ کاربر + بایگانیِ خودکار (`/api/ledger/*`) | فعال |
> | 🔬 Indicator Scanner | `src/scanner/` | `ScanReport@v1` | همبستگیِ Spearman اندیکاتور↔حرکتِ بعدی + p-value ⇒ کاندیدِ احیا (`/api/scanner/*`) | **پژوهشی** |
> | 🟧 UI Badges | `public/static/ui/` | — | نوارِ heartbeat + نشانِ شورا | فعال |
>
> **حالتِ سایه‌ای:** گره‌های رژیم/شورا در پاسخِ `/api/decision` به‌صورتِ فیلدهای `regime`/`council`
> گزارش می‌شوند اما **تصمیم را تغییر نمی‌دهند** (تصمیمِ نهایی هنوز `runCard` است).
> **حالتِ پژوهشی:** کاوشگرِ اندیکاتور فقط از `/api/scanner/:asset?tf=&horizon=` فراخوانده می‌شود و
> گزارشِ آماری برای AI/تحقیق برمی‌گرداند؛ روی صفحه یا تصمیمِ کاربر اثری ندارد (علیهِ اشتباهِ رایجِ #۳).

## قابلیت‌ها
- 🧭 **چهار حالتِ تصمیم برای هر کارت** (رجیستریِ ماژولار، `runCard`):
  - **خنثی:** صراحتاً می‌گوید وارد نمی‌شود + دلیل + **لایهٔ ناظر** (`sourceLayer`) با اعداد.
  - **نزدیک‌شدن به سیگنال:** ستاپ در حالِ شکل‌گیری + فهرستِ تأییدهایِ موردِ انتظار + درصدِ اطمینان.
  - **ورود:** جهت (Long/Short) + TP + SL + R:R + درصدِ اطمینان + حجمِ لاتِ سرمایه‌محور +
    **لایه‌های هم‌جهتِ همزمان** (`otherLayers`، تاشو) + دکمهٔ «معامله را ثبت کردم».
  - **مدیریتِ معامله:** فقط پس از ثبتِ کاربر؛ سود/زیان (R)، پیشرفت به TP، و توصیه‌های زندهٔ
    SL/TP/بستن (با اعمالِ تک‌کلیکی). TP/SL متحرکِ هم‌خوان با پلنِ همان لایه.
- 🪙 **۷ کارت (جفت‌ارز×تایم‌فریم):** XAUUSD در M5/M15/M30/H1/H4 و EURUSD در M15/M30 — هر کارت لایه‌های
  احیاشدهٔ ACCEPTED خودش را دارد (RQS+ ≥ ۸۰٪). هر لایه TP/SL مخصوصِ همان تایم‌فریم را دارد (نه اعدادِ رند/یکسان).
- ⚙️ **حسابِ مرجع:** CONTRACT_SIZE=۱۰۰ ، spread=۰.۳۳$/oz ، کمیسیون=۰ ، مارجین=۴۰$/لات (BUG-002/003/014 رفع‌شد).
- 📡 **داده زنده:** کندل از Yahoo Finance (طلا `GC=F` + rebase به spot؛ EURUSD مستقیم).
- 🔬 **جدولِ شفافیت (اختیاری/تاشو):** مقادیرِ کلیدیِ تصمیم (روند، ER، ADX، proba، RSI، ATR).
- 💾 **ذخیرهٔ معامله در localStorage** (مقاوم به رفرش)، حذف فقط با دکمهٔ «بستنِ معامله».
- ⏱️ **بروزرسانی خودکار** تصمیم هر ۳۰ ثانیه و قیمت با polling سریع‌تر.
- 📅 **S164 ماه‌پایان EURUSD:** تشخیص روز کاری باقی‌مانده تا پایان ماه، هشدار نزدیک‌شدن در ۱۲ UTC و Entry Short در ۱۳ UTC.
- 🧹 **حذف‌شده‌ها (بازطراحی):** نمودار شمعی، اجرای ONNX در مرورگر، بخشِ «وضعیتِ تحقیقِ
  علمی»، تحلیلِ MTF/بین‌بازاری/اخبار در UI، و همهٔ اطلاعاتِ اضافه. UI فقط تصمیمِ نهایی است.

## معماری فنی
- **Backend:** Hono روی Cloudflare Pages/Workers (Edge).
- **موتور تحلیل (TypeScript):** بازتولید دقیق ماژول‌های پایتونِ پروژه:
  - `src/indicators.ts` ← `engine/indicators.py` (RSI, ATR, MACD, ADX, Bollinger, Stoch, z-score, slope…)
  - `src/structure.ts` ← `engine/structure.py` (Pivot + سطوح S/R فعال با ادغام و انقضا)
  - `src/features.ts` ← `engine/features.py` (بازتولید دقیق ۵۷ feature ورودی مدل، بدون look-ahead)
  - `src/signal.ts` ← موتور امتیازدهی شفاف برای تفسیرپذیری
  - `src/external.ts` ← MTF (H1/H4/D1) + بین‌بازاری (DXY/TNX) + تقویم اخبار
- **مدل ONNX (مرورگر):** `src/browser/signal_client.ts` (باندل `esbuild` → `public/static/browser-signal.js`)
  با `onnxruntime-web` (WASM) از CDN؛ مدل‌ها در `public/static/models/`.
- **Frontend:** HTML + TailwindCSS (CDN) + Chart.js (candlestick financial) — فارسی/RTL.
- **ابزار اعتبارسنجی:** `tools/export_parity_reference.py` (مرجع پایتون) و `tools/verify_parity.mjs` (آزمون TS↔Python).

### ✅ اجرای واقعی مدل ONNX در مرورگر (نه تقریب)
در نسخه‌ی پیشین، اجرای مدل ML در سرور لبه ممکن نبود و از یک تقریب امتیازدهی استفاده می‌شد.
**اکنون این محدودیت رفع شده است:** هر ۳ فایل مدلِ ensemble ربات
(`xauusd_s14_model_{0,1,2}.onnx`) با کتابخانه‌ی **`onnxruntime-web` (WASM)** مستقیماً در
**مرورگر کاربر** بارگذاری و اجرا می‌شوند.

جریان کار (فایل `src/browser/signal_client.ts` → باندل `public/static/browser-signal.js`):
1. کندل‌های زندهی M15 (~۴۰۰۰–۵۷۰۰ کندل، ۶۰ روز) از `/api/candles` دریافت می‌شوند.
2. `buildFeatures` (فایل `src/features.ts`) دقیقاً معادل `engine/features.py` ۵۷ feature می‌سازد.
3. هر ۳ مدل ONNX روی بردار feature اجرا و میانگینِ احتمال کلاس «برد» گرفته می‌شود.
4. تصمیم LONG/NONE با آستانه‌ی `THR=0.68` + شرط رژیم صعودی — دقیقاً منطق ربات MT5.

**اعتبارسنجی parity:** خروجی TS+ONNX در برابر مرجع پایتون روی ۲۰۰۰ کندل آزمون شد:
- اختلاف feature‌ها: ~`3.6e-6` (فقط خطای گرد‌کردن float32)
- تطابق رژیم: **۱۰۰٪**
- تطابق تصمیم نهایی LONG/NONE: **۹۹.۶۵٪** (تنها ۷ اختلاف در کندل‌هایی که احتمال دقیقاً روی مرز ۰.۶۸ است)

این دیگر یک تقریب نیست — **خودِ مدل ربات** است که در مرورگر اجرا می‌شود.
«موتور امتیازدهی شفاف» همچنان وجود دارد اما فقط برای **تفسیرپذیری** (توضیح سهم عوامل)؛ تصمیم نهایی با مدل واقعی ONNX است.

## API
| مسیر | پارامتر | توضیح |
|------|---------|-------|
| `GET /api/assets` | — | فهرستِ فوریِ متادیتای ۷ کارت (میلی‌ثانیه‌ای — برای اسکلتِ کارت‌ها) |
| `GET /api/decision` | — | تصمیمِ ۴-حالتهٔ **همهٔ ۷ کارت** یک‌جا (موازی، مقاوم به خطای هر کارت) |
| `GET /api/decision/:asset` | `asset` ∈ {XAUUSD-M5, XAUUSD, XAUUSD-M30, XAUUSD-H1, XAUUSD-H4, EURUSD-M15, EURUSD-M30} | تصمیمِ یک کارت (از `runCard`) |
| `POST /api/trade/advice` | body: `{ asset, trade:{side,entry,tp,sl}, modelProbPct? }` | مدیریتِ معاملهٔ باز (حالت ۴) برای دارایی مشخص |
| `GET /api/health` | — | بررسی سلامت سرویس |
| `GET /api/candles` | `interval`,`range` | (قدیمی/داخلی) کندل‌های خامِ طلا |
| `GET /api/analysis` | `interval`,`range` | (قدیمی/داخلی) تحلیلِ کاملِ طلا |

نمونه: `/api/decision` ، `/api/decision/EURUSD`

> نکته: endpointهای قدیمیِ `/api/mtf`، `/api/intermarket`، `/api/news`، `/api/context`
> و `/api/spot` هنوز در backend موجودند اما دیگر در UI استفاده نمی‌شوند (بازطراحی).

## اجرای محلی (سندباکس)
```bash
cd web_tool
npm install
npm run build
pm2 start ecosystem.config.cjs      # اجرا روی پورت 3000
curl http://localhost:3000/api/health
```

## اجرا روی سرور مجازی / هاست خودتان
این پروژه Cloudflare Pages است، اما روی هر جای دیگری هم به‌سادگی اجرا می‌شود:

**گزینه ۱ — دیپلوی رایگان روی Cloudflare Pages (پیشنهادی):**
```bash
cd web_tool
npm run build
npx wrangler pages deploy dist --project-name xauusd-live-tool
```

**گزینه ۲ — روی VPS/هاست خودتان با Node:**
```bash
cd web_tool
npm install && npm run build
# اجرای دائم با PM2:
pm2 start "npx wrangler pages dev dist --ip 0.0.0.0 --port 3000" --name gold-tool
```
سپس با یک reverse proxy (Nginx/Caddy) روی دامنه‌ی خودتان قرار دهید.

> اگر Yahoo از IP سرور شما محدود شد، می‌توانید در `src/index.tsx` تابع `fetchGold`
> را به یک provider دیگر (مثلاً Twelve Data با کلید رایگان، یا بروکر خودتان) تغییر دهید.

## سلب مسئولیت
این ابزار صرفاً برای **تحقیق علمی** است و **توصیه‌ی مالی نیست**. معامله در بازار با ریسک همراه است.
