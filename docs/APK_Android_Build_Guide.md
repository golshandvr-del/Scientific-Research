# 📱 راهنمای کاملِ ساختِ APK اندروید — دستیارِ معاملاتِ طلا

> ## 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ این ابزار فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.**
> تعریفِ رسمیِ سودِ خالص در این پروژه = **جمعِ سودِ دو ارز: XAUUSD + EURUSD.**
> Win-Rate، Profit Factor و تعدادِ معامله در روز صرفاً اعدادِ گزارشی‌اند، نه هدف.
> رکوردِ رسمیِ فعلیِ پروژه: **سودِ خالصِ کل +۹۵٬۶۴۵$** = XAUUSD (S67+S91+S81+SHORT: +۸۶٬۴۲۲$) + EURUSD (S73: +۹٬۲۲۳$).

---

## ۱) این APK چیست؟

یک اپلیکیشنِ اندرویدِ **دستیارِ تصمیمِ معاملاتی** که دقیقاً مطابقِ سایتِ پروژه کار
می‌کند، اما موتورِ تصمیم **روی خودِ دستگاه** اجرا می‌شود (نه روی سرور). فناوری:

- **Capacitor** — پوستهٔ نیتیوِ اندروید که یک WebView را در بر می‌گیرد.
- **Pyodide** — مفسرِ واقعیِ CPython (WASM) درونِ WebView، همراهِ **numpy + pandas**.
- **موتورِ واقعیِ پروژه** (`pyengine/`: `engine/` + `s118` + `s73` + shimِ numba) —
  **بدونِ بازنویسیِ یک خط** روی دستگاه اجرا می‌شود. همان کدی که رکوردِ +۹۵٬۶۴۵$ را ساخت.

### دارایی‌ها (طبقِ User Note — فقط دو ارز)
APK **فقط** دو کارت دارد، دقیقاً مطابقِ تعریفِ سودِ خالص و سایت:

| دارایی | نمادِ داده (Yahoo) | موتورِ تصمیم |
|--------|-------------------|--------------|
| **XAUUSD** (طلا) | `GC=F` | S67 + S91 + S81 + SHORT-MA-Confluence (s118) |
| **EURUSD** (یورو/دلار) | `EURUSD=X` | S73 — Session-Open Drift |

> `DXY` و `AUDUSD` **حذف شدند** چون هیچ لبهٔ سوددهی روی آن‌ها یافت نشد
> (استراتژی‌های S69–S72 زیان‌ده بودند) و تعریفِ رسمیِ سودِ خالص فقط XAUUSD + EURUSD است.

### دادهٔ لحظه‌ای (طبقِ User Note — بدونِ کمترین تأخیر)
- داخلِ APK، افزونهٔ **CapacitorHttp** فعال است؛ در نتیجه `fetch` از لایهٔ **native**
  عبور می‌کند و **محدودیتِ CORS دور زده می‌شود**. اپ **مستقیم** از Yahoo Finance
  (`query1`/`query2`) دادهٔ کندلِ M15 را می‌گیرد — بدونِ واسطهٔ پروکسی ⇒ **کمترین تأخیر**.
- به‌روزرسانیِ خودکار هر **۱۵ ثانیه** (قابلِ‌تنظیم در تبِ تنظیمات) + دکمهٔ به‌روزرسانیِ فوری.
- هر دو دارایی **هم‌زمان (موازی)** دریافت می‌شوند (تأخیرِ ترتیبیِ قبلی حذف شد).
- زمانِ آخرین به‌روزرسانی روی نوارِ بالا نمایش داده می‌شود.

> ⚠️ **توجه:** وقتی بازارهای مالی بسته‌اند (آخرِ هفته/تعطیلات) قیمتِ جدیدی وجود ندارد
> و اپ آخرین کندلِ موجود را نشان می‌دهد؛ به‌محضِ بازگشاییِ بازار، به‌روزرسانیِ لحظه‌ای
> از سر گرفته می‌شود.

### ماشینِ حالتِ ۴-وضعیتیِ هر کارت (مطابقِ سایت)
1. **خنثی** — با ذکرِ دقیقِ دلیل (رژیم/اندیکاتور نامشخص) می‌گوید وارد نمی‌شود.
2. **نزدیک‌شدن به سیگنال** — ستاپِ در حالِ شکل‌گیری + فهرستِ تأییدهای موردِ انتظار.
3. **ورود** — جهت (Long/Short) + TP + SL + دکمهٔ «معامله را ثبت کردم».
4. **مدیریتِ معامله** — فقط پس از ثبتِ کاربر؛ توصیه‌های زندهٔ جابه‌جاییِ SL/TP یا بستن.

---

## ۲) پیش‌نیازها (روی سیستمِ خودتان — یک‌بار)

> ❗ **ساختِ APK در سندباکسِ ابری ممکن نیست** چون به Android SDK + JDK نیاز دارد.
> این مراحل را روی کامپیوترِ خودتان (ویندوز/لینوکس/مک) انجام دهید.

1. **Node.js ≥ ۱۸** — https://nodejs.org
2. **JDK 17** — مثلاً Temurin یا `sudo apt install openjdk-17-jdk`
3. **Android SDK** — ساده‌ترین راه: نصبِ **Android Studio** (SDK را خودکار می‌آورد).
   سپس متغیرهای محیطی:
   ```bash
   # لینوکس/مک
   export ANDROID_HOME=$HOME/Android/Sdk
   export PATH=$PATH:$ANDROID_HOME/platform-tools:$ANDROID_HOME/cmdline-tools/latest/bin
   ```
   ```powershell
   # ویندوز (PowerShell، یک‌بار)
   setx ANDROID_HOME "$env:USERPROFILE\AppData\Local\Android\Sdk"
   ```

