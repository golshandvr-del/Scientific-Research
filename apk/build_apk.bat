@echo off
REM =============================================================================
REM build_apk.bat - ساختِ خودکارِ APK اندروید روی ویندوز (Capacitor)
REM -----------------------------------------------------------------------------
REM قانونِ شمارهٔ ۱ پروژه: هدف فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.
REM    تعریفِ سودِ خالص = جمعِ سودِ XAUUSD + EURUSD.
REM -----------------------------------------------------------------------------
REM پیش‌نیازها: Node.js >= 18 , JDK 17 , Android SDK (Android Studio)
REM تنظیمِ متغیرها (نمونه):
REM    setx ANDROID_HOME "%USERPROFILE%\AppData\Local\Android\Sdk"
REM
REM طرزِ استفاده:  cd apk  &&  build_apk.bat
REM خروجی: android\app\build\outputs\apk\debug\app-debug.apk
REM =============================================================================
setlocal

echo ============================================================
echo   ساختِ APK - دستیارِ معاملاتِ طلا (XAUUSD + EURUSD)
echo   قانونِ شمارهٔ ۱: فقط سودِ خالصِ بیشتر
echo ============================================================

where node >nul 2>nul || (echo [X] Node.js يافت نشد. نصب کنید: https://nodejs.org & exit /b 1)

echo [1/5] نصبِ وابستگی‌های npm...
call npm install || exit /b 1

echo [2/5] افزودنِ پلتفرمِ اندروید...
if not exist android (
  call npx cap add android || exit /b 1
) else (
  echo پوشهٔ android موجود است - رد شد.
)

echo [3/5] همگام‌سازیِ www با اندروید...
call npx cap sync android || exit /b 1

echo [4/5] ساختِ APK با Gradle...
cd android
call gradlew.bat assembleDebug || (cd .. & exit /b 1)
cd ..

set APK=android\app\build\outputs\apk\debug\app-debug.apk
if exist %APK% (
  echo ============================================================
  echo APK ساخته شد: %CD%\%APK%
  echo نصب روی گوشی:  adb install -r "%APK%"
  echo ============================================================
) else (
  echo [X] APK ساخته نشد - لاگِ Gradle را بررسی کنید.
  exit /b 1
)
endlocal
