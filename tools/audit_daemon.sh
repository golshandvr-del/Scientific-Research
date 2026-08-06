#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────────────────
# راه‌اندازِ مقاومِ موتورِ ممیزی
#
# ⚠️ چرا این فایل لازم شد (اندازه‌گیری‌شده، نه حدس):
#   راه‌اندازیِ پس‌زمینه با `cmd &` از داخلِ ابزارِ Bash قابل‌اعتماد نبود —
#   پروسه بی‌صدا می‌مُرد و **هیچ لاگی** ساخته نمی‌شد، پس ناپایداریِ صف با
#   ناپایداریِ سندباکس قابلِ تفکیک نبود. `setsid`+فایلِ pid این را قطعی می‌کند.
#
# استفاده:
#   bash tools/audit_daemon.sh start [N_LAYERS]
#   bash tools/audit_daemon.sh status
#   bash tools/audit_daemon.sh stop
# ────────────────────────────────────────────────────────────────────────────
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG="$ROOT/results/_audit_rename/batch.log"
PIDF="/tmp/audit_batch.pid"

cmd="${1:-status}"
n="${2:-200}"

case "$cmd" in
  start)
    if [[ -f "$PIDF" ]] && kill -0 "$(cat "$PIDF")" 2>/dev/null; then
      echo "already running pid=$(cat "$PIDF")"
      exit 0
    fi
    cd "$ROOT"
    setsid python tools/audit_batch.py "$n" >> "$LOG" 2>&1 < /dev/null &
    echo $! > "$PIDF"
    disown 2>/dev/null || true
    sleep 2
    echo "started pid=$(cat "$PIDF") log=$LOG"
    ;;
  stop)
    if [[ -f "$PIDF" ]]; then
      pkill -9 -P "$(cat "$PIDF")" 2>/dev/null || true
      kill -9 "$(cat "$PIDF")" 2>/dev/null || true
      rm -f "$PIDF"
    fi
    pkill -9 -f audit_batch.py 2>/dev/null || true
    pkill -9 -f audit_capture.py 2>/dev/null || true
    echo stopped
    ;;
  status)
    if [[ -f "$PIDF" ]] && kill -0 "$(cat "$PIDF")" 2>/dev/null; then
      echo "RUNNING pid=$(cat "$PIDF")"
    else
      echo "NOT RUNNING"
    fi
    tail -n "${3:-8}" "$LOG" 2>/dev/null || echo "(no log yet)"
    ;;
  *)
    echo "usage: $0 {start|stop|status} [n]"
    exit 2
    ;;
esac
