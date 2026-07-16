# 🤖 ربات MT5 — معماری «روتر سه‌مغزی» (هم‌گام با پروژه)

این پوشه شامل **Expert Advisor کامل برای MetaTrader 5** است که همان تصمیم‌گیری
سایتِ تحلیل زندهٔ پروژه (`web_tool/`) را در متاتریدر بازتولید می‌کند.

> **نسخهٔ فعال و توصیه‌شده:** `XAUUSD_ThreeBrain_Robot.mq5` (v2.0)
> نسخهٔ قدیمی `XAUUSD_S14_Robot.mq5` (تک‌مغز، LONG-only) صرفاً برای **مرجع تاریخی**
> نگه داشته شده و دیگر توصیه نمی‌شود.

---

## 🧠 معماری روتر سه‌مغزی

ربات در هر کندل بسته‌شدهٔ M15 ابتدا **رژیم بازار** را تشخیص می‌دهد و سپس مغز
مناسب را صدا می‌زند — دقیقاً مثل معماری تصمیم سایت:

| رژیم | شرط | مغز فعال | جهت |
|------|-----|----------|-----|
| صعودی | `close > EMA50 > EMA200` | **S25** (ML + Weekly-Reversion) | LONG |
| نزولی | `close < EMA50 < EMA200` | **Bear/S31** (Bear-Specialist) | SHORT |
| رنج | هیچ‌کدام | — | بدون معامله |

هر مغز یک **ensemble ۳-seed از LightGBM** است که به ONNX صادر شده و روی
**۵۹ feature** (۵۷ پایه + `early_atr` + `weekly_rev`) کار می‌کند. این دقیقاً همان
مجموعهٔ feature است که در `engine/features.py` ساخته می‌شود.

## 📊 نتایج بک‌تست (OOS، Walk-Forward، ورود open بعدی، اسپرد ۰.۲$)

| مغز | استراتژی مبنا | Win Rate | Expectancy | PF | p-value | فایل نتیجه |
|-----|----------------|----------|------------|-----|---------|-----------|
| صعودی | S25 | **۶۲.۳٪** ✅ | +۰.۵۴$ | ~۱.۱۴ | **۰.۰۱۵** ✅ | `results/ML_WeeklyReversion_Context_62.md` |
| نزولی | Bear/S31 | ۵۸.۴٪ | **+۱.۷۱$** | **۱.۴۹** ✅ | ۰.۰۱۵ ✅ | `results/Bear_Specialist_Brain_Downtrend_58.md` |

> ترکیب دو مغز در رژیم‌های ناهمبسته، فرکانس معامله را جمع می‌کند (رجوع به
> `results/BullBear_DualMechanism_Portfolio_58.md`, tpd رکورد پروژه = ۴.۲۴).

---

## 📁 فایل‌های این پوشه

### نسخهٔ فعال (v2 — سه‌مغزی)
| فایل | توضیح |
|------|-------|
| `XAUUSD_ThreeBrain_Robot.mq5` | **EA فعال** — روتر سه‌مغزی (S25 + Bear) |
| `xauusd_s25_model_0/1/2.onnx` | ensemble مغز صعودی (S25) |
| `xauusd_bear_model_0/1/2.onnx` | ensemble مغز نزولی (Bear/S31) |
| `model_meta_s25.txt` | پارامترهای مغز صعودی |
| `model_meta_bear.txt` | پارامترهای مغز نزولی |
| `feature_order_s25.txt` | ترتیب دقیق ۵۹ feature (صعودی) |
| `feature_order_bear.txt` | ترتیب دقیق ۵۹ feature (نزولی) — یکسان با صعودی |
| `train_export_s25.py` | آموزش/صادرات مدل صعودی (بازتولیدپذیر) |
| `train_export_bear.py` | آموزش/صادرات مدل نزولی (بازتولیدپذیر) |

### مرجع تاریخی (v1 — تک‌مغز S14)
| فایل | توضیح |
|------|-------|
| `XAUUSD_S14_Robot.mq5` | EA قدیمی LONG-only (WR=۶۱.۶٪، p=۰.۰۸ مرزی) |
| `xauusd_s14_model_0/1/2.onnx` | ensemble مدل S14 |
| `model_meta.txt`, `feature_order.txt` | متادیتای S14 (۵۷ feature) |
| `train_export_final.py` | آموزش/صادرات S14 |

### ابزار اعتبارسنجی
| فایل | توضیح |
|------|-------|
| `validate_parity.py` + `parity_reference.txt` | مرجع صحت feature برای بررسی محاسبات MT5 |

---

## 🚀 راهنمای نصب گام‌به‌گام در MetaTrader 5

