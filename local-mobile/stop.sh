#!/data/data/com.termux/files/usr/bin/bash
# =============================================================================
#  stop.sh — توقفِ سرور و آزادسازیِ wake-lock روی گوشی (Termux)
# =============================================================================
#  اگر سرور را در پس‌زمینه اجرا کرده‌اید (با nohup یا در یک session جدا) و
#  می‌خواهید آن را کاملاً ببندید، این را اجرا کنید:
#      bash stop.sh
# =============================================================================
PORT="${PORT:-8080}"

echo "▶ در حالِ بستنِ سرور روی پورتِ ${PORT} ..."

# بستنِ پروسهٔ سرور.
# نکته: در اندروید/Termux دستورِ `fuser` مجاز نیست («Bad system call»)، پس مستقیماً
# فرآیندِ node که server.mjs را اجرا می‌کند kill می‌کنیم.
# اول حلقهٔ ری‌استارتِ start-bg.sh (وگرنه ۵ ثانیه بعد سرور را دوباره بالا می‌آورد).
DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$DIR/data/supervisor.pid" ]; then
  kill "$(cat "$DIR/data/supervisor.pid")" >/dev/null 2>&1 || true
  rm -f "$DIR/data/supervisor.pid"
fi
pkill -f "node .*server\.mjs" >/dev/null 2>&1 || true

# آزادسازیِ wake-lock تا باتری بیهوده مصرف نشود
if command -v termux-wake-unlock >/dev/null 2>&1; then
  termux-wake-unlock || true
  echo "  🔓 wake-lock آزاد شد."
fi

echo "  ✅ سرور متوقف شد."
