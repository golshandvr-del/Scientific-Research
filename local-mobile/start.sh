#!/data/data/com.termux/files/usr/bin/bash
# =============================================================================
#  راه‌اندازِ یک‌کلیکیِ «دستیارِ تصمیمِ معاملاتی» روی اندروید (Termux) یا لینوکس
# =============================================================================
#  این اسکریپت:
#    ۱) بررسی می‌کند python نصب است؛ اگر نه، در Termux نصبش می‌کند.
#    ۲) سرورِ سبک (server.py) را روی پورتِ ۸۰۸۰ اجرا می‌کند.
#    ۳) در Termux، مرورگرِ پیش‌فرضِ گوشی را روی آدرسِ لوکال باز می‌کند.
#
#  مصرفِ رم: ~۲۰–۴۰MB (به‌جای ۲GB زنجیرهٔ Node/Vite/Wrangler).
#
#  استفاده:
#      bash start.sh
#  یا با پورتِ دلخواه:
#      PORT=9000 bash start.sh
# =============================================================================

set -e
cd "$(dirname "$0")"

PORT="${PORT:-8080}"
export PORT

echo "==============================================================="
echo "  دستیارِ تصمیمِ معاملاتی — اجرای لوکال روی اندروید"
echo "==============================================================="

# --- ۱) اطمینان از وجودِ python ---
if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  echo "[*] python یافت نشد."
  if command -v pkg >/dev/null 2>&1; then
    echo "[*] در حالِ نصبِ python در Termux ..."
    pkg install -y python
  else
    echo "[!] لطفاً python را نصب کنید (در Termux: pkg install python)."
    exit 1
  fi
fi

PY=python3
command -v python3 >/dev/null 2>&1 || PY=python

# --- ۲) اجرای سرور در پس‌زمینه ---
echo "[*] در حالِ راه‌اندازیِ سرور روی پورتِ $PORT ..."
"$PY" server.py &
SRV_PID=$!

# کمی صبر تا سرور بالا بیاید
sleep 2

URL="http://localhost:$PORT"
echo ""
echo "[✓] سرور آماده است:  $URL"
echo ""

# --- ۳) بازکردنِ مرورگر (فقط در Termux با termux-open-url) ---
if command -v termux-open-url >/dev/null 2>&1; then
  echo "[*] در حالِ بازکردنِ مرورگرِ گوشی ..."
  termux-open-url "$URL" || true
else
  echo "[i] مرورگرِ گوشی را باز کنید و به این آدرس بروید:"
  echo "    $URL"
fi

echo ""
echo "  برای توقف: Ctrl+C را بزنید (یا این ترمینال را ببندید)."
echo "==============================================================="

# منتظرِ سرور می‌مانیم تا اسکریپت با آن زنده بماند
wait $SRV_PID
