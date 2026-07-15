# ربات MT5 — استراتژی ۱۴ (VWAP-Regime Selective ML)

این پوشه شامل **Expert Advisor کامل برای MetaTrader 5** است که استراتژی برندهٔ
پروژه (استراتژی ۱۴) را به‌صورت زنده اجرا می‌کند.

## خلاصهٔ استراتژی
- **جهت:** فقط LONG (خرید) — چون تحلیل نشان داد سمت SHORT در طلا edge ندارد.
- **فیلتر پایه:** `close > EMA50 > EMA200` (روند صعودی).
- **مغز تصمیم:** مدل یادگیری ماشین LightGBM (ensemble ۳ مدل) صادرشده به ONNX،
  که روی ۵۷ ویژگی (feature) کار می‌کند و احتمال موفقیت معامله را می‌دهد.
- **ورود:** وقتی احتمال مدل ≥ ۰.۶۸ باشد.
- **خروج:** TP = ۱.۰×ATR₁₄ | SL = ۱.۵×ATR₁₄ | حداکثر نگهداری ۴۸ کندل (۱۲ ساعت).

## نتایج بک‌تست (Out-of-Sample، Walk-Forward، ۱۹۴۷ معامله)
| معیار | مقدار |
|-------|-------|
| Win Rate | **۶۱.۵۸٪** ✅ (هدف >۶۰٪) |
| Expectancy | **+۰.۳۵$ / معامله** ✅ |
| معامله در روز | **۵.۲۸** ✅ (هدف ≥۳) |
| p-value | ۰.۰۸ ⚠️ (معناداری مرزی) |

## فایل‌های این پوشه
| فایل | توضیح |
|------|-------|
| `XAUUSD_S14_Robot.mq5` | **کد کامل Expert Advisor** (زبان MQL5) |
| `xauusd_s14_model.onnx` | مدل اصلی (seed=42) — برای حالت تک‌مدلی |
| `xauusd_s14_model_0/1/2.onnx` | سه مدل ensemble (seedهای ۴۲/۷/۱۲۳) |
| `model_meta.txt` | پارامترها (THR, TP, SL, WR, ...) |
| `feature_order.txt` | ترتیب دقیق ۵۷ feature |
| `train_export_final.py` | اسکریپت آموزش مدل و صادرات ONNX (بازتولیدپذیر) |
| `validate_parity.py` + `parity_reference.txt` | مرجع صحت feature برای بررسی MT5 |

## راهنمای نصب گام‌به‌گام در MetaTrader 5

### گام ۱: کپی فایل مدل ONNX
فایل‌های زیر را در پوشهٔ **Files** ترمینال کپی کنید:
```
<Data Folder>/MQL5/Files/xauusd_s14_model_0.onnx
<Data Folder>/MQL5/Files/xauusd_s14_model_1.onnx
<Data Folder>/MQL5/Files/xauusd_s14_model_2.onnx
<Data Folder>/MQL5/Files/xauusd_s14_model.onnx
```
> مسیر Data Folder را از منوی MT5: `File → Open Data Folder` پیدا کنید.

### گام ۲: کپی و کامپایل EA
1. فایل `XAUUSD_S14_Robot.mq5` را در `<Data Folder>/MQL5/Experts/` قرار دهید.
2. MetaEditor را باز کنید (F4 در MT5).
3. فایل را باز کرده و **Compile** (F7) بزنید. باید بدون خطا کامپایل شود.
   - نیازمند MT5 نسخهٔ جدید با پشتیبانی ONNX (build 3980 به بالا، سال ۲۰۲۳+).

### گام ۳: اجرا روی چارت
1. چارت **XAUUSD** با تایم‌فریم **M15** باز کنید.
2. EA را از پنجرهٔ Navigator روی چارت بکشید.
3. در تب Common تیک **Allow Algo Trading** را بزنید.
4. تنظیمات ورودی (Inputs) را بررسی کنید (پیش‌فرض‌ها مطابق استراتژی برنده‌اند).

### گام ۴: تست در Strategy Tester (توصیهٔ اکید قبل از حساب واقعی)
1. `View → Strategy Tester` (Ctrl+R).
2. Expert = `XAUUSD_S14_Robot`، Symbol = XAUUSD، Period = M15.
3. مدل «Every tick based on real ticks» و بازهٔ زمانی چند ماه اخیر.
4. نتایج را با نتایج بک‌تست پایتون (WR≈۶۱٪) مقایسه کنید.

## پارامترهای ورودی (Inputs)
| پارامتر | پیش‌فرض | توضیح |
|---------|---------|-------|
| `InpLotSize` | ۰.۰۱ | حجم ثابت هر معامله |
| `InpThreshold` | ۰.۶۸ | آستانهٔ احتمال مدل (کلید WR) |
| `InpTP_ATR` | ۱.۰ | ضریب TP |
| `InpSL_ATR` | ۱.۵ | ضریب SL |
| `InpMaxHoldBars` | ۴۸ | حداکثر نگهداری (کندل) |
| `InpMaxPositions` | ۳ | حداکثر معاملهٔ همزمان |
| `InpUseEnsemble` | true | میانگین ۳ مدل |

## ⚠️ نکات مهم صحت (پیش از استفادهٔ واقعی حتماً بخوانید)

### ۱. تفاوت حجم (Volume)
مدل با ستون `volume` دیتاست آموزش دیده؛ MT5 در حالت زنده از `tick_volume` استفاده
می‌کند. feature‌های `vol_ratio` و `vol_z20` ممکن است کمی متفاوت شوند. تأثیر معمولاً
کوچک است ولی باید در Strategy Tester تأیید شود.

### ۲. Timezone و مرز روز VWAP
VWAP لنگرشده از ابتدای هر **روز تقویمی** محاسبه می‌شود. دیتاست آموزش UTC بود؛ اگر
سرور بروکر شما timezone دیگری داشته باشد، مرز روز جابه‌جا می‌شود و VWAP کمی فرق می‌کند.
**توصیه:** عملکرد را در Strategy Tester بروکر خودتان اعتبارسنجی کنید.

### ۳. اعتبارسنجی feature-parity
پس از نصب، با `InpVerbose=true` مقادیر feature را در لاگ ببینید و با
`parity_reference.txt` (برای همان کندل‌ها) مقایسه کنید تا از یکسان‌بودن محاسبات
مطمئن شوید.

### ۴. معناداری آماری مرزی
p-value=۰.۰۸ کمی بالای ۰.۰۵ است. edge واقعی اما کوچک است (WR فقط ۱.۶٪ بالای
نقطهٔ سربه‌سر). **مدیریت ریسک محافظه‌کارانه** و شروع با حساب دمو الزامی است.

## بازتولید مدل
برای ساخت مجدد مدل ONNX از صفر:
```bash
pip install lightgbm scipy pandas numpy onnxmltools onnxconverter_common onnxruntime
python3 mt5_robot/train_export_final.py
```