---

## ۳) ساختِ APK — روشِ خودکار (توصیه‌شده)

مخزن را clone یا دانلود کنید، سپس:

```bash
cd apk

# لینوکس / مک:
bash build_apk.sh

# ویندوز:
build_apk.bat
```

اسکریپت این مراحل را خودکار انجام می‌دهد:
1. `npm install` (نصبِ Capacitor)
2. `npx cap add android` (ساختِ پروژهٔ نیتیو — اگر نبود)
3. `npx cap sync android` (کپیِ `www/` شاملِ کاملِ `pyengine/` به اندروید)
4. بررسیِ مجوزِ `INTERNET` در Manifest
5. `./gradlew assembleDebug` (ساختِ APK)

**خروجی:**
```
apk/android/app/build/outputs/apk/debug/app-debug.apk
```

نصب روی گوشیِ متصل (USB debugging روشن):
```bash
adb install -r apk/android/app/build/outputs/apk/debug/app-debug.apk
```
یا فایلِ APK را به گوشی منتقل و دستی نصب کنید (نصب از منابعِ ناشناس را فعال کنید).

---

## ۴) ساختِ APK — روشِ دستی (گام‌به‌گام)

```bash
cd apk
npm install
npx cap add android          # فقط بارِ اول
npx cap sync android         # بعد از هر تغییر در www/
cd android
./gradlew assembleDebug      # ویندوز: gradlew.bat assembleDebug
```

برای بازکردن در Android Studio (build/امضا/انتشار گرافیکی):
```bash
npx cap open android
```

---

## ۵) ساختارِ فایل‌ها

```
apk/
├── capacitor.config.json     # پیکربندیِ Capacitor (CapacitorHttp فعال، appId)
├── package.json              # وابستگی‌های Capacitor + اسکریپت‌ها
├── build_apk.sh              # اسکریپتِ خودکارِ build (لینوکس/مک)
├── build_apk.bat             # اسکریپتِ خودکارِ build (ویندوز)
├── build_pyengine_bundle.py  # بازساختِ bundleِ موتورِ واقعی در www/pyengine/
├── .gitignore                # node_modules/ و android/ و *.apk نادیده گرفته می‌شوند
├── py/                       # منبعِ live_engine.py + numba-shim
└── www/                      # ریشهٔ WebView (webDir)
    ├── index.html            # رابطِ ۳-تبی (سیگنال‌ها / موتورِ پایتون / تنظیمات)
    ├── app.js                # منطق: Pyodide + دریافتِ داده + ماشینِ حالت ۴-وضعیتی
    └── pyengine/             # موتورِ واقعیِ پروژه (اجرا با Pyodide روی دستگاه)
        ├── manifest.json
        ├── live_engine.py    # live_decision(df, asset, open_position) + reproduce_record
        ├── numba.py          # shim (pass-through njit/jit) تا موتور بدونِ numba اجرا شود
        ├── engine/           # backtest, capital_engine, indicators, scalp_engine
        └── strategies/       # s118 (SHORT exit) + s73 (EURUSD)
```

> پوشهٔ `android/` توسطِ `cap add android` **خودکار** ساخته می‌شود و در `.gitignore`
> است (در مخزن نگهداری نمی‌شود). در سندباکس تأیید شد که پس از `cap add`،
> `android/app/src/main/assets/public/` شاملِ **کاملِ `pyengine/`** و مجوزِ
> `android.permission.INTERNET` به‌طورِ خودکار در Manifest قرار می‌گیرد.

---

## ۶) به‌روزرسانیِ موتور در APK

اگر موتورِ واقعیِ پروژه (`engine/` یا `strategies/`) به‌روز شد:
```bash
cd apk
python3 build_pyengine_bundle.py   # bundleِ www/pyengine/ را از موتورِ اصلی بازمی‌سازد
npx cap sync android               # کپی به اندروید
cd android && ./gradlew assembleDebug
```

همچنین کاربر می‌تواند از تبِ **«موتورِ پایتون»** داخلِ اپ، **فایلِ .py موتورِ خودش**
را وارد کند و اپ همان کد را واقعاً اجرا کند (تابعِ
`live_decision(df, asset, open_position=None)`).

---

## ۷) عیب‌یابی

| خطا | راه‌حل |
|-----|--------|
| `SDK location not found` | `ANDROID_HOME` را تنظیم کنید یا Android Studio را نصب کنید. |
| `Could not find/JAVA_HOME` | JDK 17 نصب و `JAVA_HOME` تنظیم شود. |
| Gradle خیلی کند/گیر می‌کند | بارِ اول وابستگی‌ها دانلود می‌شوند؛ صبور باشید یا VPN فعال کنید. |
| دادهٔ آنلاین نمی‌آید | بررسیِ اینترنت؛ در مرورگر CORS مانع است (در APK نیست). بازارِ بسته = دادهٔ جدید ندارد. |
| Pyodide لود نمی‌شود | نیاز به اینترنت برای بارِ اول (CDN). پس از آن کش می‌شود. |

---

## ۸) پیوندها
- رکوردِ برنده: [`results/ShortExitLetWinnersRun_NetProfit_95645.md`](../results/ShortExitLetWinnersRun_NetProfit_95645.md)
- تغییرِ پارادایم: [`PARADIGM.md`](../PARADIGM.md)
- README اصلی: [`README.md`](../README.md)

---

**آخرین به‌روزرسانی:** ۲۰۲۶-۰۷-۱۸ · **قانونِ شمارهٔ ۱:** فقط سودِ خالص (XAUUSD + EURUSD)، نه WR.
