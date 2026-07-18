#!/usr/bin/env bash
# =============================================================================
# build_apk.sh — ساختِ خودکارِ APK اندروید از پوشهٔ apk/ (Capacitor)
# -----------------------------------------------------------------------------
# 🎯 قانونِ شمارهٔ ۱ پروژه: هدف فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.
#    تعریفِ سودِ خالص = جمعِ سودِ XAUUSD + EURUSD.
# -----------------------------------------------------------------------------
# این اسکریپت را روی سیستمِ خودتان (لینوکس/مک/WSL) اجرا کنید. سندباکسِ ابری
# نمی‌تواند APK بسازد چون به Android SDK + JDK نیاز دارد.
#
# پیش‌نیازها (یک‌بار نصب):
#   1) Node.js >= 18            → https://nodejs.org
#   2) JDK 17                   → sudo apt install openjdk-17-jdk   (یا Temurin)
#   3) Android SDK + Platform-Tools + Build-Tools 34
#      ساده‌ترین راه: Android Studio را نصب کنید (SDK را خودکار می‌آورد)
#      و متغیرهای محیطی را تنظیم کنید:
#         export ANDROID_HOME=$HOME/Android/Sdk
#         export PATH=$PATH:$ANDROID_HOME/platform-tools:$ANDROID_HOME/cmdline-tools/latest/bin
#
# طرزِ استفاده:
#   cd apk
#   bash build_apk.sh
#
# خروجی:
#   android/app/build/outputs/apk/debug/app-debug.apk
# =============================================================================
set -e

echo "════════════════════════════════════════════════════════"
echo "  ساختِ APK — دستیارِ معاملاتِ طلا (XAUUSD + EURUSD)"
echo "  قانونِ شمارهٔ ۱: فقط سودِ خالصِ بیشتر (XAUUSD+EURUSD)"
echo "════════════════════════════════════════════════════════"

# --- 0) بررسیِ پیش‌نیازها -------------------------------------------------
command -v node >/dev/null 2>&1 || { echo "❌ Node.js یافت نشد. نصب کنید: https://nodejs.org"; exit 1; }
command -v npx  >/dev/null 2>&1 || { echo "❌ npx یافت نشد (با Node.js نصب می‌شود)."; exit 1; }
if [ -z "$ANDROID_HOME" ] && [ -z "$ANDROID_SDK_ROOT" ]; then
  echo "⚠️  ANDROID_HOME تنظیم نشده. اگر build خطا داد، Android SDK را نصب و متغیر را تنظیم کنید."
fi
echo "✅ Node: $(node -v)"

# --- 1) نصبِ وابستگی‌های Capacitor ---------------------------------------
echo ""
echo "[1/5] نصبِ وابستگی‌های npm (Capacitor)…"
npm install

# --- 2) افزودنِ پلتفرمِ اندروید (اگر نبود) --------------------------------
echo ""
echo "[2/5] افزودنِ پلتفرمِ اندروید…"
if [ ! -d "android" ]; then
  npx cap add android
else
  echo "پوشهٔ android از قبل موجود است — رد شد."
fi

# --- 3) همگام‌سازیِ فایل‌های www (شاملِ pyengine) با اندروید ----------------
echo ""
echo "[3/5] همگام‌سازیِ www/ (WebView + Pyodide + موتورِ واقعی) با اندروید…"
npx cap sync android

# --- 4) اطمینان از دسترسیِ اینترنت در Manifest -----------------------------
echo ""
echo "[4/5] بررسیِ مجوزِ اینترنت در AndroidManifest…"
MANIFEST="android/app/src/main/AndroidManifest.xml"
if [ -f "$MANIFEST" ] && ! grep -q "android.permission.INTERNET" "$MANIFEST"; then
  echo "افزودنِ مجوزِ INTERNET…"
  sed -i.bak 's#<application#<uses-permission android:name="android.permission.INTERNET" />\n    <application#' "$MANIFEST"
fi

# --- 5) ساختِ APK (debug) --------------------------------------------------
echo ""
echo "[5/5] ساختِ APK (debug) با Gradle… (بارِ اول ممکن است چند دقیقه طول بکشد)"
cd android
chmod +x gradlew 2>/dev/null || true
./gradlew assembleDebug
cd ..

APK_PATH="android/app/build/outputs/apk/debug/app-debug.apk"
echo ""
echo "════════════════════════════════════════════════════════"
if [ -f "$APK_PATH" ]; then
  echo "🎉 APK با موفقیت ساخته شد:"
  echo "   $(pwd)/$APK_PATH"
  echo ""
  echo "برای نصب روی گوشیِ متصل (USB debugging روشن):"
  echo "   adb install -r \"$APK_PATH\""
else
  echo "❌ APK ساخته نشد. لاگِ Gradle بالا را بررسی کنید (معمولاً Android SDK/JDK ناقص است)."
  exit 1
fi
echo "════════════════════════════════════════════════════════"
