#!/data/data/com.termux/files/usr/bin/bash
# =============================================================================
#  start-bg.sh — اجرای سرور + نگهبانِ سیگنال در «پس‌زمینهٔ دائم» روی Termux
# =============================================================================
#  تفاوت با start.sh: این‌جا سرور با nohup و حلقهٔ «ری‌استارتِ خودکار» اجرا می‌شود،
#  پس با بستنِ پنجرهٔ Termux یا کرشِ احتمالی، دوباره بالا می‌آید. نگهبان (watcher.mjs)
#  داخلِ همان سرور است: هر کارت را پس از بسته‌شدنِ کندلش بررسی و هر سیگنالِ تازه
#  را با اعلانِ صدادارِ اندروید (termux-notification) اعلام می‌کند.
#
#  پیش‌نیاز برای اعلان (یک‌بار):  pkg install termux-api   + نصبِ اپِ «Termux:API»
#  اجرا:      bash start-bg.sh
#  وضعیت:     bash start-bg.sh status        لاگ:  tail -n 50 data/server.log
#  توقف:      bash stop.sh
#  روشن‌شدن پس از ریبوت: bash start-bg.sh install-boot   (نیازمندِ اپِ Termux:Boot)
# =============================================================================
DIR="$(cd "$(dirname "$0")" && pwd)"
PORT="${PORT:-8080}"
HOST="${HOST:-0.0.0.0}"
mkdir -p "$DIR/data"
LOG="$DIR/data/server.log"
PIDF="$DIR/data/supervisor.pid"

case "$1" in
  status)
    if [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; then
      echo "✅ در حالِ اجرا (supervisor pid $(cat "$PIDF")) — http://localhost:${PORT}/"
    else echo "⛔ اجرا نمی‌شود."; fi
    exit 0 ;;
  install-boot)
    mkdir -p "$HOME/.termux/boot"
    cat > "$HOME/.termux/boot/xau-signals.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock
bash "$DIR/start-bg.sh"
EOF
    chmod +x "$HOME/.termux/boot/xau-signals.sh"
    echo "✅ پس از هر ریبوت، با اپِ Termux:Boot خودکار اجرا می‌شود (یک‌بار اپ را باز کنید)."
    exit 0 ;;
esac

command -v node >/dev/null 2>&1 || { pkg update -y >/dev/null 2>&1; pkg install -y nodejs >/dev/null 2>&1; }
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock || true
command -v termux-notification >/dev/null 2>&1 || echo "⚠️  termux-api نصب نیست ⇒ سیگنال‌ها ثبت می‌شوند ولی اعلانِ صدادار نمی‌آید: pkg install termux-api"

# بستنِ نمونهٔ قبلی
[ -f "$PIDF" ] && kill "$(cat "$PIDF")" 2>/dev/null
pkill -f "node .*server\.mjs" >/dev/null 2>&1 || true
sleep 1

cd "$DIR"
nohup bash -c "
  while true; do
    echo \"--- \$(date) start ---\" >> '$LOG'
    PORT='$PORT' HOST='$HOST' node server.mjs >> '$LOG' 2>&1
    echo \"--- \$(date) exited (\$?) — restart in 5s ---\" >> '$LOG'
    # جلوگیری از رشدِ بی‌حدِ لاگ روی گوشی
    [ \$(wc -c < '$LOG') -gt 2000000 ] && tail -c 500000 '$LOG' > '$LOG.tmp' && mv '$LOG.tmp' '$LOG'
    sleep 5
  done
" >/dev/null 2>&1 &
echo $! > "$PIDF"
echo "✅ سرور + نگهبان در پس‌زمینه اجرا شد — http://localhost:${PORT}/"
echo "   لاگ: tail -n 50 $LOG     توقف: bash $DIR/stop.sh"
