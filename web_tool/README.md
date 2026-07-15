# XAUUSD Live Tool — ابزار تحلیل زنده طلا 🪙

ابزار وب سبک که داده‌ی **زنده و به‌روز** طلا (XAUUSD) را دریافت می‌کند و بر پایه‌ی
**استراتژی برنده‌ی پروژه‌ی تحقیقاتی (S14: VWAP-Regime Selective ML، WR≈۶۱.۶٪)**
تحلیل لحظه‌ای، خطوط حمایت/مقاومت، سناریوی شکست و پیشنهاد معامله با درصد احتمال ارائه می‌دهد.

## قابلیت‌ها
- 🤖 **سیگنال واقعی مدل ONNX (دقیقاً معادل ربات):** همان ۳ مدل LightGBM‌ِ ensemble ربات MT5 با `onnxruntime-web` مستقیماً **در مرورگر** اجرا می‌شوند (نه تقریب).
- 📊 **تحلیل چند-تایم‌فریمی (H1/H4/D1):** روند هر تایم‌فریم و هم‌راستایی آن‌ها (bullish/bearish/mixed).
- 🌐 **منابع داده خارج از OHLCV:** شاخص دلار (DXY)، بازده اوراق ۱۰ساله (US10Y) و تقویم اخبار اقتصادی USD — با تفسیر سوگیری بنیادی طلا.
- 📡 **داده زنده:** دریافت کندل‌های M15 طلا از Yahoo Finance (`GC=F` طلای آتی COMEX) — بدون کلید API، تأخیر ~۱۵ دقیقه.
- 📈 **نمودار شمعی زنده** با خطوط حمایت، مقاومت و VWAP روزانه.
- 🧱 **سطوح کلیدی:** نزدیک‌ترین حمایت و مقاومت با «قدرت» (تعداد برخورد) — با الگوریتم Pivot(5,5) پروژه، بدون look-ahead.
- 🔀 **سناریوی شکست:** «اگر این سطح شکسته شود، روند احتمالی + درصد احتمال ادامه حرکت».
- 🔬 **موتور امتیازدهی شفاف (مکمل):** سهم هر عامل (RSI، ADX، VWAP، MACD، حجم و…) برای تفسیرپذیری تصمیم مدل.
- ⏱️ **بروزرسانی خودکار** هر ۶۰ ثانیه.

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
| `GET /api/health` | — | بررسی سلامت سرویس |
| `GET /api/candles` | `interval` (پیش‌فرض `15m`)، `range` (پیش‌فرض `1mo`؛ برای `15m` حداکثر `60d`) | کندل‌های خام (ورودی مدل ONNX مرورگر) |
| `GET /api/analysis` | `interval`، `range` | تحلیل کامل: سیگنال + S/R + سناریوی شکست + شاخص‌ها |
| `GET /api/mtf` | — | تحلیل چند-تایم‌فریمی H1/H4/D1 و هم‌راستایی روند |
| `GET /api/intermarket` | — | داده‌ی بین‌بازاری: DXY + بازده اوراق ۱۰ساله + سوگیری بنیادی طلا |
| `GET /api/news` | — | تقویم اخبار اقتصادی USD (ForexFactory) + پنجره‌ی ریسک |
| `GET /api/context` | — | ترکیب mtf + intermarket + news در یک فراخوان |

نمونه: `/api/analysis?interval=15m&range=1mo` ، `/api/context`

### منابع داده‌ی خارج از OHLCV (پاسخ به «کلید عبور از سقف ۶۸٪»)
- **DXY** (`DX-Y.NYB`) و **US10Y** (`^TNX`) از Yahoo Finance — طلا معمولاً با این دو رابطه‌ی معکوس دارد.
- **تقویم اقتصادی** از `nfs.faireconomy.media` (ForexFactory) — رویدادهای USD با سطح تأثیر High/Medium/Low.

این لایه‌ی بنیادی به معامله‌گر کمک می‌کند سیگنال فنی مدل را در بستر محیط بین‌بازاری و ریسک خبری ارزیابی کند.

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