### گام ۱: کپی فایل‌های مدل ONNX
مسیر Data Folder را از `File → Open Data Folder` پیدا کنید و شش فایل مدل نسخهٔ
فعال را در `MQL5/Files/` کپی کنید:
```
MQL5/Files/xauusd_s25_model_0.onnx
MQL5/Files/xauusd_s25_model_1.onnx
MQL5/Files/xauusd_s25_model_2.onnx
MQL5/Files/xauusd_bear_model_0.onnx
MQL5/Files/xauusd_bear_model_1.onnx
MQL5/Files/xauusd_bear_model_2.onnx
```

### گام ۲: کپی و کامپایل EA
1. `XAUUSD_ThreeBrain_Robot.mq5` را در `MQL5/Experts/` قرار دهید.
2. MetaEditor را باز کنید (F4)، فایل را باز کرده و **Compile** (F7) بزنید.
   - نیازمند MT5 با پشتیبانی ONNX (build 3980 به بالا، ۲۰۲۳+).

### گام ۳: اجرا روی چارت
1. چارت **XAUUSD** تایم‌فریم **M15** باز کنید.
2. EA را از Navigator روی چارت بکشید.
3. تیک **Allow Algo Trading** را بزنید.

### گام ۴: تست در Strategy Tester (اکیداً پیش از حساب واقعی)
- `View → Strategy Tester` (Ctrl+R)، Symbol=XAUUSD، Period=M15،
  مدل «Every tick based on real ticks»، بازهٔ چند ماه اخیر.
- نتایج را با بک‌تست پایتون (WR≈۶۲٪ صعودی، ۵۸٪ نزولی) مقایسه کنید.

## ⚙️ پارامترهای ورودی (Inputs)

| گروه | پارامتر | پیش‌فرض | توضیح |
|------|---------|---------|-------|
| عمومی | `InpLotSize` | ۰.۰۱ | حجم ثابت هر معامله |
| صعودی | `InpEnableBull` | true | فعال‌سازی مغز صعودی |
| صعودی | `InpBullThreshold` | ۰.۶۸ | آستانهٔ احتمال (کلید WR) |
| صعودی | `InpBullTP_ATR` / `InpBullSL_ATR` | ۱.۰ / ۱.۵ | ضرایب TP/SL |
| نزولی | `InpEnableBear` | true | فعال‌سازی مغز نزولی |
| نزولی | `InpBearThreshold` | ۰.۶۶ | آستانهٔ احتمال |
| نزولی | `InpBearTP_ATR` / `InpBearSL_ATR` | ۱.۴ / ۱.۷ | ضرایب TP/SL (نامتقارن، منبع PF بالا) |
| مدیریت | `InpMaxHoldBars` | ۴۸ | حداکثر نگهداری (کندل) |
| مدیریت | `InpMaxPositions` | ۳ | حداکثر معاملهٔ همزمان |

## ⚠️ نکات مهم صحت (پیش از استفادهٔ واقعی حتماً بخوانید)

1. **Volume:** مدل با `volume` دیتاست آموزش دیده؛ MT5 زنده از `tick_volume`
   استفاده می‌کند. featureهای `vol_ratio`/`vol_z20` ممکن است کمی متفاوت شوند.
2. **Timezone و مرز VWAP/هفته:** VWAP و `early_atr` از مرز روز/هفتهٔ **UTC** محاسبه
   شده‌اند. اگر سرور بروکر timezone دیگری دارد، این لنگرها جابه‌جا می‌شوند.
   حتماً در Strategy Tester بروکر خودتان اعتبارسنجی کنید.
3. **feature-parity:** با `InpVerbose=true` مقادیر را با `parity_reference.txt`
   مقایسه کنید (به‌ویژه `early_atr`/`weekly_rev` که محاسبهٔ هفتگی دارند).
4. **معناداری آماری:** هر دو مغز p<۰.۰۵ دارند (بهبود نسبت به S14 با p=۰.۰۸).
   با این حال edge کوچک است؛ **مدیریت ریسک محافظه‌کارانه و شروع با دمو الزامی**.
5. **مرز پارتوی هدف چهارگانه:** طبق قانون L21 پروژه، هدف هم‌زمان
   (WR>۶۰ + PF>۱.۳ + exp>۰ + ≥۵ معامله/روز) روی دادهٔ صرف OHLCV برآورده نشد.
   ربات فعلی بهترین ترکیب اثبات‌شده را اجرا می‌کند؛ مسیر عبور از این مرز،
   دادهٔ برون‌زا (DXY/اخبار — گروه G) است که در دست تحقیق است.

## 🔄 بازتولید مدل‌ها
```bash
pip install lightgbm scipy pandas numpy scikit-learn \
            onnxmltools onnxconverter_common onnxruntime
python3 mt5_robot/train_export_s25.py    # مغز صعودی
python3 mt5_robot/train_export_bear.py   # مغز نزولی
```
