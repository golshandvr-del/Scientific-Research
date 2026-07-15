# XAUUSD Live Tool — ابزار تحلیل زنده طلا 🪙

ابزار وب سبک که داده‌ی **زنده و به‌روز** طلا (XAUUSD) را دریافت می‌کند و بر پایه‌ی
**استراتژی برنده‌ی پروژه‌ی تحقیقاتی (S14: VWAP-Regime Selective ML، WR≈۶۱.۶٪)**
تحلیل لحظه‌ای، خطوط حمایت/مقاومت، سناریوی شکست و پیشنهاد معامله با درصد احتمال ارائه می‌دهد.

## قابلیت‌ها
- 📡 **داده زنده:** دریافت کندل‌های M15 طلا از Yahoo Finance (`GC=F` طلای آتی COMEX) — بدون کلید API، تأخیر ~۱۵ دقیقه.
- 📈 **نمودار شمعی زنده** با خطوط حمایت، مقاومت و VWAP روزانه.
- 🎯 **پیشنهاد معامله:** جهت (LONG/منتظر)، نقطه ورود، TP، SL و **درصد احتمال موفقیت** (کالیبره‌شده به بازه تجربی WR پروژه).
- 🧱 **سطوح کلیدی:** نزدیک‌ترین حمایت و مقاومت با «قدرت» (تعداد برخورد) — با الگوریتم Pivot(5,5) پروژه، بدون look-ahead.
- 🔀 **سناریوی شکست:** «اگر این سطح شکسته شود، روند احتمالی + درصد احتمال ادامه حرکت».
- 🔬 **تفکیک شفاف تصمیم:** سهم هر عامل (RSI، ADX، VWAP، MACD، حجم و…) در احتمال نهایی نمایش داده می‌شود.
- ⏱️ **بروزرسانی خودکار** هر ۶۰ ثانیه.

## معماری فنی
- **Backend:** Hono روی Cloudflare Pages/Workers (Edge).
- **موتور تحلیل (TypeScript):** بازتولید دقیق ماژول‌های پایتونِ پروژه:
  - `src/indicators.ts` ← `engine/indicators.py` (RSI, ATR, MACD, ADX, Bollinger, Stoch, z-score, slope…)
  - `src/structure.ts` ← `engine/structure.py` (Pivot + سطوح S/R فعال با ادغام و انقضا)
  - `src/signal.ts` ← منطق feature و رژیمِ استراتژی S14 (`engine/features.py` + `results/VWAP_Regime_Selective_ML_BE60_62.md`)
- **Frontend:** HTML + TailwindCSS (CDN) + Chart.js (candlestick financial) — فارسی/RTL.

### ⚠️ نکته علمی صادقانه درباره‌ی «سیگنال»
مدل نهاییِ استراتژی S14 یک **LightGBM ensemble (ONNX)** است که در محیط MT5 اجرا می‌شود.
اجرای مدل ML در سرور لبه‌ی Cloudflare ممکن نیست؛ بنابراین این ابزار از یک
**«موتور امتیازدهی احتمالی شفاف»** استفاده می‌کند که بر همان feature‌ها و همان
قواعد رژیمِ S14 بنا شده و خروجی‌اش به بازه‌ی تجربی Win Rate پروژه (~۵۸–۶۶٪) کالیبره
شده است. این یک **تقریب قابل‌توضیح** از سیگنال مدل است، نه خودِ مدل ONNX. برای
سیگنال دقیقِ مدل، از ربات MT5 در `../mt5_robot/` استفاده کنید.

## API
| مسیر | پارامتر | توضیح |
|------|---------|-------|
| `GET /api/health` | — | بررسی سلامت سرویس |
| `GET /api/candles` | `interval` (پیش‌فرض `15m`)، `range` (پیش‌فرض `1mo`) | کندل‌های خام |
| `GET /api/analysis` | `interval`، `range` | تحلیل کامل: سیگنال + S/R + سناریوی شکست + شاخص‌ها |

نمونه: `/api/analysis?interval=15m&range=1mo`

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
